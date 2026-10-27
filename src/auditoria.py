"""
auditoria.py  -  RAIO-X DOS DADOS BRUTOS (antes de limpar qualquer coisa)
=========================================================================
Antes de sair limpando, eu queria saber O QUE esta sujo e QUANTO. Esse script so olha e conta,
nao altera nada. Os numeros que ele mostra estao anotados no README (dicionario das inconsistencias).

COMO RODAR:   python -m src.auditoria
Grava tambem um resumo em reports/auditoria.txt
"""

import re
import sys

import pandas as pd

from src import config, limpeza

linhas_relatorio = []


def mostrar(texto=""):
    print(texto)
    linhas_relatorio.append(texto)


def ler(nome):
    return pd.read_csv(config.PASTA_RAW / f"{nome}.csv", dtype=str, keep_default_na=False)


def contar(serie, condicao):
    """Quantas linhas da coluna batem com a condicao (uma funcao que recebe o texto e devolve True/False)."""
    return int(serie.map(condicao).sum())


# --- "detetores" de sujeira -------------------------------------------------------------------
def tem_mascara(v):            # 11.222.333/0001-81
    return bool(re.search(r"[./-]", v))


def perdeu_zero(v, tamanho):   # so digitos, mas com menos digitos que deveria
    d = "".join(c for c in v if c.isdigit())
    return v.strip().isdigit() and 0 < len(d) < tamanho


def eh_nulo_disfarcado(v):     # N/A, -, SEM INFORMACAO... (o vazio de verdade eu conto separado)
    return v.strip() != "" and limpeza.eh_nulo(v.strip())


def acento_quebrado(v):        # AquisiÃ§Ã£o
    return "Ã" in v or "Â" in v


def dinheiro_em_texto(v):      # R$, parenteses, virgula decimal...
    return bool(re.search(r"R\$|\(|,", v))


def formato_data(v):
    v = v.strip()
    if v == "":
        return "vazio"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return "AAAA-MM-DD"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", v):
        return "AAAA-MM-DDThh:mm:ss"
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", v):
        return "DD/MM/AAAA"
    if re.fullmatch(r"\d{2}/\d{2}/\d{4} .*", v):
        return "DD/MM/AAAA hh:mm"
    if re.fullmatch(r"\d{2}-\d{2}-\d{4}", v):
        return "DD-MM-AAAA"
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", v):
        return "DD.MM.AAAA"
    if re.fullmatch(r"\d{4}/\d{2}/\d{2}", v):
        return "AAAA/MM/DD"
    if re.fullmatch(r"\d{8}", v):
        return "AAAAMMDD"
    return "outro: " + v[:20]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    compras, itens, resultados = ler("compras"), ler("itens"), ler("resultados")

    mostrar("=== TAMANHO DOS ARQUIVOS ===")
    mostrar(f"compras.csv ....... {len(compras)} linhas")
    mostrar(f"itens.csv ......... {len(itens)} linhas")
    mostrar(f"resultados.csv .... {len(resultados)} linhas")
    mostrar(f"numero_controle_pncp repetido em compras: {compras['numero_controle_pncp'].duplicated().sum()}")
    mostrar(f"item repetido em itens (pncp + numero_item): {itens.duplicated(['numero_controle_pncp', 'numero_item']).sum()}")

    mostrar("\n=== 1) DOCUMENTOS (CNPJ/CPF) ===")
    mostrar(f"cnpj_orgao com mascara (. / -) ....... {contar(compras['cnpj_orgao'], tem_mascara)}")
    mostrar(f"cnpj_orgao que perdeu zero ........... {contar(compras['cnpj_orgao'], lambda v: perdeu_zero(v, 14))}")
    pj = resultados[resultados["tipo_pessoa"] == "PJ"]["ni_fornecedor"]
    pf = resultados[resultados["tipo_pessoa"] == "PF"]["ni_fornecedor"]
    mostrar(f"ni_fornecedor com mascara ............ {contar(resultados['ni_fornecedor'], tem_mascara)}")
    mostrar(f"ni_fornecedor PJ que perdeu zero ..... {contar(pj, lambda v: perdeu_zero(v, 14))}")
    mostrar(f"ni_fornecedor PF que perdeu zero ..... {contar(pf, lambda v: perdeu_zero(v, 11))}")
    mostrar(f"ni_fornecedor vazio/nulo disfarcado .. {contar(resultados['ni_fornecedor'], lambda v: limpeza.limpar_texto(v) is None)}")
    mostrar(f"tipos de pessoa: {resultados['tipo_pessoa'].value_counts().to_dict()}")

    mostrar("\n=== 2) DINHEIRO E NUMEROS EM TEXTO ===")
    for arq, df, cols in [("itens", itens, ["quantidade", "valor_unitario_estimado", "valor_total_estimado"]),
                          ("resultados", resultados, ["quantidade_homologada", "valor_unitario_homologado",
                                                      "valor_total_homologado"])]:
        for c in cols:
            mostrar(f"{arq}.{c}: com R$/virgula/parenteses = {contar(df[c], dinheiro_em_texto)}"
                    f" | negativo entre parenteses = {contar(df[c], lambda v: v.strip().startswith('('))}"
                    f" | nulo disfarcado = {contar(df[c], eh_nulo_disfarcado)}"
                    f" | vazio = {contar(df[c], lambda v: v.strip() == '')}")

    mostrar("\n=== 3) DATAS ===")
    for arq, df, c in [("compras", compras, "data_publicacao"), ("resultados", resultados, "data_resultado")]:
        mostrar(f"{arq}.{c}: {df[c].map(formato_data).value_counts().to_dict()}")
    pub = compras.set_index("numero_controle_pncp")["data_publicacao"].map(limpeza.converter_data)
    res = resultados.assign(pub=resultados["numero_controle_pncp"].map(pub),
                            hom=resultados["data_resultado"].map(limpeza.converter_data))
    invertidas = sum(1 for h, p in zip(res["hom"], res["pub"]) if h is not None and p is not None and h < p)
    mostrar(f"resultados com homologacao ANTES da publicacao: {invertidas}")
    mostrar(f"datas impossiveis ou fora de 2000-2030 (viram vazio): "
            f"{sum(1 for v, d in zip(resultados['data_resultado'], res['hom']) if v.strip() and d is None)}")

    mostrar("\n=== 4) NULOS DISFARCADOS (N/A, -, NULL, SEM INFORMACAO, 0 em texto...) ===")
    for arq, df in [("compras", compras), ("itens", itens), ("resultados", resultados)]:
        achados = {c: contar(df[c], eh_nulo_disfarcado) for c in df.columns}
        achados = {c: n for c, n in achados.items() if n}
        mostrar(f"{arq}: {achados}")

    mostrar("\n=== 5) TEXTO: ACENTO QUEBRADO E NOMES DIFERENTES ===")
    for arq, df, cols in [("compras", compras, ["razao_social_orgao", "nome_unidade", "objeto_compra", "uf_nome"]),
                          ("itens", itens, ["descricao"]), ("resultados", resultados, ["nome_fornecedor"])]:
        for c in cols:
            mostrar(f"{arq}.{c}: acento quebrado = {contar(df[c], acento_quebrado)}")
    brutos = compras["razao_social_orgao"].nunique()
    limpos = compras["razao_social_orgao"].map(limpeza.padronizar_nome).nunique()
    mostrar(f"nomes de orgao distintos: {brutos} escritos no arquivo -> {limpos} depois de padronizar")
    mostrar(f"modalidade_nome escrita de {compras['modalidade_nome'].nunique()} jeitos para "
            f"{compras['modalidade_id'].nunique()} modalidades")
    mostrar(f"uf_sigla escrita de {compras['uf_sigla'].nunique()} jeitos -> "
            f"{compras['uf_sigla'].map(limpeza.padronizar_nome).nunique()} UFs depois de padronizar")

    mostrar("\n=== OUTRAS COISAS QUE CHAMARAM ATENCAO ===")
    mostrar(f"itens sigilosos: {(itens['sigiloso'].str.lower() == 'true').sum()}")
    mostrar(f"categoria_item: {itens['categoria_item'].value_counts().to_dict()}  (nao ajuda em nada)")
    mostrar(f"resultados cancelados: {(resultados['data_cancelamento'].str.strip() != '').sum()}")
    mostrar(f"ordem_classificacao_srp vazia: {(resultados['ordem_classificacao_srp'].str.strip() == '').sum()}")

    config.PASTA_REPORTS.mkdir(parents=True, exist_ok=True)
    (config.PASTA_REPORTS / "auditoria.txt").write_text("\n".join(linhas_relatorio), encoding="utf-8")


if __name__ == "__main__":
    main()
