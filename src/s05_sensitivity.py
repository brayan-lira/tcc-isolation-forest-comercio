"""Etapa 5 - Analise de sensibilidade a escolhas de pre-processamento e ajuste.

Seis cenarios alternativos sao comparados ao modelo principal: ausencia de
winsorizacao, winsorizacao a 2,5%, padronizacao robusta dentro de cada
exercicio, numero maximo de amostras igual a 64, numero maximo de amostras
igual ao total de observacoes e reducao para 200 arvores. Cada cenario reune
20 sementes; reportam-se a correlacao de Spearman com o ranking principal e a
sobreposicao de Jaccard no grupo de 5%.

Saidas:
    outputs/tables/tabela6_sensibilidade.csv
    data/processed/rankings_cenarios.csv

Uso:
    python src/s05_sensitivity.py
"""

from __future__ import annotations

import pandas as pd
from scipy.stats import spearmanr

from s04_isolation_forest import executar_ranking, indices_do_corte, jaccard
from utils import DIR_PROCESSED, get_logger, load_config, salvar_tabela

LOG = get_logger("s05_sensitivity")

# Traducao entre as chaves declaradas nos cenarios e os parametros do modelo.
MAPA_ALTERACOES = {
    "winsorizacao_aplicar": "winsorizacao_aplicar",
    "limite_inferior": "limite_inferior",
    "limite_superior": "limite_superior",
    "padronizacao_por_exercicio": "padronizacao_por_exercicio",
    "max_samples": "max_samples",
    "n_estimators": "n_estimators",
}


def parametros_principais(cfg: dict) -> dict:
    """Reconstroi os parametros do modelo principal a partir do config."""
    mcfg = cfg["modelo"]
    params = dict(mcfg["isolation_forest"])
    params.update({
        "winsorizacao_aplicar": mcfg["winsorizacao"]["aplicar"],
        "limite_inferior": mcfg["winsorizacao"]["limite_inferior"],
        "limite_superior": mcfg["winsorizacao"]["limite_superior"],
        "padronizacao_por_exercicio": mcfg["padronizacao_por_exercicio"],
    })
    return params


def main() -> None:
    cfg = load_config()
    componentes = cfg["indicadores"]["componentes"]
    corte = cfg["modelo"]["corte_referencia"]
    n_sementes = cfg["sensibilidade"]["sementes"]

    dados = pd.read_csv(DIR_PROCESSED / "indicadores.csv")
    principal = pd.read_csv(DIR_PROCESSED / "ranking_consensual.csv")

    # Realinha o ranking principal a ordem original da amostra analitica.
    principal = principal.set_index(["CD_CVM", "ANO_REFER"])
    chave = pd.MultiIndex.from_frame(dados[["CD_CVM", "ANO_REFER"]])
    referencia = principal.loc[chave, "percentil_consensual"].reset_index(drop=True)
    grupo_referencia = indices_do_corte(referencia, corte)

    linhas, rankings = [], {"principal": referencia}
    for cenario in cfg["sensibilidade"]["cenarios"]:
        params = parametros_principais(cfg)
        for chave_alt, valor in cenario["alteracoes"].items():
            params[MAPA_ALTERACOES[chave_alt]] = valor

        consenso, _, _ = executar_ranking(dados, componentes, params, n_sementes)
        correlacao = spearmanr(consenso, referencia).statistic
        sobreposicao = jaccard(indices_do_corte(consenso, corte), grupo_referencia)

        linhas.append({
            "Cenario": cenario["rotulo"],
            "Spearman com o principal": round(float(correlacao), 3),
            f"Jaccard no top {int(corte*100)}%": round(float(sobreposicao), 3),
        })
        rankings[cenario["id"]] = consenso
        LOG.info("%-32s Spearman %.3f | Jaccard %.3f",
                 cenario["rotulo"], correlacao, sobreposicao)

    tabela = pd.DataFrame(linhas)
    salvar_tabela(tabela, "tabela6_sensibilidade")

    pd.DataFrame(rankings).assign(
        COMPANHIA_ANO=dados["COMPANHIA_ANO"].values
    ).to_csv(DIR_PROCESSED / "rankings_cenarios.csv", index=False, encoding="utf-8")

    LOG.info("\n%s", tabela.to_string(index=False))
    LOG.info("etapa 5 concluida.")


if __name__ == "__main__":
    main()
