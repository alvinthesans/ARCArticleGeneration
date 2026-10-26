from pathlib import Path

from app.core.transformerModelHandler import TransformerHandler
from app.data_models.container_class import Carousel
from app.visualQA.VLMQA.StyleConsistency import CarouselConsistentStyleValidator
from app.visualQA.VLMQA.component_extractor import ComponentExtractor
from app.visualQA.semanticQA.semantic_qa import SemanticEncoder
from app.visualQA.deterministic_file_validator import DeterministicFileValidator
from app.visualQA.data_models import CarouselQAResult, QAStatus, VisualIssue, SlideQAResult

class VisualQAServiceManager:
    def __init__(self, deterministic_validator: DeterministicFileValidator, component_extractor: ComponentExtractor, consistency_checker: CarouselConsistentStyleValidator, semantic: SemanticEncoder = SemanticEncoder(),
                 transformer_handler: TransformerHandler = TransformerHandler()):
        self.deterministic_validator = deterministic_validator
        self.semantic = semantic
        self.component_extractor = component_extractor
        self.consistency_checker = consistency_checker
        self.carousel_session_path = Path(r"D:\ProgramData\ARCArticleGeneration\carousel_sessions")
        self.carousel_session_path.mkdir(parents=True, exist_ok=True)
        self.folder_path = None
        self.curr_carousel_id = None
        self.transformer_handler = transformer_handler

    def validate_carousel(self, carousel: Carousel, carousel_id: str, semantic_threshold: float = 0.52, negative_threshold: float = 0.2,
                                retry_times: int = 0, folder_path: str | Path = None, changed_slides_id: list = None) -> CarouselQAResult:
        results = []
        issues = []

        if not self.folder_path or self.curr_carousel_id != carousel_id:
            if folder_path:
                self.folder_path = Path(folder_path)
            else:
                self.folder_path = self.carousel_session_path / carousel_id

            self.curr_carousel_id = carousel_id
            self.folder_path.mkdir(parents=True, exist_ok=True)

        if changed_slides_id:
            slides = [slide for slide in carousel.slides if slide.slide_id in changed_slides_id]
        else:
            slides = carousel.slides

        for slide in slides:
            image_path = Path(slide.image_path)

            if not image_path:
                results.append(SlideQAResult(
                    slide_id=slide.slide_id,
                    status=QAStatus.FAIL,
                    issues=[
                        VisualIssue(
                            code="IMAGE_PATH_MISSING",
                            status=QAStatus.FAIL,
                            message="Slide has no image path.",
                        )]))
                continue

            if not image_path.exists():
                results.append(SlideQAResult(
                    slide_id=slide.slide_id,
                    status=QAStatus.FAIL,
                    image=None,
                    issues=[
                        VisualIssue(
                            code="IMAGE_NOT_FOUND",
                            status=QAStatus.FAIL,
                            message=f"Image file does not exist: {image_path}")])
                )
                continue

            if not image_path.is_file():
                results.append(SlideQAResult(
                    slide_id=slide.slide_id,
                    status=QAStatus.FAIL,
                    image=None,
                    issues=[
                        VisualIssue(
                            code="IMAGE_NOT_FILE",
                            status=QAStatus.FAIL,
                            message=f"Image path is not a file: {image_path}")])
                )
                continue

            result = self.deterministic_validator.validate(slide_id=slide.slide_id, image_path=image_path)

            if result.status == QAStatus.FAIL:
                results.append(result)
                continue

            if retry_times > 0:
                visual_path = self.folder_path / f"visual_{slide.slide_id}_v{retry_times}.json"
            else:
                visual_path = self.folder_path / f"visual_{slide.slide_id}.json"

            if not visual_path.exists() or not visual_path.is_file():
                result.issues.append(VisualIssue(
                    code="NO_VISUAL_DESCRIPTION_FOUND",
                    status=QAStatus.FAIL,
                    message=f"The visual description {visual_path.name} cannot be found in {self.folder_path}"
                ))
                results.append(result)
                continue

            semantic_score = self.semantic.validate(slide_id=slide.slide_id, carousel=carousel,
                                                    visual_path=visual_path, image_path=image_path, threshold=semantic_threshold)

            print(semantic_score.model_dump_json(indent=4, ensure_ascii=False))

            if semantic_score.scene_score < semantic_threshold:
                result.issues.append(VisualIssue(
                    code="OVERALL_IMAGE_DESCRIPTION_MISMATCH",
                    status=QAStatus.FAIL,
                    message=f"Slide: {slide.slide_id}, visual semantic score got {semantic_score.scene_score:.2f}%, expected {semantic_threshold:.2f}%",
                    details= {
                        "semantic score:" : semantic_score.scene_score,
                        "visual description of slide": semantic_score.visual_prompt,
                        "image path": semantic_score.image_path
                    }
                ))

            if semantic_score.negative_score > negative_threshold:
                result.issues.append(VisualIssue(
                    code="BAD_IMAGE_QUALITY",
                    status=QAStatus.FAIL,
                    message=f"Slide: {slide.slide_id}, negative score got {semantic_score.negative_score:.2f}%, expected {negative_threshold:.2f}%",
                    details={
                        "negative score": semantic_score.negative_score,
                        "negative prompt of slide": semantic_score.negative_prompt,
                        "image path": semantic_score.image_path
                    }
                ))

            component_extracted = self.component_extractor.getComponents(carousel_id=carousel_id, image_path=image_path, visual_path=visual_path)

            if component_extracted:
                result.issues.extend(component_extracted)

            status = next((issue.status for issue in result.issues if issue.status == QAStatus.FAIL), QAStatus.PASS)

            if status == QAStatus.PASS:
                status = next((issue.status for issue in result.issues if issue.status == QAStatus.WARN),
                              QAStatus.PASS)

            result.status = status

            results.append(result)

        self.transformer_handler.siglip_model_offload()

        style_consistency_check, slide_issues = self.consistency_checker.findConsistency(carousel=carousel, carousel_id=carousel_id, changed_slides=changed_slides_id)

        if slide_issues:
            for key, value in slide_issues.items():
                curr_slide = next(result for result in results if result.slide_id == key)
                curr_slide.issues.extend(value)

                if curr_slide.status == QAStatus.FAIL:
                    continue
                else:
                    status = next((issue.status for issue in curr_slide.issues if issue.status == QAStatus.WARN), QAStatus.PASS)

                    if status == QAStatus.PASS:
                        status = next((issue.status for issue in curr_slide.issues if issue.status == QAStatus.FAIL), QAStatus.PASS)

                    curr_slide.status = status

        failed_slides = [result for result in results if result.status == QAStatus.FAIL]
        warned_slides = [result for result in results if result.status == QAStatus.WARN]

        if failed_slides:
            issues.append(
                VisualIssue(
                    code="SLIDES_FAILED",
                    status=QAStatus.FAIL,
                    message=(
                        f"{len(failed_slides)} slide(s) failed for image QA."),
                    details={
                        "slide_ids": [result.slide_id for result in failed_slides]
                    }))

        if warned_slides:
            issues.append(
                VisualIssue(
                    code="SLIDES_WARNED",
                    status=QAStatus.WARN,
                    message=(
                        f"{len(warned_slides)} slide(s) trigger warning for image QA."),
                    details={
                        "slide_ids": [result.slide_id for result in warned_slides]
                    }))

        if style_consistency_check:
            issues.extend(style_consistency_check)

        if any(issue.status == QAStatus.FAIL for issue in issues):
            status = QAStatus.FAIL
        elif any(issue.status == QAStatus.WARN for issue in issues):
            status = QAStatus.WARN
        else:
            status = QAStatus.PASS

        current_carousel = CarouselQAResult(
            carousel=carousel,
            status=status,
            slides=results,
            issues=issues
        )

        print(current_carousel.model_dump_json(indent=4, ensure_ascii=False))

        visual_status_dir = self.folder_path / "visual_status"
        visual_status_dir.mkdir(parents=True, exist_ok=True)

        if retry_times > 0:
            file_name = f"VisualConsistency{str(retry_times).zfill(2)}.json"
        else:
            file_name = f"VisualConsistency.json"

        file_path = visual_status_dir / file_name

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(current_carousel.model_dump_json(indent=4, ensure_ascii=False))

        return current_carousel