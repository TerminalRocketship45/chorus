# Deploying to Hugging Face Spaces (Gradio SDK)

Use this route when the account cannot create Docker Spaces (the Space here is
ZeroGPU hardware, Gradio SDK). The Space SDK is Gradio, but `app.py` starts the normal Chorus FastAPI app (React page at `/`,
API under `/api`) and mounts a placeholder Gradio page at `/gradio`. The Docker
route in `deploy/hf/` and the repo `Dockerfile` are unchanged.

1. **The Space** already exists: https://huggingface.co/spaces/TerminalRocketship34/Chorus
   (SDK Gradio, hardware ZeroGPU). On another account: new-space, SDK Gradio, Blank,
   Public (CPU basic works too). The script never creates it.
2. **Create a token**: Settings > Access Tokens > New token, role Write.
3. **Push**:
   ```
   export HF_USER=TerminalRocketship34 SPACE_NAME=Chorus HF_TOKEN=<token>
   bash deploy/hf_gradio/push_space.sh
   ```
   Add `DRY_RUN=1` first to see exactly which files would be pushed (no token
   needed). The script runs `npm run build` in `web/` and ships only `web/dist/`.
4. **Watch the build**: Space page > Logs. Spaces pip-installs `requirements.txt`
   (torch 2.8.0) and apt-installs `packages.txt`, then runs `python app.py`.
5. **First start**: the models are not baked in, so the first start downloads
   them (faster-whisper base.en and the MMS alignment model, about 1.5 GB in
   total) and, with `CHORUS_WARMUP=1`, loads them before serving. Expect a few
   minutes of "Starting"; later restarts re-download unless the cache survives.
6. **Switch to small.en**: Settings > Variables and secrets > New variable
   `CHORUS_ASR_MODEL` = `small.en`, then Restart the Space (small.en is
   downloaded on that start). Watch RAM and latency on 2 vCPU.
7. **Data is ephemeral**: the SQLite DB lives in `/tmp/chorus.db`, so teacher-view
   data resets whenever the Space restarts or sleeps (free Spaces sleep after
   about 48 h idle). Audio is never stored.
8. **Microphone**: Spaces are served over HTTPS, so `getUserMedia` works. If the
   page embedded on huggingface.co/spaces/... blocks the mic, open the direct
   URL `https://<user>-<space>.hf.space` instead.

## AI-written passages (optional)

`POST /api/passages/generate` asks a language model for a passage about the reader's
interests, through Hugging Face Inference Providers (`huggingface_hub.InferenceClient`,
pinned to 0.36.2 because gradio 5.50.0 needs huggingface-hub below 2.0).

- **Secret `HF_TOKEN`** (Settings > Variables and secrets > New secret). A read token is
  enough: inference calls need no write access. A fine-grained token must have the
  "Make calls to Inference Providers" permission. Use a separate token from the Write
  token used by `push_space.sh` (which is only a shell variable on your machine), and
  never put it in a Variable (variables are public). Restart the Space after adding it.
- **Variable `CHORUS_PASSAGE_MODEL`** (optional). Default
  `meta-llama/Llama-3.1-8B-Instruct`, which several Inference Providers serve. Set any
  other chat model id that Providers serve (for example `Qwen/Qwen3-8B`); check its
  model page lists a live provider.
- **Limits**: free Hugging Face accounts get only a small monthly inference credit,
  PRO accounts more (check the current amount on your billing page). Each passage costs
  a few hundred tokens, and a request can retry up to three times. When the token is
  missing, the credit is spent, the model is unavailable or the output fails the checks
  (length, digits, hyphens, non-ASCII, unsafe words), the API returns a **library
  passage** instead (`"source": "library"`, matching band and interest where possible),
  so reading always works without the secret.
- Generated passages are stored in the same ephemeral SQLite DB (`/tmp/chorus.db`) and
  disappear when the Space restarts.

## ZeroGPU notes

- Inference stays on CPU (`CHORUS_ASR_DEVICE=cpu`); no GPU is needed or used.
  ZeroGPU attaches a GPU only inside `@spaces.GPU` functions invoked through
  Gradio, and its wrapper forks a worker per call and needs Gradio request
  context, so the plain FastAPI `/api/analyze` route is not routed through it.
- ZeroGPU supports torch 2.8.0 and later and Python 3.10.13 or 3.12.12, so this
  Space file pins torch/torchaudio 2.8.0 and `python_version: 3.12.12`. The repo
  tests were run on torch 2.7.1; 2.8.0 is unverified.
- `app.py` defines a trivial `@spaces.GPU` function wired to the placeholder
  Gradio page and, on ZeroGPU, launches a throwaway local Gradio once so that
  the platform receives its startup report. Set variable `CHORUS_ZEROGPU_HOOK=0`
  to turn that off if it causes trouble.
- Local commands: this venv has no `uvicorn` script; use `python -m uvicorn`.
