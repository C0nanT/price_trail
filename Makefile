PYTHON ?= python3
PORT   ?= 8000

.PHONY: help install import serve export restore test

help:
	@echo "make install   instala as dependências (Flask)"
	@echo "make import    importa os PDFs de data/ para o SQLite (FOLDER=pasta opcional)"
	@echo "make serve     abre o gráfico, /groups e /import (PORT=8000)"
	@echo "make export    grava a curadoria em curadoria.json"
	@echo "make restore   substitui a curadoria do banco por curadoria.json"
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
