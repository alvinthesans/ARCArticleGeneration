
import re
from app.data_models.image_class import VisualBible
from app.data_models.written_content import PersistentElement
from app.validator.element_valid_models import ValidationIssue, ValidationLevel, ElementUsage

class ElementValidator:
    ENVIRONMENT_KEYWORDS = {
        "indoor": [
            "room",
            "wall",
            "floor",
            "ceiling"
        ],

        "outdoor": [
            "forest",
            "beach",
            "sea",
            "trees",
            "sky",
            "birds"
        ]
    }


    CONTRADICT = {
        "indoor": "outdoor",
        "outdoor": "indoor",
        "undefined": None
    }

    def validate(self, slide, visual_bible: VisualBible):
        issues = []

        elements = {element.elementID for element
            in visual_bible.element_list}

        for element_id in slide.visual.used_permanent_element_ids:
            if element_id not in elements:
                issues.append(ValidationIssue(
                        level=ValidationLevel.ERROR,
                        code="UNKNOWN_ELEMENT",
                        slide_id=slide.slide_id,
                        element_id=element_id,
                        message=(
                            f"Element {element_id} "
                            "does not exist in "
                            "visual_bible. remove all instance from scene_description(s)"
                        )))

        slide_elements = {element.objectID for element in slide.visual.slide_elements}

        for element_id in slide.visual.used_slide_element_ids:
            if element_id not in slide_elements:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="UNKNOWN_SLIDE_ELEMENT",
                    slide_id=slide.slide_id,
                    element_id=element_id,
                    message=(
                        f"Slide Element {element_id} "
                        "does not exist in "
                        "slide element list."
                    )))

        return issues

    def validate_element_usage(self, usage: ElementUsage, element: PersistentElement):
        if not usage.selected_components:
            return {}

        uncertainty = {}
        description = element.description.lower()

        for component in usage.selected_components:
            if component[1].lower() not in description:
                uncertainty[usage.element_id] = component[1].lower()

        return uncertainty

    def validate_slide_element_usages(self, slide, visual_bible):
        slide_usage = [usage for usage in slide.visual.element_usage]
        perm_elements = slide.visual.used_permanent_element_ids
        errors = []
        slide_uncertainty = {}

        for usage in slide_usage:
            if usage.usage != "visible" and usage.element_id in perm_elements:
                errors.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="OPTIONAL_ELEMENT_EMBEDDED",
                    slide_id=slide.slide_id,
                    element_id=usage.element_id,
                    message=(
                        f"Optional Element {usage.element_id} "
                        f"should not be embedded inside the visual description: {slide.visual.scene_description}"
                    )
                ))
                continue

            if "s" in usage.element_id and usage.element_id not in slide.visual.used_slide_element_ids:
                errors.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="SLIDE_ELEMENT_UNINCLUDED",
                    slide_id=slide.slide_id,
                    element_id=usage.element_id,
                    message=(
                        f"Slide Element {usage.element_id} declared in slide {slide.slide_id}"
                        f"was not included in the visual description: {slide.visual.scene_description}"
                        f"making it redundant and unacceptable"
                    )
                ))
                continue

            if usage.usage == "visible" and usage.element_id not in perm_elements:
                errors.append(ValidationIssue(
                    level=ValidationLevel.INFO,
                    code="ELEMENT_USAGE_UNINCLUDED",
                    slide_id=slide.slide_id,
                    element_id=usage.element_id,
                    message=(
                        f"Visible Element {usage.element_id} "
                        f"was not included in the visual description: {slide.visual.scene_description}"
                    )
                ))
                continue

            perm_element = visual_bible.get_element(usage.element_id)
            slide_uncertainty.update(self.validate_element_usage(usage, perm_element))

        return slide_uncertainty, errors




    def element_not_contradict_keyword(self, slide, visual_bible):
        errors = []
        indoor_keywords = self.ENVIRONMENT_KEYWORDS["indoor"]
        outdoor_keywords = self.ENVIRONMENT_KEYWORDS["outdoor"]

        to_transverse = [element for element in slide.visual.slide_elements if element.objectType == "environment"]

        extracted_type = []

        slide_description = slide.visual.scene_description.lower().rstrip()
        if any(value in slide_description for value in indoor_keywords):
            extracted_type.append("indoor")

        if any(value in slide_description for value in outdoor_keywords):
            extracted_type.append("outdoor")
            if "indoor" in extracted_type:
                errors.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="DESCRIPTION_CONTRADICTION",
                    slide_id=slide.slide_id,
                    message=(
                        "visual description of slide contains contradiction"
                    )
                ))

        if not extracted_type:
            extracted_type.append("undefined")
            first_type = ""
        else:
            first_type = extracted_type[0]

        for id in slide.visual.used_permanent_element_ids:
            if re.match(r"^(e)_\d{2}", id):
                curr_element = visual_bible.get_element(id)

                if not curr_element:
                    errors.append(ValidationIssue(
                        level=ValidationLevel.ERROR,
                        code="ELEMENT_NOT_EXIST",
                        slide_id=slide.slide_id,
                        element_id=id,
                        message= f"element {id} does not exist in carousel"
                    ))
                    continue

                to_transverse.append(curr_element)

        if not to_transverse:
            errors.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                code="NO_ELEMENT_EXIST",
                slide_id=slide.slide_id,
                message=f"No permanent element included in carousel, though might be intended"
            ))
            return "contradiction", errors

        for element in to_transverse:
            if any(value in element.description for value in indoor_keywords):
                e_type = "indoor"
            elif any(value in element.description for value in outdoor_keywords):
                e_type = "outdoor"
            else:
                e_type = "undefined"

            if self.CONTRADICT[e_type] == first_type:
                if isinstance(element, PersistentElement):
                    element_id = element.elementID
                else:
                    element_id = element.objectID

                errors.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="DESCRIPTION_ELEMENT_CONTRADICTION",
                    slide_id=slide.slide_id,
                    element_id=element_id,
                    message=(
                        f"visual description of slide and element {element_id} have contradiction"
                    )
                ))
            extracted_type.append(e_type)

        if errors:
            return "contradiction", errors

        return "uncertain", None

