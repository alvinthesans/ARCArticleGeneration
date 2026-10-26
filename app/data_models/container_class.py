from typing import Optional

from pydantic import BaseModel, model_validator, Field

from app.core.generalFunction import convertToLayout
from app.data_models.image_class import VisualBible, SlideVisual
from app.data_models.written_content import Language, Purpose, SlideElement


class Slide(BaseModel):
    slide_id: Optional[int] = Field(default=None, description="Slide ID")
    purpose: Purpose
    headline: str = Field(min_length=1, max_length=30)
    body: str = Field(min_length=1, max_length=80)
    visual: SlideVisual = Field(description="Slide visual")
    layout: Optional[str] = Field(default=None)

    semantic_qa_target: str = Field(min_length=1, description="Slide visual description in sentence for semantic QA")

    image_path: str | None = None

    @model_validator(mode='before')
    @classmethod
    def assign_id(cls, data: dict) -> dict:
        if isinstance(data, dict):
            data["layout"] = convertToLayout(data["purpose"])

        return data


class ElementIDAllocator:
    PREFIX = {
        "character": "sc",
        "environment": "se",
        "object": "so",
    }

    def __init__(self, existing_ids: set[str] | None = None):
        self.existing_ids = set(existing_ids or [])

    def allocate(self, object_type: str) -> str:
        prefix = self.PREFIX[object_type]

        number = 1

        while True:
            candidate = f"{prefix}_{number:02d}"

            if candidate not in self.existing_ids:
                self.existing_ids.add(candidate)
                return candidate

            number += 1

class Carousel(BaseModel):
    title: str
    langauge: Language
    style: str

    visual_bible: VisualBible

    slides: list[Slide] = Field(min_length=2, max_length=7)

    @model_validator(mode="after")
    def initialize(self):
        self.assign_slide_ids()
        self.assign_missing_element_ids()
        return self

    def assign_slide_ids(self):
        for index, slide in enumerate(self.slides, start=1):
            if not slide.slide_id:
                slide.slide_id = index
        return self

    def getSlide(self, slide_id: int) -> Slide:
        slide = next((slide for slide in self.slides if slide.slide_id == slide_id), None)

        if not slide:
            raise Exception(f"Slide {slide_id} not found")

        return slide

    def changeSlide(self, slide_id: int, new_slide: Slide) -> None:
        old_slide = self.getSlide(slide_id)
        index = self.slides.index(old_slide)

        new_slide.slide_id = old_slide.slide_id

        self.preserve_element_ids(old_slide, new_slide)
        self.slides[index] = new_slide
        self.assign_missing_element_ids()

    def preserve_element_ids(self, old_slide: Slide, new_slide: Slide):
        old_elements = self.get_slide_elements(old_slide)
        new_elements = self.get_slide_elements(new_slide)

        old_by_id = {
            element.objectID: element
            for element in old_elements
            if element.objectID
        }

        for new_element in new_elements:
            if new_element.objectID in old_by_id:
                continue

            # New element → leave None for allocator
            new_element.objectID = None

    def assign_missing_element_ids(self):
        allocator = ElementIDAllocator(
            self.get_all_element_ids()
        )
        for slide in self.slides:
            for element in self.get_slide_elements(slide):
                if element.objectID is None:
                    element.objectID = allocator.allocate(element.objectType)

    def get_all_element_ids(self) -> set[str]:
        ids = set()
        for slide in self.slides:
            for element in self.get_slide_elements(slide):
                if element.objectID:
                    ids.add(element.objectID)
        return ids

    def get_slide_elements(self, slide: Slide) -> list[SlideElement]:
        return slide.visual.slide_elements
