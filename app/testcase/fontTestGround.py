from PyQt6.QtGui import QGuiApplication

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
