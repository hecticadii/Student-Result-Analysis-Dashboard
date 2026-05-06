import os
import subprocess
import sys


def env_flag(name: str, default: bool) -> str:
    raw = os.environ.get(name)
    if raw is None:
        return "true" if default else "false"
    return "false" if raw.strip().lower() in {"0", "false", "no"} else "true"


def main() -> int:
    port = os.environ.get("PORT") or os.environ.get("STREAMLIT_SERVER_PORT") or "8501"
    address = os.environ.get("STREAMLIT_SERVER_ADDRESS", "0.0.0.0")
    headless = env_flag("STREAMLIT_SERVER_HEADLESS", True)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.port",
        str(port),
        "--server.address",
        address,
        "--server.headless",
        headless,
    ]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
