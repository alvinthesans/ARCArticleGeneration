import json
from pathlib import Path

from app.core.generalFunction import copy_to_comfyui_input
from app.data_models.prompt_package import PromptPackage


class imageGenerationService:
    def __init__(self, client, workflow):
        self.client = client
        self.workflow = workflow

    async def generate(self, prompt: PromptPackage, has_assets: bool = False, temp_dir: str = None) -> dict:
        workflow = self.workflow.build(
            positive_prompt= prompt.positive_prompt,
            negative_prompt= prompt.negative_prompt,
            overall_visual= prompt.overall_visual,

            seed = prompt.seed,
            width = prompt.width,
            height = prompt.height,

            carousel_id = prompt.metadata["carousel_id"],
            current_slide = prompt.metadata["slide_id"],
            has_assets = has_assets,
            temp_dir = temp_dir
        )

        with open("debug_workflow.json", "w", encoding="utf-8") as f:
            json.dump(
                workflow,
                f,
                indent=2,
                ensure_ascii=False
            )

        prompt_id = await self.client.queue_prompt(workflow)

        result = await self.client.wait_for_completion(prompt_id)

        if prompt.metadata["slide_id"] == 1:
            copy_to_comfyui_input(
                r"C:\Users\USER\Documents\ComfyUI\output",
                r"C:\Users\USER\Documents\ComfyUI\input",
                f"{prompt.metadata["carousel_id"]}_00001_.png"
            )

        return result

async def save_comfyui_image(client, result: dict,*,slide_id: int,output_dir: str, version: int = None) -> str:
    image_info = None

    for node_output in result.get("outputs", {}).values():
        images = node_output.get("images", [])

        if images:
            image_info = images[0]
            break

    if image_info is None:
        raise RuntimeError("No image returned by ComfyUI")

    image_bytes = await client.download_image(
        filename=image_info["filename"],
        subfolder=image_info.get("subfolder", ""),
        image_type=image_info.get("type", "output"),
    )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if version:
        final_path = output_path / f"slideImage_{slide_id:02d}_v{version}.png"
    else:
        final_path = output_path / f"slideImage_{slide_id:02d}.png"
    final_path.write_bytes(image_bytes)

    return str(final_path)