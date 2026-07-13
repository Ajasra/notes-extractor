import base64
import json
import logging
import os
import tempfile
import urllib.request
from importlib.resources import files
from pathlib import Path

import yaml
from PIL import Image, ImageEnhance

from .model import PageResult

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
_EXTS = {".jpg", ".jpeg", ".png"}


def _load_dotenv() -> None:
    env_path = files("notes_extractor").parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = val


_load_dotenv()


def load_prompt() -> str:
    prompt_path = files("notes_extractor").parent.parent / "prompt.yaml"
    with open(prompt_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["system_prompt"]


def process_image(img_path: Path, max_dim: int) -> Path:
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = ImageEnhance.Color(img).enhance(1.5)
    tmp = Path(tempfile.mktemp(suffix=".jpg"))
    img.save(tmp, "JPEG", quality=85)
    return tmp


def ollama_chat(model: str, messages: list[dict], schema: dict | None = None, timeout: int = 120) -> dict:
    body: dict[str, object] = {"model": model, "messages": messages, "stream": False}
    if schema:
        body["format"] = schema

    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if not raw:
        raise ValueError("empty response from model")
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("\n```", 1)[0]
    if "{" in raw and "}" in raw:
        raw = raw[raw.index("{"):raw.rindex("}") + 1]
    return json.loads(raw)


def extract_highlights(image_path: Path, model: str, prompt: str) -> PageResult:
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    response = ollama_chat(
        model=model,
        schema=PageResult.model_json_schema(),
        messages=[{
            "role": "user",
            "content": prompt,
            "images": [b64],
        }],
    )
    raw = response["message"]["content"]
    try:
        data = _parse_json(raw)
    except Exception:
        logging.warning("  model returned unparseable output (len=%d): %.200s", len(raw), raw)
        return PageResult()
    return PageResult(**data)


def find_book_dirs(root: Path) -> list[tuple[str, Path, list[Path]]]:
    imgs = sorted(p for p in root.iterdir() if p.suffix.lower() in _EXTS)
    if imgs:
        return [(root.name, root, imgs)]
    books = []
    for subdir in sorted(root.iterdir()):
        if subdir.is_dir():
            imgs = sorted(p for p in subdir.iterdir() if p.suffix.lower() in _EXTS)
            if imgs:
                books.append((subdir.name, subdir, imgs))
    return books


def build_markdown(book_name: str, results: list[PageResult], output_dir: Path) -> Path:
    results.sort(key=lambda r: (r.page_number is None, r.page_number or 0))
    lines = [f"# {book_name} — Highlights", ""]
    for r in results:
        heading = f"## Page {r.page_number}" if r.page_number else "## Page Unknown"
        lines.append(heading)
        for hl in r.highlights:
            lines.append(f"> {hl}")
        lines.append("")
    out = output_dir / f"{book_name}_Notes.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def run(path: str, model: str, max_dim: int) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    base = Path(path).resolve()
    if not base.exists():
        logging.error("Path not found: %s", base)
        return 1

    books = find_book_dirs(base)
    if not books:
        logging.error("No images (jpg/jpeg/png) found in %s", base)
        return 1

    prompt = load_prompt()

    logging.info("Books found: %d", len(books))
    for book_name, img_dir, images in books:
        logging.info("Processing '%s' — %d images", book_name, len(images))
        results: list[PageResult] = []
        for img_path in images:
            tmp: Path | None = None
            try:
                tmp = process_image(img_path, max_dim)
                result = extract_highlights(tmp, model, prompt)
                results.append(result)
                pn = result.page_number or "?"
                logging.info("  %s → page %s, %d highlights", img_path.name, pn, len(result.highlights))
            except Exception:
                logging.exception("  %s FAILED", img_path.name)
            finally:
                if tmp and tmp.exists():
                    tmp.unlink(missing_ok=True)

        out = build_markdown(book_name, results, img_dir.parent)
        logging.info("  → %s", out)

    logging.info("Done.")
    return 0
