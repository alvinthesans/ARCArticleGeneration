import json
from math import floor
from pathlib import Path
import ollama
from PIL import Image

from app.visualQA.data_models import VisualIssue, QAStatus, ElementObject, VLMOutputSlide, VLMOutput, Asset


class ComponentExtractor:
    def __init__(self, model_name="qwen3-vl:8b-instruct-q4_K_M"):
        self.model_name = model_name
        self.asset_folder = Path(r"D:\ProgramData\ARCArticleGeneration\app\assets")
        self.asset_folder.mkdir(parents=True, exist_ok=True)

    INSTRUCTION_PROMPT = f"""
    You are a image reviewer to see whether an image contains a list of object / characters
    you are to OUTPUT THE RESULT IN THE FOLLOWING FORMAT FOR EACH OBJECT in OutputObject:
        object_id: str
        object_name: str
        object_type: ObjectType
        bbox_2d: list = Field(default_factory=list, description="boundary box of object with coordinates")
        found: bool
        
    Where:
        object_id: remains the same as the element_id for the input of each object
            for example, if the element id has the format of: e_01, c_01, o_01, so_01, se_01, sc_01 it SHOULD NOT BE ALTERED.
        
        object_name: given the object description, give the object an appropriate, unique name
            for example: if the object is: 蕨類植物葉片, 
            CORRECT
            object_name: fern leaves
            
            WRONG
            object_name: leaves
            
            WRONG
            object_name: plant
            
        object_type: where do you think the object belongs to, what category should it be under:
            for example: object is a cat
            CORRECT:
            object_type: ObjectType.ANIMAL
            
            WRONG:
            object_type: ObjectType.CHARACTER
            
            WRONG:
            object_type: ObjectType.ARTIFICIAL
            
            example 2:
            object is a chair
            CORRECT:
            object_type: ObjectType.INDOOR
            
            WRONG:
            object_type: ObjectType.NATURE
            
        bbox_2d: the boundary box of the object, with the format [x1, y1, x2, y2], if it doesn't exist, return an empty list
            Return only a single tight bounding box enclosed entirely within the absolute physical borders of the object, 
            Completely exclude any unrelated object, including ground, reflections, background assets, and the neighboring objects. Your target box must firmly hug the object boundaries without any loose padding."
            for example: Detected a droplet
            
            DO NOT INCLUDE:
            moss, water, or background sticks
        
        found: if the object is found in the image, return True, else False
        
    Additionally, you would evaluate whether the image make sense in terms of image composition, for example, a flying person IS UNACCEPTABLE
    if yes: slide_make_sense = True
    if not: slide_make_sense = False 
            
    """

    def checkExistence(self, carousel_id: str, element: VLMOutput, manager_path: Path):
        if manager_path.exists() and manager_path.is_file():
            with open(manager_path, "r", encoding="utf-8") as file:
                dictionary = json.load(file)

            if element.object_type in dictionary:
                element = next((objects for objects in dictionary[element.object_type] if element.object_id == objects["object_id"] and carousel_id == objects["carousel_id"]), None)

            return True if not element else False

        return False


    def askSAM(self, image, element: VLMOutput, description: str, carousel_id):
        x1, y1, x2, y2 = element.bbox_2d
        width, height = image.size

        abs_x1 = int(x1 / 1000 * width)
        abs_y1 = int(y1 / 1000 * height)
        abs_x2 = int(x2 / 1000 * width)
        abs_y2 = int(y2 / 1000 * height)

        crop_box = (abs_x1, abs_y1, abs_x2, abs_y2)

        cropped_image = image.crop(crop_box)

        directory_path = self.asset_folder / element.object_type.value
        directory_path.mkdir(parents=True, exist_ok=True)

        to_save_path = self.get_new_file_name(element.object_name, directory_path)
        cropped_image.save(to_save_path)
        image_width, image_height = cropped_image.size

        return Asset(
            carousel_id=carousel_id,
            object_id=element.object_id,
            object_name=element.object_name,
            object_type=element.object_type,
            description=description,
            image_width=image_width,
            image_height=image_height,
            asset_path=to_save_path
        )

    def get_new_file_name(self, object_name: str, file_path: Path):
        file_count = 0
        for path in file_path.glob("*.png"):
            if object_name in path.stem:
                file_count += 1

        if file_count:
            file_to_save = file_path / f"{object_name}_{file_count}.png"
        else:
            file_to_save = file_path / f"{object_name}.png"

        return file_to_save

    def askVLM(self, element_objects: list[ElementObject], image_path: Path, slide_id, carousel_id):
        component_to_transverse = "Objects to seek for:"

        for element in element_objects:
            component_to_transverse += f"\n id: {element.element_id}, description: {element.description}"

        response = ollama.chat(
            model=self.model_name,
            messages=[{
                "role": "system",
                "content": self.INSTRUCTION_PROMPT
            },
                {
                    "role": "user",
                    'content': component_to_transverse,
                    'images': [image_path]
                }],
            format=VLMOutputSlide.model_json_schema(),
            options={
                "temperature": 0.1,
                "top_p": 0.9,
                "num_ctx": 4096
            }
        )
        data = json.loads(response['message']['content'])

        data["slide_id"] = slide_id
        data["carousel_id"] = carousel_id
        return VLMOutputSlide.model_validate(data)

    def get_file_path(self, carousel_id, batch=10):
        curr_carousel_count = int(carousel_id.split('_')[1])

        asset_manager_id = floor(curr_carousel_count / batch)
        asset_manager_name = f"asset_manager_{str(asset_manager_id).zfill(3)}.json"

        manager_path = self.asset_folder / asset_manager_name
        return manager_path

    def save_to_json(self, manager_path: Path, assets: list[Asset]):
        if manager_path.exists() and manager_path.is_file():
            with open(manager_path, "r", encoding="utf-8") as file:
                dictionary = json.load(file)
        else:
            dictionary = {}

        #sort into types
        for asset in assets:
            curr_type = asset.object_type
            if curr_type not in dictionary:
                dictionary[curr_type] = [asset.model_dump(mode="json")]
            else:
                dictionary[curr_type].append(asset.model_dump(mode="json"))

        with open(manager_path, "w") as file:
            json.dump(dictionary, file, indent=4, ensure_ascii=False)

    def getComponents(self, carousel_id, visual_path: Path, image_path: Path):
        issues = []

        with open(visual_path, "r", encoding="utf-8") as f:
            visual_data = json.load(f)

        metadata = visual_data["metadata"]

        explicit_used = metadata["element_used"]
        optional_choice = metadata["element_optional"]
        slide_only = metadata["slide_element"]
        slide_id = metadata["slide_id"]

        total_list = explicit_used + optional_choice

        if len(total_list) == 0:
            return [VisualIssue(
                code="NO_ELEMENT_FOUND",
                status=QAStatus.FAIL,
                message=f"No element found in {visual_path.name}",
            )]

        element_list = []
        for element in total_list:
            curr_text = element.split(":", 1)
            ids = curr_text[0]

            if "change of state for the element in slide:" in curr_text:
                description, state = curr_text[1].split("change of state for the element in slide:", 1)
            else:
                description = curr_text[1]
                state = ""

            if element in explicit_used:
                status = "embedded"
            else:
                status = "optional"

            element_list.append(ElementObject(
                category=status,
                element_id=ids,
                description=description,
                state=state if state else None
            ))

        if slide_only:
            for s_element in slide_only:
                element_list.append(ElementObject(
                    category="slide_only",
                    element_id=s_element["objectID"],
                    description=s_element["description"],
                    state=None
                ))

        results = self.askVLM(element_list, image_path, slide_id, carousel_id)
        print(results.model_dump_json(indent=4, ensure_ascii=False))

        if not results.slide_make_sense:
            issues.append(VisualIssue(
                code="IMAGE_SUPERFICIAL",
                status=QAStatus.FAIL,
                message=f"The image {image_path.name} doesn't make logical or realistic sense"
            ))

        image = Image.open(image_path).convert("RGB")

        manager_path = self.get_file_path(carousel_id)

        assets_list = []
        already_have_id = []

        for result in results.OutputObject:
            if not result.found:
                status = next(element.category for element in element_list if element.element_id == result.object_id)
                if status != "optional":
                    issues.append(VisualIssue(
                        code="ELEMENT_NOT_FOUND_IN_IMAGE",
                        status=QAStatus.FAIL,
                        message=f"The element {result.object_id} cannot be found in {image_path.name} and is compulsory"
                    ))
                continue

            if len(result.bbox_2d) != 4:
                issues.append(VisualIssue(
                    code="NOT_ENOUGH_COORDINATES",
                    status=QAStatus.FAIL,
                    message=f"The element {result.object_id} bounding box has been returned with wrong amount of coordinates, expected 4, returned {len(result.bbox_2d)} instead"
                ))
                continue

            curr_description = next(element.description for element in element_list if element.element_id == result.object_id)

            flag = self.checkExistence(carousel_id, result, manager_path)

            if not flag and result.object_id not in already_have_id:
                curr_asset = self.askSAM(image, result, curr_description, carousel_id)
                already_have_id.append(curr_asset.object_id)
                assets_list.append(curr_asset)

        self.save_to_json(manager_path, assets_list)

        return issues
