"""Etapa 7 - Geracao das seis figuras apresentadas no trabalho.

    Figura 1 - Formacao da amostra analitica
    Figura 2 - Distribuicao do escore por exercicio
    Figura 3 - Dez observacoes com maior prioridade analitica
    Figura 4 - Desvios robustos dos componentes nas maiores prioridades
    Figura 5 - Sensibilidade do ranking a escolhas de pre-processamento
    Figura 6 - Concordancia entre o modelo e a referencia contabil

Uso:
    python src/s07_figures.py
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from utils import DIR_FIGURES, DIR_PROCESSED, DIR_TABLES, get_logger, load_config

LOG = get_logger("s07_figures")

AZUL = "#1f4e79"
AZUL_CLARO = "#dbe9f5"
LARANJA = "#d4691e"
CINZA = "#8c8c8c"


def configurar_estilo(cfg: dict) -> None:
    plt.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": cfg["saidas"]["figuras_dpi"],
        "savefig.bbox": "tight",
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
    })


def salvar(fig, nome: str, cfg: dict) -> None:
    DIR_FIGURES.mkdir(parents=True, exist_ok=True)
    for extensao in cfg["saidas"]["figuras_formato"]:
        fig.savefig(DIR_FIGURES / f"{nome}.{extensao}")
    plt.close(fig)
    LOG.info("figura gravada: %s", nome)


def figura1(cfg: dict) -> None:
    dados = pd.read_csv(DIR_TABLES / "etapa3_formacao_amostra.csv")
    cores = [CINZA, AZUL, AZUL, LARANJA]

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    barras = ax.bar(dados["etapa"], dados["observacoes"],
                    color=cores[:len(dados)], width=0.62)
    ax.bar_label(barras, padding=3, fontsize=8)
    ax.set_ylabel("Observacoes companhia-ano")
    ax.set_title("Formacao da amostra analitica")
    ax.set_ylim(0, dados["observacoes"].max() * 1.15)
    plt.setp(ax.get_xticklabels(), rotation=12, ha="right")
    salvar(fig, "figura1_formacao_amostra", cfg)


def figura2(cfg: dict) -> None:
    ranking = pd.read_csv(DIR_PROCESSED / "ranking_consensual.csv")
    anos = sorted(ranking["ANO_REFER"].unique())
    series = [ranking.loc[ranking["ANO_REFER"] == a, "percentil_consensual"]
              for a in anos]

    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    # O parametro mudou de nome no matplotlib 3.9; aceita-se as duas versoes.
    try:
        caixa = ax.boxplot(series, tick_labels=anos, patch_artist=True, widths=0.55)
    except TypeError:
        caixa = ax.boxplot(series, labels=anos, patch_artist=True, widths=0.55)
    for corpo in caixa["boxes"]:
        corpo.set(facecolor=AZUL_CLARO, edgecolor=AZUL, linewidth=1.1)
    for elemento in ("whiskers", "caps"):
        for artista in caixa[elemento]:
            artista.set(color=AZUL, linewidth=1.1)
    for mediana in caixa["medians"]:
        mediana.set(color=LARANJA, linewidth=1.6)

    ax.set_xlabel("Exercicio")
    ax.set_ylabel("Percentil consensual de atipicidade")
    ax.set_title("Distribuicao do escore do Isolation Forest por exercicio")
    salvar(fig, "figura2_distribuicao_por_exercicio", cfg)


def figura3(cfg: dict) -> None:
    tabela = pd.read_csv(DIR_TABLES / "tabela4_ranking_consensual.csv")
    tabela = tabela.iloc[::-1]     # maior prioridade no topo do grafico

    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    ax.barh(tabela["Companhia-ano"], tabela["Percentil"], color=AZUL, height=0.62)
    for y, valor in enumerate(tabela["Percentil"]):
        ax.text(valor + 0.001, y, f"{valor:.3f}", va="center", fontsize=7.5)

    minimo = tabela["Percentil"].min()
    ax.set_xlim(max(0, minimo - 0.05), 1.01)
    ax.set_xlabel("Percentil consensual de atipicidade")
    ax.set_title("Dez observacoes com maior prioridade analitica")
    ax.tick_params(axis="y", labelsize=7.5)
    salvar(fig, "figura3_maiores_prioridades", cfg)


def figura4(cfg: dict) -> None:
    componentes = cfg["indicadores"]["componentes"]
    ranking = pd.read_csv(DIR_PROCESSED / "ranking_consensual.csv")
    desvios = pd.read_csv(DIR_PROCESSED / "desvios_padronizados.csv")

    corte = cfg["modelo"]["corte_referencia"]
    prioritarias = ranking.nlargest(int(np.ceil(len(ranking) * corte)),
                                    "percentil_consensual")
    chave = ["CD_CVM", "ANO_REFER"]
    matriz = (prioritarias[chave].merge(desvios, on=chave, how="left")
              [[f"z_{c}" for c in componentes]].values)
    # Limite meramente grafico: nao altera o ranking, ja calculado.
    matriz = np.clip(matriz, -3, 3)

    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    imagem = ax.imshow(matriz, cmap="RdBu_r", vmin=-3, vmax=3, aspect="auto")
    ax.set_xticks(range(len(componentes)), componentes)
    ax.set_yticks(range(len(matriz)), [f"{i+1}o" for i in range(len(matriz))])
    ax.set_xlabel("Componente contabil")
    ax.set_ylabel("Posicao no ranking")
    ax.set_title("Desvios robustos dos componentes nas maiores prioridades")
    barra = fig.colorbar(imagem, ax=ax, shrink=0.85)
    barra.set_label("Desvio padronizado (limitado a +/-3 na escala visual)", fontsize=8)
    salvar(fig, "figura4_desvios_componentes", cfg)


def figura5(cfg: dict) -> None:
    tabela = pd.read_csv(DIR_TABLES / "tabela6_sensibilidade.csv").iloc[::-1]
    coluna_jaccard = [c for c in tabela.columns if c.startswith("Jaccard")][0]

    fig, eixos = plt.subplots(1, 2, figsize=(7.8, 3.6), sharey=True)
    eixos[0].barh(tabela["Cenario"], tabela["Spearman com o principal"],
                  color=AZUL, height=0.6)
    eixos[0].set_xlabel("Correlacao de Spearman")
    eixos[0].set_xlim(0, 1.05)

    eixos[1].barh(tabela["Cenario"], tabela[coluna_jaccard], color=LARANJA, height=0.6)
    eixos[1].set_xlabel("Sobreposicao Jaccard no top 5%")
    eixos[1].set_xlim(0, 1.05)

    eixos[0].tick_params(axis="y", labelsize=8)
    fig.suptitle("Sensibilidade do ranking a escolhas de pre-processamento e ajuste",
                 fontsize=10)
    salvar(fig, "figura5_sensibilidade", cfg)


def figura6(cfg: dict) -> None:
    ranking = pd.read_csv(DIR_PROCESSED / "ranking_com_triangulacao.csv")
    if "percentil_mscore" not in ranking.columns:
        ranking["percentil_mscore"] = ranking["MSCORE"].rank(pct=True)

    corte = cfg["modelo"]["corte_referencia"]
    prioritarias = ranking.nlargest(int(np.ceil(len(ranking) * corte)),
                                    "percentil_consensual")

    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.scatter(ranking["percentil_mscore"], ranking["percentil_consensual"],
               s=26, color=CINZA, alpha=0.55, edgecolor="none")
    ax.scatter(prioritarias["percentil_mscore"], prioritarias["percentil_consensual"],
               s=34, color=LARANJA, edgecolor="none")
    for posicao, (x, y) in enumerate(zip(prioritarias["percentil_mscore"],
                                         prioritarias["percentil_consensual"]),
                                     start=1):
        ax.annotate(f"{posicao}o", (x, y), fontsize=6.5,
                    xytext=(3, 3), textcoords="offset points")

    ax.set_xlabel("Percentil do Beneish M-Score (sem corte importado)")
    ax.set_ylabel("Percentil consensual do Isolation Forest")
    ax.set_title("Concordancia entre o modelo nao supervisionado e a referencia contabil")
    salvar(fig, "figura6_concordancia_mscore", cfg)


def main() -> None:
    cfg = load_config()
    configurar_estilo(cfg)
    for funcao in (figura1, figura2, figura3, figura4, figura5, figura6):
        try:
            funcao(cfg)
        except FileNotFoundError as erro:
            LOG.warning("%s ignorada, arquivo de entrada ausente: %s",
                        funcao.__name__, erro)
        except Exception as erro:
            LOG.error("%s falhou: %s", funcao.__name__, erro, exc_info=True)
    LOG.info("etapa 7 concluida.")


if __name__ == "__main__":
    main()
