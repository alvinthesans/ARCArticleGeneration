import json

import ollama

from app.core.engine import OllamaClient
from app.data_models.container_class import Carousel
from app.validator.element_valid_models import SlideInfo, CarouselNarrative, ValidationIssue, ValidationLevel


class CarouselNarrativeValidator:
    def __init__(self, model_name = "qwen3:8b"):
        self.model_name = model_name

    INSTRUCTION = """
    You are a carousel reviewer to check whether each slide contain variation with useful/ engaging text related to the topic
    everything shall maintain a flow, avoiding repetition and are correlated to each other to form a informative / logical carousel
    
    For each slide content given, you are to output the verdict respectively with the given json format
    narrative_score: float
    diversity_score: float
    progression_score: float
    
    every score is evaluated within a range of 0.0 to 1.0, the higher score means better
    
    for the narrative score:
        it compares the current headline and body text of the slide to check whether the text makes logical sense
        it also check whether the flow and content matches the other slides naturally in chronological order
    
    for diversity score:
        it compares the visual_aim and the text given with other slide, and determine whether the slide contain enough diversity
        to ensure the carousel / post is visual or content engaging for the audience. it should stick with the same style, however,
        it shall introduce variation such as different element usage / slide elements to prevent repetition.
        
    for progression score:
        this is to check whether the slide is useful / necessary for the full carousel. Does it actually contribute to the storytelling
        or what the content tries to convey.
    
    ONLY RETURN IN VALID JSON
    """

    def carousel_narrative_check(self, carousel: Carousel, variation_threshold = 0.7,
                                       narrative_threshold = 0.5, progression_threshold = 0.5):
        topic = carousel.title
        issues_dict = {}
        slide_info = []
        for slide in carousel.slides:
            curr_headline = slide.headline
            curr_body = slide.body
            curr_visual_aim = slide.semantic_qa_target
            curr_purpose = slide.purpose

            slide_info.append(
                SlideInfo(
                    slide_id=slide.slide_id,
                    headline=curr_headline,
                    body=curr_body,
                    visual_aim=curr_visual_aim,
                    purpose=curr_purpose))

        prompt = f"""Topic of carousel: {topic}
        TO VALIDATE:"""

        for slide_prompt in slide_info:
            prompt += f"\n {slide_prompt.model_dump_json(indent=4, ensure_ascii=False)}"

        data = self.askOllama(prompt)
        count = 0

        for slide in data['slide_narrative']:
            curr_slide_element = slide_info[count]
            slide['slide_id'] = curr_slide_element.slide_id
            slide['headline'] = curr_slide_element.headline
            slide['body'] = curr_slide_element.body
            slide['purpose'] = curr_slide_element.purpose
            slide["visual_aim"] = curr_slide_element.visual_aim
            count += 1

        carousel_narrative = CarouselNarrative.model_validate(data)
        for slide in carousel_narrative.slide_narrative:
            issues = []
            if slide.narrative_score < narrative_threshold:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="NARRATIVE_SCORE_FAILED",
                    slide_id= slide.slide_id,
                    message = (f"narrative score too low, expected above {narrative_threshold} but got {slide.narrative_score}"
                               f"the flow or the text of the slide is illogical, revise and rewrite the slide to ensure logic and content flow"
                               f"headline {slide.headline}, body {slide.body} and purpose {slide.purpose}")
                ))

            if slide.diversity_score < variation_threshold:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="DIVERSITY_SCORE_FAILED",
                    slide_id= slide.slide_id,
                    message = (f"diversity score too low, expected above {variation_threshold} but got {slide.diversity_score}"
                               f"the slides are repetitive and require changes to the content, ensure it stays within the same style, but ensure variety"
                               f"headline {slide.headline}, body {slide.body}, visual {slide.visual_aim} and purpose {slide.purpose}")
                ))

            if slide.progression_score < progression_threshold:
                issues.append(ValidationIssue(
                    level=ValidationLevel.ERROR,
                    code="PROGRESSION_SCORE_FAILED",
                    slide_id=slide.slide_id,
                    message=(f"progression score too low, expected above {progression_threshold} but got {slide.progression_score}"
                             f"current slide is redundant and require revamp, ensure the slide provide value to the carousel"
                             f"headline {slide.headline}, body {slide.body} and purpose {slide.purpose}")
                ))

            if issues:
                issues_dict[slide.slide_id] = issues

        return issues_dict


    def askOllama(self, prompt):
        response = ollama.chat(
            model=self.model_name,
            think=False,
            messages=[
                {
                    "role": "system",
                    "content": self.INSTRUCTION
                },
                {
                    "role": "user",
                    'content': prompt
                }
            ],
            format=CarouselNarrative.model_json_schema(),
            options={
                "num_ctx": 4096
            }
        )

        data = json.loads(
            response['message']['content']
        )

        return data