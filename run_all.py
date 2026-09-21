"""Executa o protocolo completo, da coleta as figuras.

Uso:
    python run_all.py                   # executa todas as etapas
    python run_all.py --pular-download  # reaproveita os arquivos em data/raw
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from utils import get_logger  # noqa: E402

LOG = get_logger("run_all")

ETAPAS = [
    ("1", "Coleta dos arquivos da CVM", "s01_download_cvm"),
    ("2", "Inspecao do leiaute da CVM", "s00_inspect_layout"),
    ("3", "Formacao do painel companhia-ano", "s02_build_panel"),
    ("4", "Construcao dos indicadores e do M-Score", "s03_indicators"),
    ("5", "Aplicacao do Isolation Forest", "s04_isolation_forest"),
    ("6", "Analise de sensibilidade", "s05_sensitivity"),
    ("7", "Triangulacoes", "s06_triangulation"),
    ("8", "Geracao das figuras", "s07_figures"),
]


def main(pular_download: bool = False) -> int:
    import importlib

    inicio_total = time.time()
    for numero, descricao, modulo in ETAPAS:
        if pular_download and modulo == "s01_download_cvm":
            LOG.info("etapa %s dispensada por opcao do usuario", numero)
            continue

        LOG.info("=" * 74)
        LOG.info("Etapa %s - %s", numero, descricao)
        LOG.info("=" * 74)
        inicio = time.time()
        try:
            importlib.import_module(modulo).main()
        except Exception as erro:
            LOG.error("etapa %s interrompida: %s", numero, erro, exc_info=True)
            return 1
        LOG.info("etapa %s concluida em %.1f s", numero, time.time() - inicio)

    LOG.info("protocolo completo executado em %.1f s", time.time() - inicio_total)
    LOG.info("tabelas em outputs/tables | figuras em outputs/figures")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pular-download", action="store_true",
                        help="reaproveita os arquivos ja presentes em data/raw")
    sys.exit(main(**vars(parser.parse_args())))
