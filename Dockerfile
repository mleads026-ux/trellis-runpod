FROM nvidia/cuda:11.8.0-devel-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 CUDA_HOME=/usr/local/cuda TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9" SPCONV_ALGO=native
RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs wget curl ca-certificates build-essential ninja-build libgl1 libegl1 libopengl0 libglib2.0-0 libx11-6 libxext6 libsm6 libxrender1 libusb-1.0-0 libgomp1 libxfixes3 libxi6 libxrandr2 libxcursor1 libxinerama1 && rm -rf /var/lib/apt/lists/*
RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-py310_25.1.1-2-Linux-x86_64.sh -O /tmp/miniconda.sh && bash /tmp/miniconda.sh -b -p /opt/conda && rm /tmp/miniconda.sh
ENV PATH=/opt/conda/bin:$PATH
RUN conda create -n trellis python=3.10 -y && conda clean -afy
ENV PATH=/opt/conda/envs/trellis/bin:/opt/conda/bin:$PATH
RUN python -m pip install "numpy<2" && python -m pip install torch==2.4.0 torchvision==0.19.0 --index-url https://download.pytorch.org/whl/cu118
RUN git clone --recurse-submodules https://github.com/microsoft/TRELLIS.git /opt/TRELLIS
WORKDIR /opt/TRELLIS
# setup.sh installs CUDA extensions; build must have sufficient disk and memory.
RUN bash -lc 'source /opt/conda/etc/profile.d/conda.sh && conda activate trellis && source ./setup.sh --basic --xformers --flash-attn --diffoctreerast --spconv --mipgaussian --kaolin --nvdiffrast'
RUN python -m pip install "numpy<2" "transformers==4.44.2"
# Explicit compatible Kaolin wheel: TRELLIS setup.sh can skip CUDA extras when Docker build has no GPU.
RUN python -m pip install --no-cache-dir "kaolin==0.16.0" -f https://nvidia-kaolin.s3.us-east-2.amazonaws.com/torch-2.4.0_cu118.html
# TRELLIS setup.sh uses torch.cuda.is_available() to select CUDA extensions;
# Docker image builds run without a visible GPU, so they can silently skip these.
# Build critical rasterizers explicitly and fail the build if any import fails.
RUN git clone --depth 1 --branch v0.4.0 https://github.com/NVlabs/nvdiffrast.git /tmp/nvdiffrast && \
    python -m pip install --no-build-isolation /tmp/nvdiffrast && \
    rm -rf /tmp/nvdiffrast
RUN git clone --depth 1 --recurse-submodules https://github.com/JeffreyXiang/diffoctreerast.git /tmp/diffoctreerast && \
    python -m pip install --no-build-isolation /tmp/diffoctreerast && \
    rm -rf /tmp/diffoctreerast
RUN git clone --depth 1 https://github.com/autonomousvision/mip-splatting.git /tmp/mip-splatting && \
    python -m pip install --no-build-isolation /tmp/mip-splatting/submodules/diff-gaussian-rasterization/ && \
    rm -rf /tmp/mip-splatting
RUN python -c "import torch, kaolin, nvdiffrast.torch, diffoctreerast, diff_gaussian_rasterization; from trellis.pipelines import TrellisImageTo3DPipeline; from trellis.utils import postprocessing_utils; print('TRELLIS core and CUDA rasterizer imports OK')"
COPY scripts/ /opt/trellis-runpod/scripts/
ENV PYTHONPATH=/opt/TRELLIS
WORKDIR /workspace
EXPOSE 8000
CMD ["python", "/opt/trellis-runpod/scripts/trellis_api_server.py"]
