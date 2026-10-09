# This image targets RunPod NVIDIA Ampere/Ada GPUs (sm80/sm86/sm89).
# RTX 50-series / Blackwell (sm120) requires a separate CUDA 12.8+ build.
FROM nvidia/cuda:11.8.0-devel-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    CUDA_HOME=/usr/local/cuda \
    TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9" \
    SPCONV_ALGO=native \
    ATTN_BACKEND=xformers \
    PIP_CONSTRAINT=/opt/trellis-runpod/constraints-trellis.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    git git-lfs wget curl ca-certificates build-essential ninja-build \
    libgl1 libegl1 libopengl0 libglib2.0-0 libx11-6 libxext6 libsm6 \
    libxrender1 libusb-1.0-0 libgomp1 libxfixes3 libxi6 libxrandr2 \
    libxcursor1 libxinerama1 && rm -rf /var/lib/apt/lists/*

RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-py310_25.1.1-2-Linux-x86_64.sh -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p /opt/conda && rm /tmp/miniconda.sh
ENV PATH=/opt/conda/bin:$PATH
RUN conda create -n trellis python=3.10 -y && conda clean -afy
ENV PATH=/opt/conda/envs/trellis/bin:/opt/conda/bin:$PATH

COPY constraints-trellis.txt /opt/trellis-runpod/constraints-trellis.txt
RUN python -m pip install torch==2.4.0 torchvision==0.19.0 \
    --index-url https://download.pytorch.org/whl/cu118

# Pin TRELLIS code and its FlexiCubes submodule; never pull moving main in production.
RUN git clone https://github.com/microsoft/TRELLIS.git /opt/TRELLIS \
    && git -C /opt/TRELLIS checkout 442aa1e1afb9014e80681d3bf604e8d728a86ee7 \
    && git -C /opt/TRELLIS submodule update --init --recursive
WORKDIR /opt/TRELLIS

# Do not rely on setup.sh CUDA flags inside docker build:
# torch.cuda.is_available() is normally false with no GPU passed to docker build,
# so upstream setup.sh silently skips xformers, spconv and CUDA extension installs.
# Install the upstream --basic requirements explicitly with a compatibility lock.
RUN python -m pip install \
    pillow imageio imageio-ffmpeg tqdm easydict opencv-python-headless \
    scipy ninja rembg onnxruntime trimesh open3d xatlas pyvista \
    pymeshfix igraph transformers huggingface_hub safetensors einops \
    && python -m pip install \
    git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8

# These must exist even when docker image is built without an NVIDIA GPU.
RUN python -m pip install spconv-cu118==2.3.8 \
    && python -m pip install --no-deps xformers==0.0.27.post2 \
       --index-url https://download.pytorch.org/whl/cu118 \
    && python -m pip install --no-deps kaolin==0.16.0 \
       -f https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.4.0_cu118.html

# Kaolin's --no-deps avoids replacing the pinned CUDA PyTorch build, but its
# published package metadata still requires these runtime packages. Install
# them explicitly and let pip check enforce complete dependency resolution.
RUN python -m pip install \
    ipycanvas ipyevents jupyter-client pygltflib tornado usd-core

# Compile CUDA rasterizers for the explicit GPU architectures above.
RUN git clone --depth 1 --branch v0.4.0 https://github.com/NVlabs/nvdiffrast.git /tmp/nvdiffrast \
    && python -m pip install --no-build-isolation /tmp/nvdiffrast \
    && rm -rf /tmp/nvdiffrast
RUN git clone --depth 1 --recurse-submodules https://github.com/JeffreyXiang/diffoctreerast.git /tmp/diffoctreerast \
    && python -m pip install --no-build-isolation /tmp/diffoctreerast \
    && rm -rf /tmp/diffoctreerast
RUN git clone --depth 1 https://github.com/autonomousvision/mip-splatting.git /tmp/mip-splatting \
    && python -m pip install --no-build-isolation /tmp/mip-splatting/submodules/diff-gaussian-rasterization/ \
    && rm -rf /tmp/mip-splatting

ENV PYTHONPATH=/opt/TRELLIS
COPY scripts/ /opt/trellis-runpod/scripts/
# No GPU is required for this stage; no model download is attempted here.
RUN python -m pip check \
    && python /opt/trellis-runpod/scripts/preflight_trellis.py
WORKDIR /workspace
EXPOSE 8000
CMD ["python", "/opt/trellis-runpod/scripts/trellis_api_server.py"]
