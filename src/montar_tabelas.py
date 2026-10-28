"""
montar_tabelas.py  -  DOS CSVs BRUTOS ATE A FATO E AS 4 DIMENSOES
========================================================================================================
Aqui entram as funcoes do src/limpeza.py e as regras de negocio do enunciado (secao 4.2), uma etapa de cada vez.
Do lado de cada etapa tem o numero da regra, pra ficar facil de achar.

COMO RODAR:   python -m src.montar_tabelas
Ele grava os arquivos em data/processed/ e no final mostra uns numeros pra conferir com o anexo 8 do enunciado.
Se algum nao bater, o problema esta na etapa logo acima dele.
"""

import pandas as pd

from src import config, limpeza

# Tabelas de apoio (estao no anexo do enunciado, secao 7)
MODALIDADES = {4: "Concorrência - Eletrônica", 5: "Concorrência - Presencial", 6: "Pregão - Eletrônico",
               7: "Pregão - Presencial", 8: "Dispensa", 9: "Inexigibilidade", 12: "Credenciamento"}
REGIAO = {"AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
          "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste", "PE": "Nordeste",
          "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste", "DF": "Centro-Oeste", "GO": "Centro-Oeste",
          "MS": "Centro-Oeste", "MT": "Centro-Oeste", "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
          "PR": "Sul", "RS": "Sul", "SC": "Sul"}
PODER = {"E": "Executivo", "L": "Legislativo", "J": "Judiciário", "N": "Não informado"}


def ler(nome):
    """Le o CSV tudo como texto (dtype=str): assim o CNPJ nao perde o zero da esquerda e nada vira vazio sozinho."""
    return pd.read_csv(config.PASTA_RAW / f"{nome}.csv", dtype=str, keep_default_na=False)


def main():
    compras, itens, resultados = ler("compras"), ler("itens"), ler("resultados")
    print(f"Linhas lidas: compras={len(compras)}  itens={len(itens)}  resultados={len(resultados)}   (prova real: 2042 / 7077 / 15896)")

    # =========================================================================================
    # ETAPA 1 - LIMPAR OS 3 ARQUIVOS  (com as funcoes do src/limpeza.py)
    # =========================================================================================
    # --- compras.csv ---
    # .map(funcao) roda a funcao em cada linha da coluna.   Regra 10: orgao e sempre pessoa juridica, entao "PJ" (14 digitos)
    compras["cnpj_orgao"] = compras["cnpj_orgao"].map(lambda v: limpeza.limpar_documento(v, "PJ"))
    # nome padronizado: e por ele que agrupo os orgaos no ranking do ciclo (pergunta 4)
    compras["nome_orgao"] = compras["razao_social_orgao"].map(limpeza.padronizar_nome)
    compras["uf_sigla"] = compras["uf_sigla"].map(limpeza.padronizar_nome)
    compras["uf_nome"] = compras["uf_nome"].map(limpeza.padronizar_nome)
    # Regra 11: o arquivo nao traz a regiao, entao eu pego no dicionario REGIAO pela sigla da UF
    compras["regiao"] = compras["uf_sigla"].map(REGIAO)          # "DF" -> "Centro-Oeste"
    compras["poder"] = compras["poder_id"].map(PODER).fillna("Não informado")
    compras["modalidade_id"] = compras["modalidade_id"].astype(int)
    # Regra 9: o nome vem do codigo, porque o texto do arquivo vem escrito de varios jeitos
    compras["nome_modalidade"] = compras["modalidade_id"].map(MODALIDADES)
    compras["data_publicacao"] = compras["data_publicacao"].map(limpeza.converter_data)
    compras["objeto_compra"] = compras["objeto_compra"].map(limpeza.limpar_texto)

    # --- itens.csv ---
    itens["descricao_item"] = itens["descricao"].map(limpeza.padronizar_nome)
    itens["material_ou_servico"] = itens["material_ou_servico"].map(limpeza.limpar_texto)
    # Regra 12: numero em texto ("R$ 1.693,46") vira numero de verdade
    for coluna in ["quantidade", "valor_unitario_estimado"]:
        itens[coluna] = itens[coluna].map(limpeza.converter_numero)
    # "sigiloso" vem como texto "True"/"False" -> vira booleano
    itens["sigiloso"] = itens["sigiloso"].str.lower() == "true"
    itens["numero_item"] = itens["numero_item"].astype(int)

    # --- resultados.csv ---
    resultados["numero_item"] = resultados["numero_item"].astype(int)
    resultados["nome_fornecedor"] = resultados["nome_fornecedor"].map(limpeza.padronizar_nome)
    resultados["porte"] = resultados["porte"].map(limpeza.limpar_texto)
    # fornecedor pode ser empresa (PJ, 14 digitos), pessoa (PF, 11) ou estrangeiro (PE), entao vejo linha por linha
    resultados["ni_fornecedor"] = [limpeza.limpar_documento(ni, tipo)
                                   for ni, tipo in zip(resultados["ni_fornecedor"], resultados["tipo_pessoa"])]
    for coluna in ["quantidade_homologada", "valor_unitario_homologado"]:
        resultados[coluna] = resultados[coluna].map(limpeza.converter_numero)
    resultados["data_resultado"] = resultados["data_resultado"].map(limpeza.converter_data)
    # cancelado = tem alguma coisa escrita em data_cancelamento
    resultados["cancelado"] = resultados["data_cancelamento"].str.strip() != ""

    # =========================================================================================
    # ETAPA 2 - UM VENCEDOR POR ITEM  (regra 2)
    # =========================================================================================
    # PRIMEIRO tiro os cancelados (o ~ inverte). So depois escolho o 1o colocado:
    # assim, se o 1o foi cancelado, o 2o assume. Se fizesse ao contrario, perderia uns 60 itens.
    resultados = resultados[~resultados["cancelado"]].copy()
    # ordem 1 = vencedor; ordem vazia conta como 1
    resultados["ordem"] = pd.to_numeric(resultados["ordem_classificacao_srp"], errors="coerce").fillna(1)
    resultados["sequencial"] = pd.to_numeric(resultados["sequencial_resultado"], errors="coerce").fillna(1)
    # Ordena para o vencedor ficar em primeiro: por item, depois pela ordem, depois pelo sequencial (desempate)
    resultados = resultados.sort_values(["numero_controle_pncp", "numero_item", "ordem", "sequencial"])
    # depois de ordenado, a primeira linha de cada item e o vencedor; o resto sai
    resultados = resultados.drop_duplicates(["numero_controle_pncp", "numero_item"])

    # =========================================================================================
    # ETAPA 3 - JUNTAR OS 3 ARQUIVOS: SO ENTRAM ITENS COM RESULTADO  (regra 3)
    # =========================================================================================
    # merge junta tabelas pelas colunas em comum. how="inner" fica so com o que existe nos DOIS lados.
    # inner: item sem resultado (ou so com resultado cancelado) fica de fora -> sao os 852 da prova real
    fato = itens.merge(resultados, on=["numero_controle_pncp", "numero_item"], how="inner")
    fato = fato.merge(compras, on="numero_controle_pncp")
    print(f"Itens com resultado, antes de rejeitar: {len(fato)}")

    # =========================================================================================
    # ETAPA 4 - VALORES  (regra 5)
    # =========================================================================================
    # Uso a quantidade HOMOLOGADA nos dois totais (estimado e homologado), senao a comparacao fica injusta.
    qtd_homologada = fato["quantidade_homologada"]
    # .where: fica com a homologada quando ela e > 0; se vier vazia ou zero, usa a quantidade do item
    fato["quantidade"] = qtd_homologada.where(qtd_homologada > 0, fato["quantidade"])
    # mesma quantidade nos dois totais -> estimado e homologado ficam comparaveis
    fato["valor_total_estimado"] = (fato["valor_unitario_estimado"] * fato["quantidade"]).round(2)
    fato["valor_total_homologado"] = (fato["valor_unitario_homologado"] * fato["quantidade"]).round(2)

    # =========================================================================================
    # ETAPA 5 - ITENS REJEITADOS  (regra 4)   (nao precisa criar arquivo: so nao entram na fato)
    # =========================================================================================
    est, hom = fato["valor_total_estimado"], fato["valor_total_homologado"]
    # ~(coluna > 0) pega quem e <= 0 e tambem quem esta vazio, de uma vez so. O | quer dizer "ou"
    rejeitado = (
        ~(fato["quantidade"] > 0)                          # quantidade vazia ou <= 0
        | ~(fato["valor_unitario_estimado"] > 0)           # valor unitario estimado ausente ou <= 0
        | ~(fato["valor_unitario_homologado"] > 0)         # valor unitario homologado ausente ou <= 0
        | fato["sigiloso"]                                 # orcamento sigiloso
        | (est < 1)                                        # estimado total menor que R$ 1
        | (hom > 1000 * est)                               # homologado mais de 1000x o estimado
        | (est > 1e12) | (hom > 1e12)                      # acima de R$ 1 trilhao (nem cabe no banco)
    )
    print(f"Itens rejeitados (nao entram na fato): {rejeitado.sum()}   (prova real: 99)")
    # So pra documentar no README: o PRIMEIRO motivo de cada rejeitado (se cair em varios, vale o primeiro)
    motivos = [("quantidade vazia ou <= 0", ~(fato["quantidade"] > 0)),
               ("unitario estimado ausente ou <= 0", ~(fato["valor_unitario_estimado"] > 0)),
               ("unitario homologado ausente ou <= 0", ~(fato["valor_unitario_homologado"] > 0)),
               ("orcamento sigiloso", fato["sigiloso"]),
               ("estimado total < R$ 1", est < 1),
               ("homologado > 1000x o estimado", hom > 1000 * est),
               ("valor acima de R$ 1 trilhao", (est > 1e12) | (hom > 1e12))]
    ja_contado = pd.Series(False, index=fato.index)
    for motivo, cond in motivos:
        novos = cond & ~ja_contado
        if novos.sum():
            print(f"   - {motivo}: {novos.sum()}")
        ja_contado |= cond
    fato = fato[~rejeitado].copy()

    # =========================================================================================
    # ETAPA 6 - COMPARAVEL E ECONOMIA  (regra 6)
    # =========================================================================================
    est, hom = fato["valor_total_estimado"], fato["valor_total_homologado"]
    razao = hom / est
    # Comparavel = NAO e Credenciamento (modalidade 12) E a razao homologado/estimado esta entre 0,1 e 10.
    # Credenciamento sai porque o estimado ali e um teto global, nao o preco do item
    fato["comparavel"] = ((fato["modalidade_id"] != 12) & razao.between(0.1, 10)).astype(int)
    # Economia = estimado - homologado so nos comparaveis; nos outros fica VAZIO (NULL no banco),
    # pra ninguem confundir "sem economia" com "nao da pra comparar"
    fato["economia_valor"] = (est - hom).where(fato["comparavel"] == 1).round(2)

    # =========================================================================================
    # ETAPA 7 - CRONOLOGIA  (regra 7)
    # =========================================================================================
    fato["data_homologacao"] = fato["data_resultado"]
    # Homologar ANTES de publicar e impossivel: a data de homologacao vira vazia (o item continua na fato)
    antes = [h is not None and p is not None and h < p
             for h, p in zip(fato["data_homologacao"], fato["data_publicacao"])]
    fato.loc[antes, "data_homologacao"] = None
    # ciclo em dias (data - data da um intervalo; o .days pega o numero de dias). Mesmo dia = 0, vale.
    fato["dias_ciclo"] = [(h - p).days if h is not None and not pd.isna(h) else None
                          for h, p in zip(fato["data_homologacao"], fato["data_publicacao"])]

    # =========================================================================================
    # ETAPA 8 - PERFIL DO GASTO  (regra 8)
    # =========================================================================================
    # Se o texto cita obra/construcao/reforma/engenharia, e "Obras e engenharia" (essa regra manda sobre as outras)
    texto = fato["descricao_item"].fillna("") + " " + fato["objeto_compra"].fillna("").str.upper()
    eh_obra = texto.str.contains(r"\b(?:OBRAS?|CONSTRUÇÃO|CONSTRUCAO|REFORMA|ENGENHARIA)\b", regex=True)
    fato["perfil_gasto"] = "Bens"
    fato.loc[fato["material_ou_servico"].fillna("").str.upper().str.startswith("SERVI"), "perfil_gasto"] = "Serviços"
    # obra ganha de tudo, por isso vem por ultimo (sobrescreve Bens e Servicos)
    fato.loc[eh_obra, "perfil_gasto"] = "Obras e engenharia"

    # =========================================================================================
    # ETAPA 9 - AS 4 DIMENSOES, COM CHAVE SUBSTITUTA (sk_)  (secao 4.3 do enunciado)
    # =========================================================================================
    # Cada dimensao tem UMA linha por orgao/fornecedor/modalidade/UF, e a coluna sk_ so numera essas linhas (1, 2, 3...).
    # As quatro seguem a mesma receita: tira os repetidos, escolhe as colunas e numera.
    dim_orgao = fato.drop_duplicates("cnpj_orgao")[["cnpj_orgao", "nome_orgao", "poder"]].reset_index(drop=True)
    dim_orgao.insert(0, "sk_orgao", dim_orgao.index + 1)

    fato["ni_fornecedor"] = fato["ni_fornecedor"].fillna("NAO-INFORMADO")
    dim_fornecedor = fato.drop_duplicates("ni_fornecedor")[["ni_fornecedor", "nome_fornecedor", "tipo_pessoa", "porte"]].reset_index(drop=True)
    dim_fornecedor.insert(0, "sk_fornecedor", dim_fornecedor.index + 1)
    dim_modalidade = fato.drop_duplicates("modalidade_id")[["modalidade_id", "nome_modalidade"]].reset_index(drop=True)
    dim_modalidade.insert(0, "sk_modalidade", dim_modalidade.index + 1)
    dim_localidade = fato.drop_duplicates("uf_sigla")[["uf_sigla", "uf_nome", "regiao"]].reset_index(drop=True)
    dim_localidade.insert(0, "sk_localidade", dim_localidade.index + 1)

    # Na fato, troco o CNPJ, a sigla etc. pelo numerozinho sk_ da dimensao.
    # dict(zip(a, b)) monta um "de-para" {CNPJ: sk} e o .map faz a troca.
    for dim, chave, sk in [(dim_orgao, "cnpj_orgao", "sk_orgao"), (dim_fornecedor, "ni_fornecedor", "sk_fornecedor"),
                           (dim_modalidade, "modalidade_id", "sk_modalidade"), (dim_localidade, "uf_sigla", "sk_localidade")]:
        fato[sk] = fato[chave].map(dict(zip(dim[chave], dim[sk])))

    colunas = ["numero_controle_pncp", "numero_item", "sk_orgao", "sk_fornecedor", "sk_modalidade", "sk_localidade",
               "data_publicacao", "data_homologacao", "descricao_item", "perfil_gasto", "quantidade",
               "valor_unitario_estimado", "valor_total_estimado", "valor_unitario_homologado", "valor_total_homologado",
               "comparavel", "economia_valor", "dias_ciclo"]
    fato = fato[colunas]

    # =========================================================================================
    # ETAPA 10 - SALVAR E CONFERIR
    # =========================================================================================
    config.PASTA_PROCESSED.mkdir(parents=True, exist_ok=True)
    for nome, tabela in [("fato_item_contratado", fato), ("dim_orgao", dim_orgao), ("dim_fornecedor", dim_fornecedor),
                         ("dim_modalidade", dim_modalidade), ("dim_localidade", dim_localidade)]:
        tabela.to_csv(config.PASTA_PROCESSED / f"{nome}.csv", index=False, encoding="utf-8")

    comp = fato["comparavel"] == 1
    est_comp = fato.loc[comp, "valor_total_estimado"].sum()
    print("\n=== CONFERENCIA com o anexo 8 do enunciado (prova real) ===")
    print(f"itens na fato ............ {len(fato)}      (6126)")
    print(f"contratacoes distintas ... {fato['numero_controle_pncp'].nunique()}      (1962)")
    print(f"fornecedores ............. {len(dim_fornecedor)}      (2652)")
    print(f"orgaos (CNPJ) ............ {len(dim_orgao)}       (363)")
    print(f"volume homologado ........ R$ {fato['valor_total_homologado'].sum():,.2f}      (8.044.498.805,74 no formato brasileiro)")
    print(f"itens comparaveis ........ {comp.sum()}      (5457)")
    print(f"economia ................. {100 * fato['economia_valor'].sum() / est_comp:.2f}%      (14,46%)")
    print(f"ciclo medio / maximo ..... {fato['dias_ciclo'].mean():.1f} / {fato['dias_ciclo'].max():.0f} dias      (48,1 / 611)")
    print(f"itens sem ciclo .......... {fato['dias_ciclo'].isna().sum()}      (230)")
    print("perfil (% do volume) ..... ", (100 * fato.groupby("perfil_gasto")["valor_total_homologado"].sum()
                                         / fato["valor_total_homologado"].sum()).round(1).to_dict(), "    (referência: Obras 60,8 | Serviços 36,6 | Bens 2,6)")


if __name__ == "__main__":
    main()
