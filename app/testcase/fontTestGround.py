from PyQt6.QtGui import QGuiApplication, QFontInfo

from app.core.Style_Loader import StyleLoader
from app.data_models.written_content import Language
from app.typographyEngine.FontManager import FontManager
from app.typographyEngine.text_data_models import TextSpec, TypographyStyle
from app.typographyEngine.typographyEngine import TextAdapter
from app.typographyEngine.typography_helper_function import measure_text

app = QGuiApplication.instance() or QGuiApplication([])
font_manager = FontManager()
style_loader = StyleLoader()
text_adapter = TextAdapter(style_loader)

style = style_loader.load("minimal_editorial")

chinese_font = style.typography[Language.TRADITIONAL_CHINESE]
color = style.colors

chinese_typo, _ = text_adapter.getTypography(chinese_font, color)

registered = font_manager.register_directory()

spec = TextSpec(
    id="slide_1_headline",
    slide_id=1,
    content="慢下来，才能看见生活",
    role="headline",
    language=Language.TRADITIONAL_CHINESE,
    typography=chinese_typo
    )

result = measure_text(
    spec,
    available_width=608,
    font_manager=font_manager
)

print("Width:", result.width)
print("Height:", result.height)
print("Lines:", result.line_count)
print("Line widths:", result.line_widths)

layout = result.layout
font_info = QFontInfo(layout.font())

print("Font:", font_info.family())
print("Weight:", font_info.weight())
print("Pixel size:", font_info.pixelSize())
print()

for i in range(layout.lineCount()):
    line = layout.lineAt(i)

    start = line.textStart()
    end = start + line.textLength()
    content = layout.text()[start:end]

    print(f"Line {i + 1}")
    print("Text:", repr(content))
    print("Width:", line.naturalTextWidth())
    print("Height:", line.height())
    print("Ascent:", line.ascent())
    print("Descent:", line.descent())
    print("Y position:", line.position().y())
    print()

for width in [300, 450, 608, 700, 1000]:
    measured = measure_text(spec, available_width=width, font_manager=font_manager)

    print(
        f"Width limit: {width}, "
        f"Lines: {measured.line_count}, "
        f"Text height: {measured.height:.2f}, "
        f"Actual width: {measured.width:.2f}"
    )
