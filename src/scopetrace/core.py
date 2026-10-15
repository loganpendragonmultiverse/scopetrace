from __future__ import annotations

import csv
import io
import json
import re
from collections import deque
from datetime import date, datetime, timezone
from heapq import heappop, heappush
from typing import Any

PROJECT = "scopetrace"
SCHEMA_VERSION = 2
MAX_EXPLANATION_PATH_STEPS = 100_000
STATES = ("unstarted", "implemented", "merged", "configured", "deployed", "verified")


def _require(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    if value is None or value == "" or value == []:
        raise ValueError(f"{key} is required")
    return value


def _day(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc


def _validate_requirements(requirements: Any) -> tuple[list[dict[str, Any]], set[str]]:
    if not isinstance(requirements, list) or any(
        not isinstance(item, dict) for item in requirements
    ):
        raise ValueError("requirements must be a list of objects")
    ids = [item.get("id", "") for item in requirements]
    if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("requirements need unique non-empty ids")
    known = set(ids)
    for item in requirements:
        dependencies = item.get("depends_on", [])
        if not isinstance(dependencies, list) or any(
            not isinstance(dependency, str) or not dependency for dependency in dependencies
        ):
            raise ValueError("depends_on must be a list of requirement ids")
        links = [item.get("parent"), *dependencies]
        if any(link and link not in known for link in links):
            raise ValueError("requirement hierarchy references an unknown id")
        criteria = item.get("acceptance_criteria", [])
        criterion_ids = [
            criterion.get("id") for criterion in criteria if isinstance(criterion, dict)
        ]
        if len(criterion_ids) != len(criteria) or any(not value for value in criterion_ids):
            raise ValueError("acceptance criteria need non-empty ids")
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("acceptance criteria ids must be unique within a requirement")
    return requirements, known


def _dependency_order(requirements: list[dict[str, Any]]) -> list[str]:
    """Evaluate prerequisites first without relying on input order or recursion."""
    dependencies = {item["id"]: set(item.get("depends_on", [])) for item in requirements}
    followers: dict[str, list[str]] = {identifier: [] for identifier in dependencies}
    pending = {identifier: len(values) for identifier, values in dependencies.items()}
    for identifier, values in dependencies.items():
        for dependency in values:
            followers[dependency].append(identifier)
    ready = sorted(identifier for identifier, count in pending.items() if not count)
    order = []
    while ready:
        identifier = heappop(ready)
        order.append(identifier)
        for follower in followers[identifier]:
            pending[follower] -= 1
            if not pending[follower]:
                heappush(ready, follower)
    if len(order) != len(requirements):
        raise ValueError("requirement dependency cycle detected")
    return order


def _blocker_explanations(
    identifier: str,
    by_id: dict[str, dict[str, Any]],
    intrinsic: dict[str, bool],
    remaining_steps: int,
) -> tuple[list[dict[str, Any]], int]:
    """Give one shortest, lexicographically tied path per cause within the report budget."""
    queue = deque([identifier])
    parents: dict[str, str | None] = {identifier: None}
    explanations = []
    while queue:
        current = queue.popleft()
        row = by_id[current]
        if not intrinsic[current]:
            path = []
            cursor: str | None = current
            while cursor is not None:
                path.append(cursor)
                cursor = parents[cursor]
            path.reverse()
            remaining_steps -= len(path)
            if remaining_steps < 0:
                raise ValueError(
                    f"blocker explanation path limit ({MAX_EXPLANATION_PATH_STEPS} IDs) exceeded; "
                    "run without --explain-blockers or select a smaller input"
                )
            explanations.append(
                {
                    "path": path,
                    "requirement": current,
                    "missing_transition_evidence": list(row["missing_transition_evidence"]),
                    "unsatisfied_acceptance_criteria": sorted(
                        (
                            criterion["id"]
                            for criterion in row["acceptance_criteria"]
                            if not criterion["satisfied"]
                        ),
                        key=str,
                    ),
                }
            )
        for dependency in sorted(set(row.get("depends_on", []))):
            if not by_id[dependency]["verified"] and dependency not in parents:
                parents[dependency] = current
                queue.append(dependency)
    return sorted(explanations, key=lambda item: item["requirement"]), remaining_steps


def _normalize_evidence(
    items: Any, known: set[str], as_of: date
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("evidence must be a list of objects")
    unknown = sorted(
        {str(item.get("requirement")) for item in items if item.get("requirement") not in known}
    )
    normalized: list[dict[str, Any]] = []
    evidence_ids: set[str] = set()
    for index, item in enumerate(items, 1):
        evidence_id = str(item.get("id", f"EVID-{index}"))
        if evidence_id in evidence_ids:
            raise ValueError("evidence ids must be unique")
        evidence_ids.add(evidence_id)
        state = item.get("state")
        if state not in STATES[1:]:
            raise ValueError("evidence contains an invalid state")
        status = item.get("status", "pass")
        if status not in {"pass", "fail", "superseded"}:
            raise ValueError("evidence contains an invalid status")
        observed = _day(str(item.get("observed_at", as_of.isoformat())), "observed_at")
        expires = _day(str(item["expires_at"]), "expires_at") if item.get("expires_at") else None
        normalized.append(
            {
                **item,
                "id": evidence_id,
                "observed_at": observed.isoformat(),
                "status": status,
                "stale": bool(expires and expires < as_of),
            }
        )
    return normalized, unknown


def _supported_state(evidence: list[dict[str, Any]]) -> tuple[str, list[str]]:
    passing = {
        item["state"]
        for item in evidence
        if item["status"] == "pass" and not item["stale"] and not item.get("criterion")
    }
    supported = "unstarted"
    missing: list[str] = []
    for state in STATES[1:]:
        if state in passing:
            supported = state
        else:
            missing.append(state)
            break
    return supported, missing


def _scopetrace(data: dict[str, Any], *, explain_blockers: bool = False) -> dict[str, Any]:
    requirements, known = _validate_requirements(_require(data, "requirements"))
    order = _dependency_order(requirements)
    as_of = _day(str(data.get("as_of", datetime.now(timezone.utc).date().isoformat())), "as_of")
    evidence, unknown = _normalize_evidence(data.get("evidence", []), known, as_of)
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for requirement in requirements:
        requirement_evidence = [
            item for item in evidence if item.get("requirement") == requirement["id"]
        ]
        state, missing = _supported_state(requirement_evidence)
        criteria = []
        for criterion in requirement.get("acceptance_criteria", []):
            matches = [
                item for item in requirement_evidence if item.get("criterion") == criterion["id"]
            ]
            criteria.append(
                {
                    **criterion,
                    "satisfied": any(
                        item["state"] == "verified"
                        and item["status"] == "pass"
                        and not item["stale"]
                        for item in matches
                    ),
                    "evidence": matches,
                }
            )
        failed = [
            item for item in requirement_evidence if item["status"] == "fail" and not item["stale"]
        ]
        stale = [item["id"] for item in requirement_evidence if item["stale"]]
        row = {
            **requirement,
            "state": state,
            "claimed_state": max(
                (item["state"] for item in requirement_evidence),
                key=STATES.index,
                default="unstarted",
            ),
            "verified": state == "verified" and all(item["satisfied"] for item in criteria),
            "acceptance_criteria": criteria,
            "evidence": requirement_evidence,
            "failed_evidence": failed,
            "stale_evidence": stale,
            "missing_transition_evidence": missing,
            "blocked_by": [],
        }
        # Explanations belong to this report, never to caller-supplied requirement data.
        row.pop("blocker_explanations", None)
        rows.append(row)
        by_id[requirement["id"]] = row
    intrinsic = {identifier: bool(row["verified"]) for identifier, row in by_id.items()}
    for identifier in order:
        row = by_id[identifier]
        row["blocked_by"] = [
            dependency
            for dependency in row.get("depends_on", [])
            if not by_id[dependency]["verified"]
        ]
        if row["blocked_by"]:
            row["verified"] = False
    if explain_blockers:
        remaining_steps = MAX_EXPLANATION_PATH_STEPS
        for row in rows:
            if row["verified"]:
                row["blocker_explanations"] = []
            else:
                explanations, remaining_steps = _blocker_explanations(
                    row["id"], by_id, intrinsic, remaining_steps
                )
                row["blocker_explanations"] = explanations
    previous = data.get("previous", {})
    old_states = {
        item["id"]: item.get("state", "unstarted") for item in previous.get("requirements", [])
    }
    transitions = [
        {
            "requirement": row["id"],
            "from": old_states.get(row["id"], "unstarted"),
            "to": row["state"],
            "regression": STATES.index(row["state"])
            < STATES.index(old_states.get(row["id"], "unstarted")),
        }
        for row in rows
        if old_states.get(row["id"], "unstarted") != row["state"]
    ]
    return {
        "as_of": as_of.isoformat(),
        "requirements": rows,
        "unknown_evidence": unknown,
        "transitions": transitions,
        "summary": {
            "total": len(rows),
            "verified": sum(bool(row["verified"]) for row in rows),
            "blocked": sum(bool(row["blocked_by"]) for row in rows),
            "with_failures": sum(bool(row["failed_evidence"]) for row in rows),
            "with_stale_evidence": sum(bool(row["stale_evidence"]) for row in rows),
        },
    }


def analyze(data: dict[str, Any], *, explain_blockers: bool = False) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "project": PROJECT,
        **_scopetrace(data, explain_blockers=explain_blockers),
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def _code_span(value: str) -> str:
    longest = max((len(match.group()) for match in re.finditer(r"`+", value)), default=0)
    delimiter = chr(96) * (longest + 1)
    normalized = value.replace("\r", " ").replace("\n", " ")
    return f"{delimiter} {normalized} {delimiter}"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# ScopeTrace delivery matrix",
        "",
        "| Requirement | State | Verified | Blocked by |",
        "|---|---|---:|---|",
    ]
    for row in report["requirements"]:
        lines.append(
            f"| {row['id']} — {row.get('text', '')} | {row['state']} | "
            f"{'yes' if row['verified'] else 'no'} | {', '.join(row['blocked_by'])} |"
        )
    lines += ["", "## Summary", "", f"```json\n{json.dumps(report['summary'], indent=2)}\n```", ""]
    if any("blocker_explanations" in row for row in report["requirements"]):
        lines += [
            "## Blocking explanations",
            "",
            "Each cause has one shortest path; equal-length paths use requirement ID order.",
            "",
        ]
        for row in report["requirements"]:
            for cause in row["blocker_explanations"]:
                path = " → ".join(_code_span(value) for value in cause["path"])
                missing = (
                    ", ".join(_code_span(value) for value in cause["missing_transition_evidence"])
                    or "none"
                )
                criteria = (
                    ", ".join(
                        _code_span(str(value)) for value in cause["unsatisfied_acceptance_criteria"]
                    )
                    or "none"
                )
                lines.append(
                    f"- {path}: missing transition {missing}; unsatisfied criteria {criteria}."
                )
        if not any(row["blocker_explanations"] for row in report["requirements"]):
            lines.append("No blocking causes.")
        lines.append("")
    return "\n".join(lines)


def render_csv(report: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("requirement", "text", "state", "claimed_state", "verified", "blocked_by"))
    for row in report["requirements"]:
        writer.writerow(
            (
                row["id"],
                row.get("text", ""),
                row["state"],
                row["claimed_state"],
                str(row["verified"]).lower(),
                ";".join(row["blocked_by"]),
            )
        )
    return output.getvalue()
