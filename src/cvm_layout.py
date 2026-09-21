"""Deteccao automatica do leiaute dos arquivos da CVM.

Este modulo substitui suposicoes sobre nomes de arquivos e de colunas por
deteccao feita sobre o conteudo real dos pacotes baixados. Com ele, mudancas
de leiaute entre versoes da base deixam de interromper o protocolo em
silencio: o aviso, quando ocorre, e explicito e indica o que fazer.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from utils import get_logger, normalizar_texto

LOG = get_logger("cvm_layout")

# ---------------------------------------------------------------------------
# Secao de Pareceres e Declaracoes
# ---------------------------------------------------------------------------
TERMOS_ARQUIVO_PARECER = ["parecer", "declaracao", "declaração", "auditor"]

# Nomes ja observados para a coluna de tipo de relatorio, em ordem de
# preferencia. Se nenhum coincidir, o modulo procura qualquer coluna que
# contenha RELAT ou PARECER.
CANDIDATOS_COLUNA_TIPO = [
    "TP_RELAT_AUDITORIA",
    "TP_RELATORIO",
    "TP_RELAT",
    "TIPO_RELATORIO",
    "TP_PARECER",
    "DS_RELAT",
]

COLUNAS_CHAVE = ["CD_CVM", "DT_REFER"]

# Marcadores usados para identificar cada demonstracao pelo nome do arquivo.
# DFC_MI e DFC_MD precisam ser testados antes de DRE/DVA.
MARCADORES_GRUPO = [
    ("DFC_MI", "dfc_mi"),
    ("DFC_MD", "dfc_md"),
    ("BPA", "bpa"),
    ("BPP", "bpp"),
    ("DRE", "dre"),
    ("DVA", "dva"),
]


def ler_csv(pacote: zipfile.ZipFile, nome: str, cfg: dict,
            nrows: int | None = None) -> pd.DataFrame:
    """Le um CSV de dentro do pacote anual, preservando tudo como texto."""
    bruto = pacote.read(nome)
    quadro = pd.read_csv(io.BytesIO(bruto),
                         sep=cfg["fonte"]["separador"],
                         encoding=cfg["fonte"]["encoding"],
                         dtype=str, low_memory=False, nrows=nrows)
    quadro.columns = [c.strip().upper() for c in quadro.columns]
    return quadro


def identificar_grupo(nome_arquivo: str, tipo: str) -> str | None:
    """Mapeia o nome do arquivo para o grupo de demonstracao correspondente."""
    nome = nome_arquivo.lower()
    if f"_{tipo}." not in nome and f"_{tipo}_" not in nome:
        return None
    for grupo, marcador in MARCADORES_GRUPO:
        if marcador in nome:
            return grupo
    return None


def localizar_arquivo_parecer(pacote: zipfile.ZipFile) -> str | None:
    """Encontra o CSV da secao de pareceres dentro do pacote anual."""
    candidatos = [n for n in pacote.namelist()
                  if n.lower().endswith(".csv")
                  and any(t in n.lower() for t in TERMOS_ARQUIVO_PARECER)]
    if not candidatos:
        return None
    # Prefere o arquivo cujo nome contem "parecer" de forma explicita.
    explicitos = [n for n in candidatos if "parecer" in n.lower()]
    return sorted(explicitos or candidatos)[0]


def localizar_coluna_tipo(colunas: list[str]) -> str | None:
    """Identifica a coluna que descreve o tipo de relatorio do auditor."""
    for candidato in CANDIDATOS_COLUNA_TIPO:
        if candidato in colunas:
            return candidato
    # Busca por aproximacao, cobrindo nomes ainda nao catalogados.
    aproximados = [c for c in colunas if "RELAT" in c or "PARECER" in c]
    aproximados = [c for c in aproximados
                   if not any(x in c for x in ("DT_", "VERSAO", "CNPJ", "CD_"))]
    return aproximados[0] if aproximados else None


def carregar_pareceres(caminhos_zip: dict[int, Path], cfg: dict) -> pd.DataFrame:
    """Le a secao de pareceres de todos os exercicios, detectando o leiaute.

    Devolve um quadro com CD_CVM, DT_REFER, ANO e TIPO_RELATORIO. Quando a
    secao nao existe ou a coluna nao e identificavel, devolve quadro vazio e
    registra orientacao explicita no log, sem interromper o protocolo.
    """
    partes = []
    for ano, caminho in sorted(caminhos_zip.items()):
        if not Path(caminho).exists():
            continue

        with zipfile.ZipFile(caminho) as pacote:
            nome = localizar_arquivo_parecer(pacote)
            if nome is None:
                LOG.warning("%d: secao de pareceres nao localizada no pacote.", ano)
                continue

            quadro = ler_csv(pacote, nome, cfg)
            coluna_tipo = localizar_coluna_tipo(list(quadro.columns))
            if coluna_tipo is None:
                LOG.error("%d: coluna de tipo de relatorio nao identificada em %s. "
                          "Colunas disponiveis: %s. Execute "
                          "'python src/s00_inspect_layout.py' e acrescente o nome "
                          "correto a CANDIDATOS_COLUNA_TIPO neste modulo.",
                          ano, nome, list(quadro.columns))
                continue

            faltantes = [c for c in COLUNAS_CHAVE if c not in quadro.columns]
            if faltantes:
                LOG.error("%d: colunas de identificacao ausentes em %s: %s",
                          ano, nome, faltantes)
                continue

            LOG.info("%d: pareceres lidos de %s (coluna de tipo: %s, %d registros)",
                     ano, nome, coluna_tipo, len(quadro))

            recorte = quadro[COLUNAS_CHAVE + [coluna_tipo]].copy()
            recorte = recorte.rename(columns={coluna_tipo: "TIPO_RELATORIO"})
            recorte["ANO"] = ano
            if "VERSAO" in quadro.columns:
                recorte["VERSAO"] = pd.to_numeric(quadro["VERSAO"], errors="coerce")
            partes.append(recorte)

    if not partes:
        LOG.warning("nenhum parecer carregado; a triangulacao com o relatorio do "
                    "auditor sera ignorada na etapa 6.")
        return pd.DataFrame()

    pareceres = pd.concat(partes, ignore_index=True)
    pareceres["DT_REFER"] = pd.to_datetime(pareceres["DT_REFER"], errors="coerce")
    pareceres["CD_CVM"] = pareceres["CD_CVM"].astype(str).str.strip()
    pareceres = pareceres.dropna(subset=["CD_CVM", "DT_REFER"])

    # Mantem a maior versao por companhia e data de referencia, em coerencia
    # com o criterio aplicado as demonstracoes.
    if "VERSAO" in pareceres.columns:
        maior = pareceres.groupby(["CD_CVM", "DT_REFER"])["VERSAO"].transform("max")
        pareceres = pareceres[pareceres["VERSAO"] == maior]

    pareceres = pareceres.drop_duplicates(subset=["CD_CVM", "DT_REFER"])
    LOG.info("pareceres consolidados: %d registros", len(pareceres))
    return pareceres


def diagnosticar_tipos(pareceres: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Confere se os valores observados estao cobertos pelo config.yaml.

    Valores nao cobertos sao registrados no log: eles seriam silenciosamente
    excluidos do teste exato de Fisher, alterando o denominador sem aviso.
    """
    if pareceres.empty:
        return pd.DataFrame()

    cobertos = [normalizar_texto(v) for v in
                cfg["triangulacao"]["opiniao_modificada"]
                + cfg["triangulacao"]["opiniao_sem_ressalva"]]

    contagem = pareceres["TIPO_RELATORIO"].value_counts().reset_index()
    contagem.columns = ["tipo_relatorio", "frequencia"]
    contagem["coberto_pelo_config"] = contagem["tipo_relatorio"].map(
        lambda v: any(c in normalizar_texto(v) for c in cobertos))

    nao_cobertos = contagem[~contagem["coberto_pelo_config"]]
    if len(nao_cobertos):
        LOG.warning("tipos de relatorio NAO cobertos pelo config.yaml "
                    "(serao excluidos da triangulacao):")
        for _, linha in nao_cobertos.iterrows():
            LOG.warning("    %-45s %d registros",
                        linha["tipo_relatorio"], linha["frequencia"])
    return contagem
