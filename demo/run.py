#!/usr/bin/env python
"""
Bean & Brew — single-command launcher.

    cd demo
    uv run python run.py              # default port 8000
    uv run python run.py --port 3000
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser(description="Bean & Brew demo")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run("app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
