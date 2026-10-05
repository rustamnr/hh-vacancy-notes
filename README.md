# hh-parser

A personal job-seeker assistant: collecting vacancies from hh.ru into Obsidian notes, analysing requirements, and later resume variants and cover letters via an external LLM API, a Telegram bot that confirms applications, and result tracking to measure conversion.

Plain Python, standard library only (Python 3.9+), nothing to install.

hh.ru closed its applicant API, so the project uses only the **application token** (`HH_APP_TOKEN`), which can read public vacancies. Resumes come from your own files and applications are made by hand. See [docs/hh-api-notes.md](docs/hh-api-notes.md).

## Setup

```bash
cp .env.example .env     # fill in HH_USER_AGENT and HH_APP_TOKEN; .env is never committed
python3 -m unittest      # optional: run the tests
```

## Reading vacancies

All commands are read-only and need only `HH_USER_AGENT` and `HH_APP_TOKEN` in `.env`.

```bash
# search, as a table (id, date, title, company, salary, area, url)
python3 -m hh_parser search --text golang --period 3 --per-page 10

# search and fetch every vacancy in full, as a JSON array with separated fields
python3 -m hh_parser search --text golang --period 3 --per-page 10 --json > vacancies.json

# export: one JSON file per vacancy, data/vacancies/<id>.json (data/ is git-ignored);
# add --raw to store the API responses as is
python3 -m hh_parser search --text golang --period 7 --per-page 50 --out data/vacancies

# write notes into an Obsidian folder: no duplicates, known vacancies are not fetched again
python3 -m hh_parser search --text golang --period 7 --per-page 50 --vault "/path/to/your/vault/Vacancies"

# one vacancy by id or URL: separated fields, or the raw API response
python3 -m hh_parser vacancy https://hh.ru/vacancy/123456789
python3 -m hh_parser vacancy --raw 123456789
```

### Excluding vacancies

`--exclude "junior,джун,стажер,руководитель"` skips vacancies whose **title** contains one of the words (case and ё/е do not matter; a word matches at the start of a word of the title, so `джун` covers "Джуниор", and a phrase like `team lead` works too). It filters the search results before anything is fetched in full, so excluded vacancies cost no extra requests, and they never reach the notes. Put your usual list into `.env` once and every command uses it:

```
HH_EXCLUDE=junior,джун,стажер,стажёр,intern,trainee,руководитель,начальник,team lead,тимлид,head of,director,директор
```

`--exclude ""` switches the filter off for one run. Only the title is checked, on purpose: a description that merely says "you will mentor juniors" must not hide a good vacancy.

Fields of the JSON view: `id`, `title`, `url`, `published_at`, `archived`, `employer`, `area`, `salary {from, to, currency, gross}`, `experience`, `employment`, `schedule`, `professional_roles[]`, `key_skills[]`, `response_letter_required`, `has_test`, `responsibilities`, `requirements`, `nice_to_have`, `conditions`, `description_text`.

The four description parts are cut out by their headings ("Требования", "Обязанности", "Условия", ...), which employers write freely, so a part may be empty. `description_text` always holds the whole description.

## Obsidian

`--vault DIR` writes one Markdown note per vacancy into DIR (point it at a folder inside your Obsidian vault; plain Markdown, nothing else is needed; `~` and `$HOME` are fine in the path, put it in quotes if it has spaces). The note is named `<title> (<id>).md`, and the id in the name is what prevents duplicates: a vacancy that is already in the folder is neither fetched from hh again (this spares the request limit) nor written again, and **an existing note is never overwritten**, so your edits are safe. Notes are written one by one, so an interrupted run keeps its progress.

A note has YAML properties (id, url, employer, area, salary_from/to, experience, key_skills, published, ...) followed by the key skills, requirements, responsibilities, nice to have, conditions, the full description and an empty "My notes" section. Two properties are for you: `status` (starts as `new`; change it as you apply: `applied`, `interview`, `rejected`, ...) and `tags`. With the Dataview plugin you can build tables over them, for example:

````
```dataview
TABLE employer, salary_from, status FROM "Vacancies" WHERE status = "new" SORT published DESC
```
````

The vault folder is outside the repository, so nothing of it is committed.

## Layout

```
hh_parser/
  cli.py        commands: search, vacancy
  client.py     hh.ru API client, typed errors, paging helpers
  config.py     settings from the environment and .env
  view.py       a vacancy flattened into separate fields
  filters.py    exclusion of vacancies by words in the title
  textutil.py   HTML to plain text, splitting a description into sections
  vault.py      Markdown notes for Obsidian (no duplicates, never overwrites)
tests/          unittest, with a fake hh API on localhost
docs/           notes on the hh.ru API
```

## Plans

1. Reading vacancies from hh into Obsidian. **(done)**
2. Search profile from the resume, so that queries come from your own experience.
3. Requirement analysis and comparison with the resume.
4. Resume variants and cover letter generation through an LLM API.
5. Telegram bot, assisted applications.
6. Result tracking and conversion analytics.
