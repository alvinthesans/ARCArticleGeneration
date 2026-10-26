from enum import Enum
from typing import Literal, Any

from pydantic import BaseModel, Field


class ElementUsage(BaseModel):
    element_id: str = Field(description=("The id of the persistent element used from the visual bible"
                                         "element_id MUST BE IN Scene description, with format: e_01, o_01 or c_01"))
    usage: Literal[
        "visible",
        "optional",
        "offscreen"
    ]

    selected_components: list[tuple[int, str]] = Field(
        default_factory=list,
        description=(
            "Specific components of the persistent element "
            "that should appear in this slide."
        ), min_length=0, max_length=25
    )

    state_description: str | None

    def get_selected_component(self, component_id: int) -> str:
        if not self.selected_components:
            return ""

        component = next((c for c in self.selected_components if c == component_id), None)

        if component:
            return f"{self.element_id}_{component[0]}: {component[1]}"

        return ""


    def to_readable(self) -> str:
        component_string = ""
        if self.selected_components:
            for component in self.selected_components:
                component_string += f"component id: {component[0]}, description: {component[1]} \n"

        return f"""element ID: {self.element_id}
        usage: {self.usage}
        {f"""selected_components:
        {component_string}""" if self.selected_components else ""}
        state_description: {self.state_description}
        """

class ValidationLevel(str, Enum):
    ERROR = 3
    WARNING = 2
    INFO = 1
    MESSAGE = 0

class ValidationIssue(BaseModel):
    level: ValidationLevel

    code: str

    slide_id: int | None = None

    element_id: str | None = None

    message: str


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue]

class SlideInfo(BaseModel):
    slide_id: int
    headline: str
    body: str
    visual_aim: str
    purpose: str

class ValidateNarrative(BaseModel):
    slide_id: int | None = None
    headline: str | None = None
    body: str | None = None
    purpose: str | None = None
    visual_aim: str | None = None

    narrative_score: float
    diversity_score: float
    progression_score: float

class CarouselNarrative(BaseModel):
    slide_narrative: list[ValidateNarrative]

class LayoutRule(BaseModel):
    var_name: str
    severity: Literal['strict', 'preferred', 'optional']
    allowed_positions: list[str] = Field(default_factory=list)

    @property
    def toString(self):
        return f"{self.var_name}: value provided: {self.allowed_positions} \n"

class Layout(BaseModel):
    layout_name: str
    Constraint: list[LayoutRule]

    @property
    def get_constraint_list(self):
        return {rule.var_name for rule in self.Constraint}

    def get_Constraint_Option(self, para):
            return next((info for info in self.Constraint if info.var_name == para), None)