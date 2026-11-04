from pathlib import Path
from types import SimpleNamespace

from uzex import service


def test_macos_reload_retries_transient_bootstrap_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(service.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(service.time, "sleep", lambda _: None)
    results = iter([0, 5, 0])
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=next(results))

    monkeypatch.setattr(service.subprocess, "run", run)
    target = service.install_service(tmp_path / "project")
    assert target.exists()
    assert [call[1] for call in calls] == ["bootout", "bootstrap", "bootstrap"]
