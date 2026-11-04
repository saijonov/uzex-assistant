import pytest
from test_interface import make_service
from test_telegram import message_job

from uzex.interface import greeting
from uzex.models import Answer
from uzex.render import render_answer


@pytest.mark.parametrize(
    "text,key",
    [
        ("rahmat", "thanks"),
        ("Katta rahmat!", "thanks"),
        ("спасибо, понятно", "thanks"),
        ("hello", "greeting"),
        ("hi", "greeting"),
        ("nima qila olasan?", "about"),
        ("sen kimsan?", "about"),
        ("Что ты умеешь?", "about"),
        ("кто ты?", "about"),
    ],
)
def test_small_talk_is_answered_without_the_model(text, key):
    assert greeting(text)[0] == key


async def test_small_talk_reply_is_not_a_data_question(tmp_path, sample_database):
    service = make_service(tmp_path, sample_database)
    result = await service.prepare(message_job("rahmat"))
    assert "Qaysi ma’lumot" not in result["texts"][0]
    capability = await service.prepare(message_job("nima qila olasan?"))
    assert "bitim" in capability["texts"][0].casefold()
    service.state.close()


def test_off_topic_and_unsupported_refusals_explain_themselves():
    off_topic = Answer(outcome="unavailable", language="uz", reason="out_of_scope")
    assert "birja" in render_answer(off_topic)
    missing = Answer(outcome="unavailable", language="ru", reason="missing_field")
    assert "количеств" in render_answer(missing).casefold()
    unsupported = Answer(outcome="unavailable", language="uz", reason="unsupported")
    assert "so‘rash" in render_answer(unsupported)
