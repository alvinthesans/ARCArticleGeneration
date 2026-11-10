from app.core.Style_Loader import StyleLoader
from app.data_models.container_class import Carousel
from app.data_models.written_content import Language
from app.typographyEngine.text_data_models import DesignSystem
from app.data_models.style_class import TypographyStyle as StyleTypography
from app.typographyEngine.text_data_models import TypographyStyle as TextTypography

class TextAdapter:
    def __init__(self, style_loader: StyleLoader):
        self.style_loader = style_loader
        self.stored_designs = {}
        self.curr_style_used = None
        self.curr_design_system = None

    def getTypography(self, typography: StyleTypography, color_style) -> tuple[TextTypography, TextTypography]:

        curr_main_text_style = typography

        headline_typography = TextTypography(
            font_family=curr_main_text_style.headline_font,
            font_size=curr_main_text_style.headline_size,
            weight=curr_main_text_style.headline_weight,
            line_height=curr_main_text_style.line_height,
            letter_spacing=0,
            initial_color=color_style.primary_text
        )

        body_typography = TextTypography(
            font_family=curr_main_text_style.body_font,
            font_size=curr_main_text_style.body_size,
            weight=curr_main_text_style.body_weight,
            line_height=curr_main_text_style.line_height,
            letter_spacing=0,
            initial_color=color_style.secondary_text
        )

        return headline_typography, body_typography

    def get_style(self, curr_style_used: tuple, languages):
        if curr_style_used in self.stored_designs:
            return self.stored_designs[curr_style_used]

        style_name = curr_style_used[0]
        curr_style = self.style_loader.load(style_name)
        text_style = curr_style.typography
        color_style = curr_style.colors
        canvas = curr_style.canva_size

        if text_style is None:
            raise Exception(f"Style {style_name} not found")

        if isinstance(languages, Language):
            curr_typo = text_style[languages]
            headline_typography, body_typography = self.getTypography(curr_typo, color_style)
        else:
            headline_typography = {}
            body_typography = {}

            for language in languages:
                curr_typo = text_style[language]
                curr_headline, curr_body = self.getTypography(curr_typo, color_style)

                headline_typography[language] = curr_headline
                body_typography[language] = curr_body

        curr_design_system = DesignSystem(
            canvas_width=canvas.width,
            canvas_height=canvas.height,
            safe_margin= 80,
            headline=headline_typography,
            body=body_typography
        )

        self.stored_designs[curr_style_used] = curr_design_system

        return curr_design_system

    def create_text_objects(self, carousel: Carousel):
        style_name = carousel.style
        language_selected = carousel.language

        if (style_name, language_selected) != self.curr_style_used:
            self.curr_style_used = (style_name, language_selected)
            self.curr_design_system = self.get_style(self.curr_style_used, language_selected)




