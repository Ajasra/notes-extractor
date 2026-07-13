"""Pull the Ollama model specified in .env (NOTES_MODEL)."""
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    model = None
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("NOTES_MODEL="):
                model = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not model:
        print("No NOTES_MODEL found in .env", file=sys.stderr)
        sys.exit(1)

    print(f"Pulling {model}...")
    subprocess.run(["ollama", "pull", model], check=True)


if __name__ == "__main__":
    main()
