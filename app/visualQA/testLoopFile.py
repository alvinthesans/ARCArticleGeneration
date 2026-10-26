import asyncio
import json
from pathlib import Path

from app.core.Style_Loader import StyleLoader
from app.core.engine import OllamaClient
from app.data_models.container_class import Carousel
from app.visualQA.VLMQA.StyleConsistency import CarouselConsistentStyleValidator
from app.visualQA.VLMQA.component_extractor import ComponentExtractor
from app.visualQA.deterministic_file_validator import DeterministicFileValidator
from app.visualQA.service import VisualQAServiceManager


#
# service_manager = VisualQAServiceManager(deterministic_validator=fileValidator)
#
# carousel_string = Path(r"D:\ProgramData\ARCArticleGeneration\carousel_sessions\c_007\carousel.json").read_text()
# carousel = Carousel.model_validate_json(carousel_string)
# qa = service_manager.validate_carousel(carousel)

#print(qa.model_dump_json(indent=2))

styleLoader = StyleLoader()
style = styleLoader.load("minimal_editorial")
aspect_ratio = style.canva_size.width / style.canva_size.height

ollama_client = OllamaClient()

fileValidator = DeterministicFileValidator(expected_width=style.canva_size.width,
                                           expected_height=style.canva_size.height,
                                           expected_aspect_ratio=aspect_ratio)

component_extractor = ComponentExtractor(ollama_client)
consistency_checker = CarouselConsistentStyleValidator(ollama_client)

qaManager = VisualQAServiceManager(deterministic_validator=fileValidator, component_extractor=component_extractor, consistency_checker=consistency_checker)

async def main():
    carousel = Path(r"D:\ProgramData\ARCArticleGeneration\carousel_sessions\c_002\carousel.json")
    carousel_string = carousel.read_text(encoding="utf-8")
    carousel = Carousel.model_validate_json(carousel_string)

    result = qaManager.validate_carousel(carousel, "c_002")

    print(result.model_dump_json(indent=4, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())