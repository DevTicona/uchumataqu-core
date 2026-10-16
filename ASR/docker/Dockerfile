# ============================================================================
# Dockerfile para Entrenamiento ASR — Uchumataqu (Uru de Irohito)
# Basado 1:1 en el Dockerfile OFICIAL de k2-fsa/icefall:
#   icefall/docker/torch2.2.0-cuda12.1.dockerfile
#
# PyTorch 2.2.0 | CUDA 12.1 | cuDNN 8 | Python 3.10
# ============================================================================

FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-devel
# python 3.10

ENV LC_ALL C.UTF-8

ARG DEBIAN_FRONTEND=noninteractive

# Versiones EXACTAS verificadas por el equipo icefall para torch2.2.0+cuda12.1
ARG K2_VERSION="1.24.4.dev20240223+cuda12.1.torch2.2.0"
ARG KALDIFEAT_VERSION="1.25.4.dev20240223+cuda12.1.torch2.2.0"
ARG TORCHAUDIO_VERSION="2.2.0+cu121"

LABEL authors="k2-fsa / Proyecto Grado Uchumataqu"
LABEL k2_version=${K2_VERSION}
LABEL kaldifeat_version=${KALDIFEAT_VERSION}
LABEL github_repo="https://github.com/k2-fsa/icefall"

# -- Paquetes del sistema (identicos al Dockerfile oficial de icefall) ---------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        vim \
        libssl-dev \
        autoconf \
        automake \
        bzip2 \
        ca-certificates \
        ffmpeg \
        g++ \
        gfortran \
        git \
        libtool \
        make \
        patch \
        sox \
        subversion \
        unzip \
        valgrind \
        wget \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# -- Dependencias Python exactas del oficial de icefall ------------------------
# NOTA: numpy debe ser <2 porque k2 y kaldifeat fueron compilados con NumPy 1.x
RUN pip install --no-cache-dir "numpy<2" && \
    pip install --no-cache-dir \
      torchaudio==${TORCHAUDIO_VERSION} -f https://download.pytorch.org/whl/torchaudio/ \
      k2==${K2_VERSION} -f https://k2-fsa.github.io/k2/cuda.html \
      git+https://github.com/lhotse-speech/lhotse \
      kaldifeat==${KALDIFEAT_VERSION} -f https://csukuangfj.github.io/kaldifeat/cuda.html \
      kaldi_native_io \
      kaldialign \
      kaldifst \
      kaldilm \
      "sentencepiece>=0.1.96" \
      tensorboard \
      typeguard \
      dill \
      onnx \
      onnxruntime \
      onnxmltools \
      onnxoptimizer \
      onnxsim \
      multi_quantization \
      pytest \
      graphviz

# -- requirements.txt del propio repositorio icefall (igual que el oficial) ----
COPY docker/icefall_requirements.txt /tmp/icefall_requirements.txt
RUN pip install --no-cache-dir -r /tmp/icefall_requirements.txt

# PYTHONPATH apunta al icefall_repo ya clonado dentro del proyecto
ENV PYTHONPATH /home/primo/proyecto-grado/ASR/pipeline_icefall/icefall_repo:$PYTHONPATH

# -- Extras especificos del proyecto (exportacion, analisis, audio) ------------
RUN pip install --no-cache-dir \
      "sherpa-onnx>=1.10.0" \
      "onnxruntime-gpu>=1.17.0" \
      "pandas>=2.1.0" \
      "openpyxl>=3.1.2" \
      "tqdm>=4.66.0" \
      "tabulate>=0.9.0" \
      "librosa>=0.10.1" \
      "pydub>=0.25.1"

# -- Pin final de numpy<2 (k2/kaldifeat/lhotse requieren NumPy 1.x ABI) -------
# Se instala AL FINAL para que ningún paquete previo lo haya subido a 2.x
RUN pip install --no-cache-dir "numpy<2"

# -- Verificacion del entorno al construir la imagen ---------------------------
# NOTA: k2 y kaldifeat requieren libcuda.so.1 (GPU) para importarse, lo cual
# NO esta disponible en docker build. Se verifican solo al ejecutar el contenedor.
# Aqui solo validamos lo que puede correr sin GPU:
RUN python -c "import torch; print('PyTorch:', torch.__version__)" && \
    python -c "import lhotse; print('lhotse:', lhotse.__version__)" && \
    python -c "import sentencepiece; print('sentencepiece OK')" && \
    python -c "import numpy; print('numpy:', numpy.__version__)" && \
    python -c "import torchaudio; print('torchaudio:', torchaudio.__version__)"

# -- Crear usuario para que coincida con el UID/GID 1000 del host --------------
RUN groupadd -g 1000 primo && \
    useradd -m -u 1000 -g primo -s /bin/bash primo

WORKDIR /home/primo/proyecto-grado/ASR/pipeline_icefall

CMD ["/bin/bash"]
