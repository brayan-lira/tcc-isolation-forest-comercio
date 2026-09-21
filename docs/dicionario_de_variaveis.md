# Dicionário de variáveis

Documento de apoio ao pacote de reprodução. Descreve as contas extraídas da base da CVM, os oito componentes contábeis e as variáveis produzidas pelos *scripts*.

---

## 1. Contas fixas extraídas da CVM

Códigos do plano de contas fixo, conforme declarado em `config/config.yaml`.

| Apelido no código | Código CVM | Demonstração | Descrição |
|---|---|---|---|
| `ativo_total` | 1 | BPA | Ativo total |
| `ativo_circulante` | 1.01 | BPA | Ativo circulante |
| `recebiveis` | 1.01.03 | BPA | Contas a receber |
| `imobilizado` | 1.02.03 | BPA | Imobilizado |
| `passivo_circulante` | 2.01 | BPP | Passivo circulante |
| `divida_longo_prazo` | 2.02.01 | BPP | Empréstimos e financiamentos de longo prazo |
| `receita_liquida` | 3.01 | DRE | Receita líquida de vendas |
| `resultado_bruto` | 3.03 | DRE | Resultado bruto |
| `despesas_vendas` | 3.04.01 | DRE | Despesas com vendas |
| `despesas_gerais_adm` | 3.04.02 | DRE | Despesas gerais e administrativas |
| `resultado_liquido` | 3.11 | DRE | Resultado líquido do exercício |
| `depreciacao` | 7.04.01 | DVA | Depreciação, amortização e exaustão |
| `fco` | 6.01 | DFC | Caixa gerado pelas atividades operacionais |

Sufixos: `_t` identifica o exercício corrente; `_t1`, o exercício imediatamente anterior.

---

## 2. Componentes contábeis

Derivados de Beneish (1999) e adaptados às contas fixas disponíveis. As despesas com vendas, gerais e administrativas são somadas em valor absoluto; a depreciação é representada pela linha agregada da DVA; o componente TATA utiliza a diferença entre o resultado líquido e o fluxo de caixa operacional.

| Componente | Expressão adaptada | Leitura analítica |
|---|---|---|
| `DSRI` | (Recebíveisₜ / Vendasₜ) ÷ (Recebíveisₜ₋₁ / Vendasₜ₋₁) | Mudança relativa de recebíveis em relação às vendas |
| `GMI` | (Margem brutaₜ₋₁ / Vendasₜ₋₁) ÷ (Margem brutaₜ / Vendasₜ) | Deterioração relativa da margem bruta |
| `AQI` | [1 − (ACₜ + Imob.ₜ)/ATₜ] ÷ [1 − (ACₜ₋₁ + Imob.ₜ₋₁)/ATₜ₋₁] | Mudança na parcela de ativos não circulantes exceto imobilizado |
| `SGI` | Vendasₜ ÷ Vendasₜ₋₁ | Crescimento das vendas |
| `DEPI` | Taxa de depreciaçãoₜ₋₁ ÷ Taxa de depreciaçãoₜ | Mudança da taxa de depreciação; taxa = Dep. ÷ (Dep. + Imob.) |
| `SGAI` | (DVGAₜ / Vendasₜ) ÷ (DVGAₜ₋₁ / Vendasₜ₋₁) | Mudança das despesas de vendas, gerais e administrativas |
| `LVGI` | [(PCₜ + Dívida LPₜ)/ATₜ] ÷ [(PCₜ₋₁ + Dívida LPₜ₋₁)/ATₜ₋₁] | Mudança da alavancagem |
| `TATA` | (Resultado líquidoₜ − FCOₜ) ÷ ATₜ | Diferença entre resultado e caixa operacional sobre ativos |

**Nota:** AC = ativo circulante; AT = ativo total; Dep. = depreciação, amortização e exaustão; DVGA = despesas com vendas, gerais e administrativas; FCO = fluxo de caixa operacional; Imob. = imobilizado; LP = longo prazo; PC = passivo circulante.

Denominadores iguais a zero geram valor ausente, sem substituição arbitrária (`utils.razao_segura`). Valores negativos economicamente possíveis, como margem bruta negativa, são preservados.

---

## 3. M-Score

Combinação original de Beneish (1999), aplicada de forma contínua e ordinal:

```
M = −4,84 + 0,920·DSRI + 0,528·GMI + 0,404·AQI + 0,892·SGI
    + 0,115·DEPI − 0,172·SGAI + 4,679·TATA − 0,327·LVGI
```

Não se importa ponto de corte estimado em outro país, período e regime contábil.

---

## 4. Variáveis produzidas pelos *scripts*

### `data/processed/painel_companhia_ano.csv` (etapa 2)

| Variável | Tipo | Descrição |
|---|---|---|
| `CD_CVM` | texto | Código da companhia no cadastro da CVM |
| `DENOM_CIA` | texto | Denominação social |
| `DT_REFER` | data | Data de referência da demonstração |
| `ANO_REFER` | inteiro | Exercício de referência |
| *contas da seção 1* | real | Valor em milhares de reais |

### `data/processed/indicadores.csv` (etapa 3)

| Variável | Tipo | Descrição |
|---|---|---|
| `DSRI` … `TATA` | real | Os oito componentes contábeis |
| `MSCORE` | real | M-Score contínuo |
| `COMPANHIA_ANO` | texto | Rótulo de apresentação, no formato `DENOMINAÇÃO (ano)` |

### `data/processed/ranking_consensual.csv` (etapa 4)

| Variável | Tipo | Descrição |
|---|---|---|
| `percentil_consensual` | real | Média dos 50 percentis; define o *ranking* final |
| `posicao` | inteiro | Posição no *ranking*, sendo 1 a maior prioridade |
| `top_3`, `top_5`, `top_10` | lógico | Pertencimento aos grupos operacionais |
| `componentes_predominantes` | texto | Três maiores desvios absolutos padronizados |

### `data/processed/desvios_padronizados.csv` (etapa 4)

| Variável | Tipo | Descrição |
|---|---|---|
| `z_DSRI` … `z_TATA` | real | Componente winsorizado e padronizado de forma robusta |

Base da Figura 4 e da coluna `componentes_predominantes`. O limite de ±3 aplicado na figura é meramente gráfico e não altera o *ranking*.

### `data/processed/rankings_cenarios.csv` (etapa 5)

Percentil consensual do modelo principal e de cada um dos seis cenários alternativos, por observação.

### `data/processed/ranking_com_triangulacao.csv` (etapa 6)

Acrescenta `percentil_mscore` ao *ranking* consensual.

---

## 5. Métricas de avaliação

| Métrica | Uso |
|---|---|
| Correlação de Spearman | Estabilidade entre cada execução e o consenso; comparação entre cenários; concordância com o M-Score |
| Índice de Jaccard | Sobreposição entre grupos de 5% |
| Teste exato de Fisher | Associação entre o grupo prioritário e a opinião modificada do auditor |
| Teste de Mann-Whitney | Comparação de medianas do percentil entre grupos de opinião |

Não se utilizam métricas de classificação como acurácia, precisão ou sensibilidade: o desenho é não supervisionado e não existe, nos arquivos utilizados, variável que identifique de forma completa e temporalmente compatível as distorções relevantes.

---

## 6. Agrupamento do relatório do auditor

| Grupo | Tipos de relatório |
|---|---|
| Sem ressalva | Sem ressalva |
| Opinião modificada | Com ressalva; abstenção de opinião; negativa de opinião; adversa |

Registros sem tipo de relatório identificado permanecem no *ranking*, mas são excluídos do teste. A etapa 0 lista os valores reais encontrados na base e sinaliza os que não estiverem cobertos pelo `config.yaml`.
