# SSURGO instructions (NRCS soil database)

These instructions apply when working with SSURGO concepts, SSURGO table/column
definitions, SSURGO-derived attributes, or any code in this repo that queries
SSURGO (local SQLite SSURGO or SDA).

## Source of truth (use these first)

SSURGO “database details” for this repo live under:

- `tools/g.ssurgo.query/rag/data/*.pdf`

Prefer these PDFs over general web knowledge. If a definition, unit, or
relationship is needed, look it up in the PDFs and reflect the exact SSURGO
table/column names.

PDFs currently in-repo:

- `tools/g.ssurgo.query/rag/data/SSURGO-Metadata-Tables-and-Columns-Report.pdf`
  - Use to confirm table presence and column lists.
- `tools/g.ssurgo.query/rag/data/SSURGO-Metadata-Table-Column-Descriptions-Report.pdf`
  - Use for column meanings, units/semantics, and notes.
- `tools/g.ssurgo.query/rag/data/SSURGO-Metadata-Relationships-Report.pdf`
  - Use to confirm how tables relate (keys, parent/child relationships).
- `tools/g.ssurgo.query/rag/data/SSURGO-Metadata-Domains-Report.pdf`
  - Use to confirm enumerated/domain values.
- `tools/g.ssurgo.query/rag/data/SSURGO-Style-Metadata-Unique-Constraints-Report.pdf`
  - Use to confirm uniqueness/constraints when joining or aggregating.
- `tools/g.ssurgo.query/rag/data/SSURGO-Data-Model-Diagram-Part-1_0_0.pdf`
- `tools/g.ssurgo.query/rag/data/SSURGO-Data-Model-Diagram-Part-2.pdf`
  - Use for high-level entity relationships and join paths.
- `tools/g.ssurgo.query/rag/data/ssurgo.pdf`
  - General SSURGO reference included with this repo.

## Repo implementations (follow these constraints)

The SSURGO natural-language → SQL path and guardrails are implemented in:

- `tools/g.ssurgo.query/g.ssurgo.query.py`
  - Expects mapunit geometries to have a `mukey` attribute.
  - Mapunit-level query result shape is expected as `(mukey, value)`.
  - “Series” output expects per-component rows after a `---SERIES---` delimiter.
- `tools/g.ssurgo.query/rag/guards.py`
  - Only SELECT/CTE queries are allowed; no semicolons.
  - Table/column names must exist in the target SSURGO SQLite schema.
  - Allowed join sanity is MU→CO→HZ (see below).
- `tools/g.ssurgo.query/rag/sqlgen.py`
  - Encodes the preferred join path, MUAGGATT preference, and weighting rules.
- `tools/g.ssurgo.query/rag/kb.py`
  - KB building and PDF ingestion logic.

If repo code and a PDF disagree, treat PDFs as authoritative for SSURGO
semantics/units. Treat repo code as authoritative for required output shapes
and safety constraints.

## SSURGO keys and join rules (defaults)

Use these defaults unless the SSURGO PDFs indicate a different relationship for
a specific attribute:

- Map unit key: `mapunit.mukey`
- Component key: `component.cokey`
- Common join paths:
  - Map unit → components: `mapunit.mukey -> component.mukey`
  - Component → horizons: `component.cokey -> chorizon.cokey`

When an attribute exists at map-unit level in `muaggatt.*`, prefer that table
(No Aggregation Necessary) instead of aggregating horizon/component tables.

## Field-definition lookup workflow (do not guess)

When you need to use or explain an SSURGO field:

1. Identify the concept precisely (e.g., “available water capacity”, “Ksat”,
  “hydric rating”), plus the requested scale (map unit, component, horizon,
  or a depth-limited horizon rollup such as “to 100 cm”).
1. Search the PDFs in `tools/g.ssurgo.query/rag/data/` for the exact table and
  column name, units, domains, and caveats. If multiple similarly-named
  fields exist, list the candidates and ask which one to use.
1. Confirm the field exists in the target schema.
  If using local SSURGO SQLite, verify table/column presence.
  If using SDA, ensure the field exists in the SDA SSURGO schema.
1. Decide the join path and aggregation based on the requested scale.
  Use `muaggatt` for MU-level attributes when available.
  For component-weighted MU-level attributes, weight by
  `component.comppct_r/100`.
  For depth-limited horizon rollups, weight horizons by thickness and clip to
  requested depth.
1. If units or definitions are unclear from PDFs, ask a clarifying question.
  Do not fabricate.

## SQL safety and output requirements (for SSURGO querying)

When generating SQL for SSURGO (local SQLite or SDA):

- Allowed statements: `SELECT` and `WITH` (CTEs) only.
- Forbidden: DDL/DML (CREATE/INSERT/UPDATE/DELETE), PRAGMA, semicolons.
- Always qualify columns with their table when ambiguity is possible
  (`table.column`).
- Prefer MU-only outputs when possible.

Output shape requirements (aligned with `g.ssurgo.query`):

- Map-unit result queries must return exactly two columns: `(mukey, value)`.
- For “series” requests, also include a second query after the delimiter
  `---SERIES---` that returns:
  - `(mukey, cokey, compname, comppct_r, value)`

## Clarifying questions to ask (common SSURGO ambiguities)

Ask (briefly) when needed:

- What depth limit should be used (e.g., 30 cm, 100 cm)?
- Do you want MU-level values (one per `mukey`) or per-component/per-horizon
  outputs?
- Which aggregation method is intended (weighted average, dominant component,
  etc.) if not implied?
- Which specific SSURGO field is intended when multiple fields exist with
  similar meaning?

## What not to do

- Do not invent SSURGO column names, units, join keys, or domain values.
- Do not “simplify” by dropping join keys or returning columns that downstream
  tools don’t expect.
- Do not broaden scope beyond SSURGO unless explicitly requested.
