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

        if retrace_no == 0:
            previous_carousel = carousel_path / f"carousel.json"
        else:
            previous_carousel = carousel_path / f"carousel_v{retrace_no}.json"

        with open(previous_carousel, "r" ,encoding="utf-8") as f:
            curr_carrousel = json.load(f)

        image_list = [Path(slide["image_path"]) for slide in curr_carrousel["slides"]]
        to_remove = [image for image in carousel_path.glob("*.png") if image not in image_list]
        for path in to_remove:
            path.unlink(missing_ok=True)

        self.refresh_comfyui_output(carousel_id)

        for slide in curr_carrousel["slides"]:
            curr_path = Path(slide["image_path"])

            if "_v" in curr_path.stem:
                new_name = curr_path.stem.split("_v")[0]
                curr_path = curr_path.rename(curr_path.with_name(f"{new_name}.png"))

            slide["image_path"] = str(curr_path)
            curr_count = curr_path.stem.split("_")[1]

            file_name = f"{carousel_id}_{curr_count.zfill(5)}_.png"
            if curr_count == "01":
                input_to_path = self.comfy_input / file_name
                shutil.copy2(curr_path, input_to_path)

            shutil.copy2(curr_path, self.comfy_output / file_name)

        visual_status = carousel_path / "visual_status"
        visual_status.mkdir(parents=True, exist_ok=True)

        #Find the actual report name directory
        report_name = ("VisualConsistency.json" if retrace_no == 0
            else f"VisualConsistency{retrace_no:02d}.json")

        #Actual file path
        selected_report = visual_status / report_name

        #Validation error check
        if not selected_report.exists():
            raise FileNotFoundError(selected_report)

        for report in visual_status.glob("*.json"):
            if report != selected_report:
                report.unlink(missing_ok=True)

        if selected_report.name != "VisualConsistency.json":
            selected_report.rename(visual_status / "VisualConsistency.json")

        carousel_list.remove(previous_carousel)

        for carousel in carousel_list:
            carousel.unlink(missing_ok=True)

        previous_carousel = previous_carousel.rename(previous_carousel.with_name("carousel.json"))

        previous_carousel.write_text(
            json.dumps(curr_carrousel, indent=4, ensure_ascii=False),
            encoding="utf-8"
        )

        return Carousel.model_validate(curr_carrousel)
