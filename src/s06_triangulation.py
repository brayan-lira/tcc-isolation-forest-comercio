"""Etapa 6 - Triangulacoes com o M-Score e com o relatorio do auditor.

Primeira triangulacao: correlacao de Spearman entre o percentil consensual e o
percentil do M-Score continuo, e sobreposicao das maiores posicoes.

Segunda triangulacao: os relatorios do auditor independente sao agrupados em
sem ressalva e opiniao modificada, esta ultima formada por opiniao com
ressalva ou negativa de opiniao. Compara-se uma tabela de contingencia 2 x 2
pelo teste exato de Fisher. O relatorio do auditor nao e tratado como rotulo
de fraude: sua natureza e seu momento de emissao respondem a objetivos
distintos daqueles do algoritmo. Registros sem tipo de relatorio identificado
permanecem no ranking, mas sao excluidos do teste.

Saidas:
    outputs/tables/tabela7_tipo_relatorio.csv
    outputs/tables/triangulacao_resumo.json
    data/processed/ranking_com_triangulacao.csv

Uso:
    python src/s06_triangulation.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, mannwhitneyu, spearmanr

from s04_isolation_forest import jaccard
from utils import (DIR_PROCESSED, DIR_TABLES, get_logger, load_config,
                   normalizar_texto, salvar_json, salvar_tabela)

LOG = get_logger("s06_triangulation")


def classificar_opiniao(valor: str, cfg: dict) -> str | None:
    """Agrupa o tipo de relatorio em sem ressalva ou opiniao modificada."""
    texto = normalizar_texto(valor)
    if not texto:
        return None
    for rotulo in cfg["triangulacao"]["opiniao_modificada"]:
        if normalizar_texto(rotulo) in texto:
            return "Opiniao modificada"
    for rotulo in cfg["triangulacao"]["opiniao_sem_ressalva"]:
        if normalizar_texto(rotulo) in texto:
            return "Sem ressalva"
    return None


def triangular_mscore(ranking: pd.DataFrame, corte: float) -> dict:
    """Compara o ranking do modelo com a referencia contabil de Beneish."""
    ranking["percentil_mscore"] = ranking["MSCORE"].rank(pct=True)
    correlacao = spearmanr(ranking["percentil_consensual"],
                           ranking["percentil_mscore"])

    quantidade = int(np.ceil(len(ranking) * corte))
    grupo_modelo = ranking.nlargest(quantidade, "percentil_consensual").index
    grupo_mscore = ranking.nlargest(quantidade, "percentil_mscore").index
    coincidentes = len(set(grupo_modelo) & set(grupo_mscore))

    resultado = {
        "spearman": round(float(correlacao.statistic), 3),
        "p_valor": round(float(correlacao.pvalue), 3),
        "posicoes_coincidentes": coincidentes,
        "tamanho_do_grupo": quantidade,
        "jaccard": round(float(jaccard(grupo_modelo, grupo_mscore)), 3),
    }
    LOG.info("M-Score: Spearman %.3f (p = %.3f) | %d de %d posicoes coincidentes "
             "| Jaccard %.3f", resultado["spearman"], resultado["p_valor"],
             coincidentes, quantidade, resultado["jaccard"])
    return resultado


def triangular_auditor(ranking: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Confronta o grupo prioritario com o tipo de relatorio do auditor."""
    caminho = DIR_TABLES / "relatorio_auditor.csv"
    if not caminho.exists():
        LOG.warning("relatorio_auditor.csv ausente; triangulacao ignorada. "
                    "Execute 'python src/s00_inspect_layout.py' para verificar "
                    "a secao de pareceres no pacote da CVM.")
        return pd.DataFrame(), {}

    pareceres = pd.read_csv(caminho)
    pareceres["ANO_REFER"] = pd.to_datetime(pareceres["DT_REFER"]).dt.year
    pareceres["CD_CVM"] = pareceres["CD_CVM"].astype(str).str.strip()
    pareceres["OPINIAO"] = pareceres["TIPO_RELATORIO"].map(
        lambda v: classificar_opiniao(v, cfg))

    nao_classificados = pareceres["OPINIAO"].isna().sum()
    if nao_classificados:
        LOG.warning("%d pareceres com tipo nao coberto pelo config.yaml; "
                    "consulte outputs/tables/tipos_de_relatorio.csv",
                    nao_classificados)

    pareceres = (pareceres.dropna(subset=["OPINIAO"])
                 .drop_duplicates(subset=["CD_CVM", "ANO_REFER"]))

    ranking = ranking.copy()
    ranking["CD_CVM"] = ranking["CD_CVM"].astype(str).str.strip()
    unido = ranking.merge(pareceres[["CD_CVM", "ANO_REFER", "OPINIAO"]],
                          on=["CD_CVM", "ANO_REFER"], how="left")

    com_opiniao = unido.dropna(subset=["OPINIAO"])
    LOG.info("observacoes com tipo de relatorio identificado: %d de %d",
             len(com_opiniao), len(unido))
    if com_opiniao.empty:
        return pd.DataFrame(), {}

    corte = cfg["modelo"]["corte_referencia"]
    rotulo_corte = f"top_{int(corte * 100)}"
    com_opiniao = com_opiniao.assign(
        Grupo=np.where(com_opiniao[rotulo_corte], f"Top {int(corte*100)}%",
                       f"Fora do top {int(corte*100)}%"))

    contingencia = pd.crosstab(com_opiniao["Grupo"], com_opiniao["OPINIAO"])
    for coluna in ["Sem ressalva", "Opiniao modificada"]:
        if coluna not in contingencia.columns:
            contingencia[coluna] = 0
    contingencia = contingencia[["Sem ressalva", "Opiniao modificada"]]

    odds, p_valor = fisher_exact(contingencia.values)

    dentro = com_opiniao.loc[com_opiniao[rotulo_corte], "percentil_consensual"]
    fora = com_opiniao.loc[~com_opiniao[rotulo_corte], "percentil_consensual"]
    modificada = com_opiniao.loc[com_opiniao["OPINIAO"] == "Opiniao modificada",
                                 "percentil_consensual"]
    sem_ressalva = com_opiniao.loc[com_opiniao["OPINIAO"] == "Sem ressalva",
                                   "percentil_consensual"]

    teste_medianas = (mannwhitneyu(modificada, sem_ressalva, alternative="two-sided")
                      if len(modificada) and len(sem_ressalva) else None)

    tabela = contingencia.copy()
    tabela["Total"] = tabela.sum(axis=1)
    tabela.loc["Total"] = tabela.sum()
    tabela = tabela.reset_index()

    resultado = {
        "observacoes_com_relatorio": int(len(com_opiniao)),
        "opiniao_modificada": int((com_opiniao["OPINIAO"] == "Opiniao modificada").sum()),
        "sem_ressalva": int((com_opiniao["OPINIAO"] == "Sem ressalva").sum()),
        "fisher_odds_ratio": round(float(odds), 3) if np.isfinite(odds) else None,
        "fisher_p_valor": round(float(p_valor), 3),
        "significante_a_5pct": bool(p_valor < cfg["triangulacao"]["alfa"]),
        "mediana_percentil_dentro_do_grupo":
            round(float(dentro.median()), 3) if len(dentro) else None,
        "mediana_percentil_fora_do_grupo":
            round(float(fora.median()), 3) if len(fora) else None,
        "mediana_percentil_opiniao_modificada":
            round(float(modificada.median()), 3) if len(modificada) else None,
        "mediana_percentil_sem_ressalva":
            round(float(sem_ressalva.median()), 3) if len(sem_ressalva) else None,
        "mannwhitney_p_valor":
            round(float(teste_medianas.pvalue), 3) if teste_medianas else None,
    }
    LOG.info("Fisher: razao de chances = %s | p = %.3f (alfa = %.2f)",
             resultado["fisher_odds_ratio"], p_valor, cfg["triangulacao"]["alfa"])
    LOG.info("\n%s", tabela.to_string(index=False))
    return tabela, resultado


def main() -> None:
    cfg = load_config()
    ranking = pd.read_csv(DIR_PROCESSED / "ranking_consensual.csv")

    resumo = {}
    if cfg["triangulacao"]["mscore"]:
        resumo["mscore"] = triangular_mscore(ranking, cfg["modelo"]["corte_referencia"])

    if cfg["triangulacao"]["relatorio_auditor"]:
        tabela, resultado = triangular_auditor(ranking, cfg)
        if len(tabela):
            salvar_tabela(tabela, "tabela7_tipo_relatorio")
            resumo["relatorio_auditor"] = resultado

    salvar_json(resumo, "triangulacao_resumo")
    ranking.to_csv(DIR_PROCESSED / "ranking_com_triangulacao.csv",
                   index=False, encoding="utf-8")
    LOG.info("etapa 6 concluida.")


if __name__ == "__main__":
    main()
