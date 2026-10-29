"""
carregar.py  -  CARGA NO POSTGRESQL
===================================
Passos:  1) recria o banco e as tabelas (banco.recriar_banco + sql/01_criar_banco.sql)
         2) confere tudo ANTES de mandar pro banco (chave repetida, item apontando pra quem nao existe)
         3) carrega as 4 DIMENSOES   4) carrega a FATO (dimensao primeiro, senao a FK reclama)
         5) confere as contagens com a prova real
Tudo numa transacao so: ou entra tudo, ou nao entra nada (rollback). Nada de banco pela metade.

COMO RODAR (depois do montar_tabelas):   python -m src.carregar
"""

import sys

import pandas as pd
from psycopg2 import Error

from src import banco, config

DIMENSOES = [("dim_orgao", "sk_orgao", "cnpj_orgao", ["sk_orgao", "cnpj_orgao", "nome_orgao", "poder"]),
             ("dim_fornecedor", "sk_fornecedor", "ni_fornecedor",
              ["sk_fornecedor", "ni_fornecedor", "nome_fornecedor", "tipo_pessoa", "porte"]),
             ("dim_modalidade", "sk_modalidade", "modalidade_id", ["sk_modalidade", "modalidade_id", "nome_modalidade"]),
             ("dim_localidade", "sk_localidade", "uf_sigla", ["sk_localidade", "uf_sigla", "uf_nome", "regiao"])]

COLUNAS_FATO = ["numero_controle_pncp", "numero_item", "sk_orgao", "sk_fornecedor", "sk_modalidade", "sk_localidade",
                "data_publicacao", "data_homologacao", "descricao_item", "perfil_gasto", "quantidade",
                "valor_unitario_estimado", "valor_total_estimado", "valor_unitario_homologado", "valor_total_homologado",
                "comparavel", "economia_valor", "dias_ciclo"]


def ler(nome, **opcoes):
    """Le um CSV de data/processed. Campo vazio continua vazio (e chega vazio no banco tambem)."""
    return pd.read_csv(config.PASTA_PROCESSED / f"{nome}.csv", keep_default_na=False, na_values=[""], **opcoes)


def tuplas(tabela, colunas):
    """Transforma a tabela numa lista de linhas, que e o formato que o banco aceita. Vazio vira vazio no banco."""
    dados = tabela[colunas].astype(object)
    dados = dados.where(dados.notna(), None)
    return [tuple(linha) for linha in dados.itertuples(index=False, name=None)]


def inserir(con, tabela, colunas, dados):
    """Monta o comando de inserir e manda tudo de uma vez so, bem mais rapido que uma linha por vez."""
    marcadores = ", ".join(["%s"] * len(colunas))        # um %s pra cada coluna
    sql = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({marcadores})"
    banco.inserir_em_lote(con, sql, tuplas(dados, colunas), commit=False)   # o commit e la no fim
    print(f"   {tabela}: {len(dados)} linhas")


def validar(dims, fato):
    """Confere antes de gravar. Chave repetida e problema serio: para tudo.
    Item apontando pra quem nao existe nao para: ele vai pra linha -1 'Nao informado' e eu aviso quantos foram."""
    for nome, sk, chave, _ in DIMENSOES:
        d = dims[nome]
        if d[sk].duplicated().any() or d[chave].duplicated().any():
            raise ValueError(f"{nome}: tem chave repetida, a dimensao nao pode ter duas linhas pro mesmo {chave}")
        sem_destino = ~fato[sk].isin(d[sk])
        if sem_destino.any():
            print(f"   aviso: {sem_destino.sum()} itens sem {sk} valido -> vao pra linha -1 (Não informado)")
            fato.loc[sem_destino, sk] = -1
    if fato.duplicated(["numero_controle_pncp", "numero_item"]).any():
        raise ValueError("fato: item repetido (o grao e 1 linha por numero_controle_pncp + numero_item)")
    print("   integridade ok: sem chave repetida e sem FK solta")
    return fato


def main():
    # 0) Le tudo primeiro. dtype=str nas dimensoes pro CNPJ nao perder o zero da esquerda
    dims = {nome: ler(nome, dtype=str) for nome, *_ in DIMENSOES}
    for nome, sk, *_ in DIMENSOES:
        dims[nome][sk] = dims[nome][sk].astype(int)
    fato = ler("fato_item_contratado")
    # dias_ciclo chega como 48.0 porque tem vazio no meio; o "Int64" deixa ser numero inteiro e vazio ao mesmo tempo
    fato["dias_ciclo"] = fato["dias_ciclo"].astype("Int64")

    print("Validacao:")
    fato = validar(dims, fato)

    # 1) Banco do zero + tabelas (o script que cria as tabelas roda sozinho, sem precisar abrir o pgAdmin)
    banco.recriar_banco()
    con = banco.conectar()
    try:
        banco.executar_script(con, config.PASTA_SQL / "01_criar_banco.sql")

        # 2) Dimensoes PRIMEIRO (a fato aponta pra elas), 3) depois a fato
        print("Carga:")
        for nome, _, _, colunas in DIMENSOES:
            inserir(con, nome, colunas, dims[nome])
        inserir(con, "fato_item_contratado", COLUNAS_FATO, fato)
        con.commit()                                      # chegou aqui sem erro: confirma tudo de uma vez
    except (Error, ValueError) as erro:
        con.rollback()                                    # deu ruim: desfaz tudo, banco nao fica pela metade
        con.close()
        print(f"\nERRO na carga, nada foi gravado (rollback). Detalhe:\n{erro}")
        sys.exit(1)

    # 4) Conferencia com a prova real (a linha -1 nao conta, por isso o sk > 0)
    print("Conferencia:")
    for tabela, sk, esperado in [("fato_item_contratado", "sk_fato", 6126), ("dim_orgao", "sk_orgao", 363),
                                 ("dim_fornecedor", "sk_fornecedor", 2652), ("dim_modalidade", "sk_modalidade", 7),
                                 ("dim_localidade", "sk_localidade", 27)]:
        n = banco.consultar(con, f"SELECT COUNT(*) FROM {tabela} WHERE {sk} > 0")[0][0]
        print(f"   {tabela}: {n} (esperado {esperado}) -> {'OK' if n == esperado else 'DIVERGENTE'}")
    total = banco.consultar(con, "SELECT SUM(valor_total_homologado) FROM fato_item_contratado")[0][0]
    print(f"   volume homologado no banco: R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
          + "   (prova real: R$ 8.044.498.805,74)")
    con.close()


if __name__ == "__main__":
    main()
