import argparse
import json

from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.services.indexing import run_initial_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the initial GCAI index for a local repository.")
    parser.add_argument("repo_path", help="Repository path to scan and index")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON result")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    result = run_initial_index(args.repo_path)
    print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
