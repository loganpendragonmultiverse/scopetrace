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
