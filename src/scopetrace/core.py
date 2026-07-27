from __future__ import annotations

import json
from typing import Any

PROJECT = "scopetrace"


def _require(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    if value is None or value == "" or value == []:
        raise ValueError(f"{key} is required")
    return value


def _scopetrace(data: dict[str, Any]) -> dict[str, Any]:
    states = ["unstarted", "implemented", "merged", "configured", "deployed", "verified"]
    requirements = _require(data, "requirements")
    ids = [item.get("id") for item in requirements]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("requirements need unique non-empty ids")
    rows = []
    for requirement in requirements:
        evidence = [
            item
            for item in data.get("evidence", [])
            if item.get("requirement") == requirement["id"]
        ]
        if any(item.get("state") not in states for item in evidence):
            raise ValueError("evidence contains an invalid state")
        state = (
            max(evidence, key=lambda item: states.index(item["state"]))["state"]
            if evidence
            else "unstarted"
        )
        rows.append(
            {**requirement, "state": state, "evidence": evidence, "verified": state == "verified"}
        )
    return {
        "requirements": rows,
        "unknown_evidence": sorted(
            {item.get("requirement") for item in data.get("evidence", [])} - set(ids)
        ),
    }


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    return {"version": 1, "project": PROJECT, **_scopetrace(data)}


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [f"# {report['project'].replace('-', ' ').title()} report", ""]
    for key, value in report.items():
        if key not in {"version", "project"}:
            lines.append(f"## {key.replace('_', ' ').title()}")
            lines.append("")
            lines.append(f"```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
