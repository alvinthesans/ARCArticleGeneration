from app.data_models.style_class import StyleDefinition
from app.validator.element_valid_models import ValidationIssue, ValidationLevel


class CompositionValidator:
    contradict = {
        "top": "bottom",
        "bottom": "top",
        "left": "right",
        "right": "left",
        "none": None,
        "middle": None
    }

    warn_level = {
        'strict': ValidationLevel.ERROR,
        'preferred': ValidationLevel.INFO,
        'optional': ValidationLevel.MESSAGE
    }

    def validate(self, slide, style: StyleDefinition):
        preferred_layout = style.preferred_layouts
        issues = []
        composition = slide.visual.composition
        layout = slide.layout
        constraints = next((l.Constraint for l in preferred_layout if layout == l.layout_name), None)

        n_space = composition.negative_space
        text_safe_area = composition.text_safe_area

        for constraint in constraints:
            var_name = constraint.var_name
            curr_value = getattr(slide.visual.composition, var_name)

            if curr_value not in constraint.allowed_positions:
                issues.append(ValidationIssue(
                    level=self.warn_level[constraint.severity],
                    code= f"UNMET_{constraint.severity.upper()}_{var_name.upper()}",
                    element_id=var_name,
                    slide_id= slide.slide_id,
                    message=(f"Variable: {var_name} | value: {curr_value} not in provided options"
                          f"Given values {constraint.allowed_positions}")
                ))

        if self.contradict[n_space] and self.contradict[n_space] == text_safe_area:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.INFO,
                    code="N_SPACE_AND_TEXT_AREA_CONTRADICTS",
                    element_id = text_safe_area,
                    slide_id = slide.slide_id,
                    message=(
                        f"Slide n_space {n_space} contradict with text area {text_safe_area}"
                        "Text may be uncleared during composition"
                    )
                )
            )

        return issues