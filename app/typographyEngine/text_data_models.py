from pydantic import BaseModel

from app.data_models.written_content import Language

class TypographyStyle(BaseModel):
    font_family: str
    font_size: float
    weight: int

    line_height: float
    letter_spacing: float
    initial_color: str

class TextElement(BaseModel):
    id: str
    content: str
    role: str
    language: Language

    x: float
    y: float
    width: float
    height: float | None = None

    typography: TypographyStyle

    # color
    color: str
    opacity: float = 1.0
    rotation: float = 0.0

class DesignSystem(BaseModel):
    canvas_width: int
    canvas_height: int

    safe_margin: int

    headline: TypographyStyle | dict[Language ,TypographyStyle]
    body: TypographyStyle | dict[Language ,TypographyStyle]