import asyncio
import json
from enum import Enum

import ollama

from app.core.engine import OllamaClient
from app.core.generalFunction import JSON_FORMAT_PROMPT, PERSISTENT_ELEMENT_PROMPT
from app.core.validator_main import Validator
from app.data_models.container_class import Carousel, Slide
from app.validator.element_valid_models import ValidationIssue, ValidationLevel


class RepairEngine:
    def __init__(self, validator: Validator, ollama_client: OllamaClient, model_name = "qwen3:8b"):
        self.ollama_client = ollama_client
        self.validator = validator
        self.model_name = model_name

    class ErrorType(Enum):
        DESCRIPTION = "description"
        ELEMENT = "element"
        COMPOSITION = "composition"
        SLIDE_TEXT = "slide_text"
        WHOLE_SLIDE = "whole_slide"

    instruct_prompt = f"""
            You are a visual description reviewer tasked to fix the slide provided based on the context given
            STRICTLY FOLLOW the instructions and DO NOT modify anything OUTSIDE of the pinpointed error

            THE LANGUAGE for the headline and body, STYLE, AND TOPIC MUST REMAIN THE SAME.

            DO REMEMBER TO CHANGE ACCORDING TO THE ERROR LOGS SHOWN
            the error indication and details are shown within the error

            In case there are temporary object or character used in a slide, place them inside the slide_elements list in visual
            However, that is in the case where it is unavoidable, it is best to reference from the visual bible
            for each slide, there can only be a maximum of 2 slide elements for each slide

            If an element represents an existing visual entity,
            reuse its existing objectID.

            Only use objectID = null for genuinely new entities.

            Never create a new ID for an existing entity.
            Never renumber existing IDs.
            """

    ERROR_CODE = {
        "DESCRIPTION_CONTRADICTION_SEMANTIC_UNCERTAINTY": ErrorType.DESCRIPTION,
        "N_SPACE_AND_TEXT_AREA_CONTRADICTS": ErrorType.COMPOSITION,
        "UNKNOWN_ELEMENT": ErrorType.ELEMENT,
        "DESCRIPTION_CONTRADICTION": ErrorType.DESCRIPTION,
        "DESCRIPTION_ELEMENT_CONTRADICTION": ErrorType.ELEMENT,
        "DESCRIPTION_CONTRADICTION_SEMANTIC": ErrorType.DESCRIPTION,
        "DESCRIPTION_ELEMENT_CONTRADICTION_SEMANTIC": ErrorType.ELEMENT,
        "HEADLINE_TOO_LONG": ErrorType.SLIDE_TEXT,
        "BODY_TOO_LONG": ErrorType.SLIDE_TEXT,
        "SLIDE_ELEMENT_COUNT_EXCEED": ErrorType.ELEMENT,
        "VISUAL_ELEMENT_MISSING": ErrorType.ELEMENT,
        "UNKNOWN_COMPONENT": ErrorType.ELEMENT,
        "UNSURE_COMPONENT": ErrorType.ELEMENT,
        "OPTIONAL_ELEMENT_EMBEDDED": ErrorType.ELEMENT,
        "ELEMENT_USAGE_UNINCLUDED": ErrorType.ELEMENT,
        "ELEMENT_NOT_EXIST": ErrorType.ELEMENT,
        "SLIDE_ELEMENT_UNINCLUDED": ErrorType.ELEMENT,
        "UNKNOWN_SLIDE_ELEMENT": ErrorType.ELEMENT,
        "NO_ELEMENT_EXIST": ErrorType.ELEMENT,
        "NARRATIVE_SCORE_FAILED": ErrorType.WHOLE_SLIDE,
        "DIVERSITY_SCORE_FAILED": ErrorType.WHOLE_SLIDE,
        "PROGRESSION_SCORE_FAILED": ErrorType.WHOLE_SLIDE
    }

    INSTRUCTION_PROMPT = """
    REWRITE ONLY THE ONES MENTIONED WITHIN THE ERRORS FOR EACH SLIDE
    YOU SHOULD NOT CHANGE THE PERSISTENT ELEMENTS, YOU CAN ONLY CHOOSE THE STATE OF USAGE
    OR RATHER IT SHOWS IN THE SLIDE WHEN IT IS NOT required
    
    DO NOT CHANGE:
        - slide ID
        - slide purpose
        - persistent element IDs and description
        - layout
        
    DO NOT CHANGE the headline and body unless instructed, if instructed, change the text but DO NOT ALTER the meaning it conveys.    
    COMPOSITION SHOULD BE CHANGED ONLY IF IT IS MENTIONED, WITH THE CORRESPONDING VARIABLE NAME
    """

    def removeErrorLevel(self, debug_log, to_remove: ValidationLevel = ValidationLevel.WARNING):
        if not debug_log:
            return None

        filtered_log = {}

        for slide, error_list in debug_log.items():
            remaining_errors = [error for error in error_list if error.level.value > to_remove.value]

            if remaining_errors:
                filtered_log[slide] = remaining_errors

        return filtered_log if filtered_log else None

    async def LoopRepair(self, carousel: Carousel, debug_log: dict[int, list[ValidationIssue]],
                   allowed_level: ValidationLevel = ValidationLevel.WARNING, remain: int = 3):

        self.runEngine(carousel, debug_log)
        raw_log = await asyncio.to_thread(self.validator.validateSlides, carousel)
        await self.ollama_client.unload_model(self.model_name)

        log = self.removeErrorLevel(raw_log, allowed_level)

        if not log:
            return True

        if remain <= 0:
            print("Repair engine has reached its limit, but carousel remain conflicted",
                  "Logic requires optimization")
            print(log)

            return False

        count = remain - 1
        return await self.LoopRepair(carousel, log, allowed_level, count)

    def getBible(self, carousel):
        bible = carousel.visual_bible
        persistent_element_string = ""
        for element in bible.element_list:
            persistent_element_string += f"- {element.toString()} \n"

        return f"""
                Visual settings from the bible:
                {bible.toString()}

                Persistent Elements:
                {persistent_element_string}
                """


    def runRepair(self, debug_log: list[ValidationIssue], slide: Slide):
        visual = slide.visual

        problem_list = debug_log

        problem_sorted = {}
        for problem in problem_list:
            if problem.code.startswith("UNMET_"):
                prb_type = self.ErrorType.COMPOSITION
            elif problem.code in self.ERROR_CODE:
                prb_type = self.ERROR_CODE[problem.code.upper()]
            else:
                raise ValueError("ERROR CODE NOT REGISTERED")

            if prb_type not in problem_sorted:
                problem_sorted[prb_type] = [problem]
            else:
                problem_sorted[prb_type].append(problem)

        error_string = "ERRORS: \n"
        for p_type, problems in problem_sorted.items():
            type_string = f"{p_type.value} \n"

            for problem in problems:
                type_string += f"{problem.message} \n"

            error_string += type_string
            error_string += "\n"

        slide_element_string = ""
        for element in visual.slide_elements:
            slide_element_string += f"{element.toString()} \n"

        slide_string = f"""
        Current Headline and Body:
        Headline: {slide.headline}
        Body: {slide.body}
        
        Current Scene Description:
        {visual.scene_description}
        
        Slide only element:
        {slide_element_string}
        
        ERROR:
        {error_string}
        """

        return slide_string

    def runEngine(self, carousel: Carousel, debug_log: dict[int, list[ValidationIssue]]):
        bible_prompt = self.getBible(carousel)

        if debug_log is None:
            return

        slide_to_fix = [key for key in debug_log.keys()]

        for slide_id in slide_to_fix:
            slide = carousel.getSlide(slide_id)
            to_check_problem_for_whole = [problem for problem in iter(debug_log[slide_id]) if not problem.code.startswith("UNMET_")]

            whole_slide_problem = next((problem for problem in to_check_problem_for_whole if self.ERROR_CODE[problem.code.upper()] == self.ErrorType.WHOLE_SLIDE), None)
            if whole_slide_problem:
                error_prompt = ""
                for problem in debug_log[slide_id]:
                    error_prompt += f"\n - {problem.message}"

                repair_prompt = f"""
                    SLIDE {slide_id} ONLY:
                    {bible_prompt}
                    
                    Slide requires a full revamp and redesign, follow the instructions / indicator below:
                    the visuals will be redesigned based on the new headline / body / visual target
                    
                    Details error log:
                    {error_prompt}
                """
            else:
                slide_prompt = self.runRepair(debug_log[slide_id], slide)
                repair_prompt = f"""
                                SLIDE {slide_id} ONLY:
                                
                                {bible_prompt}
                                
                                {slide_prompt}
                                
                                {self.INSTRUCTION_PROMPT}
                                """

            new_slide = self.askOllama(repair_prompt)
            carousel.changeSlide(slide_id, new_slide)

            print(f"CHANGED SLIDE: {slide_id}")
            print(new_slide.model_dump_json(
                indent=2,
                ensure_ascii=False,
            ))
            print("---------------------------")



    def askOllama(self, prompt) -> Slide:
        response = ollama.chat(
            model=self.model_name,
            think=True,
            messages=[
                {
                    "role": "system",
                    "content": json.dumps({"identity_instruction": self.instruct_prompt,
                                                "persistent element instruction": PERSISTENT_ELEMENT_PROMPT,
                                                "field format requirement": JSON_FORMAT_PROMPT
                                           }, ensure_ascii=False)
                },
                {
                    "role": "user",
                    'content': prompt
                }
            ],
            format=Slide.model_json_schema(),
            options={
                "num_ctx": 4096
            },
            keep_alive='0'
        )

        data = json.loads(response['message']['content'])

        return Slide.model_validate(data)
