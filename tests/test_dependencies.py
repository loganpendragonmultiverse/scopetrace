import json
from copy import deepcopy
from itertools import permutations

import pytest

from scopetrace import core
from scopetrace.cli import main
from scopetrace.core import analyze, render_csv, render_markdown

STATES = ("implemented", "merged", "configured", "deployed", "verified")


def evidence_for(*ids):
    return [
        {
            "id": f"{requirement}-{state}",
            "requirement": requirement,
            "state": state,
            "observed_at": "2026-10-01",
        }
        for requirement in ids
        for state in STATES
    ]


def model(requirements, evidence):
    return {"as_of": "2026-10-15", "requirements": requirements, "evidence": evidence}


def rows(report):
    return {row["id"]: row for row in report["requirements"]}


@pytest.mark.parametrize("order", list(permutations(("A", "B", "C"))))
def test_chain_is_independent_of_requirement_order(order):
    definitions = {
        "A": {"id": "A", "depends_on": ["B"]},
        "B": {"id": "B", "depends_on": ["C"]},
        "C": {"id": "C"},
    }
    data = model([definitions[key] for key in order], evidence_for("A", "B"))
    original = deepcopy(data)
    report = analyze(data)
    by_id = rows(report)
    assert not any(row["verified"] for row in by_id.values())
    assert by_id["A"]["blocked_by"] == ["B"]
    assert by_id["B"]["blocked_by"] == ["C"]
    assert by_id["C"]["blocked_by"] == []
    assert [row["id"] for row in report["requirements"]] == list(order)
    assert report["summary"]["verified"] == 0
    assert data == original


@pytest.mark.parametrize(
    "dependencies",
    [
        {"A": ["A"]},
        {"A": ["B"], "B": ["A"]},
        {"A": ["B"], "B": ["C"], "C": ["A"]},
    ],
)
def test_dependency_cycles_are_rejected_even_with_complete_evidence(dependencies):
    data = model(
        [{"id": key, "depends_on": value} for key, value in dependencies.items()],
        evidence_for(*dependencies),
    )
    with pytest.raises(ValueError, match="dependency cycle"):
        analyze(data)


def test_diamond_explanations_are_order_independent_and_deduplicate_causes():
    definitions = {
        "A": {"id": "A", "depends_on": ["C", "B"]},
        "B": {"id": "B", "depends_on": ["D"]},
        "C": {"id": "C", "depends_on": ["D"]},
        "D": {"id": "D"},
    }
    expected = None
    for order in permutations(definitions):
        result = rows(
            analyze(
                model([definitions[key] for key in order], evidence_for("A", "B", "C")),
                explain_blockers=True,
            )
        )
        causes = result["A"]["blocker_explanations"]
        assert causes == [
            {
                "path": ["A", "B", "D"],
                "requirement": "D",
                "missing_transition_evidence": ["implemented"],
                "unsatisfied_acceptance_criteria": [],
            }
        ]
        normalized = {
            key: (row["verified"], row["blocker_explanations"]) for key, row in result.items()
        }
        expected = normalized if expected is None else expected
        assert normalized == expected
    definitions["A"]["depends_on"].reverse()
    assert (
        rows(
            analyze(
                model(list(definitions.values()), evidence_for("A", "B", "C")),
                explain_blockers=True,
            )
        )["A"]["blocker_explanations"]
        == causes
    )


def test_shortest_causal_path_wins_and_own_missing_evidence_stays_visible():
    requirements = [
        {"id": "A", "depends_on": ["B", "D"]},
        {"id": "B", "depends_on": ["D"]},
        {"id": "D"},
    ]
    result = rows(analyze(model(requirements, evidence_for("B")), explain_blockers=True))
    assert [cause["path"] for cause in result["A"]["blocker_explanations"]] == [["A"], ["A", "D"]]
    assert result["D"]["blocker_explanations"][0]["path"] == ["D"]


def test_expired_acceptance_evidence_blocks_every_dependent_at_explicit_boundary():
    requirements = [
        {"id": "A", "depends_on": ["B"]},
        {"id": "B", "depends_on": ["C"]},
        {"id": "C", "acceptance_criteria": [{"id": "AC"}]},
    ]
    evidence = evidence_for("A", "B", "C") + [
        {
            "id": "criterion",
            "requirement": "C",
            "criterion": "AC",
            "state": "verified",
            "observed_at": "2026-10-01",
            "expires_at": "2026-10-14",
        }
    ]
    result = rows(analyze(model(requirements, evidence), explain_blockers=True))
    assert not any(row["verified"] for row in result.values())
    assert result["A"]["blocker_explanations"] == [
        {
            "path": ["A", "B", "C"],
            "requirement": "C",
            "missing_transition_evidence": [],
            "unsatisfied_acceptance_criteria": ["AC"],
        }
    ]
    evidence[-1]["expires_at"] = "2026-10-15"
    fresh = rows(analyze(model(requirements, evidence), explain_blockers=True))
    assert all(row["verified"] and row["blocker_explanations"] == [] for row in fresh.values())


def test_completed_dependency_chain_and_default_schema_stay_compatible():
    requirements = [{"id": "A", "depends_on": ["B"]}, {"id": "B"}]
    for order in permutations(requirements):
        report = analyze(model(list(order), evidence_for("A", "B")))
        assert report["schema_version"] == 2
        assert report["summary"]["verified"] == 2
        assert all("blocker_explanations" not in row for row in report["requirements"])
        assert "Blocking explanations" not in render_markdown(report)
        assert render_csv(report).splitlines()[0] == (
            "requirement,text,state,claimed_state,verified,blocked_by"
        )


def test_all_verified_explanations_render_without_causes():
    report = analyze(model([{"id": "OK"}], evidence_for("OK")), explain_blockers=True)
    assert "No blocking causes." in render_markdown(report)


def test_explanations_handle_disconnected_requirements_duplicate_edges_and_failures():
    requirements = [{"id": "A", "depends_on": ["B", "B"]}, {"id": "B"}, {"id": "OK"}]
    evidence = evidence_for("OK") + [
        {"id": "failure", "requirement": "B", "state": "implemented", "status": "fail"},
        {"id": "superseded", "requirement": "B", "state": "merged", "status": "superseded"},
    ]
    result = rows(analyze(model(requirements, evidence), explain_blockers=True))
    assert result["A"]["blocked_by"] == ["B", "B"]
    assert [cause["requirement"] for cause in result["A"]["blocker_explanations"]] == ["A", "B"]
    assert result["B"]["failed_evidence"][0]["id"] == "failure"
    assert result["OK"]["verified"] and result["OK"]["blocker_explanations"] == []


@pytest.mark.parametrize("dependency", ["B", None, [None], [["B"]], [""]])
def test_malformed_dependency_lists_are_actionable(dependency):
    with pytest.raises(ValueError, match="depends_on"):
        analyze(model([{"id": "A", "depends_on": dependency}, {"id": "B"}], []))


def test_dependency_ordering_does_not_require_recursive_traversal():
    requirements = [{"id": str(i), "depends_on": [str(i + 1)]} for i in range(1199)]
    requirements.append({"id": "1199"})
    report = analyze(model(requirements, []))
    assert report["summary"]["verified"] == 0
    assert report["summary"]["blocked"] == 1199


def test_opt_in_cli_explanations_and_csv_rejection_preserve_outputs(tmp_path, capsys):
    source = tmp_path / "model.json"
    source.write_text(
        json.dumps(model([{"id": "A", "depends_on": ["B"]}, {"id": "B"}], evidence_for("A"))),
        encoding="utf-8",
    )
    original = source.read_bytes()
    assert main([str(source), "--explain-blockers", "--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert rows(report)["A"]["blocker_explanations"][0]["path"] == ["A", "B"]
    assert main([str(source), "--explain-blockers"]) == 0
    text = capsys.readouterr().out
    assert "Blocking explanations" in text and "implemented" in text
    output = tmp_path / "unchanged.csv"
    output.write_text("existing", encoding="utf-8")
    assert (
        main([str(source), "--explain-blockers", "--format", "csv", "--output", str(output)]) == 2
    )
    assert "JSON or Markdown" in capsys.readouterr().err
    assert output.read_text() == "existing"
    assert source.read_bytes() == original


def test_markdown_explanations_quote_literal_identifiers():
    identifier = "A" + chr(96) + "<em>"
    report = analyze(model([{"id": identifier}], []), explain_blockers=True)
    text = render_markdown(report)
    section = text.split("## Blocking explanations", 1)[1]
    assert chr(96) * 2 + " " + identifier + " " + chr(96) * 2 in section


def test_explanation_budget_is_report_wide_and_never_changes_default_results(
    tmp_path, capsys, monkeypatch
):
    data = model(
        [{"id": "A", "depends_on": ["B"]}, {"id": "B", "depends_on": ["C"]}, {"id": "C"}],
        evidence_for("A", "B"),
    )
    monkeypatch.setattr(core, "MAX_EXPLANATION_PATH_STEPS", 3)
    with pytest.raises(ValueError, match="path limit"):
        analyze(data, explain_blockers=True)
    assert analyze(data)["summary"]["verified"] == 0
    source = tmp_path / "input.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / "report.json"
    assert (
        main([str(source), "--explain-blockers", "--format", "json", "--output", str(output)]) == 2
    )
    assert "path limit" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("supplied", [[], [{"path": ["OLD"]}], None, "stale"])
@pytest.mark.parametrize("mixed", [False, True])
def test_caller_explanations_are_output_owned(supplied, mixed):
    requirements = [{"id": "A", "blocker_explanations": supplied}]
    if mixed:
        requirements.append({"id": "B"})
    data = model(requirements, [])
    original = deepcopy(data)
    default = analyze(data)
    assert all("blocker_explanations" not in row for row in default["requirements"])
    assert "Blocking explanations" not in render_markdown(default)
    assert "No blocking causes." not in render_markdown(default)
    explained = analyze(data, explain_blockers=True)
    for row in explained["requirements"]:
        assert row["blocker_explanations"] == [
            {
                "path": [row["id"]],
                "requirement": row["id"],
                "missing_transition_evidence": ["implemented"],
                "unsatisfied_acceptance_criteria": [],
            }
        ]
    markdown = render_markdown(explained)
    assert "Blocking explanations" in markdown
    assert "No blocking causes." not in markdown
    assert "OLD" not in markdown
    assert data == original


def test_supplied_explanations_do_not_override_verified_result():
    data = model([{"id": "A", "blocker_explanations": [{"path": ["OLD"]}]}], evidence_for("A"))
    report = analyze(data, explain_blockers=True)
    assert report["requirements"][0]["blocker_explanations"] == []
    assert "No blocking causes." in render_markdown(report)
