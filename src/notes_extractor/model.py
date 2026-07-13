from pydantic import BaseModel


class PageResult(BaseModel):
    page_number: int | None = None
    highlights: list[str] = []
