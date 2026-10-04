.DEFAULT_GOAL := help
.PHONY: help test search collect export vacancy

PY       ?= python3
TEXT     ?= golang
PERIOD   ?= 7
PER_PAGE ?= 50
PAGES    ?= 1
AREA     ?=
# Folder for Obsidian notes, e.g. VAULT="$(HOME)/Documents/MyVault/Vacancies".
# Set it here or per call: make collect VAULT=...
VAULT    ?= $(HOME)/Documents/Obsidian Vault/HH-Vacancies
OUT      ?= data/vacancies

SEARCH = $(PY) -m hh_parser search --text "$(TEXT)" --period $(PERIOD) --per-page $(PER_PAGE) --pages $(PAGES) $(if $(AREA),--area $(AREA))

help: ## List commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables: TEXT PERIOD PER_PAGE PAGES AREA VAULT OUT, e.g. make collect TEXT=python PERIOD=3"

test: ## Run the tests
	$(PY) -m unittest

search: ## Show a table of found vacancies
	$(SEARCH)

collect: ## Save new vacancies as Obsidian notes (needs VAULT)
	@test -n "$(VAULT)" || { echo "set VAULT to a folder in your Obsidian vault: make collect VAULT=..."; exit 1; }
	$(SEARCH) --vault "$(VAULT)"

export: ## Save every found vacancy as a JSON file into OUT
	$(SEARCH) --out "$(OUT)"

vacancy: ## Print one vacancy as JSON (needs ID=<id or url>)
	@test -n "$(ID)" || { echo "usage: make vacancy ID=<id or hh.ru url>"; exit 1; }
	$(PY) -m hh_parser vacancy "$(ID)"
