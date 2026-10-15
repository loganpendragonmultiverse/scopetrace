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
