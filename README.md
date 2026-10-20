# ScopeTrace

[![CI](https://github.com/loganpendragonmultiverse/scopetrace/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/scopetrace/actions/workflows/ci.yml)

Turn requirements, acceptance criteria, dependencies, and supplied evidence into a conservative delivery-state matrix. Version 1.2 evaluates dependencies independently of row order while preserving the contiguous implementation, merge, configuration, deployment and verification evidence gates.

## Three-minute start

```bash
python -m pip install .
scopetrace examples/sample.json
scopetrace examples/sample.json --format csv --output matrix.csv
```

JSON preserves the complete evidence model, Markdown produces a reviewable matrix, and CSV supports project-management import. Existing output files are never overwritten.

## Evidence model

Evidence has a stable ID, requirement ID, delivery state, pass/fail/superseded status, observation date, optional expiration date, source reference, and optional acceptance-criterion ID. Expired evidence cannot advance a requirement. Failed evidence remains visible. Requirements can depend on other requirements and remain blocked until those dependencies are verified.

Supplying a previous ScopeTrace report produces explicit progress and regression transitions. Unknown evidence is retained in a review queue instead of being silently discarded.

## Interpretation boundary

ScopeTrace validates the consistency of supplied evidence; it does not contact GitHub, deployment providers, or other systems and cannot prove that a reference is truthful. A requirement is verified only when its delivery-state evidence is contiguous, its acceptance criteria are satisfied, and its dependencies are verified.

Python 3.10 or newer is supported on Windows, macOS, and Linux with no runtime dependencies, telemetry, account, or hosted service.

## Development

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src
pytest
python -m build
```

Part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/). Licensed under the [MIT License](LICENSE).

## Dependency blockers

Dependencies are evaluated before the requirements that depend on them. Reordering
requirements does not change verification results, and dependency cycles are rejected.
Reports keep the input row order. A row's delivery state describes its own evidence;
its verified flag also requires every dependency to be verified.

For a causal explanation, request JSON or Markdown:

```bash
scopetrace examples/sample.json --explain-blockers --format json
scopetrace examples/sample.json --explain-blockers
```

Each row then includes blocker_explanations. A cause identifies a requirement
missing its own evidence or acceptance criteria, a path to that requirement, the
first missing delivery transition, and unsatisfied criterion IDs. A path containing
only the row itself explains missing evidence on that row. Verified rows have no
causes. Direct unverified dependencies remain in blocked_by.

If several paths lead to the same cause, the report includes one shortest path.
Equal-length paths use lexicographic requirement-ID order. This avoids listing every
path through a diamond-shaped graph. Explanations do not fetch references, establish
their truth, or change the existing treatment of failed, superseded and stale evidence.

The Python API accepts analyze(data, explain_blockers=True). The option is off by
default; ordinary JSON fields, Markdown and CSV columns retain their existing shape.
The CLI rejects --explain-blockers with CSV rather than dropping the explanations.

Explanations are bounded to 100,000 requirement-ID occurrences across all paths in
one report. Exceeding this limit fails before an output file is written; run without
the option or select a smaller input. Default reports do not use this path budget.

## 1.2.1 as-of and publication boundaries

Evidence observed after `as_of` stays visible with `future: true` but cannot advance delivery state, acceptance criteria or current failure summaries. Evidence observed exactly on that date is eligible. Expiry remains inclusive: evidence expiring on `as_of` is still current. Omitted observation dates retain the documented default of `as_of`; this remains supplied evidence rather than independent proof. Past/default report shapes and the existing treatment of failed, superseded and stale records remain intact.

JSON inputs are bounded to 10 MB, with duplicate keys/non-finite constants and symlink paths refused. Malformed roots, criteria, evidence identities and previous snapshots fail clearly. Reports require a distinct new destination with an existing parent; exclusive creation preserves existing or competing files. Markdown matrix cells render literal pipes, line breaks and markup safely. Keep all existing checks/coverage and installed wheel/source acceptance, including observation-date/dependency/criterion boundary fixtures.

JSON inputs reject nesting beyond 128 containers with an actionable error, including parser recursion failures.

Wheel installations include the synthetic example at `<environment>/share/doc/scopetrace/examples/sample.json` (where `<environment>` is the Python installation or virtual-environment prefix). Pass this path to `scopetrace` to run the example outside a source checkout.

JSON numeric overflow (such as `1e400`) is rejected alongside non-finite constants; ordinary finite fractions remain supported.
