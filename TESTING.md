# Testing

Use an isolated environment with Python 3.10 or newer:

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src
pytest
python -m build
```

The existing 90% branch-coverage gate remains enabled. CI covers Python 3.10 and
3.14 on Linux, Windows and macOS; tagged distribution builds use Python 3.12.

## Dependency regression acceptance

- Every ordering of a three-requirement chain gives the same verification result.
  In the original implementation, three of six orderings incorrectly left the
  top dependent verified when the leaf lacked evidence.
- Self-cycles and two/three-node cycles fail even when every node has complete
  evidence. The original implementation accepted fully evidenced cycles.
- Diamond graphs have one explanation per cause. Shortest paths win; equal-length
  paths are tied by requirement ID, independently of row and edge order.
- Missing own transitions, expired evidence and unsatisfied acceptance criteria
  remain visible and propagate through every dependent. Evidence expiring exactly
  on the as-of date keeps the existing inclusive behavior.
- Deep dependency chains do not require recursive graph traversal.
- Default output fields/CSV headers and row order stay compatible; opt-in Markdown
  quotes literal IDs and CSV plus explanations fails before writing an output.
- CLI output safety checks leave source input and existing destinations untouched.

Run focused regressions with pytest tests/test_dependencies.py, followed by the
complete suite and installed-wheel checks. Use supplied fixture data only; do not
fetch or execute evidence references.

- The explanation budget is shared by the entire report, fails before an output is
  written, and does not limit ordinary reports.

- Caller-supplied blocker explanations are ignored in default and opt-in reports;
  mixed rows render safely and fresh evidence-derived causes replace stale data.

## 1.2.1 as-of and publication boundaries

Evidence observed after `as_of` stays visible with `future: true` but cannot advance delivery state, acceptance criteria or current failure summaries. Evidence observed exactly on that date is eligible. Expiry remains inclusive: evidence expiring on `as_of` is still current. Omitted observation dates retain the documented default of `as_of`; this remains supplied evidence rather than independent proof. Past/default report shapes and the existing treatment of failed, superseded and stale records remain intact.

JSON inputs are bounded to 10 MB, with duplicate keys/non-finite constants and symlink paths refused. Malformed roots, criteria, evidence identities and previous snapshots fail clearly. Reports require a distinct new destination with an existing parent; exclusive creation preserves existing or competing files. Markdown matrix cells render literal pipes, line breaks and markup safely. Keep all existing checks/coverage and installed wheel/source acceptance, including observation-date/dependency/criterion boundary fixtures.

JSON inputs reject nesting beyond 128 containers with an actionable error, including parser recursion failures.

Wheel installations include the synthetic example at `<environment>/share/doc/scopetrace/examples/sample.json` (where `<environment>` is the Python installation or virtual-environment prefix). Pass this path to `scopetrace` to run the example outside a source checkout.

JSON numeric overflow (such as `1e400`) is rejected alongside non-finite constants; ordinary finite fractions remain supported.
