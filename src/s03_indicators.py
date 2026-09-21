"""Etapa 3 - Construcao dos oito componentes contabeis e do M-Score.

Os componentes derivam de Beneish (1999) e foram adaptados as contas fixas
disponiveis na base da CVM. Exige-se par de exercicios consecutivos com o
mesmo dia e mes de encerramento. Denominadores iguais a zero produzem valor
ausente, sem substituicao arbitraria. Valores negativos economicamente
possiveis, como margem bruta negativa, sao preservados.

Saidas:
    data/processed/indicadores.csv
    outputs/tables/tabela3_estatisticas_descritivas.csv
    outputs/tables/etapa3_formacao_amostra.csv

Uso:
    python src/s03_indicators.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils import (DIR_PROCESSED, get_logger, load_config, razao_segura,
                   salvar_tabela)

LOG = get_logger("s03_indicators")


def emparelhar_exercicios(painel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Une cada observacao ao exercicio anterior da mesma companhia.

    Exige mesmo dia e mes de encerramento, de modo que mudanca de periodo de
    reporte nao seja interpretada como mudanca economica.
    """
    painel = painel.copy()
    painel["DT_REFER"] = pd.to_datetime(painel["DT_REFER"])
    painel["DIA_MES"] = painel["DT_REFER"].dt.strftime("%m-%d")
    painel["ANO_REFER"] = painel["DT_REFER"].dt.year

    identificacao = {"CD_CVM", "DENOM_CIA", "DT_REFER", "ANO_REFER", "DIA_MES"}
    contas = [c for c in painel.columns if c not in identificacao]

    # Sufixos explicitos: o exercicio corrente recebe _t; o anterior, _t1.
    atual = painel.rename(columns={c: f"{c}_t" for c in contas + ["DIA_MES"]})
    anterior = (painel[["CD_CVM", "ANO_REFER", "DIA_MES"] + contas]
                .assign(ANO_REFER=lambda d: d["ANO_REFER"] + 1)
                .rename(columns={c: f"{c}_t1" for c in contas + ["DIA_MES"]}))

    pares = atual.merge(anterior, on=["CD_CVM", "ANO_REFER"], how="inner")

    if cfg["filtros"]["exigir_mesma_data_fiscal"]:
        antes = len(pares)
        pares = pares[pares["DIA_MES_t"] == pares["DIA_MES_t1"]]
        LOG.info("pares descartados por data fiscal divergente: %d",
                 antes - len(pares))

    pares = pares[pares["ANO_REFER"].isin(cfg["fonte"]["anos_escore"])]
    LOG.info("pares consecutivos elegiveis: %d observacoes, %d companhias",
             len(pares), pares["CD_CVM"].nunique())
    return pares.reset_index(drop=True)


def calcular_componentes(p: pd.DataFrame) -> pd.DataFrame:
    """Calcula os oito componentes conforme a Tabela 1 do trabalho."""
    fora = pd.DataFrame(index=p.index)

    # DSRI - mudanca relativa de recebiveis em relacao as vendas.
    rec_t = razao_segura(p["recebiveis_t"], p["receita_liquida_t"])
    rec_t1 = razao_segura(p["recebiveis_t1"], p["receita_liquida_t1"])
    fora["DSRI"] = razao_segura(rec_t, rec_t1)

    # GMI - deterioracao relativa da margem bruta (t-1 sobre t).
    mb_t = razao_segura(p["resultado_bruto_t"], p["receita_liquida_t"])
    mb_t1 = razao_segura(p["resultado_bruto_t1"], p["receita_liquida_t1"])
    fora["GMI"] = razao_segura(mb_t1, mb_t)

    # AQI - parcela de ativos nao circulantes exceto imobilizado.
    aq_t = 1 - razao_segura(p["ativo_circulante_t"] + p["imobilizado_t"],
                            p["ativo_total_t"])
    aq_t1 = 1 - razao_segura(p["ativo_circulante_t1"] + p["imobilizado_t1"],
                             p["ativo_total_t1"])
    fora["AQI"] = razao_segura(aq_t, aq_t1)

    # SGI - crescimento das vendas.
    fora["SGI"] = razao_segura(p["receita_liquida_t"], p["receita_liquida_t1"])

    # DEPI - mudanca da taxa de depreciacao; taxa = Dep / (Dep + Imobilizado).
    dep_t = p["depreciacao_t"].abs()
    dep_t1 = p["depreciacao_t1"].abs()
    taxa_t = razao_segura(dep_t, dep_t + p["imobilizado_t"])
    taxa_t1 = razao_segura(dep_t1, dep_t1 + p["imobilizado_t1"])
    fora["DEPI"] = razao_segura(taxa_t1, taxa_t)

    # SGAI - despesas com vendas, gerais e administrativas, em valor absoluto.
    dvga_t = p["despesas_vendas_t"].abs() + p["despesas_gerais_adm_t"].abs()
    dvga_t1 = p["despesas_vendas_t1"].abs() + p["despesas_gerais_adm_t1"].abs()
    sga_t = razao_segura(dvga_t, p["receita_liquida_t"])
    sga_t1 = razao_segura(dvga_t1, p["receita_liquida_t1"])
    fora["SGAI"] = razao_segura(sga_t, sga_t1)

    # LVGI - mudanca da alavancagem.
    alav_t = razao_segura(p["passivo_circulante_t"] + p["divida_longo_prazo_t"],
                          p["ativo_total_t"])
    alav_t1 = razao_segura(p["passivo_circulante_t1"] + p["divida_longo_prazo_t1"],
                           p["ativo_total_t1"])
    fora["LVGI"] = razao_segura(alav_t, alav_t1)

    # TATA - diferenca entre resultado e caixa operacional sobre ativos.
    fora["TATA"] = razao_segura(p["resultado_liquido_t"] - p["fco_t"],
                                p["ativo_total_t"])

    return fora.replace([np.inf, -np.inf], np.nan)


def calcular_mscore(indicadores: pd.DataFrame, cfg: dict) -> pd.Series:
    """M-Score de Beneish na combinacao original, em uso continuo e ordinal."""
    coef = cfg["indicadores"]["mscore_coeficientes"]
    score = pd.Series(coef["intercepto"], index=indicadores.index, dtype=float)
    for componente in cfg["indicadores"]["componentes"]:
        score = score + coef[componente] * indicadores[componente]
    return score


def main() -> None:
    cfg = load_config()
    componentes = cfg["indicadores"]["componentes"]

    painel = pd.read_csv(DIR_PROCESSED / "painel_companhia_ano.csv")
    n_bruto = len(painel)
    LOG.info("painel bruto lido: %d observacoes", n_bruto)

    pares = emparelhar_exercicios(painel, cfg)
    n_pares = len(pares)

    indicadores = calcular_componentes(pares)
    base = pd.concat([
        pares[["CD_CVM", "DENOM_CIA", "DT_REFER", "ANO_REFER"]],
        indicadores,
    ], axis=1)

    completos = base.dropna(subset=componentes).copy()
    LOG.info("observacoes com os oito componentes completos: %d (perda de %d)",
             len(completos), n_pares - len(completos))

    completos["MSCORE"] = calcular_mscore(completos, cfg)
    completos["COMPANHIA_ANO"] = (completos["DENOM_CIA"].str.strip()
                                  + " (" + completos["ANO_REFER"].astype(str) + ")")
    completos = completos.reset_index(drop=True)
    completos.to_csv(DIR_PROCESSED / "indicadores.csv", index=False, encoding="utf-8")

    # Tabela 3 - estatisticas descritivas dos componentes.
    descritivas = pd.DataFrame({
        "Indicador": componentes,
        "Media": [completos[c].mean() for c in componentes],
        "Mediana": [completos[c].median() for c in componentes],
        "Q1": [completos[c].quantile(0.25) for c in componentes],
        "Q3": [completos[c].quantile(0.75) for c in componentes],
        "Minimo": [completos[c].min() for c in componentes],
        "Maximo": [completos[c].max() for c in componentes],
    }).round(3)
    salvar_tabela(descritivas, "tabela3_estatisticas_descritivas")
    LOG.info("\n%s", descritivas.to_string(index=False))

    corte = cfg["modelo"]["corte_referencia"]
    formacao = pd.DataFrame([
        {"etapa": "Painel 2020-2025", "observacoes": n_bruto},
        {"etapa": "Pares consecutivos", "observacoes": n_pares},
        {"etapa": "Amostra completa", "observacoes": len(completos)},
        {"etapa": f"Prioridade ({corte:.0%})",
         "observacoes": int(np.ceil(len(completos) * corte))},
    ])
    salvar_tabela(formacao, "etapa3_formacao_amostra")
    LOG.info("companhias distintas na amostra analitica: %d",
             completos["CD_CVM"].nunique())
    LOG.info("etapa 3 concluida.")


if __name__ == "__main__":
    main()
