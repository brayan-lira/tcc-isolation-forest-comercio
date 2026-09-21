# Aplicação do algoritmo "Isolation Forest" na priorização de observações contábeis atípicas em companhias abertas do comércio brasileiro

Pacote de reprodução do Trabalho de Conclusão de Curso apresentado ao **MBA em Data Science e Analytics — USP/ESALQ**.

**Autor:** Brayan Roberto Vieira Lira
**Orientador:** Prof. Dr. Renato Máximo Sátiro
**Ano:** 2026

---

## O que este repositório contém

Os *scripts* desenvolvidos para extração, tratamento, cálculo dos indicadores, aplicação do modelo e análises de sensibilidade descritos na seção de Material e Métodos do trabalho.

O estudo **não desenvolve nem programa** a lógica computacional do algoritmo: utiliza a implementação já existente e consolidada disponibilizada pela biblioteca `scikit-learn` (Pedregosa et al., 2011), aplicada a dados contábeis reais.

Os arquivos brutos da CVM, de grande volume, **não são redistribuídos**. O roteiro abaixo permite obtê-los diretamente do portal oficial.

## Estrutura

```
.
├── config/config.yaml          Todos os parâmetros metodológicos do estudo
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
├── data/{raw,interim,processed}   Não versionados (ver .gitignore)
├── outputs/{figures,tables,logs}
└── run_all.py                  Executa todas as etapas em sequência
```

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

A etapa 1 baixa cerca de 1 GB do portal da CVM. Para reaproveitar arquivos já presentes em `data/raw`:

```bash
python run_all.py --pular-download
```

## Verifique o leiaute antes de confiar nos números

O portal da CVM altera ocasionalmente os nomes de arquivos e de colunas. A **etapa 0** abre os pacotes baixados e relata o que de fato existe:

```bash
python src/s00_inspect_layout.py
```

O relatório mostra, para cada exercício, todos os CSV e suas colunas, qual é o arquivo da seção de pareceres, qual coluna traz o tipo de relatório do auditor e **quais valores essa coluna contém**. Mostra também a **grafia exata** de cada setor no cadastro, destacando a que corresponde ao `config.yaml`.

Essa verificação evita duas falhas silenciosas:

- Se a grafia do setor divergir, o filtro retorna vazio e o painel sai com zero observações.
- Se houver tipos de relatório não previstos no `config.yaml`, eles são excluídos do teste exato de Fisher e alteram o denominador sem aviso.

## Fonte dos dados

Cadastro de companhias abertas e arquivos anuais das Demonstrações Financeiras Padronizadas (DFP), disponibilizados pela Comissão de Valores Mobiliários em <https://dados.cvm.gov.br>.

Os arquivos referentes ao período de 2020 a 2025 foram obtidos em **6 de agosto de 2026**. Tamanhos e códigos *hash* SHA-256 são gravados em `data/raw/proveniencia.csv` pela etapa 1, de modo a identificar a versão dos dados diante de eventuais reapresentações.

> **Atenção à reprodutibilidade.** A CVM atualiza os arquivos periodicamente com reapresentações. Uma execução em data posterior pode divergir dos números publicados no trabalho caso alguma companhia tenha reapresentado suas demonstrações. Compare sempre o `sha256` obtido com o registrado em `data/raw/proveniencia.csv`.

## Critérios de elegibilidade

Declarados em `config/config.yaml` e aplicados na etapa 2:

| Critério | Valor |
|---|---|
| Setor (cadastro CVM) | Comércio (Atacado e Varejo) |
| Tipo de demonstração | Consolidada |
| Moeda / escala | Real / milhares |
| Plano de contas | Fixo (`ST_CONTA_FIXA = S`) |
| Ordem do exercício | Último |
| Versão | Maior versão por companhia e data de referência |
| Janela de período (DRE, DVA, DFC) | 330 a 380 dias |
| Pares consecutivos | Mesmo dia e mês de encerramento |
| Imputação de valores essenciais | Não realizada |

## Parâmetros do modelo

| Parâmetro | Valor |
|---|---|
| Winsorização (apenas para ajuste) | Percentis 1 e 99 |
| Padronização | Robusta — mediana e intervalo interquartil |
| Número de árvores | 500 |
| Máximo de amostras por árvore | 128 |
| Contaminação | `auto` |
| Sementes | 50 (0 a 49) |
| Agregação | Média dos 50 percentis |
| Cortes operacionais | 3%, 5% e 10%, construídos **após** o *ranking* |

Os grupos de prioridade não decorrem do parâmetro de contaminação; representam apenas limites de capacidade de revisão.

## Saídas geradas

**Tabelas** (`outputs/tables/`)

| Arquivo | Conteúdo |
|---|---|
| `tabela2_distribuicao_temporal.csv` | Observações, companhias e cortes por exercício |
| `tabela3_estatisticas_descritivas.csv` | Estatísticas dos oito componentes |
| `tabela4_ranking_consensual.csv` | Grupo prioritário de 5% e componentes predominantes |
| `tabela5_frequencia_componentes.csv` | Frequência de cada componente entre as prioridades |
| `tabela6_sensibilidade.csv` | Spearman e Jaccard dos seis cenários |
| `tabela7_tipo_relatorio.csv` | Contingência 2 × 2 com o relatório do auditor |
| `estabilidade_aleatoria.csv` | Spearman e Jaccard de cada semente |
| `triangulacao_resumo.json` | M-Score e teste exato de Fisher |
| `leiaute_cvm.csv` | Arquivos e colunas encontrados nos pacotes da CVM |

**Figuras** (`outputs/figures/`) — Figuras 1 a 6 em PNG e PDF, a 300 dpi.

## Limites de interpretação

A unidade de análise é a observação companhia-ano, e não o lançamento contábil. O resultado indica **onde** investigar, mas não identifica a transação, o lançamento ou o controle interno que originou o desvio. A lista de prioridades antecede — e não substitui — os procedimentos de resposta previstos na NBC TA 330.

O relatório do auditor independente **não é tratado como rótulo de fraude**: sua natureza e seu momento de emissão respondem a objetivos distintos daqueles do algoritmo. O M-Score é utilizado de forma contínua e ordinal, sem importação de ponto de corte estimado em outro país, período e regime contábil.

## Aspectos éticos

Foram utilizados exclusivamente dados corporativos públicos, sem coleta junto a participantes e sem identificação de pessoas naturais, razão pela qual a pesquisa não demandou submissão a comitê de ética.

Ferramentas de inteligência artificial generativa foram empregadas como apoio à estruturação do protocolo, à depuração do código e à revisão linguística do texto. Dados, referências, cálculos e interpretações foram integralmente conferidos pelo autor, e nenhuma saída gerada por tais ferramentas foi aceita como evidência ou como resultado de pesquisa.

## Referências

BENEISH, M. D. The detection of earnings manipulation. *Financial Analysts Journal*, v. 55, n. 5, p. 24-36, 1999.

LIU, F. T.; TING, K. M.; ZHOU, Z.-H. Isolation Forest. In: *2008 IEEE International Conference on Data Mining*, Pisa, Itália. Proceedings... p. 413-422.

PEDREGOSA, F. et al. Scikit-learn: machine learning in Python. *Journal of Machine Learning Research*, v. 12, p. 2825-2830, 2011.

## Licença

Código sob licença MIT (ver `LICENSE`). Os dados da CVM permanecem sujeitos aos termos do portal de dados abertos.
