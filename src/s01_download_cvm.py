"""Etapa 1 - Obtencao dos arquivos brutos no portal de dados abertos da CVM.

Baixa, para cada exercicio configurado, o pacote anual das Demonstracoes
Financeiras Padronizadas (DFP) e o cadastro de companhias abertas. Os
arquivos brutos NAO sao versionados no repositorio em razao do volume; este
script permite obte-los diretamente da fonte oficial.

Ao final, grava data/raw/proveniencia.csv com tamanho e codigo hash SHA-256
de cada arquivo, de modo a identificar a versao dos dados utilizada.

Uso:
    python src/s01_download_cvm.py
    python src/s01_download_cvm.py --forcar   # rebaixa mesmo se ja existir
"""

from __future__ import annotations

import argparse
import time
import zipfile
from pathlib import Path

import requests

from utils import DIR_RAW, get_logger, load_config, registrar_proveniencia

LOG = get_logger("s01_download_cvm")

TEMPO_LIMITE = 300
TENTATIVAS = 3
ESPERA_ENTRE_TENTATIVAS = 10

# O portal recusa requisicoes sem identificacao de navegador.
CABECALHOS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept": "*/*",
}


def baixar(url: str, destino: Path, forcar: bool = False) -> bool:
    """Baixa um arquivo, com novas tentativas e preservando o que ja existe."""
    if destino.exists() and destino.stat().st_size > 1024 and not forcar:
        LOG.info("ja existe, download dispensado: %s", destino.name)
        return True

    for tentativa in range(1, TENTATIVAS + 1):
        LOG.info("baixando %s (tentativa %d de %d)", url, tentativa, TENTATIVAS)
        try:
            resposta = requests.get(url, timeout=TEMPO_LIMITE, stream=True,
                                    headers=CABECALHOS)
            resposta.raise_for_status()
        except requests.RequestException as erro:
            LOG.warning("falha: %s", erro)
            if tentativa < TENTATIVAS:
                time.sleep(ESPERA_ENTRE_TENTATIVAS)
                continue
            LOG.error("nao foi possivel baixar %s apos %d tentativas.",
                      url, TENTATIVAS)
            LOG.error("Baixe manualmente pelo navegador e salve em %s", destino)
            return False

        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "wb") as handle:
            for pedaco in resposta.iter_content(chunk_size=1 << 20):
                handle.write(pedaco)
        LOG.info("gravado: %s (%.1f MB)", destino.name,
                 destino.stat().st_size / 1e6)
        return True
    return False


def main(forcar: bool = False) -> None:
    cfg = load_config()
    fonte = cfg["fonte"]
    DIR_RAW.mkdir(parents=True, exist_ok=True)
    baixados = []

    # Cadastro de companhias abertas: fornece a classificacao setorial.
    cadastro = DIR_RAW / "cad_cia_aberta.csv"
    if baixar(fonte["url_cadastro"], cadastro, forcar):
        baixados.append(cadastro)

    # Pacotes anuais das DFP.
    for ano in fonte["anos"]:
        url = f"{fonte['base_url_dfp']}/dfp_cia_aberta_{ano}.zip"
        destino = DIR_RAW / f"dfp_cia_aberta_{ano}.zip"
        if not baixar(url, destino, forcar):
            continue
        try:
            with zipfile.ZipFile(destino) as pacote:
                if pacote.testzip() is not None:
                    LOG.error("pacote corrompido: %s", destino.name)
                    continue
                LOG.info("%s contem %d arquivos", destino.name,
                         len(pacote.namelist()))
        except zipfile.BadZipFile:
            LOG.error("arquivo nao e um ZIP valido: %s. Provavelmente o portal "
                      "devolveu uma pagina de erro. Apague o arquivo e tente "
                      "novamente.", destino.name)
            continue
        baixados.append(destino)

    if not baixados:
        LOG.error("nenhum arquivo obtido; verifique a conexao ou as URLs.")
        return

    proveniencia = registrar_proveniencia(baixados, DIR_RAW / "proveniencia.csv")
    LOG.info("proveniencia registrada para %d arquivos", len(proveniencia))
    LOG.info("data de referencia declarada no TCC: %s",
             fonte["data_referencia_coleta"])
    LOG.info("proxima etapa recomendada: python src/s00_inspect_layout.py")
    LOG.info("etapa 1 concluida.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forcar", action="store_true",
                        help="rebaixa os arquivos mesmo que ja existam")
    main(**vars(parser.parse_args()))
