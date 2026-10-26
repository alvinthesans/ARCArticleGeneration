from app.data_models.container_class import Carousel, Slide
from app.validator.element_valid_models import ValidationLevel, ValidationIssue


def validate_carousel(slide: Slide):
    errors = []

    if len(slide.headline) > 30:
        errors.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                code="HEADLINE_TOO_LONG",
                slide_id=slide.slide_id,
                message="Headline too long, should be less than 30 characters",
            )
        )

    if len(slide.body) > 80:
        errors.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                code="BODY_TOO_LONG",
                slide_id=slide.slide_id,
                message="Body too long, should be less than 80 characters",
            )
        )

    if len(slide.visual.used_slide_element_ids) > 2:
        errors.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                code="SLIDE_ELEMENT_COUNT_EXCEED",
                slide_id=slide.slide_id,
                message="too much slide only elements",
            )
        )

    return errors