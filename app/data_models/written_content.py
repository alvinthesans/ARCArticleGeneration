import weakref
from enum import Enum
from typing import Literal, Optional, ClassVar, Union
from pydantic import BaseModel, Field, model_validator


# we need:
# Slide, Carousel, Visual bible, Object, Character, Visual Direction

class Purpose(str, Enum):
    HOOK = "hook"
    CONTEXT = "context"
    PROBLEM = "problem"
    INSIGHT = "insight"
    EXAMPLE = "example"
    BREATH = "breath"
    TAKEAWAY = "takeaway"
    ENDING = "ending"

class Language(str, Enum):
    TRADITIONAL_CHINESE = "zh-HK"
    ENGLISH = "en"
    SIMPLIFIED_CHINESE = "zh-CN"

class Character(BaseModel):
    age: int
    gender: Literal['male', 'female']
    ethnicity: str

    face_description: str
    skin_description: str
    hair_description: str
    other_description: str = Field(min_length=0)

    wardrobe_description: str

    default_emotion: str

    def toString(self) -> str:
        return f"""
        age: {self.age}
        gender: {self.gender}
        
        ethnicity: {self.ethnicity}
        face_description: {self.face_description}
        skin_description: {self.skin_description}
        hair_description: {self.hair_description}
        other_description: {self.other_description}
        
        wardrobe_description: {self.wardrobe_description}
        default_emotion: {self.default_emotion}
        """

class PersistentElement(BaseModel):
    elementID: Optional[str] = Field(default=None, description="Element ID")
    elementType: Literal['character', 'environment', 'object']
    description: Union[str, Character] = Field(
        description=(
            "If the elementType is environment or object, the description should describe the element in words / sentences"
            "If the elementType is character, provide a detail description of the character with the character class"
        )
    )
    persistence: Literal["required", "preferred", "optional"]
    _registry: ClassVar[list["PersistentElement"]] = []

    def toString(self):
        return f"""
        elementID: {self.elementID}
        elementType: {self.elementType}
        description: {self.description if isinstance(self.description, str) else self.description.toString()}
        persistence: {self.persistence}
        """

    def getInstances(self):
        return self._registry

    @model_validator(mode='after')
    def _register(self) -> "PersistentElement":
        PersistentElement._registry.append(self)
        return self

    @classmethod
    def get_count(cls, target_type: str) -> int:
        if target_type == "all":
            return sum(1 for _ in cls._registry)

        return sum(1 for instance in cls._registry if instance.elementType == target_type)

    @model_validator(mode='after')
    def set_ID(self) -> "PersistentElement":
        if self.elementID:
            return self

        if self.elementType == 'character':
            current_count = PersistentElement.get_count(target_type='character')
            current_count = str(current_count).zfill(2)
            self.elementID = f"c_{current_count}"
        elif self.elementType == 'environment':
            current_count = PersistentElement.get_count(target_type='environment')
            current_count = str(current_count).zfill(2)
            self.elementID = f"e_{current_count}"
        else:
            current_count = PersistentElement.get_count(target_type='object')
            current_count = str(current_count).zfill(2)
            self.elementID = f"o_{current_count}"

        return self

class SlideElement(BaseModel):
    objectID: Optional[str] = Field(default=None, description="Object ID")
    objectType: Literal['character', 'environment', 'object']
    description: Union[str, Character] = Field(
        description=(
            "If the objectType is environment or object, the description should describe the element in words / sentences"
            "If the objectType is character, provide a detail description of the character with the character class"
        )
    )

    def toString(self):
        return f"""
        objectID: {self.objectID}
        objectType: {self.objectType}
        description: {self.description if isinstance(self.description, str) else self.description.toString()}
        """