# Quarto instructions

These instructions apply when editing the Quarto website, notebooks rendered
into the site, navigation, or generated documentation outputs.

## Source of truth (use these first)

- `_quarto.yml`
  - Website configuration and navbar structure.
- `index.qmd` and other `*.qmd` files
  - Primary content sources for the site.
- `notebooks/`
  - Source notebooks and Quarto notebook wrappers.
- `templates/` and `grass.scss`
  - Repo styling and templates.

## Generated outputs (do not edit by hand)

- `docs/` is the Quarto output directory (generated).
- `_freeze/` contains frozen execution outputs (generated).

When changing site content, edit the source `.qmd` / `.ipynb` files and then
render. Do not directly edit HTML under `docs/` unless explicitly requested.

## Rendering conventions

- This repo uses `execute: freeze: auto` in `_quarto.yml`.
  - Prefer minimal changes that keep freeze behavior consistent.
- If adding new pages, also update `_quarto.yml` navigation when the page
  should be discoverable from the navbar.

## What not to do

- Do not add new themes, fonts, or design systems that conflict with existing
  styling (`grass.scss`).
- Do not commit large rendered artifacts if the change can be represented in
  source files.
