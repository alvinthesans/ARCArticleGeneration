from app.core.transformerModelHandler import TransformerHandler
from app.data_models.container_class import Carousel
from app.data_models.style_class import StyleDefinition
from app.validator.ContradictDetector import StringPromptValidator
from app.validator.carousel_narrative_validator import CarouselNarrativeValidator
from app.validator.composition_validator import CompositionValidator
from app.validator.element_valid_models import ValidationIssue, ValidationLevel
from app.validator.element_validator import ElementValidator
from app.validator.slide_validator import validate_carousel


class Validator:
    def __init__(self, style: StyleDefinition, composer: CompositionValidator = CompositionValidator(), element_validator: ElementValidator = ElementValidator(),
                 semantic_validator: StringPromptValidator = StringPromptValidator(), narrative_validator: CarouselNarrativeValidator = CarouselNarrativeValidator(),
                 transformer_handler: TransformerHandler = TransformerHandler()):
        self.composer = composer
        self.element_validator = element_validator
        self.style = style
        self.semantic_validator = semantic_validator
        self.narrative_validator = narrative_validator
        self.transformer_handler = transformer_handler

    def validateSlides(self, carousel: Carousel, to_check_slides: list = None):
        debug_log = {}

        narrative_error = self.narrative_validator.carousel_narrative_check(carousel)

        if narrative_error:
            return narrative_error

        visual_bible = carousel.visual_bible

        if to_check_slides:
            slides = [slide for slide in carousel.slides if slide.slide_id in to_check_slides]
        else:
            slides = carousel.slides

        for slide in slides:
            errors = []
            visual = visual_bible.validate_slide_visual(slide.visual)

            if visual:
                errors.append(ValidationIssue(
                            level=ValidationLevel.ERROR,
                            code="VISUAL_ELEMENT_MISSING",
                            slide_id=slide.slide_id,
                            message=(
                                f"{visual}"
                            )
                        ))

            errors.extend(validate_carousel(slide))
            errors.extend(self.composer.validate(slide, self.style))
            errors.extend(self.element_validator.validate(slide, visual_bible))

            verdict, log = self.element_validator.element_not_contradict_keyword(slide, visual_bible)
            if verdict == "contradiction":
                errors.extend(log)
            else:
                verdict, log = self.semantic_validator.element_not_contradict_transformer(slide, visual_bible)
                if verdict == "contradiction":
                    errors.extend(log)
                elif verdict == "uncertain":
                    errors.append(
                        ValidationIssue(
                            level=ValidationLevel.INFO,
                            code="DESCRIPTION_CONTRADICTION_SEMANTIC_UNCERTAINTY",
                            slide_id=slide.slide_id,
                            message=(
                                f"sentence transformer cannot determine {slide.slide_id} visual description's contradiction"
                            )
                        )
                    )

            component_existance, c_error = self.element_validator.validate_slide_element_usages(slide, visual_bible)
            if c_error:
                errors.extend(c_error)

            if component_existance:
                component_error = self.semantic_validator.is_component_in_element(component_existance, visual_bible, slide.slide_id)
                errors.extend(component_error)

            if errors:
                debug_log[slide.slide_id] = errors

        self.transformer_handler.cross_encoder_offload()
        return debug_log

