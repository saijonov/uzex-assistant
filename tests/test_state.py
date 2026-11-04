import json

from uzex.state import State


def test_duplicate_updates_are_not_processed_twice(tmp_path):
    state = State(tmp_path / "state.db")
    assert state.enqueue(10, 1, {"text": "hello"})
    assert not state.enqueue(10, 1, {"text": "hello"})
    assert state.offset() == 11
    assert state.claim()
    assert state.claim() is None
    state.close()


def test_restart_recovers_inflight_job_and_preserves_offset(tmp_path):
    path = tmp_path / "state.db"
    state = State(path)
    state.enqueue(10, 1, {"text": "question"})
    job = state.claim()
    state.save_result(job["id"], {"texts": ["verified answer"]})
    assert state.claim() is None
    state.close()
    state = State(path)
    recovered = state.claim()
    assert recovered["id"] == job["id"]
    assert json.loads(recovered["result"])["texts"] == ["verified answer"]
    assert state.offset() == 11
    state.close()


def test_chats_and_pending_jobs_are_isolated(tmp_path):
    state = State(tmp_path / "state.db")
    state.remember(1, "secret question", "answer")
    assert state.chat(2)["history"] == []
    state.enqueue(1, 1, {})
    state.enqueue(2, 1, {})
    state.enqueue(3, 2, {})
    first = state.claim()
    second = state.claim()
    assert first["chat_id"] == 1
    assert second["chat_id"] == 2
    state.complete(first["id"])
    assert state.claim()["update_id"] == 2
    state.reset(1)
    assert state.chat(1)["history"] == []
    state.close()
