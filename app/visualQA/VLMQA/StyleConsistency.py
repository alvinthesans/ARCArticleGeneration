import json
from math import floor
from pathlib import Path

import ollama
from app.data_models.container_class import Carousel
from app.visualQA.data_models import VisualConsistencyResult, VisualIssue, QAStatus


class CarouselConsistentStyleValidator:
    def __init__(self, model_name = "qwen3-vl:8b-instruct-q4_K_M"):
        self.asset_folder = Path(r"D:\ProgramData\ARCArticleGeneration\app\assets")
        self.asset_folder.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name

    INSTRUCTION_PROMPT = f"""You are a carousel validator which check style consistency and composition of given images
    For each image, you would compare it against each other, and check whether the image match the requested style
    You are to also discover whether the image has the correct composition as requested
    
    For each image, you are to output:
        style_consistency_score: float
        match_other_slides_score: float

        got_composition: Composition
    
        verdict_subject_position: bool
        verdict_focal_point: bool
        verdict_text_safe_area: bool
        verdict_negative_space: bool
        verdict_subject_scale: bool
        framing: bool
        
        style_consistency_score: compare the image with the given style and output the score ranging from 0.00 to 1.00
        lower than 0.5 means they are not likely related
        more than 0.5 means they possesses similar characteristics
        
        this is to indicate the similarity between the image and the specified overall style goal
        
        match_other_slides_score: compare the image with every other images in the sequence and output the similarity ranging from 0.00 to 1.00
        this is to indicate how well the image fits with the other images of the overall carousel
        lower than 0.5 means they are not likely related
        more than 0.5 means they possesses similar characteristics
        Do keep in mind that this score is calculated by comparing with all other images, which mean the score shouldn't be affected by abnormal data, while flagging it under the corresponding image 
        
        got_composition: the composition of the image
        verdict_subject_position: bool
        verdict_focal_point: bool
        verdict_text_safe_area: bool
        verdict_negative_space: bool
        verdict_subject_scale: bool
        framing: bool
        
        based on the given image, identify the composition of the image and compare with the given expected composition.
        input the composition you have detected in the image at got_composition, and by comparing with the given expectation, change the verdict and framing boolean accordingly
        
        for example:
        if the expected subject_position and the one found in the image is the same, verdict_subject_position = True, else, False
        this applies for the other switches listed above as well.
    """

    def findConsistency(self, carousel: Carousel, carousel_id, changed_slides: list = None, similarity_threshold: float = 0.55, style_threshold: float = 0.3, pass_boundary: float = 0.9):
        issues = []
        slide_issues = {}
        if changed_slides:
            curr_carousel_score = self.validate(carousel, carousel_id, changed_slides)
        else:
            curr_carousel_score = self.validate(carousel, carousel_id)

        vlm_outputs = curr_carousel_score.slide_list_verdict
        failed_similarity = 0
        failed_style = 0

        if not vlm_outputs:
            return [VisualIssue(
                code="NO_VERDICT_RETURNED",
                status=QAStatus.FAIL,
                message="The vlm didn't return any verdict"
            )], None

        slide_count = len(vlm_outputs)

        for verdict in vlm_outputs:
            curr_style_consistency_score = verdict.style_consistency_score
            curr_match_other_slides_score = verdict.match_other_slides_score
            slide_only = []

            if curr_style_consistency_score < style_threshold:
                failed_style += 1
                slide_only.append(VisualIssue(
                    code="STYLE_CONSISTENCY_FAILED",
                    status=QAStatus.FAIL,
                    message=(f"Slide {verdict.slide_id} didn't match the overall style given"
                             f"Overall style: {curr_carousel_score.style_description}"),
                    details= {
                        "score given": curr_style_consistency_score,
                        "score expected above": style_threshold,
                        "style expected": curr_carousel_score.style_description,
                        "image path": verdict.image_path
                    }
                ))

            if curr_match_other_slides_score > similarity_threshold:
                failed_similarity += 1
                slide_only.append(VisualIssue(
                    code="SLIDE_VISUAL_TOO_SIMILAR",
                    status=QAStatus.FAIL,
                    message=(f"Slide {verdict.slide_id} are too similar with other slides"
                             f"Expected threshold below: {similarity_threshold}, got: {curr_match_other_slides_score}"),
                    details={
                        "score given": curr_match_other_slides_score,
                        "score expected below": similarity_threshold,
                        "image path": verdict.image_path
                    }
                ))

            slide_issues[verdict.slide_id] = slide_only

        to_pass = floor(slide_count * pass_boundary)
        if failed_style > to_pass:
            issues.append(VisualIssue(
                code="CAROUSEL_STYLE_FAILED",
                status=QAStatus.FAIL,
                message=(f"Carousel {curr_carousel_score.carousel_id} style failed, over {pass_boundary:.2%} doesn't match the expected style, style prompt revision needed"
                         f"Overall style: {curr_carousel_score.style_description}"),
                details={
                    "passing boundary": pass_boundary,
                    "failed slides count": failed_style,
                    "style expected": curr_carousel_score.style_description,
                    "carousel id": curr_carousel_score.carousel_id,
                }
            ))

        # if failed_similarity > to_pass:
        #     issues.append(VisualIssue(
        #         code="CAROUSEL_SLIDE_DIFFERENCE",
        #         status=QAStatus.WARN,
        #         message= f"Carousel {curr_carousel_score.carousel_id}, possesses differentiate slide over {pass_boundary:.2%}, but may due to request from topic / user prompt",
        #         details={
        #             "passing boundary": pass_boundary,
        #             "different slide count": failed_similarity,
        #             "carousel id": curr_carousel_score.carousel_id
        #         }
        #     ))

        return issues, slide_issues


    def validate(self, carousel: Carousel, carousel_id, changed_slides: list = None):
        bible = carousel.visual_bible

        overall_style = f"""medium: {bible.medium}
        camera: {bible.camera}
        lighting: {bible.lighting}
        color_palette: {bible.color_palette}
        mood: {bible.mood}
        composition_style: {bible.composition_style}
        """

        compositions = []
        image_paths = []

        if changed_slides:
            slides = [slide for slide in carousel.slides if slide.slide_id in changed_slides]
        else:
            slides = carousel.slides

        for slide in slides:
            image_paths.append(Path(slide.image_path))
            compositions.append([slide.slide_id, slide.visual.composition])

        composition_string = ""
        for s_id, composition in compositions:
            composition_string += f"""
            Slide ID: {s_id}
            Composition expected:
            {composition.toString()}"""

        user_prompt = f"""
        Overall style for style_consistency_score:
        {overall_style}
        
        Composition to look for and verdict:
        {composition_string}
        """

        response = ollama.chat(
            model=self.model_name,
            messages=[{
                "role": "system",
                "content": self.INSTRUCTION_PROMPT
            },
                {
                    "role": "user",
                    'content': user_prompt,
                    'images': image_paths
                }],
            format=VisualConsistencyResult.model_json_schema()
        )

        data = json.loads(response['message']['content'])
        data["carousel_id"] = carousel_id
        data["style_description"] = overall_style

        listOfVerdicts = data["slide_list_verdict"]

        count = 0
        for verdict in listOfVerdicts:
            slide_id = compositions[count][0]
            image_path = carousel.getSlide(slide_id).image_path

            verdict["expected_composition"] = compositions[count][1]
            verdict["image_path"] = image_path
            verdict["slide_id"] = slide_id
            count += 1

        return VisualConsistencyResult.model_validate(data)
