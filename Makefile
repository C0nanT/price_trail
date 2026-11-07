PYTHON ?= python3
PORT   ?= 8000
TAILWIND ?= bin/tailwindcss
CSS_ARGS = -c tailwind.config.js -i tailwind/input.css -o pricetrail/web/app.css

.PHONY: help install import serve export restore test css css-watch

help:
	@echo "make install   instala as dependências (Flask)"
	@echo "make import    importa os PDFs de data/ para o SQLite (FOLDER=pasta opcional)"
	@echo "make serve     abre o gráfico, /groups e /import (PORT=8000)"
	@echo "make export    grava a curadoria em curadoria.json"
	@echo "make restore   substitui a curadoria do banco por curadoria.json"
	@echo "make css       gera pricetrail/web/app.css com o Tailwind (veja o README)"
	@echo "make css-watch regera o CSS a cada mudança"
	@echo "make test      roda a suíte de testes"

install:
	$(PYTHON) -m pip install -r requirements.txt

import:
	$(PYTHON) -m pricetrail import $(FOLDER)

serve:
	$(PYTHON) -m pricetrail serve --port $(PORT)

export:
	$(PYTHON) -m pricetrail export

restore:
	$(PYTHON) -m pricetrail restore

test:
	$(PYTHON) -m unittest discover -s tests -t .

css:
	$(TAILWIND) $(CSS_ARGS) --minify

css-watch:
	$(TAILWIND) $(CSS_ARGS) --watch
