"""
Entry point: start the FastAPI backend.

Usage:
    python scripts/run_api.py
    python scripts/run_api.py --port 8001
"""
import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the OSS Risk Agent API server.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true", default=False)
    args = parser.parse_args()

    reload_flag = (
        []
        if args.no_reload
        else ["--reload", "--reload-dir", str(_ROOT / "api")]
    )
    cmd = [
        sys.executable, "-m", "uvicorn",
        "api.main:app",
        "--port", str(args.port),
        *reload_flag,
    ]
    subprocess.run(cmd, cwd=str(_ROOT), check=True)


if __name__ == "__main__":
    main()
