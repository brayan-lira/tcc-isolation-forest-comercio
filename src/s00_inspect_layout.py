"""Etapa 0 - Inspecao do leiaute real dos arquivos da CVM.

Executar esta etapa logo apos o download resolve, de uma vez, a unica
incerteza do protocolo: o nome exato dos arquivos dentro do pacote anual, o
nome das colunas de cada um e a grafia do setor no cadastro. O script nao
supoe nada; apenas abre os ZIP baixados e relata o que de fato existe.

Relatorio gravado em outputs/tables/leiaute_cvm.csv e impresso no console,
com destaque para:
  - os arquivos de cada demonstracao (BPA, BPP, DRE, DVA, DFC_MI, DFC_MD);
  - o arquivo da secao de Pareceres e Declaracoes;
  - a coluna que identifica o tipo de relatorio do auditor e seus valores;
  - a grafia exata do setor no cadastro de companhias abertas.

Uso:
    python src/s00_inspect_layout.py
"""

from __future__ import annotations

import zipfile

import pandas as pd

from cvm_layout import (identificar_grupo, ler_csv, localizar_arquivo_parecer,
                        localizar_coluna_tipo)
from utils import DIR_RAW, get_logger, load_config, normalizar_texto, salvar_tabela

LOG = get_logger("s00_inspect_layout")


def inspecionar_cadastro(cfg: dict) -> None:
    """Mostra a grafia exata do setor, evitando perda silenciosa de companhias."""
    caminho = DIR_RAW / "cad_cia_aberta.csv"
    if not caminho.exists():
        LOG.warning("cadastro ausente; execute antes: python src/s01_download_cvm.py")
        return

    cadastro = pd.read_csv(caminho, sep=cfg["fonte"]["separador"],
                           encoding=cfg["fonte"]["encoding"], dtype=str)
    cadastro.columns = [c.strip().upper() for c in cadastro.columns]
    if "SETOR_ATIV" not in cadastro.columns:
        LOG.error("coluna SETOR_ATIV ausente. Colunas: %s", list(cadastro.columns))
        return

    contagem = cadastro["SETOR_ATIV"].value_counts()
    alvo = normalizar_texto(cfg["filtros"]["setor_cvm"])

    LOG.info("=" * 74)
    LOG.info("SETORES NO CADASTRO (grafia exata e numero de companhias)")
    LOG.info("=" * 74)
    encontrado = False
    for setor, quantidade in contagem.items():
        marca = ""
        if normalizar_texto(setor) == alvo:
            marca = "   <<< corresponde ao config.yaml"
            encontrado = True
        LOG.info("%5d  %s%s", quantidade, setor, marca)

    if not encontrado:
        LOG.error("-" * 74)
        LOG.error("ATENCAO: nenhum setor corresponde a '%s' do config.yaml.",
                  cfg["filtros"]["setor_cvm"])
        LOG.error("Copie a grafia correta da lista acima para filtros.setor_cvm.")
        LOG.error("Sem isso, o painel sera formado com zero observacoes.")
        LOG.error("-" * 74)


def inspecionar_pacotes(cfg: dict) -> list[dict]:
    """Percorre os pacotes anuais e relata arquivos, grupos e colunas."""
    linhas = []
    tipo = cfg["filtros"]["tipo_demonstracao"]

    for ano in cfg["fonte"]["anos"]:
        caminho = DIR_RAW / f"dfp_cia_aberta_{ano}.zip"
        if not caminho.exists():
            LOG.warning("%s ausente; execute antes a etapa 1.", caminho.name)
            continue

        LOG.info("=" * 74)
        LOG.info("PACOTE %s", caminho.name)
        LOG.info("=" * 74)

        with zipfile.ZipFile(caminho) as pacote:
            nomes = sorted(n for n in pacote.namelist() if n.lower().endswith(".csv"))
            grupos_vistos = set()

            for nome in nomes:
                colunas = list(ler_csv(pacote, nome, cfg, nrows=5).columns)
                grupo = identificar_grupo(nome, tipo)
                if grupo:
                    grupos_vistos.add(grupo)
                LOG.info("%-52s %s", nome, f"[{grupo}]" if grupo else "")
                LOG.info("     colunas: %s", ", ".join(colunas))
                linhas.append({"ano": ano, "arquivo": nome, "grupo": grupo or "",
                               "n_colunas": len(colunas),
                               "colunas": " | ".join(colunas)})

            esperados = {"BPA", "BPP", "DRE", "DVA"}
            faltando = esperados - grupos_vistos
            if faltando:
                LOG.error("%d: demonstracoes nao localizadas para o tipo '%s': %s",
                          ano, tipo, sorted(faltando))
            if not ({"DFC_MI", "DFC_MD"} & grupos_vistos):
                LOG.error("%d: nenhuma demonstracao de fluxo de caixa localizada.", ano)

            inspecionar_parecer(pacote, ano, cfg)

    return linhas


def inspecionar_parecer(pacote: zipfile.ZipFile, ano: int, cfg: dict) -> None:
    """Identifica o arquivo e a coluna de tipo de relatorio, e lista os valores."""
    nome = localizar_arquivo_parecer(pacote)
    if nome is None:
        LOG.error("%d: nenhum arquivo de parecer localizado. A triangulacao com o "
                  "relatorio do auditor ficara indisponivel (Tabela 7).", ano)
        return

    quadro = ler_csv(pacote, nome, cfg)
    coluna = localizar_coluna_tipo(list(quadro.columns))

    LOG.info("-" * 74)
    LOG.info("PARECER  arquivo ...... %s", nome)
    LOG.info("PARECER  coluna tipo .. %s", coluna or "NAO IDENTIFICADA")

    if coluna is None:
        LOG.error("Acrescente o nome correto a CANDIDATOS_COLUNA_TIPO em "
                  "src/cvm_layout.py. Colunas disponiveis: %s",
                  list(quadro.columns))
        LOG.info("-" * 74)
        return

    cobertos = [normalizar_texto(v) for v in
                cfg["triangulacao"]["opiniao_modificada"]
                + cfg["triangulacao"]["opiniao_sem_ressalva"]]

    LOG.info("PARECER  valores distintos encontrados:")
    for valor, quantidade in quadro[coluna].value_counts().items():
        marca = "" if any(c in normalizar_texto(valor) for c in cobertos) \
            else "   <<< NAO coberto pelo config.yaml"
        LOG.info("         %5d  %s%s", quantidade, valor, marca)
    LOG.info("Valores nao cobertos serao excluidos do teste exato de Fisher.")
    LOG.info("-" * 74)


def main() -> None:
    cfg = load_config()
    inspecionar_cadastro(cfg)
    linhas = inspecionar_pacotes(cfg)

    if linhas:
        destino = salvar_tabela(pd.DataFrame(linhas), "leiaute_cvm")
        LOG.info("relatorio de leiaute gravado em %s", destino)
    LOG.info("etapa 0 concluida.")


if __name__ == "__main__":
    main()
