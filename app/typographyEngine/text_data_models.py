from dataclasses import dataclass, field
from typing import Literal

from PyQt6.QtGui import QTextLayout
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

class TextSpec(BaseModel):
    id: str
    slide_id: int

    content: str
    role: Literal["headline", "body"]
    language: Language | list[Language]

    typography: TypographyStyle

# Real Time data classes without json serialization or validation
@dataclass
class MeasuredText:
    width: float
    height: float
    line_count: int
    line_widths: tuple[float, ...]

    #Hide during print
    layout: QTextLayout = field(repr=False)