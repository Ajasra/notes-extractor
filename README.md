# Notes Extractor

Extract highlighted text from book page photos and screenshots using a local Qwen-VL model via Ollama. 100% offline — nothing leaves your machine.

Works with:
- Physical book photos (colored marker highlights)
- Web article screenshots (text selection highlights)
- App screenshots (dark/light mode)

## Prerequisites

- [Ollama](https://ollama.com) with `qwen2.5vl:7b` pulled:
  ```
  ollama pull qwen2.5vl:7b
  ```
- [uv](https://docs.astral.sh/uv/) for dependency management

## Quick Start

```bash
# Clone and install
git clone <repo-url> && cd notes-extractor
uv sync

# Drop photos in a folder
mkdir -p books/my-book
# ... copy your phone photos there ...

# Extract
uv run extract-notes -p books/my-book
# Output: books/my-book_Notes.md
```

## Usage

```
uv run extract-notes [options]

Options:
  -p, --path PATH     Book directory or root with subdirs (default: ./books)
  -m, --model MODEL   Ollama vision model name (default: qwen2.5vl:7b)
  -r, --max-dim N     Max image dimension before inference (default: 1280)
```

### Single book

```
uv run extract-notes -p books/atomic-habits
```

### Batch (multiple books at once)

```
uv run extract-notes -p books/
```
Each subfolder under `books/` is treated as a separate book.

## Output Format

```markdown
# Book Name — Highlights

## Page 42
> Highlighted passage from page 42.

## Page Unknown
> Highlight from a page where the number wasn't detected.
```

## Model Selection

Set `NOTES_MODEL` in `.env` to switch models:

```
NOTES_MODEL=qwen2.5vl:3b
```

Then pull it:

```
uv run python scripts/pull_model.py
```

## Custom Prompt

Edit `prompt.yaml` to tune how the model identifies highlights — no code changes needed.

## Environment

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama API URL |
| `NOTES_MODEL` | `qwen2.5vl:7b` | Default model (set in `.env`) |
# notes-extractor
