from sentence_transformers import CrossEncoder
import numpy as np
import re

from app.core.transformerModelHandler import TransformerHandler
from app.data_models.container_class import Slide
from app.data_models.image_class import VisualBible
from app.validator.element_valid_models import ValidationIssue, ValidationLevel


class StringPromptValidator:
    def __init__(self, transformer_handler: TransformerHandler = TransformerHandler()):
        self.transformer_handler = transformer_handler

    def is_component_in_element(self, uncertainty: dict, visual_bible: VisualBible, slide_id: int, threshold: float = 0.75):
        if not uncertainty:
            return []

        errors = []
        ids = []
        components = []
        pairs = []

        for element_id, component in uncertainty.items():
            curr_component = component.lower().rstrip()
            components.append(curr_component)

            ids.append(element_id)
            element_description = visual_bible.get_element(element_id).description.lower()
            pairs.append((element_description, curr_component))

        raw_scores = self.transformer_handler.ask_cross_encoder(pairs)

        for curr_index, logits in enumerate(raw_scores):
            exp_logits = np.exp(logits - np.max(logits))
            probabilities = exp_logits / exp_logits.sum()

            prob_contradiction = probabilities[0]
            prob_entailment = probabilities[1]
            prob_uncertain = probabilities[2]

            if prob_entailment > threshold:
                continue

            if prob_contradiction > prob_uncertain:
                errors.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="UNKNOWN_COMPONENT",
                    slide_id=slide_id,
                    element_id=ids[curr_index],
                    message=(
                        f"element ID: {ids[curr_index]} does not contain {components[curr_index]}"
                    )
                ))
            else:
                errors.append(ValidationIssue(
                    level=ValidationLevel.INFO,
                    code="UNSURE_COMPONENT",
                    slide_id=slide_id,
                    element_id=ids[curr_index],
                    message=(
                        f"element ID: {ids[curr_index]} may not contain {components[curr_index]}"
                    )
                ))

        return errors

    def is_prompt_conflicting(self, prompt: str, slide_id: int, threshold: float = 0.5):
        """
        Evaluates a single string for internal visual contradictions
        using a self-referencing cross-encoder technique.
        """
        premise = prompt
        hypothesis = f"All physical attributes described in '{prompt}' can exist simultaneously in a single object or scene."

        scores = self.transformer_handler.ask_cross_encoder(([(premise, hypothesis)]))[0]

        exp_scores = np.exp(scores - np.max(scores))
        probabilities = exp_scores / exp_scores.sum()

        contradiction_prob = probabilities[0]

        if bool(contradiction_prob >= threshold):
            return ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="DESCRIPTION_CONTRADICTION_SEMANTIC",
                    slide_id=slide_id,
                    message=(
                        f"visual description: {prompt}"
                        "contains contradiction"
                    )
                )
        else:
            return None

    def element_not_contradict_transformer(self, slide: Slide, visual_bible: VisualBible):
        errors = []
        premise = slide.visual.scene_description.lower().rstrip()

        prompt_verdict = self.is_prompt_conflicting(premise, slide.slide_id)

        if prompt_verdict:
            errors.append(prompt_verdict)

        element_ids = [element.objectID for element in slide.visual.slide_elements if
                       element.objectType == "environment"]
        slide_element_description = []

        for ids in element_ids:
            curr_element = slide.visual.getSlideElement(ids)
            if curr_element:
                slide_element_description.append(curr_element.description)

        for ids in slide.visual.used_permanent_element_ids:
            if re.match(r"^(e)_\d{2}$", ids):
                element_ids.append(ids)
                slide_element_description.append(visual_bible.get_element(ids).description)

        if not slide_element_description:
            return "uncertain", None

        pairs = [(premise, desc) for desc in slide_element_description]

        raw_scores = self.transformer_handler.ask_cross_encoder(pairs)

        if raw_scores.ndim == 1:
            raw_scores = np.expand_dims(raw_scores, axis=0)

        entailment_flag = False

        for curr_index, logits in enumerate(raw_scores):
            exp_logits = np.exp(logits - np.max(logits))
            probabilities = exp_logits / exp_logits.sum()

            prob_contradiction = probabilities[0]
            prob_entailment = probabilities[1]

            if prob_contradiction > 0.60:
                errors.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="DESCRIPTION_ELEMENT_CONTRADICTION_SEMANTIC",
                    slide_id=slide.slide_id,
                    element_id=element_ids[curr_index],
                    message=(
                        f"visual description: {slide_element_description[curr_index]}"
                        f"contradicts with {premise}"
                    )
                ))
            elif prob_entailment > 0.55:
                entailment_flag = True

        if errors:
            return "contradiction", errors

        if entailment_flag:
            return "entailment", None

        return "uncertain", None