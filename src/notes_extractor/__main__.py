import argparse
import os

from .extract import run

DEFAULT_MODEL = os.environ.get("NOTES_MODEL", "qwen2.5vl:7b")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract highlights from book page photos")
    parser.add_argument("--path", "-p", default="./books", help="Book directory or root with subdirs")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Ollama vision model (env: NOTES_MODEL, default: {DEFAULT_MODEL})")
    parser.add_argument("--max-dim", "-r", type=int, default=1280, help="Max image dimension before inference")
    args = parser.parse_args()
    raise SystemExit(run(args.path, args.model, args.max_dim))


if __name__ == "__main__":
    main()
