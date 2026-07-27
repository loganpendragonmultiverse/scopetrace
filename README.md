# ScopeTrace

[![CI](https://github.com/loganpendragonmultiverse/scopetrace/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/scopetrace/actions/workflows/ci.yml)

Turn explicit requirements and evidence into a delivery-state matrix without overstating completion. The command runs locally, uses explicit UTF-8 JSON input, and produces deterministic JSON or Markdown reports without modifying the supplied source material.

## Three-minute start

```bash
python -m pip install .
scopetrace examples/sample.json
scopetrace examples/sample.json --format json --output report.json
```

The example documents the complete v1 input shape. Markdown is intended for immediate review; JSON preserves structured evidence for scripts and later comparison. An existing output file is never overwritten.

## Privacy and platforms

All requirements and evidence stay local.

Python 3.10 or newer is supported on Windows, macOS, and Linux. The package has no runtime dependencies, telemetry, account, or hosted service.

## Interpretation boundary

ScopeTrace reports the strongest state supported by supplied evidence. It does not inspect deployment providers or independently validate that evidence is truthful.

## Development

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src
pytest
python -m build
```

The project is feature-complete for its documented v1 scope. Maintenance focuses on correctness, security, compatibility, and well-supported input improvements.

Part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/). Licensed under the [MIT License](LICENSE).
