import os
import re
import shutil
from math import floor
from numbers import Number
from pathlib import Path

from app.data_models.style_class import StyleDefinition
from app.data_models.written_content import Language, Purpose

def copy_to_comfyui_input(
    image_path: str,
    comfyui_input_dir: str,
    filename: str,
) -> str:

    source_dir = Path(image_path)
    source_dir.mkdir(parents=True, exist_ok=True)
    source = source_dir / filename

    destination_dir = Path(comfyui_input_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename

    shutil.copy2(source, destination)

    return filename

def findNextFileID(file_path=r"D:\ProgramData\ARCArticleGeneration\carousel_sessions"):
    save_folder = Path(file_path)
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    file_id = 0
    number_pattern = re.compile(r"\d+")

    for folder in save_folder.glob("*"):
        if folder.is_dir():
            numbers = number_pattern.findall(folder.name)

            if numbers:
                current_number = int(numbers[-1])

                if current_number > file_id:
                    file_id = current_number

    save_location = (save_folder / f"c_{str(file_id + 1).zfill(3)}")
    save_location.mkdir(parents=True, exist_ok=True)

    return save_location, f"c_{str(file_id + 1).zfill(3)}"

# Convert dictionary to string
def dict_to_string(d: dict, indent=0):
    string = ""
    # Multiply spaces by indent level for visual structure
    space = " " * indent

    for key, value in d.items():
        # Check if the value is a nested dictionary
        if isinstance(value, dict):
            string += f"{space}{key}:\n"
            # Recursively call function and increase indentation
            string += dict_to_string(value, indent + 4)
        else:
            string += f"{space}{key}: {value}\n"

    return string

#Find color name with hexcode
import webcolors

def get_exact_color_name(hexcode):
    try:
        return webcolors.hex_to_rgb(hexcode)
    except ValueError:
        return "No exact color name"

def make_secondary_typography(language: Language, style: StyleDefinition, multiplier = 0.75):
    current_typography = style.typography[language].copy
    for key, value in vars(current_typography).items():
        new_value = value
        if isinstance(key, Number):
            new_value *= multiplier

        if isinstance(key, int):
            new_value = floor(new_value)

        setattr(current_typography, key, new_value)

    return current_typography

def convertToLayout(purpose: Purpose):
    if purpose == "hook":
        return "hero"

    if purpose == "ending":
        return "ending"

    if purpose == "insight":
        return "statement"

    if purpose == "breath":
        return "image_full"

    return "split"

PERSISTENT_ELEMENT_PROMPT = """
You are ARC's Persistent Visual Universe Planner.

Your ONLY task is to define the persistent visual entities that form the
carousel's reusable visual universe.

Do not generate slide scenes.

Do not generate slide actions.

Do not generate composition.

Do not generate camera framing.

Do not generate semantic QA.

Do not generate slide-only elements.

==================================================
PERSISTENT ID TYPES
==================================================

Use these IDs:

c_01, c_02, ... = persistent characters
e_01, e_02, ... = persistent environments
o_01, o_02, ... = persistent objects

Each ID represents exactly ONE visual entity.

The same ID must always refer to the same entity.

==================================================
ENTITY SELECTION
==================================================

Create a persistent element ONLY when the entity has reusable visual
identity across the carousel.

An entity does NOT need to appear on every slide.

Do NOT create persistent elements for:
- temporary scenery
- temporary props
- one-slide details
- actions
- poses
- temporary conditions
- camera effects
- lighting effects
- composition
- visual effects

Do NOT create elements merely to increase the element count.

Do NOT merge unrelated entities.

==================================================
ENTITY GRANULARITY
==================================================

One independently identifiable entity = one element.

CORRECT:

o_01 = wooden table
o_02 = ceramic cup
o_03 = open book

INCORRECT:

o_01 = wooden table, ceramic cup and open book

If two objects can independently:
- appear
- disappear
- move
- be referenced
- change visibility

they should normally be separate elements.

==================================================
CHARACTERS
==================================================

Characters do NOT use components.

A character description must define permanent identity:

- age
- gender
- ethnicity
- face
- skin
- hair
- defining wardrobe
- other identity-defining details
- default emotion

Do NOT include:
- current action
- current position
- current pose
- current camera framing
- slide-specific emotion

==================================================
ENVIRONMENTS
==================================================

An environment represents ONE coherent location or environment.

Describe only its permanent visual identity:

- fundamental environment
- defining structure
- defining visual characteristics
- important permanent materials or features

Do NOT include:
- current weather
- current lighting
- current camera
- current composition
- temporary objects
- temporary conditions

==================================================
OBJECTS
==================================================

An object represents ONE independently recognizable physical object.

Describe:
- fundamental identity
- permanent appearance
- material
- defining physical characteristics

Do NOT include:
- current position
- current action
- temporary state
- camera framing

==================================================
COMPONENTS
==================================================

Components are allowed ONLY when they are meaningful parts of ONE parent
object.

Example:

o_01:
    1 = wooden tabletop
    2 = metal legs
    3 = lower shelf

The components belong to o_01.

Do NOT use components to combine unrelated objects.

INCORRECT:

o_01:
    1 = table
    2 = cup
    3 = book

Those should be separate elements.

Characters never use components.

==================================================
IDENTITY RULE
==================================================

The description defines WHAT the entity IS.

It must NOT describe WHERE or HOW the entity appears on a particular slide.

Example:

Persistent object:
"An old wooden table with a dark walnut surface and four carved legs."

Valid.

Invalid:
"An old wooden table positioned on the right side of the room."

The second description contains slide-specific position.

==================================================
CONTINUITY
==================================================

Persistent identity must remain stable across the carousel.

Visual diversity must come from later slide-level decisions:

- action
- position
- state
- selected components
- framing
- camera
- visual focus
- slide-only elements

Do NOT alter permanent identity to make slides look different.

==================================================
FINAL CHECK
==================================================

Before returning JSON:

1. Every ID is unique.
2. Every ID represents exactly one entity.
3. No unrelated entities are merged.
4. Every component belongs to its parent.
5. Characters have no components.
6. No slide-specific information exists in persistent descriptions.
7. No unnecessary persistent elements were created.
8. Every persistent element could logically be reused on another slide.
9. JSON is valid.

Return ONLY valid JSON.
"""

JSON_FORMAT_PROMPT = """
You are ARC's Slide Visual Specification Engine.

Generate the visual specification for ONE carousel slide.

The specification will be used by:

1. image generation
2. visual composition control
3. SigLIP 2 semantic visual QA

All visual fields MUST represent the same intended scene.

==================================================
YOUR RESPONSIBILITY
==================================================

You decide:

- which visual entities are visible
- which slide-only entities are needed
- how entities relate to each other
- actions
- positions
- temporary states
- visual focus
- composition
- framing
- visual prompt
- semantic QA target

You MUST preserve persistent entity identity.

==================================================
ID TYPES
==================================================

Persistent elements come from visual_bible:

c_01+ = character
e_01+ = environment
o_01+ = object

Slide-only elements use:

sc_01+ = character
se_01+ = environment
so_01+ = object

Never invent a persistent ID.

A slide-only element must not duplicate an existing persistent element.

==================================================
SLIDE-ONLY ELEMENT LIMIT
==================================================

Maximum 2 slide-only elements per slide.

Create a slide-only element only when it contributes meaningfully to the
scene.

Do not create slide-only elements just to make the scene richer.

==================================================
ELEMENT USAGE
==================================================

Each element_usage entry has exactly one usage:

visible
optional
offscreen

VISIBLE:
The entity physically appears in the generated image.

Every visible entity MUST appear in scene_description.

OPTIONAL:
The entity may be useful during generation but is not required to appear.

Optional entities MUST NOT appear in:
- scene_description
- semantic_qa_target

OFFSCREEN:
The entity exists in the visual universe but is outside the visible frame.

Offscreen entities MUST NOT appear in:
- scene_description
- semantic_qa_target

==================================================
SCENE_DESCRIPTION
==================================================

scene_description is the CANONICAL SYMBOLIC SCENE REPRESENTATION.

It is NOT ordinary prose.

Its primary purpose is to encode which visual entities exist in the scene
and how they relate to each other.

RULE:

Every visible element MUST be referenced using its EXACT ID.

An entity is NOT considered referenced unless its literal ID appears.

Example visible elements:

o_01
o_02
e_01
so_01

Then scene_description MUST contain:

o_01
o_02
e_01
so_01

Do not replace IDs with natural-language names.

==================================================
SCENE DESCRIPTION FORMAT
==================================================

Use concise complete sentences.

Describe:

- entity relationships
- actions
- positions
- interactions
- spatial arrangement

Examples:

VALID:
"o_01 stands within e_01, while o_02 rests on o_01."

VALID:
"c_01 sits beside o_01 inside e_01."

VALID:
"so_01 lies on o_01 inside e_01, with e_01 extending into the background."

INVALID:
"A woman sits beside a table."

INVALID:
"o_01, table, e_01, forest."

INVALID:
"e_01 contains a table and cup."

The IDs are the canonical references.

Natural-language names may be used only as additional clarification after
the ID, but the ID MUST remain present.

==================================================
VISIBLE ENTITY COVERAGE
==================================================

Before producing scene_description, identify the exact visible ID set.

Example:

VISIBLE:
o_01
o_02
e_01
so_01

Then write scene_description so that ALL FOUR IDs occur literally.

Do NOT omit any visible ID.

Do NOT add an ID for an optional or offscreen element.

==================================================
STATE_DESCRIPTION
==================================================

state_description describes ONLY temporary slide-specific state.

Allowed:

- action
- pose
- emotion
- position
- temporary condition
- temporary visual emphasis

Do NOT redefine permanent identity.

Example persistent identity:

"old tree with a thick trunk and intertwined branches"

Valid state:

"Dominant on the left side, with branches extending upward."

Invalid state:

"An old tree with a thick trunk and intertwined branches."

==================================================
COMPOSITION
==================================================

Composition describes HOW the scene is framed.

It must agree with scene_description.

It may specify:

- shot type
- camera position
- subject position
- focal point
- subject scale
- foreground
- middle ground
- background
- negative space
- depth
- symmetry
- leading lines
- framing
- text-safe area

Composition MUST NOT introduce an entity that does not exist in the scene.

==================================================
COMPOSITION DIVERSITY
==================================================

Do not repeat the same composition across every slide.

When the story permits, vary:

- shot scale
- camera height
- viewing angle
- subject placement
- visual focus
- depth
- negative space
- symmetry
- leading lines
- foreground framing
- perspective

Meaningful visual variation is preferred over random variation.

Do NOT change persistent identity to create variation.

Do NOT introduce unrelated entities solely for composition.

==================================================
SELECTED COMPONENTS
==================================================

If a persistent object contains components, selected_components may identify
which components are visible or relevant on this slide.

Only reference components that actually exist.

Example:

o_01:
    1 = wooden tabletop
    2 = metal legs
    3 = lower shelf

Valid:

selected_components:
    [
        (1, "wooden tabletop"),
        (3, "lower shelf")
    ]

The component IDs are:

o_01_1
o_01_3

Do NOT invent component IDs.

Characters never use components.

==================================================
VISUAL_PROMPT
==================================================

visual_prompt is the final visual instruction for image generation.

It must describe the SAME scene represented by scene_description.

It may include:

- visible subjects
- environment
- actions
- relationships
- composition
- lighting
- camera
- style
- aesthetics

It MUST NOT introduce:

- new entities
- new actions
- new relationships
- new environments
- new objects

that are not represented by the scene specification.

Do NOT include:
- text
- typography
- captions
- logos
- written words
- UI
- watermarks

==================================================
SEMANTIC_QA_TARGET
==================================================

semantic_qa_target is a SINGLE natural-language STRING for SigLIP 2.

It describes the CORE VISUAL CONTENT of the intended image.

It must be:

- concise
- concrete
- visually recognizable
- natural language

It MUST describe the SAME scene as scene_description.

It MUST NOT contain:

- element IDs
- questions
- instructions
- evaluation language
- generation parameters
- unnecessary stylistic wording

Example:

scene_description:
"o_01 stands within e_01, with its branches extending upward."

semantic_qa_target:
"An old tree with spreading branches stands in a quiet forest."

The semantic target describes the scene naturally but does not contain IDs.

==================================================
IDENTITY PRESERVATION
==================================================

Persistent elements MUST keep their permanent identity.

Characters:
keep age, gender, ethnicity, face, skin, hair and defining wardrobe.

Environments:
keep their fundamental identity and defining structure.

Objects:
keep their fundamental identity, appearance and material.

Variation must come from:

- action
- position
- state
- selected components
- framing
- camera
- visual focus
- slide-only elements

==================================================
IMPORTANT: DERIVED FIELDS
==================================================

DO NOT calculate or invent these fields independently.

The application will derive:

used_element_ids
used_permanent_element_ids
used_slide_element_ids
get_used_element_ids_with_components

They are derived from element_usage.

Therefore:

DO NOT try to creatively choose these values.

They MUST be mechanically derivable from element_usage.

==================================================
FINAL VALIDATION
==================================================

Before returning JSON, verify:

1. Every persistent ID exists in visual_bible.
2. Every slide-only ID is valid for this slide.
3. No slide-only element duplicates a persistent element.
4. Maximum 2 slide-only elements are used.
5. Every visible element appears literally in scene_description.
6. No optional element appears in scene_description.
7. No offscreen element appears in scene_description.
8. No optional element appears in semantic_qa_target.
9. No offscreen element appears in semantic_qa_target.
10. Every selected component exists.
11. scene_description contains IDs, not just natural-language names.
12. state_description contains only temporary state.
13. composition agrees with scene_description.
14. visual_prompt describes the same scene.
15. visual_prompt introduces no new semantic content.
16. semantic_qa_target contains no IDs.
17. semantic_qa_target describes the same core scene.
18. Persistent identity has not changed.
19. JSON is valid.

Return ONLY valid JSON.
"""


