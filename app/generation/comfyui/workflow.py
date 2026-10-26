import copy, json
from pathlib import Path

class ComfyUIWorkflow:
    def __init__(self, workflow_path: str | Path):
        self.workflow_path = Path(workflow_path)

        with open(self.workflow_path, "r") as f:
            self.template = json.load(f)

    def find_node_by_title(self, title):
        for node_id, node_data in self.template.items():
            if "_meta" in node_data and node_data["_meta"].get("title") == title:
                return node_id
        raise ValueError(f"Node with title '{title}' not found!")

    def build(self, positive_prompt: str, negative_prompt: str,
              overall_visual: str, seed:int, width:int, height:int,
            carousel_id: str, current_slide:int, has_assets = False, temp_dir: str = None) -> dict:

        workflow = copy.deepcopy(self.template)

        node = {
            "positive_prompt": workflow[self.find_node_by_title("Slide Visual Prompt")],
            "negative_prompt": workflow[self.find_node_by_title("Negative Prompt default")],
            "overall_visual": workflow[self.find_node_by_title("Overall visual setting")],
            "use_image": workflow[self.find_node_by_title("Use image?")],
            "image reference": workflow[self.find_node_by_title("Image direct reference")],
            "prompt_refine": workflow[self.find_node_by_title("Visual prompt refine with image?")],
            "reference_image": workflow[self.find_node_by_title("Load Image with Switch")],
            "image_size": workflow[self.find_node_by_title("Image size (Input)")],
            "sampler": workflow[self.find_node_by_title("SamplerCustom")],
            "output": workflow[self.find_node_by_title("Image output")],
            "asset_input": workflow[self.find_node_by_title("Asset Reference")],
            "image_edit": workflow[self.find_node_by_title("Image Edit?")],
        }

        node["positive_prompt"]["inputs"]["value"] = positive_prompt
        node["negative_prompt"]["inputs"]["value"] = negative_prompt
        node["overall_visual"]["inputs"]["value"] = overall_visual

        if current_slide == 1:
            node["use_image"]["inputs"]["value"] = False
            node["prompt_refine"]["inputs"]["value"] = False
        else:
            node["use_image"]["inputs"]["value"] = True
            node["prompt_refine"]["inputs"]["value"] = True

            if has_assets:
                node["image_edit"]["inputs"]["value"] = True
                node["asset_input"]["inputs"]["folder"] = temp_dir

            node["reference_image"]["inputs"]["image"] = f"{carousel_id}_00001_.png"

        node["image_size"]["inputs"]["width"] = width
        node["image_size"]["inputs"]["height"] = height
        node["output"]["inputs"]["filename_prefix"] = carousel_id

        node["sampler"]["inputs"]["noise_seed"] = seed

        return workflow
