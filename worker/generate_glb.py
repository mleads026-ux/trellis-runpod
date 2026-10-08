import os,sys
from PIL import Image
os.environ.setdefault("SPCONV_ALGO","native")
from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.utils import postprocessing_utils

if len(sys.argv) < 3:
    raise SystemExit("usage: generate_glb.py INPUT_IMAGE OUTPUT_GLB")

pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
pipeline.cuda()
image = Image.open(sys.argv[1]).convert("RGB")
outputs = pipeline.run(image, seed=1)
glb = postprocessing_utils.to_glb(
    outputs["gaussian"][0],
    outputs["mesh"][0],
    simplify=0.95,
    texture_size=1024,
)
glb.export(sys.argv[2])
print("GLB_READY", sys.argv[2])
