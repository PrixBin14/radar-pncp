"""
limpeza.py  -  FUNCOES DE LIMPEZA
=================================
Cada funcao resolve UM problema dos dados brutos (CNPJ com mascara, "R$ 1.234,56", datas em varios formatos...).
A ideia e simples: funcoes pequenas, que fazem uma coisa so, e que da pra testar uma por uma.

COMO TESTAR:   python -m src.limpeza
Roda os exemplos la de baixo e mostra  ✔  ou  ✘  em cada um.
"""

from datetime import datetime

# Textos que na pratica querem dizer "nao tem nada aqui" (sempre comparo em MAIUSCULAS)
NULOS = {"N/A", "NULL", "NONE", "NAN", "-", "0", "SEM INFORMAÇÃO", "SEM INFORMACAO",
         "NÃO INFORMADO", "NAO INFORMADO", "NÃO SE APLICA", "NAO SE APLICA"}

# Formatos de data que encontrei nos arquivos (%d = dia, %m = mes, %Y = ano com 4 digitos)
FORMATOS_DATA = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%Y%m%d"]


# ---------------------------------------------------------------------------------------------
# 1) TEXTO  (nulos disfarcados, espacos, acento quebrado)
# ---------------------------------------------------------------------------------------------
def remover_invisiveis(texto):
    """Apaga uns caracteres invisiveis que vem grudados no texto e fazem 'Ana' ser diferente de 'Ana'."""
    for c in ["​", "‌", "‍", "﻿"]:
        texto = texto.replace(c, "")
    return texto


def consertar_acento(texto):
    """'AquisiÃ§Ã£o' -> 'Aquisição'. Isso acontece quando o arquivo foi aberto com a codificacao errada
    e os acentos viram bagunca. O truque e desfazer o erro: "desembrulha" e le de novo do jeito certo.
    Se o texto ja estava certo, da erro no meio do caminho e eu devolvo do jeito que veio."""
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def tirar_espacos(texto):
    """'  Ana   Maria ' -> 'Ana Maria'.
    O split() separa as palavras (some com todo espaco sobrando) e o join junta de novo com um espaco so."""
    return " ".join(texto.split())


def eh_nulo(texto, zero_eh_nulo=True):
    """True se o texto e um 'nulo disfarcado': vazio, N/A, NULL, -, SEM INFORMACAO...
    Pegadinha: o "0" so e nulo em campo de TEXTO. Em quantidade ou valor, zero e numero de verdade."""
    chave = texto.upper()
    if chave == "":
        return True
    if chave == "0":
        # quem chama decide se o zero conta como nulo ou nao
        return zero_eh_nulo
    return chave in NULOS


def limpar_texto(texto, zero_eh_nulo=True):
    """Faxina geral num texto: invisiveis, acento, espacos. Se no fim for 'nulo disfarcado', vira None."""
    if texto is None:
        return None
    texto = remover_invisiveis(texto)
    texto = consertar_acento(texto.strip(" "))
    texto = tirar_espacos(texto)
    if eh_nulo(texto, zero_eh_nulo):
        return None
    return texto


def padronizar_nome(texto):
    """Nome de orgao / fornecedor / item: limpo e em MAIUSCULAS, pra 'Ministério da Saúde' e 'MINISTÉRIO  DA SAÚDE '
    virarem a MESMA coisa.   'Pregão-Eletrônico' -> 'PREGÃO - ELETRÔNICO'."""
    texto = limpar_texto(texto)
    if texto is None:
        return None
    texto = texto.upper()
    # hifen sempre com espaco dos dois lados (o tirar_espacos la embaixo tira o espaco que sobrar)
    texto = texto.replace("-", " - ")
    return tirar_espacos(texto)


# ---------------------------------------------------------------------------------------------
# 2) DOCUMENTOS  (CNPJ = 14 digitos, CPF = 11)
# ---------------------------------------------------------------------------------------------
def limpar_documento(texto, tipo_pessoa=None):
    """Deixa so os numeros do CNPJ/CPF e devolve os zeros da esquerda que se perderam.
       '11.222.333/0001-81' (PJ) -> '11222333000181'     '1222333000181' (PJ, perdeu o zero) -> '01222333000181'
       '1234567890' (PF)         -> '01234567890'        'ABC123' (PE, estrangeiro) -> 'ABC123' (nao mexo)
    Lixo ('N/A', '-') ou numero grande demais -> None."""
    texto = limpar_texto(texto)
    if texto is None:
        return None
    if tipo_pessoa == "PE":
        # estrangeiro nao tem CNPJ brasileiro, o codigo dele pode ter letra
        return texto.upper()
    # tira ponto, barra, traco... fica so digito
    digitos = "".join(c for c in texto if c.isdigit())
    if digitos == "":
        return None
    if tipo_pessoa == "PJ":
        tamanho = 14
    elif tipo_pessoa == "PF":
        tamanho = 11
    else:                                    # sem o tipo: mais de 11 digitos e CNPJ, senao CPF
        tamanho = 14 if len(digitos) > 11 else 11
    if len(digitos) > tamanho:               # digito sobrando = documento impossivel
        return None
    # quando alguem abre no Excel o zero da esquerda some; o zfill coloca ele de volta
    return digitos.zfill(tamanho)


# ---------------------------------------------------------------------------------------------
# 3) DINHEIRO E NUMEROS EM TEXTO
# ---------------------------------------------------------------------------------------------
def converter_numero(texto):
    """'R$ 1.234,56' -> 1234.56      '1,234.56' -> 1234.56      '0,754' -> 0.754      '(1.500,00)' -> -1500.0
    REGRA DESTA BASE: ponto OU virgula SOZINHO e sempre o DECIMAL ('746.815' -> 746.815, nao 746 mil!).
    So o simbolo REPETIDO e milhar ('1.234.567'). Quando tem os dois, o ULTIMO e o decimal.
    Se nao der pra converter ('N/A', vazio) -> None. Zero e numero valido."""
    texto = limpar_texto(texto, zero_eh_nulo=False)     # aqui o 0 vale, nao e nulo
    if texto is None:
        return None
    texto = texto.replace("R$", "").replace(" ", "")
    # negativo pode vir de 3 jeitos: (1.500,00)   -12,50   1.500,00-
    negativo = texto.startswith("(") or texto.startswith("-") or texto.endswith("-")
    texto = texto.strip("()-")
    if "." in texto and "," in texto:
        if texto.rfind(",") > texto.rfind("."):
            # 1.234,56 -> jeito brasileiro: tiro os pontos e a virgula vira ponto
            texto = texto.replace(".", "").replace(",", ".")
        else:
            # 1,234.56 -> jeito americano: so tiro as virgulas
            texto = texto.replace(",", "")
    elif "," in texto:
        if texto.count(",") > 1:
            # 1,234,567 -> virgula repetida e milhar
            texto = texto.replace(",", "")
        else:
            # 12,5 -> virgula sozinha e decimal
            texto = texto.replace(",", ".")
    elif texto.count(".") > 1:
        # 1.234.567 -> ponto repetido e milhar
        texto = texto.replace(".", "")
    # ponto sozinho (1234.56 ou 746.815) ja e decimal, o float entende direto
    try:
        numero = float(texto)
    except ValueError:
        return None
    return -numero if negativo else numero


# ---------------------------------------------------------------------------------------------
# 4) DATAS  (varios formatos no mesmo campo)
# ---------------------------------------------------------------------------------------------
def converter_data(texto):
    """'2025-03-10T08:30:00', '10/03/2025 14:20', '10.03.2025', '20250310' -> 2025-03-10 (sem hora).
    None pra vazio, data que nao existe ('31/02/2025') ou ano maluco ('0001-01-01': so aceito 2000 a 2030)."""
    texto = limpar_texto(texto)
    if texto is None:
        return None
    # os 10 primeiros caracteres sao a data; o resto e hora, que nao interessa
    texto = texto[:10]
    for formato in FORMATOS_DATA:
        try:
            data = datetime.strptime(texto, formato).date()
        except ValueError:
            continue                          # nao era esse formato, tenta o proximo
        if 2000 <= data.year <= 2030:
            return data
        return None
    return None


# =============================================================================================
# AUTOTESTE: python -m src.limpeza
# =============================================================================================
from datetime import date  # noqa: E402

CASOS = [
    # (funcao, argumentos, resultado esperado)
    ("tirar_espacos", ("  Ana   Maria ",), "Ana Maria"),
    ("eh_nulo", ("N/A",), True), ("eh_nulo", ("SEM INFORMAÇÃO",), True), ("eh_nulo", ("",), True),
    ("eh_nulo", ("Ana",), False), ("eh_nulo", ("0", True), True), ("eh_nulo", ("0", False), False),
    ("limpar_texto", ("AquisiÃ§Ã£o de mÃ³veis",), "Aquisição de móveis"),
    ("limpar_texto", ("Aquisição",), "Aquisição"),
    ("limpar_texto", ("  Ministério  da   Saúde  ",), "Ministério da Saúde"),
    ("limpar_texto", ("n/a",), None), ("limpar_texto", (" ",), None), ("limpar_texto", ("0",), None),
    ("padronizar_nome", ("  Ministério  da   Saúde  ",), "MINISTÉRIO DA SAÚDE"),
    ("padronizar_nome", ("Pregão-Eletrônico",), "PREGÃO - ELETRÔNICO"),
    ("limpar_documento", ("11.222.333/0001-81", "PJ"), "11222333000181"),
    ("limpar_documento", ("11222333000181", None), "11222333000181"),
    ("limpar_documento", ("1222333000181", "PJ"), "01222333000181"),
    ("limpar_documento", ("360305000104", "PJ"), "00360305000104"),
    ("limpar_documento", ("111.444.777-35", "PF"), "11144477735"),
    ("limpar_documento", ("1234567890", "PF"), "01234567890"),
    ("limpar_documento", (" 11222333000181 ", "PJ"), "11222333000181"),
    ("limpar_documento", ("N/A", "PJ"), None), ("limpar_documento", ("-", "PJ"), None),
    ("limpar_documento", ("ABC123", "PE"), "ABC123"),
    ("limpar_documento", ("123456789012345", "PJ"), None),
    ("converter_numero", ("R$ 1.234,56",), 1234.56), ("converter_numero", ("1,234.56",), 1234.56),
    ("converter_numero", ("1234.56",), 1234.56), ("converter_numero", ("1.234",), 1.234),
    ("converter_numero", ("0,754",), 0.754), ("converter_numero", ("746.815",), 746.815),
    ("converter_numero", ("1.234.567",), 1234567.0), ("converter_numero", ("12,5",), 12.5),
    ("converter_numero", ("1.234.567,89",), 1234567.89), ("converter_numero", ("R$ -12,50",), -12.5),
    ("converter_numero", ("(1.500,00)",), -1500.0), ("converter_numero", ("1.500,00-",), -1500.0),
    ("converter_numero", ("R$ 2.000,00",), 2000.0), ("converter_numero", ("493231.6000",), 493231.6),
    ("converter_numero", ("0",), 0.0), ("converter_numero", ("N/A",), None), ("converter_numero", ("",), None),
    ("converter_data", ("2025-03-10T08:30:00",), date(2025, 3, 10)), ("converter_data", ("10/03/2025",), date(2025, 3, 10)),
    ("converter_data", ("10-03-2025",), date(2025, 3, 10)), ("converter_data", ("2025/03/10",), date(2025, 3, 10)),
    ("converter_data", ("20250310",), date(2025, 3, 10)), ("converter_data", ("10/03/2025 14:20",), date(2025, 3, 10)),
    ("converter_data", ("10.03.2025",), date(2025, 3, 10)), ("converter_data", ("31/02/2025",), None),
    ("converter_data", ("0001-01-01",), None), ("converter_data", ("-",), None), ("converter_data", ("",), None),
]


def testar():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")        # pro ✔ e o ✘ aparecerem em qualquer terminal
    except (AttributeError, ValueError):
        pass
    acertos = 0
    for nome, args, esperado in CASOS:
        try:
            obtido = globals()[nome](*args)
            ok = obtido == esperado
        except Exception as erro:
            obtido, ok = f"erro: {type(erro).__name__}", False
        acertos += ok
        print(f"{'✔' if ok else '✘'} {nome}{args} -> {obtido!r}" + ("" if ok else f"   (esperado {esperado!r})"))
    print(f"\n{acertos} de {len(CASOS)} exemplos certos" + ("  ✔ tudo certo!" if acertos == len(CASOS) else "  -> tem coisa pra arrumar"))
    return acertos == len(CASOS)


if __name__ == "__main__":
    raise SystemExit(0 if testar() else 1)
