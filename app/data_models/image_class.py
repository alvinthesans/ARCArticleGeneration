from typing import Literal
import re

from pydantic import BaseModel, Field, model_validator, computed_field

from app.data_models.written_content import SlideElement, PersistentElement
from app.validator.element_valid_models import ElementUsage


class Composition(BaseModel):
    subject_position: Literal["left", "left_third", "center", "right_third", "right"]
    focal_point: Literal["left", "left_third", "center", "right_third", "right",
                        "top", "top_third", "bottom", "bottom_third"]
    text_safe_area: Literal["left", "top", "middle", "right", "bottom", "none"]
    negative_space: Literal["left", "top", "middle", "right", "bottom", "none"]
    subject_scale: Literal["small", "medium", "large"]
    framing: str

    def toString(self):
        return f"""
        subject_position: {self.subject_position}
        focal_point: {self.focal_point}
        text_safe_area: {self.text_safe_area}
        negative_space: {self.negative_space}
        subject_scale: {self.subject_scale}
        framing: {self.framing}
        """

class SlideVisual(BaseModel):
    visual_role: str

    composition: Composition = Field()
    shot_type: str

    scene_description: str = Field(
        description=("Scene description. Reference every character, environment, "
        "and object ONLY by ID. "
        "Allowed ID formats: c_01, e_01, o_01, sc_01, se_01, so_01. "
        "Do not invent element names or IDs."
        "For environment: you can ONLY edit what's inside and NOT what it is"
        "For character: you can ONLY edit the emotions, position or action"
        "For object: you can ONLY edit its motion or position"))

    element_usage: list[ElementUsage] = Field(description=("This is to indicate how the slide visual uses the persistent elements:"
                                                           "element_id MUST BE IN Scene description, with format: e_01, o_01 or c_01"
                                                           "visible: the element is visible without any changes of it's description"
                                                           "optional: the element mat appear in the slide"
                                                           "offscreen: the element is offscreen but still referenced"
                                                           "only write state_description if it is state_change, else it should be None"))


    slide_elements: list[SlideElement] = Field(default_factory=list,
                                               min_length=0, max_length=2)

    def getSlideElement(self, objectID: str) -> SlideElement:
        return next((element for element in self.slide_elements if objectID == element.objectID), None)

    @computed_field
    @property
    def used_element_ids(self) -> list[str]:
        pattern = r"(?:sc|se|so|c|e|o)_\d{2}"
        return list(
            dict.fromkeys(
                re.findall(
                    pattern,
                    self.scene_description
                )
            )
        )

    @computed_field
    @property
    def get_visible_element_usage(self) -> list[str]:
        return [usage.element_id for usage in self.element_usage if usage.usage == "visible"]

    @computed_field
    @property
    def get_optional_element_usage(self) -> list[str]:
        return [usage.element_id for usage in self.element_usage if usage.usage == "optional"]

    @computed_field
    @property
    def get_used_element_ids_with_components(self) -> list[str]:
        return [
            element_id
            for element_id in self.used_element_ids
            if re.match(r"^(c|e|o)_\d{2}_\d", element_id)
        ]

    @computed_field
    @property
    def used_permanent_element_ids(self) -> list[str]:
        return [
            element_id
            for element_id in self.used_element_ids
            if re.match(r"^(c|e|o)_\d{2}", element_id)
        ]

    @computed_field
    @property
    def used_slide_element_ids(self) -> list[str]:
        return [
            element_id
            for element_id in self.used_element_ids
            if re.match(r"^(sc|se|so)_\d{2}", element_id)
        ]

    def toVisualString(self):
        return f""" 
        role: {self.visual_role}
        scene_description: {self.scene_description}
        composition: {self.composition.toString()}
        shot_type: {self.shot_type}
        """

class VisualBible(BaseModel):
    element_list: list[PersistentElement] = Field(min_length=2, max_length=10)

    medium: str
    canvas_width: int
    canvas_height: int
    camera: str
    lighting: str
    color_palette: str
    mood: str
    composition_style: str
    negative_prompt: str

    def toString(self):
        return f"""
        medium: {self.medium}
        canvas_size: f"{self.canvas_width}px x {self.canvas_height}px"
        camera: {self.camera}
        lighting: {self.lighting}
        color_palette: {self.color_palette}
        mood: {self.mood}
        composition_style: {self.composition_style}
        negative_prompt: {self.negative_prompt}
        """

    def get_element_ids(self) -> set[str]:
        return {
            element.elementID for element in self.element_list
        }

    def getElementList(self):
        return [element.elementID for element in self.element_list]

    def get_element(self, element_id: str) -> PersistentElement | None:
        return next((
            item for item in self.element_list
            if item.elementID == element_id
        ), None)

    def validate_slide_visual(self, slide_visual: SlideVisual):
        valid_ids = self.get_element_ids()

        invalid_ids = [
            element_id
            for element_id in slide_visual.used_permanent_element_ids
            if element_id not in valid_ids
        ]

        if invalid_ids:
            return f"Unknown persistent element IDs: {invalid_ids}"

        return False

