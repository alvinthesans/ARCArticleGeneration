import json
import shutil
from pathlib import Path

from app.data_models.container_class import Carousel


class RefreshStatus:
    def __init__(self, comfy_input: Path = Path(r"C:\Users\USER\Documents\ComfyUI\input"), comfy_output: Path = Path(r"C:\Users\USER\Documents\ComfyUI\output")):
        self.comfy_input = comfy_input
        self.comfy_output = comfy_output
        self.comfy_input.mkdir(parents=True, exist_ok=True)
        self.comfy_output.mkdir(parents=True, exist_ok=True)

    def refresh_comfyui_output(self, carousel_id: str):
        reference_image = self.comfy_input / f"{carousel_id}_00001_.png"
        reference_image.unlink(missing_ok=True)

        image_list = [path for path in self.comfy_output.glob(f"{carousel_id}_*.png")]
        for image_path in image_list:
            image_path.unlink(missing_ok=True)

    def deleteAll(self, carousel_path: Path, carousel_id: str):
        self.refresh_comfyui_output(carousel_id)
        shutil.rmtree(str(carousel_path), ignore_errors=True)

    def trace_back_carousel(self, carousel_path: Path, carousel_id: str, retrace_no: int):
        carousel_path.mkdir(parents=True, exist_ok=True)

        retrace_no_str = str(retrace_no)
        carousel_list = [carousel for carousel in carousel_path.glob("carousel*.json")]
        image_list = [image for image in carousel_path.glob("*.png") if f"v{retrace_no_str}" in image.name]
        to_remove = [image for image in carousel_path.glob("*.png") if image not in image_list]

        visual_status = carousel_path / "visual_status"
        visual_status.mkdir(parents=True, exist_ok=True)

        visual_consistency_qa = [item for item in visual_status.glob("*.json") if retrace_no_str not in item.stem]
        for visual_qa in visual_consistency_qa:
            visual_qa.unlink(missing_ok=True)

        remain_qa = next(visual_status.glob("*.json"))

        remain_qa.rename(remain_qa.with_name("VisualConsistency.json"))

        for path in to_remove:
            path.unlink(missing_ok=True)

        self.refresh_comfyui_output(carousel_id)

        for image_path in image_list:
            if "_v" in image_path.stem:
                new_name = image_path.stem.split("_v")[0]
                image_path.rename(image_path.with_name(f"{new_name}.png"))

            curr_count = image_path.stem.split("_")[1]

            file_name = f"{carousel_id}_{curr_count.zfill(5)}_.png"
            if curr_count == "01":
                input_to_path = self.comfy_input / file_name
                shutil.copy(image_path, input_to_path)

            shutil.copy(image_path, self.comfy_output / file_name)

        if retrace_no == 0:
            previous_carousel = carousel_path / f"carousel.json"
        else:
            previous_carousel = carousel_path / f"carousel_v{retrace_no}.json"

        carousel_list.remove(previous_carousel)

        for carousel in carousel_list:
            carousel.unlink(missing_ok=True)

        previous_carousel.rename(previous_carousel.with_name("carousel.json"))

        with open(previous_carousel, "r") as f:
            data = json.load(f)

        carousel = Carousel.model_validate(data)

        for slide in carousel.slides:
            curr_path = Path(slide.image_path)
            if "_v" in curr_path.stem:
                new_name = curr_path.stem.split("_v")[0]
                slide.image_path = str(curr_path.rename(curr_path.with_name(f"{new_name}.png")))

        return carousel
