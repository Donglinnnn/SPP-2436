# Net-Zero Concrete — SCM LCA Framework

## Project context

This research website was developed in the context of SPP 2436 *Net-Zero Concrete*. It provides a structured way to collect process data for waste-derived supplementary cementitious materials (SCMs), build a route from individual processing steps, and calculate a traceable foreground life-cycle inventory. A calculated SCM can be saved as a material item and used in a concrete, mortar, or paste mix. 

## Run locally

Python 3.11 or newer is required. From this folder:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open the local URL printed in the terminal. Foreground SCM calculations run without Brightway; LCA and mix-impact calculations require your own licensed, locally configured ecoinvent/Brightway database. Project history stays on your computer in the Git-ignored `data/` directory. Never commit `local_config.toml`, the project database, or licensed inventory.

## Connect your own ecoinvent / Brightway installation

1. Install or import your licensed ecoinvent database and an LCIA method into a local Brightway project using Brightway's instructions and your own license. The project must already have `lci/databases.db`, `methods.json`, and `processed/` packages. Nothing in this repository downloads licensed data or asks for ecoinvent account credentials.
2. Copy `local_config.template.toml` to ignored `local_config.toml`. Set `background.project_dir` to the actual project directory, `background.python` to a Python executable with `bw2calc`, `bw2data`, and `numpy`, and the **exact** Brightway database and method labels from that project. The included names are defaults for the author's setup, not promises that every installation uses those labels. If an expected provider differs, add a `[background.providers.<key>]` name/location override.
3. From this folder run `python -m src.recipes.check_background`. Each line checks one stage: project, database/providers, paired electricity and heat scenarios, freight lists, exact C0/C1/C2 inventory entries, method/packages, and a real calculation in an isolated temporary project. A `FAIL` line identifies the stage; the command exits nonzero. It does not modify the source Brightway database, write an LCA cache, print a licensed factor, or test online credentials.
