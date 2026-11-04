from uzex.config import Settings
from uzex.health import health
from uzex.state import State


def test_health_does_not_reset_working_jobs(tmp_path, sample_database):
    settings = Settings(
        _env_file=None, database_path=sample_database.path, state_path=tmp_path / "state.db"
    )
    state = State(settings.state_path)
    state.enqueue(1, 1, {"text": "question"})
    job = state.claim()
    state.heartbeat()
    assert health(settings)["healthy"]
    assert state.claim() is None
    state.complete(job["id"])
    state.close()
