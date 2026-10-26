import inspect

from pydantic import BaseModel, field_validator

from app.data_models.written_content import SlideElement


class PromptPackage(BaseModel):
    positive_prompt: str
    negative_prompt: str
    overall_visual: str

    image_composition: str

    width: int
    height: int

    seed: int

    metadata: dict = {
        "carousel_id": str,
        "slide_id": int,
        "element": list,
        "element_used": list,
        "element_optional": list,
        "slide_element": list[SlideElement],
        "layout": str,
    }

    @field_validator("positive_prompt", "overall_visual", "image_composition")
    @classmethod
    def clean_multiline_strings(cls, v: str) -> str:
        cleaned = inspect.cleandoc(v)
        return " ".join(cleaned.splitlines())