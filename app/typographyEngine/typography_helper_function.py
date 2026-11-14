from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QFont, QTextOption, QTextLayout

from app.typographyEngine.FontManager import FontManager
from app.typographyEngine.text_data_models import TextSpec, MeasuredText


def measure_text(spec: TextSpec, available_width: float,font_manager: FontManager) -> MeasuredText:
    if available_width <= 0:
        raise ValueError("Width must be positive")

    style = spec.typography

    if style.line_height <= 0 or style.font_size <= 0:
        raise ValueError(f"Invalid typography dimensions, line_height: {style.line_height}, font_size: {style.font_size}")

    # Current version: single paragraph only.
    if "\n" in spec.content:
        raise ValueError("Explicit line breaks not yet supported")

    languages_used = [lang for lang in spec.language]
    font = font_manager.find_registered_font(style.font_family, weight=400)
    font_manager.add_alias(
        "Chocolate Classical Sans",
        font.families[0]
    )

    font = font_manager.resolve_registered_font(
        font_id=font.font_id,
        weight=style.weight,
        pixel_size=round(style.font_size),
        text=spec.content,
        language=languages_used
    )

    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, style.letter_spacing)

    options = QTextOption()
    options.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    options.setUseDesignMetrics(True)

    layout = QTextLayout(spec.content, font)
    layout.setTextOption(options)
    layout.setCacheEnabled(True)

    y = 0.0
    bottom = 0.0
    widths = []

    layout.beginLayout()
    try:
        while True:
            line = layout.createLine()

            if not line.isValid():
                break

            line.setLineWidth(available_width)
            line.setPosition(QPointF(0, y))

            widths.append(line.naturalTextWidth())
            bottom = max(bottom, y + line.height())

            y += line.height() * style.line_height
    finally:
        layout.endLayout()

    return MeasuredText(
        width=max(widths, default=0.0),
        height=bottom,
        line_count=len(widths),
        line_widths=tuple(widths),
        layout=layout
    )
