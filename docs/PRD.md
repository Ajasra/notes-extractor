# PRD.md — Local Book Highlight Extractor (Product Requirements Document)

## 1. Product Overview & Vision
For active readers who prefer physical books but use digital knowledge bases (e.g., Obsidian, Logseq, Notion), extracting hand-highlighted text is a tedious manual task. 

This product is a **100% local, offline utility** that transforms physical highlights into digital markdown files. The user simply takes photos of highlighted pages with their phone, dumps them into a folder, and runs a single command. The system handles image optimization, character recognition, highlight segmentation, and structured markdown synthesis.

### Core Value Propositions
* **Privacy First:** 100% offline. Personal reading notes and book data never leave the local machine.
* **Low Friction:** No manual transcription. Just point, shoot, and dump photos into a folder.
* **Zero Cost:** No subscription fees or cloud token billing. It runs on the user's existing hardware.

---

## 2. User Persona & Workflow

### User Profile
* **The Physical Reader:** Prefers paper books and tactile highlighters (yellow, green, pink, blue).
* **The Digital Note-Taker:** Uses a Markdown-based personal knowledge management (PKM) vault.
* **The Hardware Owner:** Owns an Nvidia RTX GPU (8GB VRAM class) and values offline self-hosting.

### End-to-End Workflow
1. **Highlighting:** User reads a physical book and highlights key passages with standard markers.
2. **Capture:** Upon finishing the book (or a reading session), the user snaps photos of the marked pages using their phone. No special scanning app is required—normal perspective camera shots are sufficient.
3. **File Drop:** User connects their phone or transfers the images to their laptop, dropping them into a folder named after the book (e.g., `books/Clean_Code/`).
4. **Execution:** User runs the local CLI script: `python extract_notes.py --path books/Clean_Code`.
5. **Consumption:** The script produces a clean `Clean_Code_Notes.md` file. The user opens this in their markdown editor and immediately has their structured quotes and page numbers ready for review.

---

### 2.1 One-Command Onboarding
Using `uv`, setting up the local workspace requires zero boilerplate. The developer or user simply runs:

1. **Install `uv` (if not installed):**
   ```bash
   # On macOS/Linux:
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # On Windows:
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

## 3. Product Features & Requirements

### 3.1 Batch and Single Directory Processing
* **Requirement:** The system must accept a folder path. If the folder contains subfolders, it should detect them as distinct books and process them in a batch. If the folder contains only images, it must process it as a single book.
* **Rationale:** Simplifies bulk processing when a user catches up on archiving multiple books.

### 3.2 Visual Ingestion Optimization
* **Requirement:** Phone photos are high-resolution (12MP+) and often contain perspective skew, page curl, shadows, and low contrast. The pipeline must dynamically resize and enhance image contrast/saturation before feeding the image to the model.
* **Rationale:** Massive images crash consumer GPUs (RTX 3070 8GB). Enhancing contrast makes text sharper for the local model, while boosting saturation separates the highlighter color from the page background.

### 3.3 Visual Document Understanding (VDU) via Local VLM
* **Requirement:** The system must use a local Vision-Language Model (Qwen2.5-VL) via Ollama to perform layout analysis and OCR simultaneously.
* **Requirements for the Model:**
  1. Identify page numbers printed at the header or footer of the page.
  2. Differentiate between plain text and highlighted text.
  3. Extract *only* the highlighted text.
  4. Preserve line structure and spelling exactly as printed.

### 3.4 Strict Output Formatting
* **Requirement:** The system must enforce JSON structure on the local model output using schema validation (Pydantic). 
* **Rationale:** Standard text generation from LLMs is unpredictable. We need a guaranteed JSON payload containing an array of strings (the highlights) and an integer/null (the page number) to programmatically compile the markdown.

### 3.5 Markdown Synthesis
* **Requirement:** The output must be a clean markdown file named after the book folder. Highlights must be organized under Header 2 (`## Page X`) sections and formatted as standard markdown blockquotes (`> Highlighted text`).
* **Sorting Rule:** The file must be sorted in ascending order of detected page numbers to match the actual reading progress of the book.

---

## 4. Technical Constraints & Target Environment

| Constraint | Specification | Rationale |
| :--- | :--- | :--- |
| **Compute Limit** | NVIDIA RTX 3070 (Laptop/Desktop) — 8GB VRAM | Heavy models (11B+ parameters) will fail or swap to system RAM, becoming painfully slow. |
| **Runtime Environment** | Windows 11 or Linux, Python 3.10+ | Standard development OS. Windows consumes ~1.5GB of GPU memory just for the display, reducing available VRAM to ~6GB. |
| **Local Inference Host** | Ollama Engine (v0.5.0 or later) | Handles token routing, memory allocation, and Pydantic schema serialization natively. |
| **Target Model** | `qwen2.5vl:7b` (quantized) or `moondream` | Optimal trade-off between OCR accuracy, spatial reasoning (identifying highlights), and low VRAM footprint. |

---

## 5. Non-Functional Requirements & Fail-Safe Invariants

### 5.1 System Safety & VRAM Protection
The script must never allow the GPU to run out of memory. If a huge image bypasses the downscaler or if Ollama is unresponsive, the script must catch the exception, release the VRAM context, and alert the user.

### 5.2 Graceful Degradation
* **Unreadable Pages:** If a page is too blurry, dark, or lacks highlights, the system must not crash. It should skip the page, log the warning, and continue to the next image.
* **Missing Page Numbers:** If the page number is cut off in the photo, the system must assign `null` to the page number and place the highlights at the end of the markdown file under a `## Page Unknown` section.

### 5.3 Temporary Storage Hygiene
The program must not leave optimized, resized copies of the photos on the disk. All preprocessed temporary image files must be deleted immediately after inference, regardless of whether the inference succeeded or failed.

---

## 6. Future Roadmap (Out of Scope for v1)
* **Double-Page Splitting:** Automated cropping for photos that capture two pages side-by-side.
* **Multi-Color Semantic Mapping:** Mapping highlighter colors to specific markdown tags (e.g., *Yellow* for key terms, *Green* for actionable advice, *Pink* for disagreed arguments).
* **Obsidian Vault Sync:** Direct integration with a configured Obsidian directory to append new notes directly to the user's vault.