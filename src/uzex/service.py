import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path


def install_service(project: Path) -> Path:
    if sys.platform != "darwin":
        raise ValueError("This command installs the macOS service; use Docker on a server")
    project = project.resolve()
    logs = project / "var"
    logs.mkdir(parents=True, exist_ok=True)
    target = Path.home() / "Library/LaunchAgents/uzex21.assistant.plist"
    target.parent.mkdir(parents=True, exist_ok=True)
    label = "uzex21.assistant"
    body = {
        "Label": label,
        "ProgramArguments": [str(project / ".venv/bin/python"), "-m", "uzex.cli", "bot"],
        "WorkingDirectory": str(project),
        "EnvironmentVariables": {"PYTHONPATH": str(project / "src"), "PYTHONUNBUFFERED": "1"},
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(logs / "bot.log"),
        "StandardErrorPath": str(logs / "bot.log"),
    }
    target.write_bytes(plistlib.dumps(body))
    target.chmod(0o600)
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{label}"], capture_output=True, check=False)
    for _ in range(12):
        loaded = subprocess.run(
            ["launchctl", "bootstrap", domain, str(target)], capture_output=True, check=False
        )
        if loaded.returncode == 0:
            return target
        time.sleep(0.25)
    raise RuntimeError("Could not load the local service; check launchctl and var/bot.log")
