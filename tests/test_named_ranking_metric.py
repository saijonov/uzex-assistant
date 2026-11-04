import pytest
from test_answer_fit import detail_review

from uzex.policy import missing_requirements


@pytest.mark.parametrize(
    "question",
    [
        "Garov foizi eng yuqori shartnoma qaysi?",
        "У какого контракта самый высокий залог?",
        "Eng yuqori narxli tovar qaysi?",
        "Какой регион с самой большой средней суммой?",
    ],
)
@pytest.mark.parametrize("ranking_by", ["missing", "not_needed"])
def test_a_named_metric_needs_no_ranking_question(question, ranking_by):
    review = detail_review(
        task="rank", subject="contract", ranking_by=ranking_by, missing_fields=["ranking"]
    )
    assert missing_requirements(review, question, [], None) == []


def test_the_model_can_say_another_metric_was_named():
    review = detail_review(task="rank", subject="contract", ranking_by="other")
    assert missing_requirements(review, "Eng zo'r shartnoma", [], None) == []


@pytest.mark.parametrize("question", ["Eng yaxshi broker?", "Какой брокер лучший?"])
def test_a_vague_ranking_still_asks(question):
    review = detail_review(task="rank", subject="broker", ranking_by="missing")
    assert missing_requirements(review, question, [], None) == ["ranking"]
