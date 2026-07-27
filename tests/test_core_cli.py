import json

import pytest

from scopetrace.cli import main
from scopetrace.core import analyze, render_csv, render_json, render_markdown


def chain(requirement: str, criterion: str | None = None) -> list[dict]:
    items = []
    for index, state in enumerate(
        ("implemented", "merged", "configured", "deployed", "verified"), 1
    ):
        item = {
            "id": f"E-{requirement}-{index}",
            "requirement": requirement,
            "state": state,
            "observed_at": "2026-07-01",
        }
        if criterion and state == "verified":
            item["criterion"] = criterion
        items.append(item)
    return items


def test_verified_chain_criteria_dependencies_and_exports():
    requirements = [
        {
            "id": "REQ-1",
            "text": "Export",
            "acceptance_criteria": [{"id": "AC-1", "text": "Valid JSON"}],
        },
        {"id": "REQ-2", "text": "Deploy", "depends_on": ["REQ-1"]},
    ]
    evidence = (
        chain("REQ-1")
        + [{"id": "AC", "requirement": "REQ-1", "criterion": "AC-1", "state": "verified"}]
        + chain("REQ-2")
    )
    report = analyze({"as_of": "2026-07-27", "requirements": requirements, "evidence": evidence})
    assert report["summary"]["verified"] == 2
    assert report["requirements"][0]["acceptance_criteria"][0]["satisfied"] is True
    assert "REQ-1" in render_markdown(report)
    assert render_csv(report).startswith("requirement,text,state")
    assert '"schema_version": 2' in render_json(report)


def test_missing_transition_stale_failure_unknown_and_blocking():
    requirements = [
        {"id": "A", "text": "A"},
        {"id": "B", "text": "B", "depends_on": ["A"]},
    ]
    evidence = [
        {"id": "late", "requirement": "A", "state": "verified", "status": "fail"},
        {"id": "old", "requirement": "A", "state": "implemented", "expires_at": "2026-01-01"},
        {"id": "unknown", "requirement": "Z", "state": "implemented", "status": "superseded"},
        {"id": "b1", "requirement": "B", "state": "implemented"},
    ]
    report = analyze({"as_of": "2026-07-27", "requirements": requirements, "evidence": evidence})
    assert report["requirements"][0]["state"] == "unstarted"
    assert report["requirements"][1]["blocked_by"] == ["A"]
    assert report["unknown_evidence"] == ["Z"]
    assert report["summary"] == {
        "total": 2,
        "verified": 0,
        "blocked": 1,
        "with_failures": 1,
        "with_stale_evidence": 1,
    }


def test_previous_snapshot_reports_regression_and_progression():
    report = analyze(
        {
            "requirements": [{"id": "A"}, {"id": "B"}],
            "evidence": chain("B")[:2],
            "previous": {"requirements": [{"id": "A", "state": "deployed"}]},
        }
    )
    assert {item["requirement"] for item in report["transitions"]} == {"A", "B"}
    assert (
        next(item for item in report["transitions"] if item["requirement"] == "A")["regression"]
        is True
    )


@pytest.mark.parametrize(
    "data,message",
    [
        ({}, "requirements is required"),
        ({"requirements": "bad"}, "list of objects"),
        ({"requirements": [{"id": "A"}, {"id": "A"}]}, "unique"),
        ({"requirements": [{"id": "A", "depends_on": ["B"]}]}, "unknown id"),
        ({"requirements": [{"id": "A", "acceptance_criteria": ["bad"]}]}, "criteria need"),
        (
            {"requirements": [{"id": "A", "acceptance_criteria": [{"id": "X"}, {"id": "X"}]}]},
            "must be unique",
        ),
        ({"requirements": [{"id": "A"}], "evidence": "bad"}, "evidence must"),
        (
            {"requirements": [{"id": "A"}], "evidence": [{"requirement": "A", "state": "bogus"}]},
            "invalid state",
        ),
        (
            {
                "requirements": [{"id": "A"}],
                "evidence": [{"requirement": "A", "state": "implemented", "status": "bogus"}],
            },
            "invalid status",
        ),
        (
            {
                "requirements": [{"id": "A"}],
                "evidence": [
                    {"id": "X", "requirement": "A", "state": "implemented"},
                    {"id": "X", "requirement": "A", "state": "merged"},
                ],
            },
            "ids must be unique",
        ),
        ({"as_of": "bad", "requirements": [{"id": "A"}]}, "ISO date"),
    ],
)
def test_invalid_models(data, message):
    with pytest.raises(ValueError, match=message):
        analyze(data)


def test_cli_formats_and_output_safety(tmp_path, capsys):
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"requirements": [{"id": "A", "text": "A"}]}), encoding="utf-8")
    assert main([str(source), "--format", "csv"]) == 0
    assert "requirement,text" in capsys.readouterr().out
    output = tmp_path / "report.json"
    assert main([str(source), "--format", "json", "--output", str(output)]) == 0
    assert main([str(source), "--output", str(output)]) == 2
