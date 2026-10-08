FROM nvidia/cuda:11.8.0-devel-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 CUDA_HOME=/usr/local/cuda TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9" SPCONV_ALGO=native
RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs wget curl ca-certificates build-essential ninja-build libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
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
COPY scripts/ /opt/trellis-runpod/scripts/
ENV PYTHONPATH=/opt/TRELLIS
WORKDIR /workspace
CMD ["bash"]
