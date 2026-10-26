import asyncio
import json

from app.generation.comfyui.pipeline import ComfyUIClient
from app.generation.comfyui.workflow import ComfyUIWorkflow


async def main():

    client = ComfyUIClient()

    stats = await client.get_system_stats()

    print(stats)

    workflow_creation = ComfyUIWorkflow(r"D:\ProgramData\ARCArticleGeneration\app\generation\comfyui\workflows\image_v0_1.json")

    workflow = workflow_creation.build(
        positive_prompt="""A calm wellness scene showing a young adult resting peacefully beside 
        a large sunlit window, surrounded by soft natural textures, indoor plants, 
        and a warm cup of tea. The atmosphere feels quiet, restorative, and emotionally comforting.
        """,
        negative_prompt="""blurry, low quality, low resolution, distorted anatomy, malformed hands, 
        extra fingers, missing fingers, duplicated objects, unnatural proportions, 
        harsh artificial lighting, oversaturated colors, cluttered composition, 
        text, watermark, logo, distracting background elements""",

        overall_visual="""Soft, peaceful wellness aesthetic with natural materials, muted earthy tones, 
        gentle sunlight, spacious composition, and a warm sense of emotional recovery.""",

        width=768,
        height=960,

        seed=759564661059046,
        carousel_id="c_099",
        current_slide=1,
    )

    prompt_id = await client.queue_prompt(workflow)

    result = await client.wait_for_completion(prompt_id)

    await client.close()

asyncio.run(main())