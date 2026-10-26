## v0.4 Create the visual QA

### VISUAL QA v0.1
Deterministic model first
input the carousel
verify every generated image_path exist
check if satisfy image dimensions

### Visual QA v0.2
Use SigLIP 2 Base
image → embedding
text  → embedding
image + text → similarity

get enough data to calibrate the threshold for accepting scene images

### Visual QA v0.3
Use SigLIP 2 Base
image → embedding
text  → embedding
image + text → similarity

### Visual QA v0.4
Deterministic image/file QA 
Local CLIP/SigLIP semantic QA <-- we are here
Calibration from real ARC outputs
Carousel consistency + diversity/repetition
Composition QA later
Repair/regeneration later, with QA remaining non-mutating

## v0.5 Create the text layer engine

### v0.1 Simple backbone structure