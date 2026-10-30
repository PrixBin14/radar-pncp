-- =====================================================================================
-- 02_perguntas.sql  -  as 6 perguntas da Controladoria
-- Rodar no pgAdmin (Query Tool), uma consulta de cada vez, no banco pncp_controladoria.
-- Regrinhas que valem pra todas:
--   * percentual e sempre SOMA / SOMA (nunca media de percentuais)
--   * economia so conta item comparavel (comparavel = 1)
--   * NULLIF(x, 0) evita divisao por zero (Credenciamento nao tem item comparavel)
-- =====================================================================================


-- -------------------------------------------------------------------------------------
-- P1. ECONOMIA GLOBAL: quanto o governo economizou (R$ e %)?
-- -------------------------------------------------------------------------------------
SELECT
    COUNT(*)                                                                 AS itens_na_fato,
    SUM(comparavel)                                                          AS itens_comparaveis,
    ROUND(100.0 * SUM(comparavel) / COUNT(*), 2)                             AS pct_itens_comparaveis,
    SUM(valor_total_homologado)                                              AS volume_homologado,
    SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado   ELSE 0 END)     AS estimado_comparavel,
    SUM(CASE WHEN comparavel = 1 THEN valor_total_homologado ELSE 0 END)     AS homologado_comparavel,
    SUM(economia_valor)                                                      AS economia_rs,
    ROUND(100.0 * SUM(economia_valor)
          / NULLIF(SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct,
    SUM(CASE WHEN comparavel = 1 AND valor_total_homologado > valor_total_estimado
             THEN 1 ELSE 0 END)                                              AS itens_com_sobrepreco
FROM fato_item_contratado;


-- -------------------------------------------------------------------------------------
-- P2. CONCENTRACAO: os 10 maiores fornecedores e quanto do orcamento eles levam
-- (o denominador e a subconsulta com o volume total)
-- -------------------------------------------------------------------------------------
SELECT
    RANK() OVER (ORDER BY SUM(f.valor_total_homologado) DESC)               AS ranking,
    d.ni_fornecedor,
    d.nome_fornecedor,
    COUNT(*)                                                                 AS itens,
    SUM(f.valor_total_homologado)                                            AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2) AS pct_do_total
FROM fato_item_contratado f
JOIN dim_fornecedor d ON d.sk_fornecedor = f.sk_fornecedor
GROUP BY d.ni_fornecedor, d.nome_fornecedor
ORDER BY volume DESC
LIMIT 10;

-- P2 (complemento): quanto os 10 maiores, JUNTOS, concentram do volume total
SELECT
    ROUND(100.0 * SUM(volume) / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2) AS concentracao_top10_pct
FROM (
    SELECT SUM(valor_total_homologado) AS volume
    FROM fato_item_contratado
    GROUP BY sk_fornecedor
    ORDER BY volume DESC
    LIMIT 10
) top10;


-- -------------------------------------------------------------------------------------
-- P3. MODALIDADES: qual tem mais desagio (economia %) e qual movimenta mais dinheiro
-- (Credenciamento fica com economia vazia: nenhum item dele e comparavel, e isso e esperado)
-- -------------------------------------------------------------------------------------
SELECT
    m.nome_modalidade,
    COUNT(*)                                                                 AS itens,
    SUM(f.valor_total_homologado)                                            AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2) AS pct_volume,
    SUM(f.economia_valor)                                                    AS economia_rs,
    ROUND(100.0 * SUM(f.economia_valor)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct
FROM fato_item_contratado f
JOIN dim_modalidade m ON m.sk_modalidade = f.sk_modalidade
GROUP BY m.nome_modalidade
ORDER BY volume DESC;


-- -------------------------------------------------------------------------------------
-- P4. CICLO: dias entre publicar o edital e homologar, por orgao
-- agrupado pelo NOME (o mesmo orgao tem varias unidades/CNPJ), so orgaos com 5+ itens com ciclo.
-- COUNT(dias_ciclo) conta so quem tem ciclo (ignora os vazios), e o AVG tambem ignora.
-- -------------------------------------------------------------------------------------

-- visao geral primeiro
SELECT
    ROUND(AVG(dias_ciclo), 1)          AS ciclo_medio_dias,
    MAX(dias_ciclo)                    AS ciclo_maximo_dias,
    COUNT(dias_ciclo)                  AS itens_com_ciclo,
    COUNT(*) - COUNT(dias_ciclo)       AS itens_sem_ciclo
FROM fato_item_contratado;

-- ranking por orgao (os mais demorados primeiro)
SELECT
    o.nome_orgao,
    COUNT(DISTINCT o.cnpj_orgao)       AS unidades_compradoras,
    COUNT(f.dias_ciclo)                AS itens_com_ciclo,
    ROUND(AVG(f.dias_ciclo), 1)        AS ciclo_medio_dias,
    MAX(f.dias_ciclo)                  AS ciclo_maximo_dias
FROM fato_item_contratado f
JOIN dim_orgao o ON o.sk_orgao = f.sk_orgao
GROUP BY o.nome_orgao
HAVING COUNT(f.dias_ciclo) >= 5
ORDER BY ciclo_medio_dias DESC;


-- -------------------------------------------------------------------------------------
-- P5. REGIONAL: onde se gasta mais e onde se consegue mais desconto
-- -------------------------------------------------------------------------------------

-- por regiao
SELECT
    l.regiao,
    COUNT(DISTINCT f.sk_orgao)                                               AS unidades_compradoras,
    COUNT(*)                                                                 AS itens,
    SUM(f.valor_total_homologado)                                            AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2) AS pct_volume,
    ROUND(100.0 * SUM(f.economia_valor)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct
FROM fato_item_contratado f
JOIN dim_localidade l ON l.sk_localidade = f.sk_localidade
GROUP BY l.regiao
ORDER BY volume DESC;

-- por estado (UF)
SELECT
    l.uf_sigla,
    l.uf_nome,
    l.regiao,
    COUNT(DISTINCT f.sk_orgao)                                               AS unidades_compradoras,
    COUNT(*)                                                                 AS itens,
    SUM(f.valor_total_homologado)                                            AS volume,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2) AS pct_volume,
    ROUND(100.0 * SUM(f.economia_valor)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct
FROM fato_item_contratado f
JOIN dim_localidade l ON l.sk_localidade = f.sk_localidade
GROUP BY l.uf_sigla, l.uf_nome, l.regiao
ORDER BY volume DESC;


-- -------------------------------------------------------------------------------------
-- P6. PERFIL DO GASTO: bens, servicos ou obras? (perfil_gasto ja esta na fato, nao precisa de JOIN)
-- -------------------------------------------------------------------------------------
SELECT
    perfil_gasto,
    COUNT(*)                                                                 AS itens,
    SUM(valor_total_homologado)                                              AS volume,
    ROUND(100.0 * SUM(valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 1) AS pct_volume,
    ROUND(SUM(valor_total_homologado) / COUNT(*), 2)                         AS ticket_medio_por_item,
    ROUND(100.0 * SUM(economia_valor)
          / NULLIF(SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado ELSE 0 END), 0), 2) AS economia_pct
FROM fato_item_contratado
GROUP BY perfil_gasto
ORDER BY volume DESC;
