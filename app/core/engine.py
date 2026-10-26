import json

import httpx
import ollama

from app.core.generalFunction import JSON_FORMAT_PROMPT, PERSISTENT_ELEMENT_PROMPT
from app.core.promptConstructer import PromptConstruct
from app.data_models.container_class import Carousel
from app.data_models.style_class import StyleDefinition
from app.data_models.written_content import Language

class OllamaClient:
    def __init__(self, base_url="http://127.0.0.1:11434"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=300)

    async def unload_model(self, model: str):
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": model,
                "prompt": "",
                "keep_alive": 0,
            },
        )

        response.raise_for_status()


class ContentGenerator:
    def __init__(self, prompt_construct: PromptConstruct, ollama_client: OllamaClient, model_name = "qwen3:8b"):
        self.prompt_construct = prompt_construct
        self.ollama_client = ollama_client
        self.model_name = model_name

    async def generate(self, topic:str, style: StyleDefinition, language: Language, user_instruction: str = None) -> Carousel:
        visual_style = style.image
        prompt_style = f""" style name: {style.name}
        canvas size: {style.canva_size.width}px x {style.canva_size.height}px
        medium: {visual_style.medium}
        camera: {visual_style.camera}
        color palette: {visual_style.color_treatment}
        mood: {visual_style.mood}
        layout constraint: {style.getLayoutString}
        composition style: {visual_style.composition}
        negative_prompt: {style.negative_prompt}
        """

        response = ollama.chat(
            model=self.model_name,
            think=False,
            messages= [
                {
                    "role": "system",
                    "content": json.dumps({"identity_instruction": self.prompt_construct.getDefaultPrompt(),
                                                "persistent element instruction": PERSISTENT_ELEMENT_PROMPT,
                                                "field format requirement": JSON_FORMAT_PROMPT
                                           }, ensure_ascii=False)
                },
                {
                    "role": "user",
                    'content': json.dumps({
                        "topic": topic,
                        "style": prompt_style,
                        "language": language.name,
                        "user instruction": user_instruction if user_instruction else "",
                    }, ensure_ascii=False)
                }
            ],
            format=Carousel.model_json_schema()
        )

        data = json.loads(
            response['message']['content']
        )

        return Carousel.model_validate(data)

    async def unload_model(self):
        await self.ollama_client.unload_model(self.model_name)