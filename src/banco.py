"""
banco.py  -  conexao e utilitarios do PostgreSQL
------------------------------------------------
Mesmo papel do banco.py dos projetos anteriores: abrir conexao, executar SQL e
inserir em lote. Acrescenta recriar_banco() (o CREATE DATABASE do PostgreSQL
precisa de autocommit e de uma conexao em OUTRO banco) e executar_script() para
rodar os arquivos da pasta sql/.
"""

import re

import psycopg2
from psycopg2 import Error, sql
from psycopg2.extras import execute_values

from src import config


def conectar(database=None):
    """Abre a conexao no banco do projeto (ou em 'database', se informado)."""
    try:
        return psycopg2.connect(dbname=database or config.PG_DATABASE, **config.PG_CONFIG)
    except Error as erro:
        raise RuntimeError(
            f"Nao foi possivel conectar ao PostgreSQL em {config.PG_CONFIG['host']}:{config.PG_CONFIG['port']}. "
            f"Confira o arquivo .env e se o servico esta no ar. Detalhe: {erro}"
        )


def recriar_banco():
    """DROP + CREATE DATABASE (conecta no banco administrativo 'postgres')."""
    con = conectar("postgres")
    con.autocommit = True
    cur = con.cursor()
    nome = sql.Identifier(config.PG_DATABASE)
    # encerra sessoes abertas no banco, senao o DROP falha
    cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                (config.PG_DATABASE,))
    cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(nome))
    cur.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(nome))
    cur.close()
    con.close()


def _separar_comandos(texto):
    """Quebra um script .sql em comandos (remove comentarios '-- ...' e separa por ';')."""
    sem_comentarios = re.sub(r"--[^\n]*", "", texto)
    return [c.strip() for c in sem_comentarios.split(";") if c.strip()]


def executar_script(conexao, caminho):
    cursor = conexao.cursor()
    for comando in _separar_comandos(caminho.read_text(encoding="utf-8")):
        cursor.execute(comando)
    conexao.commit()
    cursor.close()


def executar(conexao, comando, params=None):
    cursor = conexao.cursor()
    cursor.execute(comando, params)
    conexao.commit()
    cursor.close()


def consultar(conexao, comando, params=None):
    """SELECT -> lista de tuplas."""
    cursor = conexao.cursor()
    cursor.execute(comando, params)
    linhas = cursor.fetchall()
    cursor.close()
    return linhas


def inserir_em_lote(conexao, sql_insert, linhas, commit=True):
    """Insere varias linhas de uma vez.

    'sql_insert' vem no formato  INSERT INTO t (a,b) VALUES (%s, %s)
    e e convertido para o formato do execute_values (VALUES %s), que envia
    o lote inteiro em UM comando (muito mais rapido que executemany).
    commit=False: deixa a transacao aberta, pra quem chamou decidir se confirma tudo
    no fim ou desfaz tudo (rollback) se der erro no meio.
    """
    if not linhas:
        return
    base = re.sub(r"VALUES\s*\(.*\)\s*$", "VALUES %s", sql_insert, flags=re.S)
    cursor = conexao.cursor()
    execute_values(cursor, base, linhas, page_size=2000)
    if commit:
        conexao.commit()
    cursor.close()
