import json
from copy import deepcopy
from pathlib import Path

import pytest

from scopetrace import _io
from scopetrace.cli import main
from scopetrace.core import analyze, render_markdown

STATES = ("implemented", "merged", "configured", "deployed", "verified")


def model():
    return {
        "as_of": "2026-10-20",
        "requirements": [{"id": "A"}],
        "evidence": [
            {"id": s, "requirement": "A", "state": s, "observed_at": "2026-10-20"} for s in STATES
        ],
    }


@pytest.mark.parametrize("root", [[], None, "bad", 4])
def test_invalid_roots_are_actionable(tmp_path, root):
    source = tmp_path / "model.json"
    source.write_text(json.dumps(root))
    assert main([str(source)]) == 2


@pytest.mark.parametrize(
    "patch",
    [
        {"parent": {}},
        {"text": []},
        {"acceptance_criteria": None},
        {"acceptance_criteria": [{"id": {"bad": 1}}]},
    ],
)
def test_malformed_requirement_fields(patch):
    data = model()
    data["requirements"][0].update(patch)
    with pytest.raises((TypeError, ValueError)):
        analyze(data)


@pytest.mark.parametrize(
    "patch",
    [{"requirement": {}}, {"criterion": []}, {"id": None}, {"status": []}, {"observed_at": "bad"}],
)
def test_malformed_evidence_fields(patch):
    data = model()
    data["evidence"][0].update(patch)
    with pytest.raises((TypeError, ValueError)):
        analyze(data)


@pytest.mark.parametrize(
    "previous",
    [
        None,
        [],
        {"requirements": None},
        {"requirements": [None]},
        {"requirements": [{"id": "A", "state": "bad"}]},
        {"requirements": [{"id": "A"}, {"id": "A"}]},
    ],
)
def test_malformed_previous_snapshots(previous):
    data = model()
    data["previous"] = previous
    with pytest.raises((TypeError, ValueError), match="previous"):
        analyze(data)


def test_future_transition_does_not_advance_or_verify_dependents():
    data = model()
    data["requirements"].append({"id": "B", "depends_on": ["A"]})
    data["evidence"] += [{"id": "B-" + s, "requirement": "B", "state": s} for s in STATES]
    data["evidence"][-1]["future"] = True  # caller flag cannot override its actual date
    data["evidence"][0]["observed_at"] = "2026-10-21"
    before = deepcopy(data)
    report = analyze(data, explain_blockers=True)
    first, second = report["requirements"]
    assert not first["verified"] and first["state"] == "unstarted"
    assert first["evidence"][0]["future"] is True
    assert second["blocked_by"] == ["A"] and not second["verified"]
    assert "future" not in second["evidence"][-1]
    assert second["blocker_explanations"][0]["requirement"] == "A"
    assert data == before
    data["as_of"] = "2026-10-21"
    assert analyze(data)["summary"]["verified"] == 2


def test_future_criterion_failure_and_expiry_boundaries():
    data = model()
    data["requirements"][0]["acceptance_criteria"] = [{"id": "AC"}]
    data["evidence"] += [
        {
            "id": "criterion",
            "requirement": "A",
            "criterion": "AC",
            "state": "verified",
            "observed_at": "2026-10-21",
        },
        {
            "id": "failure",
            "requirement": "A",
            "state": "verified",
            "status": "fail",
            "observed_at": "2026-10-21",
        },
    ]
    row = analyze(data)["requirements"][0]
    assert not row["verified"] and not row["acceptance_criteria"][0]["satisfied"]
    assert row["failed_evidence"] == []
    data["as_of"] = "2026-10-21"
    for item in data["evidence"]:
        item["expires_at"] = "2026-10-21"
    row = analyze(data)["requirements"][0]
    assert row["verified"] and len(row["failed_evidence"]) == 1
    assert row["stale_evidence"] == []
    data["as_of"] = "2026-10-22"
    assert not analyze(data)["requirements"][0]["verified"]


def test_literal_markdown_cells_and_example():
    data = model()
    data["requirements"][0]["text"] = "literal | column\n<script>"
    rendered = render_markdown(analyze(data))
    assert "literal &#124; column &lt;script&gt;" in rendered
    example = Path(__file__).parents[1] / "examples/sample.json"
    assert main([str(example)]) == 0


def test_json_and_read_boundaries(tmp_path, monkeypatch):
    path = tmp_path / "input.json"
    for text in ['{"requirements":[],"requirements":[]}', '{"number":NaN}']:
        path.write_text(text)
        assert main([str(path)]) == 2
    monkeypatch.setattr(_io, "MAX_INPUT_BYTES", 64)
    path.write_bytes(b"x" * 65)
    assert main([str(path)]) == 2
    path.write_bytes(b"\xff")
    assert main([str(path)]) == 2


def test_output_race_missing_parent_and_symlink(tmp_path, monkeypatch):
    path = tmp_path / "model.json"
    path.write_text(json.dumps(model()))
    output = tmp_path / "report.json"
    assert main([str(path), "--output", str(tmp_path / "missing" / "report")]) == 2
    original = Path.open

    def race(candidate, mode="r", *args, **kwargs):
        if candidate == output and mode == "x":
            with original(candidate, "w", encoding="utf-8") as handle:
                handle.write("other writer")
        return original(candidate, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", race)
    assert main([str(path), "--output", str(output)]) == 2
    assert output.read_text() == "other writer"
    absent = tmp_path / "absent"
    link = tmp_path / "link.json"
    try:
        link.symlink_to(absent)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    assert main([str(path), "--output", str(link)]) == 2
    assert not absent.exists() and link.is_symlink()
    with pytest.raises(ValueError):
        _io.write_new(link, "preserve")
    with pytest.raises(ValueError):
        _io.preflight([output, output])


@pytest.mark.parametrize("depth", [129, 1100], ids=["bounded-depth", "parser-depth"])
def test_nested_json_returns_actionable_error(tmp_path, capsys, depth):
    path = tmp_path / "input.json"
    path.write_text("[" * depth + "0" + "]" * depth)
    assert main([str(path)]) == 2
    assert "nesting" in capsys.readouterr().err


def test_markdown_requirement_fields_render_links_emphasis_and_code_literally():
    data = model()
    text = r"[review](https://example.test/) **VERIFIED** `code` \path"
    data["requirements"][0]["text"] = text
    rendered = render_markdown(analyze(data))
    assert r"\[review\]\(https://example.test/\) \*\*VERIFIED\*\* \`code\` \\path" in rendered
    data["requirements"][0]["id"] = text
    data["evidence"] = []
    assert r"\[review\]\(https://example.test/\)" in render_markdown(analyze(data))


def test_finite_json_fractions_remain_supported(tmp_path):
    path = tmp_path / "finite.json"
    path.write_text('{"fraction":1.25,"tiny":1e-10}')
    assert _io.load_json(path) == {"fraction": 1.25, "tiny": 1e-10}


@pytest.mark.parametrize("number", ["1e400", "-1e400"])
def test_overflow_in_evidence_extensions_cannot_emit_infinity(tmp_path, capsys, number):
    path = tmp_path / "model.json"
    path.write_text(
        '{"requirements":[{"id":"A"}],"evidence":[{"id":"E","requirement":"A","state":"implemented","extra":'
        + number
        + "}]}"
    )
    assert main([str(path), "--format", "json"]) == 2
    output = capsys.readouterr()
    assert "numbers must be finite" in output.err and not output.out
