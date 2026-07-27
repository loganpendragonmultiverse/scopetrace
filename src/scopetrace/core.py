from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timezone
from typing import Any

PROJECT = "scopetrace"
SCHEMA_VERSION = 2
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
    ids = [str(item.get("id", "")) for item in requirements]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("requirements need unique non-empty ids")
    known = set(ids)
    for item in requirements:
        links = [item.get("parent"), *item.get("depends_on", [])]
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


def _scopetrace(data: dict[str, Any]) -> dict[str, Any]:
    requirements, known = _validate_requirements(_require(data, "requirements"))
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
        rows.append(row)
        by_id[requirement["id"]] = row
    for row in rows:
        row["blocked_by"] = [
            dependency
            for dependency in row.get("depends_on", [])
            if not by_id[dependency]["verified"]
        ]
        if row["blocked_by"]:
            row["verified"] = False
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


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "project": PROJECT, **_scopetrace(data)}


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


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
