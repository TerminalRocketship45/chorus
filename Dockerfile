# Chorus on Hugging Face Spaces (Docker SDK, CPU basic: 2 vCPU / 16 GB RAM).
# Spaces runs the container as uid 1000 and routes traffic to port 7860.

# ---- stage 1: build the React app ------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- stage 2: runtime -------------------------------------------------------
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    TORCH_HOME=/home/user/.cache/torch \
    NLTK_DATA=/home/user/nltk_data \
    PATH=/home/user/.local/bin:$PATH \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN chown user:user /app
USER user

# CPU-only torch/torchaudio at the versions pinned in requirements.txt, then
# everything else (pytest and httpx are test-only, so they are left out).
COPY --chown=user requirements.txt /app/requirements.txt
RUN pip install --user \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.7.1 torchaudio==2.7.1 \
 && grep -vE '^(torch|torchaudio|pytest|httpx)==' requirements.txt > /tmp/req-runtime.txt \
 && pip install --user -r /tmp/req-runtime.txt

# Pre-download every model at build time so startup needs no network.
# base.en AND small.en are cached so CHORUS_ASR_MODEL can be flipped later
# without a rebuild (g2p_en 2.1.0 still asks for the legacy tagger name at
# import, so both tagger names are fetched and G2p() is built once to prove it); only the selected one is loaded into RAM.
RUN python -c "import nltk; [nltk.download(p, quiet=True) for p in ('averaged_perceptron_tagger_eng', 'averaged_perceptron_tagger', 'cmudict')]" \
 && python -c "from g2p_en import G2p; G2p()" \
 && python -c "from faster_whisper.utils import download_model; [download_model(m) for m in ('base.en', 'small.en')]" \
 && python -c "import torchaudio; torchaudio.pipelines.MMS_FA.get_model()"

COPY --chown=user src/ /app/src/
COPY --chown=user --from=web /web/dist /app/web/dist

ENV PYTHONPATH=/app/src \
    CHORUS_ASR_DEVICE=cpu \
    CHORUS_ASR_MODEL=small.en \
    CHORUS_BEAM_SIZE=5 \
    CHORUS_SAME_SOUND=1 \
    CHORUS_DIGIT_CONTEXT=1 \
    CHORUS_VAD=1 \
    CHORUS_WARMUP=1 \
    CHORUS_DB=/tmp/chorus.db \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2
# NOTE: free-tier storage is ephemeral, so the SQLite DB (teacher view data)
# is lost whenever the Space restarts or sleeps.

EXPOSE 7860
CMD ["uvicorn", "chorus_api.app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
