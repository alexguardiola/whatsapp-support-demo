import argparse

import uvicorn

from .app import create_app
from .settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="support-bot")
    parser.add_argument("--fake-llm", action="store_true", help="replay recorded model outputs instead of calling a model")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    settings = Settings.from_env(**({"fake_llm": True} if args.fake_llm else {}))
    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
