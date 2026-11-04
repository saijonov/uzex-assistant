import json
from pathlib import Path


def test_evaluation_has_both_languages_and_safety_coverage():
    main = json.loads(Path("evaluation/cases.json").read_text())
    challenge = json.loads(Path("evaluation/challenge.json").read_text())
    assert len(main) >= 100
    assert len(challenge) >= 30
    for cases in (main, challenge):
        assert {case["language"] for case in cases} == {"uz", "ru"}
        assert len({case["id"] for case in cases}) == len(cases)
        assert any(case["category"] == "safety" for case in cases)
