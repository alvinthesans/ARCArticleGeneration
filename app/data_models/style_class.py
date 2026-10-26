#Style, Visual bible, Visual Direction, Color Palette
#Camera, Typography, lighting, imagesStyle
from pydantic import BaseModel

from app.data_models.written_content import Language
from app.validator.element_valid_models import Layout


# Style Construct / Object

class CanvasStyle(BaseModel):
    width: int
    height: int

class TypographyStyle(BaseModel):
    headline_font: str
    body_font: str

    headline_weight: int = 700
    body_weight: int = 400

    headline_size: int = 72
    body_size: int = 36

    line_height: float = 1.2

class ColorStyle(BaseModel):
    background: str
    primary_text: str
    secondary_text: str

    accent: str | None = None

class ImageStyle(BaseModel):
    medium: str
    lighting: str
    camera: str
    color_treatment: str
    contrast: str
    composition: str
    mood: str

class StyleDefinition(BaseModel):
    name: str
    canva_size: CanvasStyle
    typography: dict[Language, TypographyStyle]
    colors: ColorStyle
    image: ImageStyle

    preferred_layouts: list[Layout]
    negative_prompt: str

    @property
    def getLayoutString(self):
        layout_string = ""
        for layout in self.preferred_layouts:
            strict = [rule for rule in layout.Constraint if rule.severity == 'strict']
            preferred = [rule for rule in layout.Constraint if rule.severity == 'preferred']
            optional = [rule for rule in layout.Constraint if rule.severity == 'optional']

            rule_string = ""
            if strict:
                rule_string += "strictly required to follow: \n"
                for rule in strict:
                    rule_string += rule.toString

            if preferred:
                rule_string += "preferred: \n"
                for rule in preferred:
                    rule_string += rule.toString

            if optional:
                rule_string += "optional: \n"
                for rule in optional:
                    rule_string += rule.toString

            layout_string += f"""
            layout name: {layout.layout_name}
            -----------------------------------
            Constraint to follow:
            {rule_string}
            ___________________________________
            """

        return layout_string

# End of Style Construct