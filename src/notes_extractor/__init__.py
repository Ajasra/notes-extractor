"""Notes Extractor — extract highlighted text from photos using local Qwen-VL."""

from .model import PageResult
from .extract import run

__all__ = ["PageResult", "run"]
