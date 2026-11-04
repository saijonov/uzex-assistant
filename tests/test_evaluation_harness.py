import json
from pathlib import Path

import pytest
from test_engine import ScriptedClient, finish, review

from uzex.config import Settings
from uzex.engine import Engine
from uzex.evaluate import evaluate, evaluate_conversations, grade_turn

CASES = Path("evaluation/hard.json")


def shown(text="", outcome="answer", language="uz", files=None, sql=None, rows=None):
    return {
        "text": text,
        "outcome": outcome,
        "language": language,
        "files": files or [],
        "sql": sql,
        "rows": rows or [],
    }


def test_number_is_found_in_the_text_the_user_reads():
    turn = {"outcomes": ["answer"], "in_text": ["115763"]}
    assert grade_turn(turn, shown("Yozuvlar soni: 115 763")) == []
    assert grade_turn(turn, shown("Yozuvlar soni: 99 306"))


def test_a_value_hidden_in_evidence_but_not_shown_fails():
    turn = {"outcomes": ["answer"], "in_text": ["BK111"]}
    assert grade_turn(turn, shown("Yozuvlar soni: 32 422", rows=[{"broker_code": "BK111"}]))


def test_wrong_outcome_and_language_fail():
    turn = {"outcomes": ["answer"], "language": "ru"}
    assert grade_turn(turn, shown(outcome="clarify", language="ru"))
    assert grade_turn(turn, shown(language="uz"))
    assert grade_turn(turn, shown(language="ru")) == []


def test_forbidden_text_fails():
    turn = {"outcomes": ["answer"], "not_in_text": ["2 025"]}
    assert grade_turn(turn, shown("yil: 2 025"))
    assert grade_turn(turn, shown("yil: 2025")) == []


def test_file_expectations_are_exact():
    wants = {"outcomes": ["answer"], "file_rows": 120}
    assert grade_turn(wants, shown(files=[120])) == []
    assert grade_turn(wants, shown(files=[100]))
    assert grade_turn(wants, shown())
    declines = {"outcomes": ["answer"], "no_file": True}
    assert grade_turn(declines, shown(files=[5]))
    assert grade_turn(declines, shown()) == []


def test_follow_up_must_use_every_previous_record():
    turn = {"outcomes": ["answer"], "uses_previous_ids": True}
    previous = shown(rows=[{"deal_id": "100001"}, {"deal_id": "100002"}])
    good = shown(sql="SELECT 1 WHERE deal_id IN ('100001', '100002')")
    bad = shown(sql="SELECT 1 WHERE deal_id IN ('100001')")
    assert grade_turn(turn, good, previous) == []
    assert grade_turn(turn, bad, previous)


def test_same_question_must_not_repeat_in_a_conversation():
    turn = {"outcomes": ["clarify", "answer"], "differs_from_previous": True}
    previous = shown("Qaysi davr uchun?", outcome="clarify")
    assert grade_turn(turn, shown("Qaysi davr uchun?", outcome="clarify"), previous)
    assert grade_turn(turn, shown("Boshqa savol", outcome="clarify"), previous) == []


async def test_single_questions_use_the_production_language_path(tmp_path, sample_database):
    client = ScriptedClient(
        [("query_registry", {"sql": "SELECT COUNT(*) AS n FROM registry"}), finish()]
    )
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            [
                {
                    "id": "c",
                    "category": "x",
                    "language": "ru",
                    "question": "Сколько сделок?",
                    "outcomes": ["answer"],
                    "expected_values": ["27"],
                }
            ]
        )
    )
    engine = Engine(Settings(_env_file=None), client, sample_database)
    summary = await evaluate(engine, cases, tmp_path / "out.json")
    assert summary["passed"] == 1
    assert "override from the caller is: none" in client.requests[0]["instructions"]


async def test_conversations_run_through_the_real_service(tmp_path, sample_database):
    client = ScriptedClient(
        [
            ("query_registry", {"sql": "SELECT broker_code FROM brokers ORDER BY broker_code"}),
            finish(),
            review(reference="context"),
            ("about_previous_result", {"language": "ru", "topic": "completeness"}),
        ]
    )
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            [
                {
                    "id": "brokers",
                    "category": "critical",
                    "turns": [
                        {
                            "q": "Все брокеры",
                            "outcomes": ["answer"],
                            "language": "ru",
                            "file_rows": 120,
                        },
                        {"q": "это всё?", "outcomes": ["about"], "in_text": ["120"]},
                        {"q": "спасибо", "outcomes": [None], "in_text": ["Пожалуйста"]},
                    ],
                }
            ]
        )
    )
    engine = Engine(Settings(_env_file=None), client, sample_database)
    output = tmp_path / "out.json"
    summary = await evaluate_conversations(engine, cases, output)
    assert summary["passed"] == 1, summary
    assert summary["turns"] == 3
    assert json.loads(output.read_text())["failures"] == []


async def test_a_failed_turn_fails_its_conversation_and_names_why(tmp_path, sample_database):
    client = ScriptedClient(
        [("query_registry", {"sql": "SELECT COUNT(*) AS n FROM registry"}), finish()]
    )
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            [
                {
                    "id": "wrong",
                    "category": "critical",
                    "turns": [
                        {"q": "Сколько?", "outcomes": ["answer"], "in_text": ["999999"]},
                    ],
                }
            ]
        )
    )
    engine = Engine(Settings(_env_file=None), client, sample_database)
    summary = await evaluate_conversations(engine, cases, tmp_path / "out.json")
    assert summary["passed"] == 0
    assert summary["failures"][0]["id"] == "wrong"
    assert "999999" in summary["failures"][0]["problems"][0]


def test_hard_cases_cover_what_the_old_sets_never_tested():
    cases = json.loads(CASES.read_text())
    turns = [turn for case in cases for turn in case["turns"]]
    assert len({case["id"] for case in cases}) == len(cases)
    assert sum(len(case["turns"]) > 1 for case in cases) >= 20
    assert any(turn.get("uses_previous_ids") for turn in turns)
    assert any(turn.get("file_rows") for turn in turns)
    assert any(turn.get("no_file") for turn in turns)
    assert any("about" in turn["outcomes"] for turn in turns)
    assert {turn.get("language") for turn in turns} >= {"uz", "ru"}
    categories = {case["category"] for case in cases}
    assert "critical" in categories
    critical = [case for case in cases if case["category"] == "critical"]
    assert 8 <= len(critical) <= 20


@pytest.mark.parametrize("field", ["in_text", "not_in_text"])
def test_hard_case_expectations_are_text_lists(field):
    for case in json.loads(CASES.read_text()):
        for turn in case["turns"]:
            assert isinstance(turn.get(field, []), list)
            assert "q" in turn and turn["outcomes"]
