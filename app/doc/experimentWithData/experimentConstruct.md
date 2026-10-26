Calibration test v0.1 for obtaining threshold for visual QA with semantic models
Target:
- can scene score seperate normal scene with wrong ones
- can visual bible score identify whether the slide follows the overall carousel visual
- whether persistent element score can be independent as a signal

Data set composition:

1st experiment:
a-----------------------------a
7 carousel with around 5 slides
scene score: compare image with scene_description
visual bible score: compare image with overall visual

then we look at it's:
mean
median
min
max
std
distribution
a------------------------------a

2nd experiment: Scene mismatch
a------------------------------a
By using the same carousel, we switch the scene description with other slide's description
this provides a wrong score for comparison purpose
the ideal situation is the correct score is higher than the wrong score

it would be ideal to see the ratio for this scenario

ideal construct:
1 × correct scene
2 × wrong scenes
for each image

A. 同 carousel 的另一页
B. 完全不同 carousel 的 scene

a------------------------------a

3rd experiment: Viusal bible mismatch
By using the same set of data, we can feed an overall visual from a different carousel and pair with the image
this can be paired up with the 2nd experiment, as the overall visual for each visual.txt contains
the visual bible information except permanent element stored

recommended class structure:
CalibrationRecord(
    carousel_id="c_001",
    slide_id=1,

    image_path="...",

    scene_score=-5.23,
    wrong_scene_score=-8.71,

    style_score=-6.12,
    foreign_style_score=-9.32,
)

scene_margin = scene_score - wrong_scene_score

style_margin = style_score - foreign_style_score

where margin > 0 means the correct scene score is higher


make sure the correct scene is higher than wrong score, where wrong score comes from the negative prompt

4th experiment: Element adherence
since we uses element usage, which might include the partial component from persistent element:
we can see whether the slide contains the selected component and excluded the non included ones

the data can be dragged from the carousel.json from the respected visual, data can be extracted through seraching
with the corresponding slide id.