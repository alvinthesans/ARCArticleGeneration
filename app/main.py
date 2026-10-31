import asyncio
import json
import logging
import shutil
import tempfile

from copy import deepcopy
from pathlib import Path
import gc
import torch

from app.assets.assetGetter import AssetGetter
from app.core.Style_Loader import StyleLoader
from app.core.engine import ContentGenerator, OllamaClient
from app.core.generalFunction import findNextFileID
from app.core.promptConstructer import PromptConstruct
from app.core.refreshStatus import RefreshStatus
from app.core.transformerModelHandler import TransformerHandler
from app.core.validator_main import Validator
from app.data_models.written_content import Language
from app.fixer.RepairEngine import RepairEngine
from app.fixer.VisualRepairEngine import VisualRepairEngine
from app.generation.comfyui.launcher import start_comfyui, stop_comfyui
from app.generation.comfyui.pipeline import ComfyUIClient
from app.generation.comfyui.workflow import ComfyUIWorkflow
from app.generation.image_generator import imageGenerationService, save_comfyui_image
from app.visual.visualPrompt import VisualPlanner
from app.visualQA.VLMQA.StyleConsistency import CarouselConsistentStyleValidator
from app.visualQA.VLMQA.component_extractor import ComponentExtractor
from app.visualQA.data_models import QAStatus
from app.visualQA.deterministic_file_validator import DeterministicFileValidator
from app.visualQA.semanticQA.semantic_qa import SemanticEncoder
from app.visualQA.service import VisualQAServiceManager

logger = logging.getLogger(__name__)

MODEL_CONTENT = "qwen3:8b"
MODEL_VLM = "qwen3-vl:8b-instruct-q4_K_M"
COMFY_NODE_ID = "311"
COMFY_WORKFLOW_PATH = Path(
    r"D:\ProgramData\ARCArticleGeneration\app\generation\comfyui\workflows\image_v0_2.json"
)

ollamaClient = OllamaClient()
styleLoader = StyleLoader()
prompt_constructer = PromptConstruct()
contentGen = ContentGenerator(prompt_constructer, ollamaClient)
transformer_handler = TransformerHandler()
assetGetter = AssetGetter(transformer_handler=transformer_handler)
status_refresh = RefreshStatus()
semantic_encoder = SemanticEncoder(transformer_handler=transformer_handler)
component_extractor = ComponentExtractor()
consistency_checker = CarouselConsistentStyleValidator()

async def run_pipeline(retries_left: int = 3):
    if retries_left <= 0:
        logger.error("Pipeline failed consistently after multiple retries. Aborting.")
        return QAStatus.FAIL

    language = Language.TRADITIONAL_CHINESE
    style = styleLoader.load("minimal_editorial")
    topic = "慢下来，才能看见生活"
    user_prompt = """做一个关于“慢下来，才能看见生活”的中文 Instagram 轮播。
                    希望整体感觉安静、温暖、有一点治愈感，但不要太刻意或者空泛。可以通过日常生活和自然中的一些小片段来表达，比如清晨窗边的阳光、雨后的街道、安静的咖啡馆、树影、河边、黄昏的天空之类的。
                    每一页最好有不同的场景和构图，不要一直重复同一种画面。可以有远景，也可以有很近的细节，有些画面可以留很多空白，有些则可以让自然元素充满整个画面。希望不同场景之间虽然不一样，但看起来仍然属于同一个视觉系列。
                    不要出现人物，重点通过环境、物件、光影和空间感来表达“从忙碌到放慢，再重新注意到身边的小事”这个过程。
                    文字不要太长，要像是在分享一个简单但值得思考的生活感受，而不是在说教。"""

    try:
        result = await main(language, style, topic, user_prompt)
        if result is None:
            return await run_pipeline(retries_left - 1)

        carousel_validated, carousel_location, st, r_e, c_id = result

        qa_status = await visual_qa(
            st, carousel_validated, c_id, carousel_location, r_e,
            retries_left=retries_left
        )

        if qa_status == QAStatus.FAIL and retries_left > 1:
            logger.warning(
                "Visual QA failed. Retrying full pipeline (%s retries left).",
                retries_left - 1
            )
            return await run_pipeline(retries_left - 1)

        print(f"the application has ran successfully uptill Visual QA! {qa_status}")
        return qa_status

    except Exception:
        logger.exception("Pipeline run failed")
        await refresh_all(ollamaClient)
        return await run_pipeline(retries_left - 1)


async def refresh_all(ollama_client: OllamaClient):
    for model in (MODEL_CONTENT, MODEL_VLM):
        try:
            await ollama_client.unload_model(model)
        except Exception:
            logger.warning("Failed to unload model %s", model, exc_info=True)

    for var_name in list(globals().keys()):
        obj = globals().get(var_name)
        if obj is None:
            continue

        cls_str = str(obj.__class__)
        if "transformers." in cls_str or "torch.nn." in cls_str:
            del globals()[var_name]

    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


async def main(language, style, topic, user_prompt=None):
    should_retry = False
    carousel = None
    repair_engine = None

    try:
        carousel = await contentGen.generate(topic, style, language, user_prompt)
        validator = Validator(style)
        repair_engine = RepairEngine(validator, ollamaClient)

        errors = await asyncio.to_thread(validator.validateSlides, carousel)
        adjusted_errors = repair_engine.removeErrorLevel(errors)

        if adjusted_errors:
            success = await repair_engine.LoopRepair(carousel, adjusted_errors)
            if not success:
                should_retry = True

    except Exception:
        logger.exception("Content generation/repair failed")
        should_retry = True

    finally:
        await contentGen.unload_model()

    if should_retry or carousel is None or repair_engine is None:
        return None

    current_save_location, carousel_id = findNextFileID()
    print(
        "Carousel before image generation:\n"
        + carousel.model_dump_json(indent=2, ensure_ascii=False)
    )

    process = None
    try:
        process = start_comfyui()
        client = ComfyUIClient()
        workflow = ComfyUIWorkflow(COMFY_WORKFLOW_PATH)
        image_service = imageGenerationService(client, workflow)

        await client.wait_for_comfyui()

        carousel_with_img = await generate_carousel_images(
            carousel, current_save_location, carousel_id, client, image_service
        )

        carousel_final = carousel_with_img.model_dump_json(
            indent=2, ensure_ascii=False
        )

        carousel_path = current_save_location / "carousel.json"
        carousel_path.write_text(carousel_final, encoding="utf-8")

        return carousel_with_img, current_save_location, style, repair_engine, carousel_id

    finally:
        if process is not None:
            stop_comfyui(process)


async def generate_carousel_images(
    carousel, current_save_location, carousel_id, client, image_service
):
    visual_planner = VisualPlanner(carousel.visual_bible)
    stats = await client.get_system_stats()
    print(stats)

    has_assets = assetGetter.find_all_asset()

    for slide in carousel.slides:
        promptPackage = visual_planner.createVisualPrompt(slide, carousel_id)
        visual_save_file = current_save_location / f"visual_{slide.slide_id}.json"
        asset_found = None

        if has_assets:
            asset_found = await assetGetter.get_existing_assets(promptPackage)

        if asset_found:
            with tempfile.TemporaryDirectory() as temp_dir_name:
                folder = Path(temp_dir_name)
                for asset in asset_found:
                    asset_path = Path(asset)
                    destination = folder / asset_path.name
                    shutil.copy2(asset_path, destination)

                result = await image_service.generate(
                    promptPackage, has_assets=True, temp_dir=temp_dir_name
                )
        else:
            result = await image_service.generate(promptPackage)

        slide.image_path = await save_comfyui_image(
            client=client,
            result=result,
            slide_id=slide.slide_id,
            output_dir=current_save_location,
        )

        text_data = (
            result.get("outputs", {})
            .get(COMFY_NODE_ID, {})
            .get("text")
        )

        if text_data is None:
            logger.warning(
                "No text output found for node %s; keeping original negative prompt.",
                COMFY_NODE_ID,
            )
            new_neg_prompt = promptPackage.negative_prompt
        else:
            new_neg_prompt = text_data[0] if isinstance(text_data, list) else text_data

        new_package = deepcopy(promptPackage)
        new_package.negative_prompt = new_neg_prompt

        print(
            f"final visual prompt: "
            f"{new_package.model_dump_json(indent=4, ensure_ascii=False)}"
        )

        with open(visual_save_file, "w", encoding="utf-8") as f:
            json.dump(
                new_package.model_dump(),
                f,
                indent=4,
                ensure_ascii=False,
            )

    transformer_handler.cross_encoder_offload()
    return carousel


async def visual_qa(style, carousel, carousel_id, carousel_folder, repair_engine, retries_left=3):
    qa_status = QAStatus.PASS
    try:
        aspect_ratio = style.canva_size.width / style.canva_size.height

        file_validator = DeterministicFileValidator(
            expected_width=style.canva_size.width,
            expected_height=style.canva_size.height,
            expected_aspect_ratio=aspect_ratio,
        )

        qa_service = VisualQAServiceManager(
            deterministic_validator=file_validator,
            component_extractor=component_extractor,
            consistency_checker=consistency_checker,
            semantic= semantic_encoder,
            transformer_handler=transformer_handler,
        )

        visual_errors = qa_service.validate_carousel(carousel, carousel_id, folder_path=carousel_folder)

        await ollamaClient.unload_model(MODEL_VLM)

        if visual_errors:
            visual_repair_engine = VisualRepairEngine(
                qa_service,
                assetGetter,
                repair_engine,
                ollama_client=ollamaClient,
                transformer_handler=transformer_handler
            )

            qa_status = await visual_repair_engine.mainLoop(
                visual_errors, carousel_id
            )

            if qa_status == QAStatus.RETRY:
                if retries_left <= 1:
                    logger.error("Visual QA retry limit reached.")
                    return QAStatus.FAIL

                await refresh_all(ollamaClient)

                visual_status = carousel_folder / "visual_status"
                visual_status.mkdir(parents=True, exist_ok=True)
                visual_consistency_qa = list(visual_status.glob("*.json"))

                if not visual_consistency_qa:
                    logger.error(
                        "Retry requested but no visual status registry logs found."
                    )
                    return QAStatus.FAIL

                penalty_score = []
                for visual_qa_file in visual_consistency_qa:
                    with open(visual_qa_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    suffix = visual_qa_file.stem.split("Consistency")[1]
                    index_no = int(suffix) if suffix else 0
                    penalty = 0
                    for issue in data.get("issues", []):
                        details = issue.get("details", {})
                        slide_ids = details.get("slide_ids")
                        if slide_ids is not None:
                            penalty += len(slide_ids)
                        else:
                            penalty += 1
                    penalty_score.append((index_no, penalty))

                if not penalty_score:
                    return QAStatus.FAIL

                min_index = min(penalty_score, key=lambda x: x[1])[0]

                best_carousel = status_refresh.trace_back_carousel(
                    carousel_path=carousel_folder,
                    carousel_id=carousel_id,
                    retrace_no=min_index,
                )

                if best_carousel is None:
                    logger.error("Could not trace back best carousel.")
                    return QAStatus.FAIL

                return await visual_qa(
                    style,
                    best_carousel,
                    carousel_id,
                    carousel_folder,
                    repair_engine,
                    retries_left=retries_left - 1,
                )

            elif qa_status == QAStatus.FAIL:
                status_refresh.deleteAll(carousel_folder, carousel_id)
                return QAStatus.FAIL
        else:
            qa_status = QAStatus.PASS

        print(qa_status)

    finally:
        await refresh_all(ollamaClient)

    return qa_status


if __name__ == "__main__":
    asyncio.run(run_pipeline())