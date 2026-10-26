import asyncio
import json
import shutil
import tempfile
from copy import deepcopy
from enum import IntEnum
from pathlib import Path

from app.assets.assetGetter import AssetGetter
from app.core.engine import OllamaClient
from app.core.transformerModelHandler import TransformerHandler
from app.fixer.RepairEngine import RepairEngine
from app.generation.comfyui.launcher import start_comfyui, stop_comfyui
from app.generation.comfyui.pipeline import ComfyUIClient
from app.generation.comfyui.workflow import ComfyUIWorkflow
from app.generation.image_generator import imageGenerationService, save_comfyui_image
from app.visual.visualPrompt import VisualPlanner
from app.visualQA.data_models import CarouselQAResult, QAStatus
from app.visualQA.service import VisualQAServiceManager


class VisualRepairEngine:
    def __init__(self, qa_service: VisualQAServiceManager, asset_getter: AssetGetter, fixer: RepairEngine, model_name: str = "qwen3:8b", ollama_client: OllamaClient = None,
                 session_path: str = r"D:\ProgramData\ARCArticleGeneration\carousel_sessions", transformer_handler: TransformerHandler = TransformerHandler()):
        self.qa_service = qa_service
        self.model_name = model_name
        self.client = ollama_client
        self.fixer = fixer
        self.assetGetter = asset_getter
        self.session_path = Path(session_path)
        self.session_path.mkdir(parents=True, exist_ok=True)
        self.has_assets = False
        self.transformer_handler = transformer_handler

    class ActionRequired(IntEnum):
        REPAIR = 1
        REVISE_PROMPT = 2
        REPAIR_WHOLE_CAROUSEL = 3

    ERROR_CODE = {
        "STYLE_CONSISTENCY_FAILED": ActionRequired.REPAIR,
        "SLIDE_VISUAL_TOO_SIMILAR": ActionRequired.REPAIR,
        "IMAGE_CORRUPTED": ActionRequired.REPAIR,
        "WIDTH_HEIGHT_MISSING": ActionRequired.REPAIR,
        "WIDTH_MISSING": ActionRequired.REPAIR,
        "HEIGHT_MISSING": ActionRequired.REPAIR,
        "UNEXPECTED_WIDTH": ActionRequired.REPAIR,
        "UNEXPECTED_HEIGHT": ActionRequired.REPAIR,
        "EXPECTED_ASPECT_RATIO_NOT_FOUND": ActionRequired.REVISE_PROMPT,
        "UNEXPECTED_ASPECT_RATIO": ActionRequired.REPAIR,
        "NO_ELEMENT_FOUND": ActionRequired.REVISE_PROMPT,
        "IMAGE_SUPERFICIAL": ActionRequired.REVISE_PROMPT,
        "ELEMENT_NOT_FOUND_IN_IMAGE": ActionRequired.REPAIR,
        "NOT_ENOUGH_COORDINATES": ActionRequired.REPAIR,
        "IMAGE_PATH_MISSING": ActionRequired.REPAIR,
        "IMAGE_NOT_FOUND": ActionRequired.REPAIR,
        "IMAGE_NOT_FILE": ActionRequired.REPAIR,
        "NO_VISUAL_DESCRIPTION_FOUND": ActionRequired.REVISE_PROMPT,
        "OVERALL_IMAGE_DESCRIPTION_MISMATCH": ActionRequired.REPAIR,
        "BAD_IMAGE_QUALITY": ActionRequired.REPAIR
    }

    def filter_error(self, carousel_status: CarouselQAResult, trigger_level = QAStatus.FAIL, curr_retry_times = 0):
        error_log = {}
        error_slide_id = []

        if trigger_level == QAStatus.FAIL:
            carousel_issues = [issue for issue in carousel_status.issues if issue.status == QAStatus.FAIL]
        else:
            carousel_issues = carousel_status.issues

        for issues in carousel_issues:
            code = issues.code.upper()
            if "CAROUSEL" in code or "NO_VERDICT_RETURNED" in code:
                return self.ActionRequired.REPAIR_WHOLE_CAROUSEL

            if 'SLIDES' in code:
                slide_affected = issues.details["slide_ids"]
                error_slide_id.extend(slide_affected)

        for ids in error_slide_id:
            slide_errors = []
            slide = next(slide for slide in carousel_status.slides if slide.slide_id == ids)
            remaining_error = slide.issues

            if trigger_level == QAStatus.FAIL:
                remaining_error = [issue for issue in remaining_error if issue.status == QAStatus.FAIL]

            if not remaining_error:
                continue

            error_code_list = [self.ERROR_CODE[error.code] for error in remaining_error]
            priority_for_slide = max(error_code_list)

            for error in remaining_error:
                if curr_retry_times >= 2 or self.ERROR_CODE[error.code] == priority_for_slide:
                    slide_errors.append(error)

            error_log[ids] = slide_errors

        return error_log

    async def mainLoop(self, carousel_status: CarouselQAResult, carousel_id: str, curr_repair_times: int = 0, max_loop: int = 3):
        filter_error = self.filter_error(carousel_status, QAStatus.FAIL, curr_repair_times)

        if not filter_error:
            return QAStatus.PASS

        if isinstance(filter_error, self.ActionRequired):
            detail_string = ""
            for issue in carousel_status.issues:
                detail_string += f"\n {issue.model_dump_json(indent=4, ensure_ascii=False)}"

            print(f"Carousel requires total reconstruct, error: {detail_string}")
            return QAStatus.FAIL

        carousel = carousel_status.carousel

        bible_prompt = self.fixer.getBible(carousel)

        new_carousel = await self.determineAction(filter_error, bible_prompt, carousel)

        await self.client.unload_model(self.model_name)
        await self.client.unload_model("qwen3-vl:8b-instruct-q4_K_M")

        carousel_folder = self.session_path / carousel_id
        carousel_folder.mkdir(parents=True, exist_ok=True)

        process = start_comfyui()

        carousel_fixed = None
        try:
            client = ComfyUIClient()
            workflow = ComfyUIWorkflow(
                r"D:\ProgramData\ARCArticleGeneration\app\generation\comfyui\workflows\image_v0_2.json")

            image_service = imageGenerationService(client, workflow)
            await client.wait_for_comfyui()

            self.has_assets = self.assetGetter.find_all_asset()
            carousel_fixed, changed_slides_id = await self.regenerate_images(new_carousel, carousel_id=carousel_id, carousel_folder=carousel_folder,
                                                          curr_repair_times=curr_repair_times, image_service=image_service,
                                                          client=client, filter_error=filter_error)

        finally:
            stop_comfyui(process)

        carousel_new_path = carousel_folder / f"carousel_v{curr_repair_times + 1}.json"
        carousel_to_json = carousel_fixed.model_dump_json(indent=4, ensure_ascii=False)

        print(f"Revise carousel {curr_repair_times + 1}: {carousel_to_json}")

        carousel_new_path.write_text(carousel_to_json, encoding="utf-8")

        curr_carousel_status = self.qa_service.validate_carousel(carousel_fixed, carousel_id, retry_times=curr_repair_times + 1, changed_slides_id=changed_slides_id)
        await self.client.unload_model("qwen3-vl:8b-instruct-q4_K_M")

        if curr_carousel_status.status == QAStatus.PASS:
            return QAStatus.PASS

        if curr_repair_times < max_loop:
            new_time = curr_repair_times + 1
            return await self.mainLoop(curr_carousel_status, carousel_id, new_time, max_loop)

        return QAStatus.RETRY


    async def determineAction(self, filter_error, bible_prompt, carousel):
        curr_carousel = deepcopy(carousel)
        changed_slides = []

        for slide_id, errors in filter_error.items():
            to_do = self.ERROR_CODE[errors[0].code]

            if to_do == self.ActionRequired.REVISE_PROMPT:
                error_string = ""
                slide = curr_carousel.getSlide(slide_id)

                for error in errors:
                    error_string += f"\n {error.model_dump_json(indent=4, ensure_ascii=False)}"

                slide_element_string = ""
                for element in slide.visual.slide_elements:
                    slide_element_string += f"{element.toString()} \n"

                slide_string = f"""
                        Current Headline and Body:
                        Headline: {slide.headline}
                        Body: {slide.body}

                        Current Scene Description:
                        {slide.visual.scene_description}

                        Slide only element:
                        {slide_element_string}
                """

                change_prompt = f"""
                SLIDE {slide_id} ONLY:
                    {bible_prompt}

                Current Slide:
                {slide_string}
                    
                Slide requires a full revamp and redesign, follow the instructions / indicator below:
                the visuals will be redesigned based on the new headline / body / visual target
                BUT DO NOT CHANGE THE IMAGE PATH
                {error_string}
                """

                new_slide = self.fixer.askOllama(change_prompt)
                curr_carousel.changeSlide(slide_id, new_slide)
                changed_slides.append(slide_id)

        errors = await asyncio.to_thread(self.fixer.validator.validateSlides, curr_carousel, changed_slides)
        await self.client.unload_model(self.model_name)

        adjusted_errors = self.fixer.removeErrorLevel(errors)

        if adjusted_errors:
            success = await self.fixer.LoopRepair(curr_carousel, adjusted_errors)
            if not success:
                return carousel

        return curr_carousel


    async def regenerate_images(self, carousel, carousel_id, carousel_folder, curr_repair_times,
                                image_service, client, filter_error):

        visual_planner = VisualPlanner(carousel.visual_bible)
        changed_slides = []

        for slide in carousel.slides:
            if slide.slide_id not in filter_error:
                continue

            changed_slides.append(slide.slide_id)
            promptPackage = visual_planner.createVisualPrompt(slide, carousel_id)

            visual_save_file = carousel_folder / f"visual_{slide.slide_id}_v{curr_repair_times + 1}.json"
            asset_found = None

            if self.has_assets:
                asset_found = await self.assetGetter.get_existing_assets(promptPackage)

            if asset_found:
                with tempfile.TemporaryDirectory() as temp_dir_name:
                    folder = Path(temp_dir_name)
                    for asset in asset_found:
                        asset_path = Path(asset)
                        destination = folder / asset_path.name
                        shutil.copy2(asset_path, destination)

                    result = await image_service.generate(promptPackage, has_assets=True, temp_dir=temp_dir_name)
            else:
                result = await image_service.generate(promptPackage)

            slide.image_path = await save_comfyui_image(
                client=client,
                result=result,
                slide_id=slide.slide_id,
                output_dir=carousel_folder,
                version=curr_repair_times + 1
            )

            text_data = result['outputs']['311']["text"]
            new_neg_prompt = text_data[0] if isinstance(text_data, list) else text_data

            new_package = deepcopy(promptPackage)
            new_package.negative_prompt = new_neg_prompt

            print(f"visual prompt v{curr_repair_times + 1}: {new_package.model_dump_json(indent=4, ensure_ascii=False)}")

            with open(visual_save_file, "w", encoding="utf-8") as f:
                json.dump(
                    new_package.model_dump(),
                    f,
                    indent=4,
                    ensure_ascii=False
                )

        self.transformer_handler.cross_encoder_offload()

        return carousel, changed_slides



