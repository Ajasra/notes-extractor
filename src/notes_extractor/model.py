from pydantic import BaseModel


class OcrResult(BaseModel):
    page_number: int | None = None
    highlights: list[str] = []
    book_title: str | None = None


class PageResult(BaseModel):
    page_number: int | None = None
    highlights: list[str] = []
    book_title: str | None = None
    image_name: str | None = None
