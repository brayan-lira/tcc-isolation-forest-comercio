"""Etapa 4 - Aplicacao do algoritmo "Isolation Forest" e ranking consensual.

O estudo nao programa a logica do algoritmo: utiliza a implementacao ja
existente e consolidada da biblioteca "scikit-learn" (Pedregosa et al., 2011),
aplicada a dados contabeis reais.

Procedimento, conforme a secao de metodos:
  1. winsorizacao nos percentis 1 e 99, apenas para o ajuste do modelo;
  2. padronizacao robusta - centralizacao pela mediana, escala pelo IQR;
  3. 50 execucoes, com sementes distintas de 0 a 49, 500 arvores e numero
     maximo de amostras por arvore igual a 128, contaminacao automatica;
  4. inversao do sinal do escore, de modo que valores maiores representem
     maior atipicidade;
  5. conversao de cada execucao em percentis e media dos 50 percentis, que
     define o ranking final.

Os grupos de 3%, 5% e 10% sao construidos posteriormente ao ranking, apenas
como limites de capacidade de revisao; a contaminacao nao e utilizada para
presumir a parcela de anomalias da populacao.

Saidas:
    data/processed/ranking_consensual.csv
    data/processed/desvios_padronizados.csv
    outputs/tables/tabela2_distribuicao_temporal.csv
    outputs/tables/tabela4_ranking_consensual.csv
    outputs/tables/tabela5_frequencia_componentes.csv
    outputs/tables/estabilidade_aleatoria.csv
    outputs/tables/estabilidade_resumo.json

Uso:
    python src/s04_isolation_forest.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import IsolationForest

from utils import DIR_PROCESSED, get_logger, load_config, salvar_json, salvar_tabela

LOG = get_logger("s04_isolation_forest")


# --------------------------------------------------------------------------
# Nucleo reutilizavel: a etapa 5 importa estas funcoes para os cenarios.
# --------------------------------------------------------------------------
def winsorizar(X: pd.DataFrame, inferior: float, superior: float) -> pd.DataFrame:
    """Limita cada atributo aos percentis informados, apenas para o ajuste."""
    limites = X.quantile([inferior, superior])
    return X.clip(lower=limites.loc[inferior], upper=limites.loc[superior], axis=1)


def padronizar_robusto(X: pd.DataFrame) -> pd.DataFrame:
    """Centraliza pela mediana e escala pelo intervalo interquartil."""
    mediana = X.median()
    iqr = X.quantile(0.75) - X.quantile(0.25)
    iqr = iqr.replace(0, np.nan)          # atributo constante nao e escalado
    return (X - mediana) / iqr


def preparar_atributos(dados: pd.DataFrame, componentes: list[str],
                       params: dict) -> pd.DataFrame:
    """Aplica winsorizacao e padronizacao conforme os parametros do cenario."""
    X = dados[componentes].astype(float).copy()

    if params.get("winsorizacao_aplicar", True):
        X = winsorizar(X, params["limite_inferior"], params["limite_superior"])

    if params.get("padronizacao_por_exercicio", False):
        X = (X.groupby(dados["ANO_REFER"].values, group_keys=False)
             .apply(padronizar_robusto))
    else:
        X = padronizar_robusto(X)

    return X.fillna(0.0)


def executar_ranking(dados: pd.DataFrame, componentes: list[str], params: dict,
                     n_sementes: int) -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    """Executa o modelo com n sementes e devolve o percentil consensual.

    Retorna:
        consenso  - media dos percentis das execucoes (ranking final);
        percentis - matriz observacoes x sementes, com um percentil por celula;
        X         - atributos winsorizados e padronizados, usados na explicacao.
    """
    X = preparar_atributos(dados, componentes, params)
    max_samples = params["max_samples"]
    if max_samples == "n":
        max_samples = len(X)
    max_samples = min(int(max_samples), len(X))

    percentis = {}
    for semente in range(n_sementes):
        modelo = IsolationForest(
            n_estimators=params["n_estimators"],
            max_samples=max_samples,
            contamination=params.get("contamination", "auto"),
            bootstrap=params.get("bootstrap", False),
            n_jobs=params.get("n_jobs", -1),
            random_state=semente,
        )
        modelo.fit(X.values)
        # Sinal invertido: quanto maior, mais atipica e a observacao.
        escore = -modelo.score_samples(X.values)
        percentis[semente] = pd.Series(escore, index=X.index).rank(pct=True)

    percentis = pd.DataFrame(percentis)
    consenso = percentis.mean(axis=1).rename("percentil_consensual")
    return consenso, percentis, X


def indices_do_corte(consenso: pd.Series, corte: float) -> pd.Index:
    """Seleciona as observacoes do grupo operacional de maior prioridade."""
    quantidade = int(np.ceil(len(consenso) * corte))
    return consenso.nlargest(quantidade).index


def jaccard(a: pd.Index, b: pd.Index) -> float:
    """Sobreposicao entre dois grupos de prioridade."""
    a, b = set(a), set(b)
    uniao = a | b
    return len(a & b) / len(uniao) if uniao else np.nan


def explicar(X: pd.DataFrame, indice, quantos: int) -> list[str]:
    """Componentes de maior desvio absoluto padronizado de uma observacao.

    A decomposicao indica quais relacoes contabeis afastam a observacao do
    centro da amostra, sem atribuir causalidade.
    """
    linha = X.loc[indice]
    return list(linha.abs().sort_values(ascending=False).head(quantos).index)


# --------------------------------------------------------------------------
def main() -> None:
    cfg = load_config()
    componentes = cfg["indicadores"]["componentes"]
    mcfg = cfg["modelo"]

    params = dict(mcfg["isolation_forest"])
    params.update({
        "winsorizacao_aplicar": mcfg["winsorizacao"]["aplicar"],
        "limite_inferior": mcfg["winsorizacao"]["limite_inferior"],
        "limite_superior": mcfg["winsorizacao"]["limite_superior"],
        "padronizacao_por_exercicio": mcfg["padronizacao_por_exercicio"],
    })

    dados = pd.read_csv(DIR_PROCESSED / "indicadores.csv")
    LOG.info("amostra analitica: %d observacoes, %d companhias",
             len(dados), dados["CD_CVM"].nunique())

    consenso, percentis, X = executar_ranking(
        dados, componentes, params, mcfg["sementes"])
    LOG.info("modelo principal executado com %d sementes", mcfg["sementes"])

    dados["percentil_consensual"] = consenso
    dados["posicao"] = consenso.rank(ascending=False, method="first").astype(int)

    desvios = X.copy()
    desvios.columns = [f"z_{c}" for c in componentes]
    pd.concat([dados[["CD_CVM", "COMPANHIA_ANO", "ANO_REFER"]], desvios], axis=1) \
        .to_csv(DIR_PROCESSED / "desvios_padronizados.csv",
                index=False, encoding="utf-8")

    # Grupos operacionais, construidos depois do ranking.
    for corte in mcfg["cortes_operacionais"]:
        rotulo = f"top_{int(corte * 100)}"
        dados[rotulo] = False
        dados.loc[indices_do_corte(consenso, corte), rotulo] = True

    # Explicacao de cada prioridade: tres maiores desvios absolutos.
    quantos = mcfg["componentes_explicativos"]
    dados["componentes_predominantes"] = [
        "; ".join(explicar(X, i, quantos)) for i in dados.index
    ]

    dados.sort_values("posicao").to_csv(
        DIR_PROCESSED / "ranking_consensual.csv", index=False, encoding="utf-8")

    # ---------------- Tabela 2 - distribuicao temporal ---------------------
    temporal = (dados.groupby("ANO_REFER")
                .agg(Observacoes=("CD_CVM", "size"),
                     Companhias=("CD_CVM", "nunique"),
                     **{f"Top {int(c*100)}%": (f"top_{int(c*100)}", "sum")
                        for c in mcfg["cortes_operacionais"]})
                .reset_index().rename(columns={"ANO_REFER": "Exercicio"}))
    total = {"Exercicio": "Total", "Observacoes": len(dados),
             "Companhias": dados["CD_CVM"].nunique()}
    for c in mcfg["cortes_operacionais"]:
        total[f"Top {int(c*100)}%"] = int(dados[f"top_{int(c*100)}"].sum())
    temporal = pd.concat([temporal, pd.DataFrame([total])], ignore_index=True)
    salvar_tabela(temporal, "tabela2_distribuicao_temporal")
    LOG.info("\n%s", temporal.to_string(index=False))

    # ---------------- Tabela 4 - grupo prioritario -------------------------
    corte_ref = mcfg["corte_referencia"]
    prioritarias = dados.nlargest(int(np.ceil(len(dados) * corte_ref)),
                                  "percentil_consensual").copy()
    tabela4 = pd.DataFrame({
        "Posicao": range(1, len(prioritarias) + 1),
        "Companhia-ano": prioritarias["COMPANHIA_ANO"].values,
        "Percentil": prioritarias["percentil_consensual"].round(3).values,
        "Componentes": prioritarias["componentes_predominantes"].values,
    })
    salvar_tabela(tabela4, "tabela4_ranking_consensual")
    LOG.info("\n%s", tabela4.to_string(index=False))

    # ---------------- Tabela 5 - frequencia dos componentes ----------------
    ocorrencias = prioritarias["componentes_predominantes"].str.split("; ").explode()
    frequencia = ocorrencias.value_counts().rename_axis("Componente").reset_index(
        name="Frequencia")
    frequencia["% das ocorrencias"] = (
        100 * frequencia["Frequencia"] / len(ocorrencias)).round(1)
    frequencia["% das prioridades"] = (
        100 * frequencia["Frequencia"] / len(prioritarias)).round(1)
    frequencia = pd.concat([frequencia, pd.DataFrame([{
        "Componente": "Total", "Frequencia": len(ocorrencias),
        "% das ocorrencias": 100.0, "% das prioridades": np.nan}])],
        ignore_index=True)
    salvar_tabela(frequencia, "tabela5_frequencia_componentes")
    LOG.info("\n%s", frequencia.to_string(index=False))

    # ---------------- Estabilidade aleatoria -------------------------------
    grupo_consenso = indices_do_corte(consenso, corte_ref)
    correlacoes, sobreposicoes = [], []
    for semente in percentis.columns:
        correlacoes.append(spearmanr(percentis[semente], consenso).statistic)
        sobreposicoes.append(
            jaccard(indices_do_corte(percentis[semente], corte_ref), grupo_consenso))

    estabilidade = pd.DataFrame({"semente": percentis.columns,
                                 "spearman_com_consenso": correlacoes,
                                 "jaccard_top5": sobreposicoes})
    salvar_tabela(estabilidade, "estabilidade_aleatoria")

    # Frequencia de selecao de cada observacao entre as execucoes.
    selecao = pd.Series(0, index=dados.index)
    for semente in percentis.columns:
        selecao.loc[indices_do_corte(percentis[semente], corte_ref)] += 1
    taxa = (selecao / len(percentis.columns)).sort_values(ascending=False)

    resumo = {
        "observacoes": int(len(dados)),
        "companhias": int(dados["CD_CVM"].nunique()),
        "sementes": int(mcfg["sementes"]),
        "spearman_mediano": float(np.median(correlacoes)),
        "spearman_minimo": float(np.min(correlacoes)),
        "jaccard_mediano": float(np.median(sobreposicoes)),
        "jaccard_minimo": float(np.min(sobreposicoes)),
        "percentil_minimo_no_grupo": float(consenso.loc[grupo_consenso].min()),
        "percentil_maximo_no_grupo": float(consenso.loc[grupo_consenso].max()),
        "observacoes_selecionadas_em_todas": int((taxa == 1).sum()),
        "taxa_selecao_nona_posicao": float(taxa.iloc[8]) if len(taxa) > 8 else None,
        "taxa_selecao_decima_posicao": float(taxa.iloc[9]) if len(taxa) > 9 else None,
    }
    salvar_json(resumo, "estabilidade_resumo")
    LOG.info("Spearman mediano %.3f (minimo %.3f) | Jaccard mediano %.3f (minimo %.3f)",
             resumo["spearman_mediano"], resumo["spearman_minimo"],
             resumo["jaccard_mediano"], resumo["jaccard_minimo"])
    LOG.info("etapa 4 concluida.")


if __name__ == "__main__":
    main()
