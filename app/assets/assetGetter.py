import asyncio
import json
from pathlib import Path

import numpy as np

from app.core.transformerModelHandler import TransformerHandler
from app.data_models.prompt_package import PromptPackage

class AssetGetter:
    def __init__(self, asset_folder: Path = Path(r"D:\ProgramData\ARCArticleGeneration\app\assets"), transformer_handler: TransformerHandler = TransformerHandler()):
        self.asset_folder = asset_folder
        self.asset_folder.mkdir(parents=True, exist_ok=True)
        self.asset_files = [p for p in self.asset_folder.glob("*.json")]
        self.asset_list = []

        self.transformer_handler = transformer_handler
        self.find_all_asset()

    def find_all_asset(self) -> bool:
        object_list = []
        if not self.asset_files:
            return False

        for asset_file in self.asset_files:
            with open(asset_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for asset_list in data.values():
                object_list.extend(asset_list)

        self.asset_list = []
        for asset in object_list:
            curr_object_type = asset["object_id"].split("_")[0]
            description_sim = asset["description"].split("change of state for the element in slide:")[0] if "change of state for the element in slide:" in asset["description"] else asset["description"]

            self.asset_list.append([curr_object_type, description_sim, asset["asset_path"]])

        return True

    def _sync_get_existing_assets(self, visual, threshold):
        neccessary_elements = visual.metadata.get("element_used", [])
        matched = []

        if not neccessary_elements:
            return []

        to_seek = []
        for element_object in neccessary_elements:
            element, desc = element_object.split(":", 1)
            object_type = element.split("_")[0]
            potential_candidates = [asset for asset in self.asset_list if asset[0] == object_type]
            simplified_description = desc.split("change of state for the element in slide:")[0] if "change of state for the element in slide:" in desc else desc
            to_seek.append([element, simplified_description, potential_candidates])

        for element_object in to_seek:
            if len(matched) >= 2:
                break

            candidates = element_object[2]
            if not candidates:
                continue

            pairs = [(element_object[1], desc[1]) for desc in candidates]
            raw_scores = self.transformer_handler.ask_cross_encoder(pairs)

            to_compare = []
            for curr_index, logits in enumerate(raw_scores):
                exp_logits = np.exp(logits - np.max(logits))
                probabilities = exp_logits / exp_logits.sum()

                prob_entailment = probabilities[1]
                to_compare.append([curr_index, prob_entailment])

            if not to_compare:
                continue

            best_prob = max(to_compare, key=lambda x: x[1])

            if best_prob[1] > threshold:
                matched.append(candidates[best_prob[0]][2])

        return matched

    async def get_existing_assets(self, visual: PromptPackage, threshold=0.8):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_get_existing_assets, visual, threshold
        )