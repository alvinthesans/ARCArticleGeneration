
import json
from pathlib import Path
from PIL import Image
import itertools

from app.core.transformerModelHandler import TransformerHandler
from app.data_models.container_class import Carousel
from app.visualQA.data_models import SemanticScore

class SemanticEncoder:
    def __init__(self, transformer_handler: TransformerHandler = TransformerHandler()):
        self.transformer_handler = transformer_handler

    def validate(self, slide_id: int, carousel: Carousel, image_path: Path, visual_path: Path, threshold = 0.5) -> SemanticScore:
        img = Image.open(image_path).convert("RGB")

        visual_text_path = visual_path

        with open(visual_text_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        negative_prompt = data["negative_prompt"]

        visual_prompt = carousel.getSlide(slide_id).semantic_qa_target

        texts = [visual_prompt, negative_prompt]

        scores = self.transformer_handler.ask_Siglip_Model(texts, img)

        scene_score = scores[0]

        if scene_score < threshold:
            e_usage = carousel.getSlide(slide_id).visual.element_usage
            optional_usage = [usage for usage in e_usage if usage.usage == "optional"]
            to_test = []

            if optional_usage:
                for usage in optional_usage:
                    if usage.selected_components:
                        components = [component[1] for component in usage.selected_components]
                        curr_element = ", ".join(components)
                    else:
                        element = carousel.visual_bible.get_element(usage.element_id)
                        curr_element =  element.description if isinstance(element.description, str) else element.description.toString()

                    if usage.state_description:
                        element_description = f"element: {curr_element}, state: {usage.state_description}"
                        to_test.append(usage.state_description)
                    else:
                        element_description = f"element: {curr_element}"

                    to_test.append(element_description)

            if to_test:
                text_container = []
                for r in range(1, len(to_test) + 1):
                    text_container.extend(itertools.combinations(to_test, r))

                text_retest = [f"{visual_prompt}, containing: {t}" for t in text_container]
                retest_scores = self.transformer_handler.ask_Siglip_Model(text_retest, img)
                max_score = max(retest_scores)

                if max_score > scene_score:
                    scene_score = max_score
                    index = retest_scores.index(max_score)
                    visual_prompt = text_retest[index]

        return SemanticScore(
            slide_id = slide_id,
            image_path = image_path,
            scene_score = scene_score,
            negative_score = scores[1],
            visual_prompt = visual_prompt,
            negative_prompt = negative_prompt
        )

