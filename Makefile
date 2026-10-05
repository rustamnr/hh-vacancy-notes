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
# Quotes inside the value (VAULT ?= "/path with spaces") would break the commands below.
override VAULT := $(subst ",,$(VAULT))
OUT      ?= data/vacancies
# Vacancies whose title contains one of these words are skipped (case and ё/е do not matter).
# Make it empty to fall back to HH_EXCLUDE from .env, or pass it per call: make collect EXCLUDE=junior
EXCLUDE  ?= junior,джун,стажер,стажёр,intern,trainee,руководитель,начальник,team lead,тимлид,head of,director,директор,Tech Lead
override EXCLUDE := $(subst ",,$(EXCLUDE))

SEARCH = $(PY) -m hh_parser search --text "$(TEXT)" --period $(PERIOD) --per-page $(PER_PAGE) --pages $(PAGES) $(if $(AREA),--area $(AREA)) $(if $(EXCLUDE),--exclude "$(EXCLUDE)")

help: ## List commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables: TEXT PERIOD PER_PAGE PAGES AREA EXCLUDE VAULT OUT, e.g. make collect TEXT=python PERIOD=3"

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