from PIL import Image, UnidentifiedImageError
from pathlib import Path
from app.visualQA.data_models import SlideQAResult
from app.visualQA.data_models import ImageFileInfo, QAStatus, VisualIssue

class DeterministicFileValidator:
    def __init__(self, *, expected_width: int | None = None,
        expected_height: int | None = None, expected_aspect_ratio: float | None = None,
        aspect_ratio_tolerance: float = 0.01):

        self.expected_width = expected_width
        self.expected_height = expected_height
        self.expected_aspect_ratio = expected_aspect_ratio
        self.aspect_ratio_tolerance = aspect_ratio_tolerance

    def validate(self, slide_id: int, image_path: Path) -> SlideQAResult:
        info = ImageFileInfo(
            path=str(image_path),
            exists=image_path.exists(),
            file_size_bytes=image_path.stat().st_size
            if image_path.exists() and image_path.is_file() else None)

        try:
            with Image.open(image_path) as image:
                image.verify() # verify if image can be decoded

            with Image.open(image_path) as image:
                info.readable = True
                info.width = image.width
                info.height = image.height
                info.format = image.format

        except (UnidentifiedImageError, OSError, ValueError) as exc:
            return SlideQAResult(
                slide_id=slide_id,
                status=QAStatus.FAIL,
                image=info,
                issues=[
                    VisualIssue(
                        code="IMAGE_CORRUPTED",
                        status=QAStatus.FAIL,
                        message="Image could not be decoded.",
                        details={"error": str(exc)},
                    )])

        issues: list[VisualIssue] = []

        self.check_dimensions(info, issues)
        self.check_aspect_ratio(info, issues)

        status = self.resolve_status(issues)

        return SlideQAResult(
            slide_id=slide_id,
            status=status,
            image=info,
            issues=issues,
        )

    def check_dimensions(self,info: ImageFileInfo,issues: list[VisualIssue]) -> None:
        if not info.width or not info.height:
            if not info.width and not info.height:
                missing = "WIDTH AND HEIGHT"
                code = "WIDTH_HEIGHT_MISSING"
            else:
                missing = "WIDTH" if not info.width else "HEIGHT"
                code = f"{missing}_MISSING"

            issues.append(
                VisualIssue(
                    code=code,
                    status=QAStatus.FAIL,
                    message=(
                        f"dimension of image should contain value, but {missing.lower()} is missing."
                    )))
            return

        if self.expected_width and info.width != self.expected_width:
            issues.append(
                VisualIssue(
                    code="UNEXPECTED_WIDTH",
                    status=QAStatus.FAIL,
                    message=(
                        f"Expected width {self.expected_width}, "
                        f"got {info.width}."
                    ),
                    details={
                        "expected": self.expected_width,
                        "actual": info.width,
                    }))

        if self.expected_height and info.height != self.expected_height:
            issues.append(
                VisualIssue(
                    code="UNEXPECTED_HEIGHT",
                    status=QAStatus.FAIL,
                    message=(
                        f"Expected height {self.expected_height}, "
                        f"got {info.height}."
                    ),
                    details={
                        "expected": self.expected_height,
                        "actual": info.height,
                    }))

    def check_aspect_ratio(self, info: ImageFileInfo, issues: list[VisualIssue]) -> None:

        if self.expected_aspect_ratio is None or not info.width or not info.height:
            has_aspect_ratio = True if self.expected_aspect_ratio else False
            if not has_aspect_ratio:
                issues.append(
                    VisualIssue(
                        code="EXPECTED_ASPECT_RATIO_NOT_FOUND",
                        status=QAStatus.FAIL,
                        message=(
                            f"Expected Aspect ratio not found inside the validator, value: {self.expected_aspect_ratio}."
                        )))
            return

        actual_ratio = info.width / info.height

        if abs(actual_ratio - self.expected_aspect_ratio) > self.aspect_ratio_tolerance:
            issues.append(
                VisualIssue(
                    code="UNEXPECTED_ASPECT_RATIO",
                    status=QAStatus.FAIL,
                    message=(
                        f"Expected aspect ratio "
                        f"{self.expected_aspect_ratio:.4f}, "
                        f"got {actual_ratio:.4f}."
                    ),
                    details={
                        "expected": self.expected_aspect_ratio,
                        "actual": actual_ratio,
                    }))

    @staticmethod
    def resolve_status(issues: list[VisualIssue]) -> QAStatus:
        if any(issue.status == QAStatus.FAIL for issue in issues):
            return QAStatus.FAIL

        if any(issue.status == QAStatus.WARN for issue in issues):
            return QAStatus.WARN

        return QAStatus.PASS