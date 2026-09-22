# Aplicação do algoritmo "Isolation Forest" na priorização de observações contábeis atípicas em companhias abertas do comércio brasileiro

**Versão de referência do trabalho:** v1.0.0

## Situação do repositório

Versão reproduzível validada em 21 de setembro de 2026.

### Principais resultados reproduzidos

- 235 observações companhia-ano
- 188 pares consecutivos elegíveis
- 187 observações analíticas
- 43 companhias
- Spearman mediano = 0,997
- Jaccard mediano = 1,000

Pacote de reprodução do Trabalho de Conclusão de Curso apresentado ao **MBA em Data Science e Analytics — USP/ESALQ**.

**Autor:** Brayan Roberto Vieira Lira

**Orientador:** Prof. Dr. Renato Máximo Sátiro

**Ano:** 2026

---

## O que este repositório contém

Os *scripts* desenvolvidos para extração, tratamento, cálculo dos indicadores, aplicação do modelo e análises de sensibilidade descritos na seção de Material e Métodos do trabalho.

O estudo **não desenvolve nem programa** a lógica computacional do algoritmo. Utiliza a implementação já consolidada disponibilizada pela biblioteca `scikit-learn` (Pedregosa et al., 2011), aplicada a dados contábeis reais.

Os arquivos brutos da CVM, de grande volume, **não são redistribuídos**. O roteiro abaixo permite obtê-los diretamente do portal oficial.

---

## Estrutura

```text
.
├── config/
│   └── config.yaml            Todos os parâmetros metodológicos do estudo
├── src/
│   ├── utils.py                Funções de apoio, proveniência e hash SHA-256
│   ├── cvm_layout.py           Detecção do leiaute real dos arquivos da CVM
│   ├── s00_inspect_layout.py   Etapa 0 - inspeção do leiaute e do cadastro
│   ├── s01_download_cvm.py     Etapa 1 - coleta no portal de dados abertos
│   ├── s02_build_panel.py      Etapa 2 - filtros e painel companhia-ano
│   ├── s03_indicators.py       Etapa 3 - oito componentes e M-Score
│   ├── s04_isolation_forest.py Etapa 4 - modelo e ranking consensual
│   ├── s05_sensitivity.py      Etapa 5 - seis cenários alternativos
│   ├── s06_triangulation.py    Etapa 6 - M-Score e relatório do auditor
│   └── s07_figures.py          Etapa 7 - Figuras 1 a 6
├── docs/
│   ├── dicionario_de_variaveis.md
│   └── como_publicar_no_github.md
├── data/
│   ├── raw/                    Dados obtidos diretamente da CVM
│   ├── interim/                Arquivos intermediários do processamento
│   └── processed/              Base analítica utilizada no estudo
├── outputs/
│   ├── figures/
│   ├── tables/
│   └── logs/
└── run_all.py                  Executa todas as etapas em sequência
```

---

## Como reproduzir

Requer Python 3.10 ou superior.

```bash
git clone https://github.com/brayan-lira/tcc-isolation-forest-comercio.git
cd tcc-isolation-forest-comercio

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run_all.py
```

Para executar uma etapa isolada:

```bash
python src/s04_isolation_forest.py
```

A etapa 1 baixa aproximadamente 1 GB do portal da CVM. Para reaproveitar arquivos já presentes em `data/raw`:

```bash
python run_all.py --pular-download
```

---

## Conferência rápida da reprodução

Uma execução bem-sucedida deve reproduzir os principais resultados do estudo.

| Resultado | Valor esperado |
|------------|------------|
| Observações companhia-ano | 235 |
| Pares consecutivos elegíveis | 188 |
| Observações analíticas | 187 |
| Companhias | 43 |
| Spearman mediano | 0,997 |
| Jaccard mediano | 1,000 |

Ao final da execução, o protocolo deve gerar:

- 6 figuras em PNG e PDF;
- tabelas analíticas em `outputs/tables`;
- relatório de proveniência dos dados;
- ranking consensual do Isolation Forest;
- análises de sensibilidade;
- triangulação com M-Score e relatório do auditor.

---

## Verifique o leiaute antes de confiar nos números

O portal da CVM altera ocasionalmente nomes de arquivos e colunas. A **etapa 0** abre os pacotes baixados e relata exatamente o que existe.

```bash
python src/s00_inspect_layout.py
```

O relatório mostra, para cada exercício:

- todos os CSV existentes;
- todas as colunas encontradas;
- qual é o arquivo da seção de pareceres;
- qual coluna contém o tipo de relatório do auditor;
- quais valores essa coluna apresenta;
- a grafia exata dos setores no cadastro da CVM.

Essa verificação evita duas falhas silenciosas:

- Se a grafia do setor divergir, o filtro retorna vazio e o painel sai com zero observações.
- Se houver tipos de relatório não previstos no `config.yaml`, eles podem ser excluídos do teste exato de Fisher e alterar os resultados sem aviso.

---

## Fonte dos dados

Cadastro de companhias abertas e arquivos anuais das Demonstrações Financeiras Padronizadas (DFP), disponibilizados pela Comissão de Valores Mobiliários em <https://dados.cvm.gov.br>.

Os arquivos referentes ao período de 2020 a 2025 foram obtidos em **21 de setembro de 2026**.

Tamanhos e códigos SHA-256 são gravados em `data/raw/proveniencia.csv` pela etapa 1, permitindo identificar precisamente a versão dos dados utilizada na pesquisa.

> **Atenção à reprodutibilidade.** A CVM atualiza periodicamente os arquivos em função de reapresentações. Uma execução em data posterior pode divergir dos números apresentados neste trabalho caso alguma companhia tenha reapresentado suas demonstrações. Compare sempre os códigos SHA-256 obtidos com os registrados em `data/raw/proveniencia.csv`.

---

## Critérios de elegibilidade

Declarados em `config/config.yaml` e aplicados na etapa 2.

| Critério | Valor |
|---|---|
| Setor (cadastro CVM) | Comércio (Atacado e Varejo) |
| Tipo de demonstração | Consolidada |
| Moeda / escala | Real / milhares |
| Plano de contas | Fixo (`ST_CONTA_FIXA = S`) |
| Ordem do exercício | Último |
| Versão | Maior versão por companhia e data de referência |
| Janela de período (DRE, DVA e DFC) | 330 a 380 dias |
| Pares consecutivos | Mesmo dia e mês de encerramento |
| Imputação de valores essenciais | Não realizada |

---

## Parâmetros do modelo

| Parâmetro | Valor |
|---|---|
| Winsorização (apenas para ajuste) | Percentis 1 e 99 |
| Padronização | Robusta (mediana e intervalo interquartil) |
| Número de árvores | 500 |
| Máximo de amostras por árvore | 128 |
| Contaminação | `auto` |
| Sementes | 50 (0 a 49) |
| Agregação | Média dos 50 percentis |
| Cortes operacionais | 3%, 5% e 10%, definidos após o ranking |

Os grupos de prioridade não decorrem diretamente do parâmetro de contaminação. Representam apenas limites operacionais de capacidade de revisão.

---

## Saídas geradas

### Tabelas (`outputs/tables/`)

| Arquivo | Conteúdo |
|---|---|
| `tabela2_distribuicao_temporal.csv` | Tabela 3 do trabalho — observações, companhias e cortes por exercício |
| `tabela3_estatisticas_descritivas.csv` | Tabela 4 do trabalho — estatísticas dos oito componentes |
| `tabela4_ranking_consensual.csv` | Tabela 5 do trabalho — grupo prioritário de 5% e componentes predominantes |
| `tabela5_frequencia_componentes.csv` | Tabela 6 do trabalho — frequência dos componentes entre as prioridades |
| `tabela6_sensibilidade.csv` | Tabela 7 do trabalho — Spearman e Jaccard dos seis cenários |
| `tabela7_tipo_relatorio.csv` | Tabela 8 do trabalho — contingência 2 × 2 com o relatório do auditor |
| `estabilidade_aleatoria.csv` | Spearman e Jaccard para cada semente |
| `taxa_selecao_por_posicao.csv` | Taxa de seleção de cada posição do grupo prioritário |
| `triangulacao_resumo.json` | M-Score e teste exato de Fisher |
| `leiaute_cvm.csv` | Arquivos e colunas encontrados nos pacotes da CVM |

> **Nota sobre a numeração.** Os nomes dos arquivos seguem a ordem de geração do protocolo. A numeração das tabelas no trabalho é uma unidade maior a partir da terceira, porque a Tabela 2 apresenta os hiperparâmetros do modelo e não decorre de arquivo de saída.

### Figuras (`outputs/figures/`)

Figuras 1 a 6 em formatos PNG e PDF, a 300 dpi.

---

## Limites de interpretação

A unidade de análise é a observação companhia-ano, e não o lançamento contábil.

O resultado indica **onde investigar**, mas não identifica a transação, o lançamento ou o controle interno responsável pelo desvio observado.

A lista de prioridades antecede — e não substitui — os procedimentos de resposta previstos na NBC TA 330.

O relatório do auditor independente **não é tratado como rótulo de fraude**. Sua natureza e seu momento de emissão respondem a objetivos distintos daqueles do algoritmo.

O M-Score é utilizado de forma contínua e ordinal, sem importação de pontos de corte desenvolvidos em outros países, períodos ou regimes contábeis.

---

## Aspectos éticos

Foram utilizados exclusivamente dados corporativos públicos, sem coleta junto a participantes e sem identificação de pessoas naturais. Por essa razão, a pesquisa não demandou submissão a comitê de ética.

Ferramentas de inteligência artificial generativa foram empregadas como apoio à estruturação do protocolo, à depuração do código e à revisão linguística do texto. Dados, referências, cálculos e interpretações foram integralmente conferidos pelo autor, e nenhuma saída gerada por tais ferramentas foi aceita como evidência ou resultado de pesquisa.

---

## Referências

BENEISH, M. D. *The detection of earnings manipulation*. Financial Analysts Journal, v. 55, n. 5, p. 24-36, 1999.

LIU, F. T.; TING, K. M.; ZHOU, Z.-H. *Isolation Forest*. In: 2008 IEEE International Conference on Data Mining, Pisa, Itália. Proceedings... p. 413-422.

PEDREGOSA, F. et al. *Scikit-learn: machine learning in Python*. Journal of Machine Learning Research, v. 12, p. 2825-2830, 2011.

---

## Licença

Código sob licença MIT (ver `LICENSE`).

Os dados da CVM permanecem sujeitos aos termos do portal de dados abertos.
