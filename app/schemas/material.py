from pydantic import BaseModel


class MaterialResponse(BaseModel):
    id: str
    filename: str
    page_count: int
    reused: bool = False
