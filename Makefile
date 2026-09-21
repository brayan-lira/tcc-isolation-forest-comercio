# Atalhos para as etapas do protocolo.
.PHONY: ajuda instalar dados leiaute painel indicadores modelo sensibilidade triangulacao figuras tudo limpar

ajuda:
	@echo "make instalar       - instala as dependencias"
	@echo "make tudo           - executa todas as etapas"
	@echo "make dados          - etapa 1: coleta na CVM"
	@echo "make leiaute        - etapa 0: inspeciona o leiaute da CVM"
	@echo "make painel         - etapa 2: painel companhia-ano"
	@echo "make indicadores    - etapa 3: componentes e M-Score"
	@echo "make modelo         - etapa 4: Isolation Forest"
	@echo "make sensibilidade  - etapa 5: cenarios alternativos"
	@echo "make triangulacao   - etapa 6: M-Score e auditor"
	@echo "make figuras        - etapa 7: Figuras 1 a 6"
	@echo "make limpar         - remove saidas e intermediarios"

instalar:
	pip install -r requirements.txt

dados:          ; python src/s01_download_cvm.py
leiaute:        ; python src/s00_inspect_layout.py
painel:         ; python src/s02_build_panel.py
indicadores:    ; python src/s03_indicators.py
modelo:         ; python src/s04_isolation_forest.py
sensibilidade:  ; python src/s05_sensitivity.py
triangulacao:   ; python src/s06_triangulation.py
figuras:        ; python src/s07_figures.py

tudo:
	python run_all.py

limpar:
	find data/interim data/processed outputs -type f ! -name '.gitkeep' -delete
	find . -type d -name __pycache__ -exec rm -rf {} +
