# SPEC.md — Local Book Highlight Extractor

## §G. Goal
Extract book highlights and page numbers from phone photos locally using Qwen-VL and write to sorted Markdown.

## §C. Constraints
* **C1 (Compute):** Local RTX 3070 (8GB VRAM limit). Must prevent out-of-memory (OOM) faults.
* **C2 (Model):** Must use Qwen-VL model via Ollama (default: `qwen2.5vl:7b` or `qwen2.5vl:3b`).
* **C3 (Platform):** Offline execution, Python 3.10+, managed exclusively via `uv`. Zero manual virtualenvs.
* **C4 (Memory Cap):** Attention layers must be bounded by scaling down input images to prevent token-count explosion.

## §I. Interfaces
* **I1 (Input Structure):** Directories containing JPEG/PNG phone photos.
* **I2 (File Name Ordering):** Alphanumeric sorting of image files (e.g., `page_001.jpg`, `page_002.jpg`) defines processing order.
* **I3 (Output File):** `[Book_Title]_Notes.md` generated in the parent folder of the images.
* **I4 (Format Validation):** Enforced JSON output from Ollama matching Pydantic schema: `{"page_number": int|null, "highlights": list[str]}`.
* **I5 (CLI Arguments):** Command-line parser executing with the following options:
  * `--path` / `-p` : Path to a single book directory OR a root directory containing multiple books (Default: `./books`).
  * `--model` / `-m` : Name of the target Ollama vision model (Default: `qwen2.5vl:7b`).
  * `--max-dim` / `-r` : Maximum bounding box dimension to resize photos (Default: `1280`).
* **I6 (Execution Interface):** Run via `uv run` utilizing inline script metadata (PEP 723) to guarantee reproducible environments:
  ```bash
  uv run extract_notes.py [options]
  ```

## §V. Invariants
* **V1 (Memory Protection):** Raw input images must be downscaled to `--max-dim` before passing to Ollama to cap active VRAM footprint.
* **V2 (Visual Optimization):** Contrast and saturation must be artificially boosted on temporary images to assist VLM highlight detection.
* **V3 (Robust Cleanup):** All intermediate processed temporary images must be aggressively deleted immediately after inference, even if inference fails.
* **V4 (Output Determinism):** Output markdown blocks must be written in ascending order of detected page numbers; fallback to filename ordering if page numbers are undetected.
* **V5 (Fault Tolerance):** A single failed image processing loop must not crash the entire book batch execution. Empty or failed extractions must be logged and bypassed.

## §T. Tasks
| id | status | task | cites |
| :--- | :---: | :--- | :--- |
| T1 | . | Install uv and configure target Python version runtime via uv python install 3.11 | C3 |
| T1 | . | Setup project layout, install dependencies, and download `qwen2.5vl:7b` via Ollama | C2, C3 |
| T2 | . | Implement command-line interface parser (argparse) to ingest paths, model name, and dimensions | I5 |
| T3 | . | Implement image downscaler, contrast/saturation enhancer, and temporary image handler | V1, V2, V3 |
| T4 | . | Declare Pydantic model for page number and highlight list schema | I4 |
| T5 | . | Write Ollama API integration wrapper invoking structured Qwen-VL query | C1, C2, I4 |
| T6 | . | Build directory iterator that detects single-folder vs batch-folder paths and handles sorting | I1, I2, V5 |
| T7 | . | Implement markdown generation engine with page sorting and fallback logic | I3, V4 |
| T8 | . | Add global exception handler, execution logging, and automated temp file cleanup | V3, V5 |

## §B. Bugs
| id | date | cause | fix |
| :--- | :--- | :--- | :--- |