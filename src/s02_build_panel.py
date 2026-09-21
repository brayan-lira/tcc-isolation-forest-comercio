"""Etapa 2 - Formacao do painel companhia-ano a partir dos arquivos da CVM.

Aplica, na ordem, os criterios de elegibilidade declarados em config.yaml:
setor Comercio (Atacado e Varejo), demonstracoes consolidadas, moeda Real,
escala em milhares, plano de contas fixo, ordem do exercicio igual ao ultimo
e maior versao disponivel para a mesma companhia e data de referencia. Contas
de resultado (DRE), de valor adicionado (DVA) e de fluxo de caixa (DFC) sao
mantidas apenas quando o periodo informado compreende de 330 a 380 dias.

Linhas repetidas com o mesmo valor sao consolidadas; grupos de uma mesma conta
com valores conflitantes sao excluidos e registrados.

Saidas:
    data/interim/painel_contas_longo.parquet
    data/processed/painel_companhia_ano.csv
    outputs/tables/etapa2_formacao_painel.csv
    outputs/tables/conflitos_de_conta.csv
    outputs/tables/relatorio_auditor.csv
    outputs/tables/tipos_de_relatorio.csv

Uso:
    python src/s02_build_panel.py
"""

from __future__ import annotations

import zipfile

import pandas as pd

from cvm_layout import (carregar_pareceres, diagnosticar_tipos,
                        identificar_grupo, ler_csv)
from utils import (DIR_INTERIM, DIR_PROCESSED, DIR_RAW, exigir_colunas,
                   get_logger, load_config, normalizar_texto, salvar_tabela)

LOG = get_logger("s02_build_panel")

GRUPOS_FLUXO = {"DRE", "DVA", "DFC_MI", "DFC_MD"}

COLUNAS_BASE = ["CNPJ_CIA", "CD_CVM", "DENOM_CIA", "DT_REFER", "VERSAO",
                "ORDEM_EXERC", "CD_CONTA", "DS_CONTA", "ESCALA_MOEDA",
                "MOEDA", "VL_CONTA"]


def carregar_ano(ano: int, cfg: dict) -> tuple[pd.DataFrame, int]:
    """Carrega e empilha as demonstracoes consolidadas de um exercicio."""
    caminho = DIR_RAW / f"dfp_cia_aberta_{ano}.zip"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} nao encontrado. Execute antes: python src/s01_download_cvm.py"
        )

    tipo = cfg["filtros"]["tipo_demonstracao"]
    partes, cortadas_janela = [], 0

    with zipfile.ZipFile(caminho) as pacote:
        for nome in pacote.namelist():
            if not nome.lower().endswith(".csv"):
                continue
            grupo = identificar_grupo(nome, tipo)
            if grupo is None:
                continue

            quadro = ler_csv(pacote, nome, cfg)
            exigir_colunas(quadro, COLUNAS_BASE, nome)
            quadro["GRUPO"] = grupo
            quadro["ANO"] = ano

            # Janela de 330 a 380 dias: aplica-se apenas a contas de fluxo,
            # que possuem periodo de apuracao declarado.
            if grupo in GRUPOS_FLUXO and {"DT_INI_EXERC", "DT_FIM_EXERC"} <= set(quadro.columns):
                inicio = pd.to_datetime(quadro["DT_INI_EXERC"], errors="coerce")
                fim = pd.to_datetime(quadro["DT_FIM_EXERC"], errors="coerce")
                dias = (fim - inicio).dt.days
                dentro = dias.between(cfg["filtros"]["janela_dias_min"],
                                      cfg["filtros"]["janela_dias_max"])
                cortadas_janela += int((~dentro).sum())
                quadro = quadro[dentro].copy()

            partes.append(quadro)

    if not partes:
        raise RuntimeError(
            f"nenhuma demonstracao '{tipo}' encontrada em {caminho.name}. "
            f"Execute 'python src/s00_inspect_layout.py' para inspecionar o pacote."
        )

    empilhado = pd.concat(partes, ignore_index=True)
    LOG.info("%d: %d linhas carregadas | %d linhas fora da janela de %d-%d dias",
             ano, len(empilhado), cortadas_janela,
             cfg["filtros"]["janela_dias_min"], cfg["filtros"]["janela_dias_max"])
    return empilhado, cortadas_janela


def filtrar_elegiveis(dados: pd.DataFrame, cadastro: pd.DataFrame,
                      cfg: dict) -> pd.DataFrame:
    """Aplica os filtros de setor, moeda, escala, conta fixa, ordem e versao."""
    filtros = cfg["filtros"]

    dados["DT_REFER"] = pd.to_datetime(dados["DT_REFER"], errors="coerce")
    dados["VL_CONTA"] = pd.to_numeric(
        dados["VL_CONTA"].str.replace(",", ".", regex=False), errors="coerce")
    dados["VERSAO"] = pd.to_numeric(dados["VERSAO"], errors="coerce")
    dados["CD_CVM"] = dados["CD_CVM"].str.strip()

    # Setor, a partir do cadastro de companhias abertas.
    alvo = normalizar_texto(filtros["setor_cvm"])
    cadastro = cadastro.copy()
    cadastro["SETOR_NORM"] = cadastro["SETOR_ATIV"].map(normalizar_texto)
    cadastro["CD_CVM"] = cadastro["CD_CVM"].astype(str).str.strip()
    do_setor = set(cadastro.loc[cadastro["SETOR_NORM"] == alvo, "CD_CVM"])
    if not do_setor:
        LOG.error("nenhuma companhia com setor '%s'. Execute "
                  "'python src/s00_inspect_layout.py' para ver a grafia exata "
                  "no cadastro e corrija filtros.setor_cvm no config.yaml.",
                  filtros["setor_cvm"])
    else:
        LOG.info("companhias do setor no cadastro: %d", len(do_setor))
    dados = dados[dados["CD_CVM"].isin(do_setor)]
    LOG.info("apos filtro de setor: %d linhas", len(dados))

    dados = dados[dados["MOEDA"].map(normalizar_texto) == normalizar_texto(filtros["moeda"])]
    dados = dados[dados["ESCALA_MOEDA"].map(normalizar_texto)
                  == normalizar_texto(filtros["escala_moeda"])]
    LOG.info("apos moeda e escala: %d linhas", len(dados))

    if filtros["plano_contas_fixo"] and "ST_CONTA_FIXA" in dados.columns:
        dados = dados[dados["ST_CONTA_FIXA"].str.strip().str.upper() == "S"]
        LOG.info("apos plano de contas fixo: %d linhas", len(dados))

    dados = dados[dados["ORDEM_EXERC"].map(normalizar_texto)
                  == normalizar_texto(filtros["ordem_exercicio"])]
    LOG.info("apos ordem do exercicio: %d linhas", len(dados))

    if filtros["manter_maior_versao"]:
        maior = dados.groupby(["CD_CVM", "DT_REFER"])["VERSAO"].transform("max")
        dados = dados[dados["VERSAO"] == maior]
        LOG.info("apos manter a maior versao: %d linhas", len(dados))

    return dados.dropna(subset=["VL_CONTA", "DT_REFER"])


def consolidar_contas(dados: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Consolida repeticoes identicas e separa grupos com valores conflitantes."""
    chave = ["CD_CVM", "DT_REFER", "GRUPO", "CD_CONTA"]
    distintos = dados.groupby(chave)["VL_CONTA"].nunique()

    conflitantes = distintos[distintos > 1].reset_index()[chave]
    if len(conflitantes):
        LOG.warning("grupos de conta com valores conflitantes: %d", len(conflitantes))
        dados = dados.merge(conflitantes.assign(_conflito=1), on=chave, how="left")
        dados = dados[dados["_conflito"].isna()].drop(columns="_conflito")

    antes = len(dados)
    consolidado = dados.drop_duplicates(subset=chave + ["VL_CONTA"])
    LOG.info("repeticoes de conta com o mesmo valor consolidadas: %d",
             antes - len(consolidado))
    return consolidado, conflitantes


def montar_painel(dados: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Transpoe as contas de interesse para o formato companhia-ano."""
    contas = cfg["contas"]
    dados["CD_CONTA"] = dados["CD_CONTA"].str.strip()
    dados["ANO_REFER"] = dados["DT_REFER"].dt.year

    colunas = []
    for apelido, spec in contas.items():
        # DFC aceita tanto o metodo indireto quanto o direto.
        grupos = ["DFC_MI", "DFC_MD"] if spec["grupo"] == "DFC" else [spec["grupo"]]
        recorte = dados[(dados["CD_CONTA"] == spec["codigo"])
                        & (dados["GRUPO"].isin(grupos))]
        serie = (recorte.groupby(["CD_CVM", "DENOM_CIA", "DT_REFER", "ANO_REFER"])
                 ["VL_CONTA"].first().rename(apelido))
        colunas.append(serie)
        LOG.info("conta %-20s (%-8s): %d observacoes",
                 apelido, spec["codigo"], serie.notna().sum())

    painel = pd.concat(colunas, axis=1).reset_index()
    painel = painel.sort_values(["CD_CVM", "DT_REFER"]).reset_index(drop=True)
    LOG.info("painel bruto: %d observacoes companhia-ano, %d companhias",
             len(painel), painel["CD_CVM"].nunique())
    return painel


def main() -> None:
    cfg = load_config()

    caminho_cadastro = DIR_RAW / "cad_cia_aberta.csv"
    if not caminho_cadastro.exists():
        raise FileNotFoundError(
            "cadastro ausente. Execute: python src/s01_download_cvm.py")
    cadastro = pd.read_csv(caminho_cadastro, sep=cfg["fonte"]["separador"],
                           encoding=cfg["fonte"]["encoding"], dtype=str)
    cadastro.columns = [c.strip().upper() for c in cadastro.columns]
    exigir_colunas(cadastro, ["CD_CVM", "SETOR_ATIV"], "cadastro")

    partes, total_janela = [], 0
    for ano in cfg["fonte"]["anos"]:
        quadro, cortadas = carregar_ano(ano, cfg)
        partes.append(quadro)
        total_janela += cortadas

    dados = pd.concat(partes, ignore_index=True)
    LOG.info("linhas contabeis retiradas pela janela de periodo: %d", total_janela)

    dados = filtrar_elegiveis(dados, cadastro, cfg)
    dados, conflitos = consolidar_contas(dados)

    DIR_INTERIM.mkdir(parents=True, exist_ok=True)
    try:
        dados.to_parquet(DIR_INTERIM / "painel_contas_longo.parquet", index=False)
    except Exception:  # pyarrow ausente
        dados.to_csv(DIR_INTERIM / "painel_contas_longo.csv", index=False)

    painel = montar_painel(dados, cfg)
    DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    painel.to_csv(DIR_PROCESSED / "painel_companhia_ano.csv",
                  index=False, encoding="utf-8")

    # Pareceres, com deteccao automatica de leiaute.
    caminhos = {ano: DIR_RAW / f"dfp_cia_aberta_{ano}.zip"
                for ano in cfg["fonte"]["anos_escore"]}
    pareceres = carregar_pareceres(caminhos, cfg)
    if len(pareceres):
        salvar_tabela(pareceres, "relatorio_auditor")
        tipos = diagnosticar_tipos(pareceres, cfg)
        if len(tipos):
            salvar_tabela(tipos, "tipos_de_relatorio")

    salvar_tabela(conflitos if len(conflitos) else pd.DataFrame(
        columns=["CD_CVM", "DT_REFER", "GRUPO", "CD_CONTA"]), "conflitos_de_conta")

    formacao = pd.DataFrame([
        {"etapa": "Linhas fora da janela de 330-380 dias", "valor": total_janela},
        {"etapa": "Grupos de conta com valores conflitantes", "valor": len(conflitos)},
        {"etapa": "Painel bruto (observacoes companhia-ano)", "valor": len(painel)},
        {"etapa": "Companhias distintas no painel bruto",
         "valor": painel["CD_CVM"].nunique()},
    ])
    salvar_tabela(formacao, "etapa2_formacao_painel")
    LOG.info("etapa 2 concluida.")


if __name__ == "__main__":
    main()
