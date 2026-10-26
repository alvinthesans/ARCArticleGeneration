import json
import random

from app.data_models.container_class import Slide
from app.data_models.image_class import VisualBible
from app.data_models.prompt_package import PromptPackage

class VisualPlanner:
    def __init__(self, bible: VisualBible):
        self.bible = bible

    def changeBible(self, bible: VisualBible):
        self.bible = bible

    def createVisualPrompt(self, slide: Slide, carousel_id: int) -> PromptPackage:
        visual = slide.visual
        option_id = [ids for ids in visual.get_optional_element_usage]

        persistent_element_used = []
        for element in visual.used_permanent_element_ids:
            curr_element = self.bible.get_element(element)
            if curr_element is not None:
                persistent_element_used.append(curr_element)
            else:
                raise ValueError("Element Not Found in Bible")

        element_dictionary = []
        optional_dictionary = []
        slide_dictionary = []

        if visual.slide_elements:
            for slide_element in visual.slide_elements:
                slide_dictionary.append(f"Slide element {slide_element.objectID}: {slide_element.description if isinstance(slide_element.description, str) else slide_element.description.toString()}")

        for usage in visual.element_usage:
            if usage.usage == "offscreen" or usage.element_id not in visual.used_element_ids or "s" in usage.element_id:
                continue

            component_list = []
            if usage.selected_components:
                for i in range(1, len(usage.selected_components) + 1):
                    if usage.get_selected_component(i):
                        component_list.append(usage.get_selected_component(i))
            else:
                curr_element = self.bible.get_element(usage.element_id)

                if curr_element is None:
                    raise ValueError(f"Element {usage.element_id} Not Found")

                component_list = f"{curr_element.elementID}: {curr_element.description if isinstance(curr_element.description, str) else curr_element.description.toString()}"

            if isinstance(component_list, list):
                element_string = f"Element {usage.element_id}:"
                for component in component_list:
                    element_string += f" {component} \n"
            else:
                element_string = component_list

            if usage.state_description:
                element_string += f" change of state for the element in slide: {usage.state_description}"

            if usage.element_id in visual.get_visible_element_usage:
                element_dictionary.append(element_string)
            else:
                optional_dictionary.append(element_string)

        element_dictionary_string = " \n".join(element_dictionary)
        optional_dictionary_string = " \n".join(optional_dictionary)
        slide_dictionary_string = " \n".join(slide_dictionary)

        composition_string = f"""
        Composition and stage direction:
        composition: {visual.composition.toString()}
        shot_type: {visual.shot_type}"""

        positive_prompt = f"""medium: {self.bible.medium}
        scene_description: {visual.scene_description}
        Element Indication for scene_description:
        {element_dictionary_string if element_dictionary_string else "No persistent element used"}
        {slide_dictionary_string if slide_dictionary_string else "No slide elements used"}
        
        Optional aesthetic to include for visual enhancement:
        {optional_dictionary_string if optional_dictionary_string else "No optional element to select from"}
        {composition_string}
        """

        negative_prompt = self.bible.negative_prompt

        overall_visual = f"""camera settings: {self.bible.camera}
        lighting: {self.bible.lighting}
        color palette: {self.bible.color_palette}
        mood: {self.bible.mood}
        composition interpretation: {self.bible.composition_style}
        """

        height = self.bible.canvas_height
        width = self.bible.canvas_width
        seed = random.randint(0, 2**32 - 1)

        return PromptPackage(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            overall_visual=overall_visual,
            image_composition=composition_string,
            seed=seed,
            height=height,
            width=width,
            metadata={
                "carousel_id": carousel_id,
                "slide_id": slide.slide_id,
                "element": [visual.used_permanent_element_ids, option_id],
                "element_used": element_dictionary,
                "element_optional": optional_dictionary,
                "slide_element": slide.visual.slide_elements,
                "layout": slide.layout
            }
        )