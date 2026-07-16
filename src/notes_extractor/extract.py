import base64
import json
import logging
import os
import tempfile
import urllib.request
from importlib.resources import files
from pathlib import Path

import yaml
from PIL import Image, ImageEnhance, ImageOps

from .model import OcrResult, PageResult

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


def detect_rotation(img_path: Path, model: str) -> int:
    # ponytail: downscale to 320 for extremely fast orientation pre-check
    tmp_lowres = Path(tempfile.mktemp(suffix=".jpg"))
    try:
        img = Image.open(img_path)
        img = ImageOps.exif_transpose(img)
        img.thumbnail((320, 320))
        img.save(tmp_lowres, "JPEG", quality=80)

        b64 = base64.b64encode(tmp_lowres.read_bytes()).decode()
        prompt = (
            "Analyze the orientation of the text in this image. "
            "How many degrees clockwise does the image need to be rotated to make the text upright and readable from left to right? "
            "Respond ONLY with one of these integers: 0, 90, 180, 270."
        )
        response = ollama_chat(
            model=model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [b64],
            }],
            timeout=15
        )
        content = response["message"]["content"].strip()
        logging.info("  Orientation pre-check result: %s", content)
        for word in content.split():
            clean = "".join(filter(str.isdigit, word))
            if clean in {"0", "90", "180", "270"}:
                return int(clean)
    except Exception as e:
        logging.warning("  Failed to detect rotation: %s", e)
    finally:
        if tmp_lowres.exists():
            tmp_lowres.unlink(missing_ok=True)
    return 0


def process_image(img_path: Path, max_dim: int, model: str) -> Path:
    img = Image.open(img_path)
    img = ImageOps.exif_transpose(img)
    
    # Auto-detect rotation using VLM if no EXIF rotation
    angle = detect_rotation(img_path, model)
    if angle == 90:
        logging.info("  Rotating image 90 degrees clockwise")
        img = img.transpose(Image.ROTATE_270)
    elif angle == 180:
        logging.info("  Rotating image 180 degrees")
        img = img.transpose(Image.ROTATE_180)
    elif angle == 270:
        logging.info("  Rotating image 270 degrees clockwise")
        img = img.transpose(Image.ROTATE_90)

    img = img.convert("RGB")
    # Apply autocontrast with conservative cutoff to protect yellow highlights
    img = ImageOps.autocontrast(img, cutoff=0.5)

    w, h = img.size
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.5)
    # ponytail: enhance saturation moderately after white-balancing to make colors pop without false positives
    img = ImageEnhance.Color(img).enhance(1.3)
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


def consolidate_highlights(highlights: list[str]) -> list[str]:
    # ponytail: simple heuristic to merge consecutive fragments that belong to same sentence/clause
    if not highlights:
        return []
    merged = []
    current = ""
    for hl in highlights:
        hl = hl.strip()
        if not hl:
            continue
        if not current:
            current = hl
            continue

        ends_with_sentence_end = current[-1] in ".!?"
        starts_with_lowercase = hl[0].islower()
        has_punctuation = any(c in current[-3:] for c in ".,!?;:")

        if not ends_with_sentence_end or starts_with_lowercase or not has_punctuation:
            current = current + " " + hl
        else:
            merged.append(current)
            current = hl

    if current:
        merged.append(current)
    return merged


def extract_highlights(image_path: Path, model: str, prompt: str, prev_highlight: str | None = None, is_first_page: bool = False) -> OcrResult:
    b64 = base64.b64encode(image_path.read_bytes()).decode()
    user_content = prompt
    if prev_highlight:
        user_content += f"\n\nContext: The last highlight extracted from the previous page was: \"{prev_highlight}\". If the first highlight on this page is a direct continuation of it, start the first highlight string with '[CONTINUATION] ' followed by the remaining text."
    if is_first_page:
        user_content += "\n\nContext: This is the first page of the book. Check if it is a cover or title page. If so, extract the book title and return it in the 'book_title' field."

    response = ollama_chat(
        model=model,
        schema=OcrResult.model_json_schema(),
        messages=[{
            "role": "user",
            "content": user_content,
            "images": [b64],
        }],
    )
    raw = response["message"]["content"]
    try:
        data = _parse_json(raw)
    except Exception:
        logging.warning("  model returned unparseable output (len=%d): %.200s", len(raw), raw)
        return OcrResult()
    return OcrResult(**data)


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
    
    # ponytail: Find first non-empty book_title if available
    book_title = None
    for r in results:
        if r.book_title:
            book_title = r.book_title.strip()
            break

    title = book_title if book_title else book_name
    lines = [f"# {title} — Highlights", ""]
    for r in results:
        if not r.highlights:
            continue
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
        
        # ponytail: load incremental progress cache if available
        cache_file = img_dir.parent / f"{book_name}_Notes.cache.json"
        results: list[PageResult] = []
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    results = [PageResult(**item) for item in cached_data]
                logging.info("  Loaded %d cached pages", len(results))
            except Exception as e:
                logging.warning("  Failed to load cache: %s", e)

        processed_images = {r.image_name for r in results if r.image_name}

        for idx, img_path in enumerate(images):
            if img_path.name in processed_images:
                logging.info("  %s — already processed (cached)", img_path.name)
                continue

            tmp: Path | None = None
            try:
                tmp = process_image(img_path, max_dim, model)
                
                # Get the last non-empty highlight for page-to-page continuation context
                prev_hl = None
                for r in reversed(results):
                    if r.highlights:
                        prev_hl = r.highlights[-1]
                        break

                ocr_res = extract_highlights(tmp, model, prompt, prev_hl, is_first_page=(idx == 0))

                # Wrap OcrResult into PageResult with image_name
                result = PageResult(
                    page_number=ocr_res.page_number,
                    highlights=ocr_res.highlights,
                    book_title=ocr_res.book_title,
                    image_name=img_path.name
                )

                # Check for continuation prefix
                if result.highlights and result.highlights[0].strip().startswith("[CONTINUATION]"):
                    continuation_part = result.highlights[0].strip()
                    continuation_text = continuation_part[len("[CONTINUATION]"):].strip()
                    merged = False
                    for r in reversed(results):
                        if r.highlights:
                            # ponytail: append to last highlight of the previous page
                            r.highlights[-1] = (r.highlights[-1].rstrip() + " " + continuation_text).strip()
                            merged = True
                            break
                    if merged:
                        result.highlights.pop(0)

                # Now consolidate highlights on this page
                result.highlights = consolidate_highlights(result.highlights)

                results.append(result)
                pn = result.page_number or "?"
                logging.info("  %s → page %s, %d highlights", img_path.name, pn, len(result.highlights))

                # ponytail: save cache and build markdown after every page
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump([r.model_dump() for r in results], f, ensure_ascii=False, indent=2)

                build_markdown(book_name, results, img_dir.parent)

            except Exception:
                logging.exception("  %s FAILED", img_path.name)
            finally:
                if tmp and tmp.exists():
                    tmp.unlink(missing_ok=True)

        # ponytail: clean up cache file if completed successfully
        if len(results) == len(images):
            if cache_file.exists():
                cache_file.unlink(missing_ok=True)

        out = img_dir.parent / f"{book_name}_Notes.md"
        logging.info("  → %s", out)

    logging.info("Done.")
    return 0
