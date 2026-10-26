import re
from enum import Enum
from pathlib import Path
from typing import Literal, Any

from pydantic import BaseModel, Field, model_validator

from app.data_models.container_class import Carousel
from app.data_models.image_class import Composition


class QAStatus(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    RETRY = "retry"

class CalibrationRecordSimplified(BaseModel):
    carousel_id: str
    slide_id: int
    image_path: Path

    scene_score: float
    wrong_scene_same_carousel: tuple[str, float]
    wrong_scene_wrong_carousel: tuple[str, str, float]

class VisualIssue(BaseModel):
    code: str
    status: QAStatus
    message: str
    details: dict = Field(default_factory=dict)

class ImageFileInfo(BaseModel):
    path: str
    exists: bool
    readable: bool = False
    width: int | None = None
    height: int | None = None
    format: str | None = None
    file_size_bytes: int | None = None

class SlideQAResult(BaseModel):
    slide_id: int
    status: QAStatus
    image: ImageFileInfo | None = None
    issues: list[VisualIssue] = Field(default_factory=list)


class CarouselQAResult(BaseModel):
    carousel: Carousel
    status: QAStatus
    slides: list[SlideQAResult] = Field(default_factory=list)
    issues: list[VisualIssue] = Field(default_factory=list)


class SemanticScore(BaseModel):
    slide_id: int
    image_path: Path
    scene_score: float
    negative_score: float
    visual_prompt: str
    negative_prompt: str

class ElementObject(BaseModel):
    category: str
    element_id: str
    description: str
    state: str | None

    @model_validator(mode="after")
    def check_id(self):
        if not re.match(r"(?:sc|se|so|c|e|o)_\d{2}", self.element_id):
            raise ValueError("element_id has changed!")
        return self

class ObjectType(str, Enum):
    NATURE = "nature"
    ARTIFICIAL = "artificial"
    ANIMAL = "animal"
    CHARACTER = "character"
    INDOOR = "indoor"
    OUTDOOR = "outdoor"

class VLMOutput(BaseModel):
    object_id: str
    object_name: str
    object_type: ObjectType
    bbox_2d: list = Field(default_factory=list, description="boundary box of object with coordinates")
    found: bool

class VLMOutputSlide(BaseModel):
    slide_id: int = None
    carousel_id: str = None
    slide_make_sense: bool

    OutputObject: list[VLMOutput] = Field(default_factory=list)

class Asset(BaseModel):
    carousel_id: str
    object_id: str
    object_name: str
    object_type: ObjectType
    description: str

    image_width: int
    image_height: int

    asset_path: Path = None

class VLMCompositionVerdict(BaseModel):
    slide_id: int = None
    style_consistency_score: float
    match_other_slides_score: float

    expected_composition: Composition = None
    image_path: Path = None

    got_composition: Composition

    verdict_subject_position: bool
    verdict_focal_point: bool
    verdict_text_safe_area: bool
    verdict_negative_space: bool
    verdict_subject_scale: bool
    framing: bool

    @model_validator(mode="after")
    def check_composition(self):
        expected = vars(self.expected_composition)
        actual = vars(self.got_composition)
        paired_comparison = {k: (expected[k], actual[k]) for k in expected if k in actual}

        for item, value in paired_comparison.items():
            if item == "framing":
                continue

            if value[0] != value[1] and value[0]:
                setattr(self, f"verdict_{item}", False)
            else:
                setattr(self, f"verdict_{item}", True)

        return self

    @model_validator(mode="after")
    def normalize_score(self):
        self.style_consistency_score = max(0.00, min(self.style_consistency_score, 1.00))
        self.match_other_slides_score = max(0.00, min(self.match_other_slides_score, 1.00))

        return self

class VisualConsistencyResult(BaseModel):
    carousel_id: str = None
    style_description: str = None
    slide_list_verdict: list[VLMCompositionVerdict]






