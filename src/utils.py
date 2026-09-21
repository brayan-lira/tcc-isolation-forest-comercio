"""Funcoes de apoio compartilhadas pelos scripts do estudo."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"

DIR_RAW = ROOT / "data" / "raw"
DIR_INTERIM = ROOT / "data" / "interim"
DIR_PROCESSED = ROOT / "data" / "processed"
DIR_FIGURES = ROOT / "outputs" / "figures"
DIR_TABLES = ROOT / "outputs" / "tables"
DIR_LOGS = ROOT / "outputs" / "logs"


def load_config(path: Path | str = CONFIG_PATH) -> dict:
    """Le o arquivo unico de configuracao do estudo."""
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def get_logger(nome: str) -> logging.Logger:
    """Logger que escreve simultaneamente no console e em outputs/logs."""
    DIR_LOGS.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(nome)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    arquivo = logging.FileHandler(DIR_LOGS / f"{nome}.log", mode="w", encoding="utf-8")
    arquivo.setFormatter(fmt)
    logger.addHandler(arquivo)
    return logger


def normalizar_texto(valor) -> str:
    """Remove acentos, espacos duplos e caixa, para comparacao de rotulos.

    A classificacao setorial do cadastro da CVM aparece com grafias
    ligeiramente distintas entre versoes do arquivo; a comparacao
    normalizada evita perda silenciosa de companhias elegiveis.
    """
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.upper().split())


def sha256_arquivo(caminho: Path, bloco: int = 1 << 20) -> str:
    """Codigo hash SHA-256 do arquivo, usado no registro de proveniencia."""
    digest = hashlib.sha256()
    with open(caminho, "rb") as handle:
        for pedaco in iter(lambda: handle.read(bloco), b""):
            digest.update(pedaco)
    return digest.hexdigest()


def registrar_proveniencia(arquivos: list[Path], destino: Path) -> pd.DataFrame:
    """Grava nome, tamanho e hash SHA-256 dos arquivos brutos baixados.

    Esse registro identifica a versao exata dos dados diante de eventuais
    reapresentacoes de demonstracoes pelas companhias.
    """
    linhas = []
    for caminho in sorted(arquivos):
        if not caminho.exists():
            continue
        linhas.append({
            "arquivo": caminho.name,
            "tamanho_bytes": caminho.stat().st_size,
            "sha256": sha256_arquivo(caminho),
        })
    quadro = pd.DataFrame(linhas)
    destino.parent.mkdir(parents=True, exist_ok=True)
    quadro.to_csv(destino, index=False, encoding="utf-8")
    return quadro


def salvar_tabela(quadro: pd.DataFrame, nome: str, indice: bool = False) -> Path:
    """Salva uma tabela de resultado em outputs/tables."""
    DIR_TABLES.mkdir(parents=True, exist_ok=True)
    destino = DIR_TABLES / f"{nome}.csv"
    quadro.to_csv(destino, index=indice, encoding="utf-8")
    return destino


def salvar_json(objeto: dict, nome: str) -> Path:
    DIR_TABLES.mkdir(parents=True, exist_ok=True)
    destino = DIR_TABLES / f"{nome}.json"
    with open(destino, "w", encoding="utf-8") as handle:
        json.dump(objeto, handle, ensure_ascii=False, indent=2, default=str)
    return destino


def razao_segura(numerador: pd.Series, denominador: pd.Series) -> pd.Series:
    """Divisao que devolve ausente quando o denominador e zero ou nulo.

    A metodologia nao admite substituicao arbitraria de denominador zero.
    """
    denominador = denominador.where(denominador != 0)
    return numerador / denominador


def exigir_colunas(quadro: pd.DataFrame, colunas: list[str], contexto: str) -> None:
    """Falha cedo e com mensagem clara se o leiaute da CVM mudar."""
    faltantes = [c for c in colunas if c not in quadro.columns]
    if faltantes:
        raise KeyError(
            f"[{contexto}] colunas ausentes no arquivo da CVM: {faltantes}. "
            f"Execute 'python src/s00_inspect_layout.py' para ver o leiaute real. "
            f"Colunas encontradas: {list(quadro.columns)}"
        )
