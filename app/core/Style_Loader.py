from pathlib import Path

import yaml

from app.data_models.style_class import StyleDefinition


class StyleLoader:
    def __init__(self, style_directory: str  = "D:\ProgramData\ARCArticleGeneration\styles"):
        self.style_directory = Path(style_directory)

    def load(self, style_name: str) -> StyleDefinition:
        path = (
                self.style_directory
                / f"{style_name}.yaml"
        )

        if not path.exists():
            raise FileNotFoundError(f"Style {style_name} not found")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return StyleDefinition.model_validate(data)