import sys
import textwrap

from devin_janitor.inventory import SessionRow
from devin_janitor.judge import (
    CommandJudge,
    NoneJudge,
    OllamaJudge,
    _parse_verdict_text,
    make_judge,
)


def row() -> SessionRow:
    return SessionRow(
        id="s", origin="cli", title="t", project="/p",
        created=0.0, last_activity=0.0, prompt="hello",
    )


def test_none_judge_abstains():
    j = make_judge("none")
    assert isinstance(j, NoneJudge)
    v = j.judge(row(), "statement")
    assert v.keep is None  # abstain → caller keeps the session


def test_make_judge_specs():
    assert make_judge(None).name == "none"
    assert make_judge("command:echo keep").name == "command"
    j = make_judge("ollama:llama3@http://h:1")
    assert isinstance(j, OllamaJudge)
    assert j.model == "llama3" and j.host == "http://h:1"
    import pytest

    with pytest.raises(ValueError):
        make_judge("bogus")


def test_command_judge_parses_verdict(tmp_path):
    script = tmp_path / "judge.py"
    script.write_text(
        textwrap.dedent(
            """
            import sys, json
            payload = json.loads(sys.stdin.read())
            print(json.dumps({"keep": False, "why": "noise"}))
            """
        ),
        encoding="utf-8",
    )
    j = CommandJudge(f'"{sys.executable}" "{script}"')
    v = j.judge(row(), "statement")
    assert v.keep is False  # explicit delete verdict


def test_command_judge_fail_open_on_nonzero_exit():
    j = CommandJudge(f'"{sys.executable}" -c "import sys; sys.exit(1)"')
    v = j.judge(row(), "statement")
    assert v.keep is None  # fail-open


def test_command_judge_fail_open_on_bad_command():
    j = CommandJudge("definitely-not-a-real-binary-xyz123")
    v = j.judge(row(), "statement")
    assert v.keep is None


def test_ollama_unavailable_when_no_server():
    # Nothing should be listening on this port → available() is False
    j = OllamaJudge(host="http://127.0.0.1:9")
    assert j.available() is False


def test_ollama_judge_fail_open_when_down():
    j = OllamaJudge(host="http://127.0.0.1:9", timeout=1)
    v = j.judge(row(), "statement")
    assert v.keep is None


def test_parse_verdict_text():
    assert _parse_verdict_text('{"keep": false}') is False
    assert _parse_verdict_text('{"value": true}') is True
    assert _parse_verdict_text('{"abstained": true}') is None
    assert _parse_verdict_text("DELETE") is False
    assert _parse_verdict_text("keep") is True
    assert _parse_verdict_text("hmm not sure") is None
