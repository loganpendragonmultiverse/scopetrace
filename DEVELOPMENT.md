# Development contract

Turn explicit requirements and evidence into a delivery-state matrix without overstating completion.

Preserve deterministic, source-safe behavior and the interpretation boundary documented in the README. Every feature release must update tests, version metadata, `CHANGELOG.md`, README claims and limitations, repository metadata, release assets, and the Forge catalog together.

## Dependency evaluation and explanations

Version 1.2.0 corrects input-order-dependent verification: a completely evidenced
dependent must stay unverified when a transitive prerequisite lacks evidence.
Validate dependency cycles before evaluation and traverse prerequisites without
Python recursion, while retaining input row order and existing evidence eligibility.

--explain-blockers adds causal evidence only when requested. Include one shortest
path per independently unverified requirement, with lexicographic tie breaking.
Keep missing own evidence and unsatisfied acceptance criteria distinct from direct
dependency IDs. Preserve the default report schema and CSV columns.

Run the full checks in TESTING.md. Publication remains a separate protected merge,
tag/artifact and Forge reconciliation step after independent review.

Causal traversal stores parent links rather than copying paths into the work queue.
Materialized paths have a report-wide 100,000-ID budget; exceeding it fails clearly
before CLI output publication. The default verification path has no explanation budget.

## 1.2.1 as-of and publication boundaries

Evidence observed after `as_of` stays visible with `future: true` but cannot advance delivery state, acceptance criteria or current failure summaries. Evidence observed exactly on that date is eligible. Expiry remains inclusive: evidence expiring on `as_of` is still current. Omitted observation dates retain the documented default of `as_of`; this remains supplied evidence rather than independent proof. Past/default report shapes and the existing treatment of failed, superseded and stale records remain intact.

JSON inputs are bounded to 10 MB, with duplicate keys/non-finite constants and symlink paths refused. Malformed roots, criteria, evidence identities and previous snapshots fail clearly. Reports require a distinct new destination with an existing parent; exclusive creation preserves existing or competing files. Markdown matrix cells render literal pipes, line breaks and markup safely. Keep all existing checks/coverage and installed wheel/source acceptance, including observation-date/dependency/criterion boundary fixtures.

JSON inputs reject nesting beyond 128 containers with an actionable error, including parser recursion failures.

Wheel installations include the synthetic example at `<environment>/share/doc/scopetrace/examples/sample.json` (where `<environment>` is the Python installation or virtual-environment prefix). Pass this path to `scopetrace` to run the example outside a source checkout.

JSON numeric overflow (such as `1e400`) is rejected alongside non-finite constants; ordinary finite fractions remain supported.
