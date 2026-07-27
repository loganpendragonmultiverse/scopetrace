# ScopeTrace

[![CI](https://github.com/loganpendragonmultiverse/scopetrace/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/scopetrace/actions/workflows/ci.yml)

Turn requirements, acceptance criteria, dependencies, and supplied evidence into a conservative delivery-state matrix. Version 1.1 prevents a high-level claim from skipping the implementation, merge, configuration, deployment, or verification evidence beneath it.

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
