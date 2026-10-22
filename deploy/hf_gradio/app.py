"""Hugging Face Space entry point (Gradio SDK).

The Space SDK is Gradio, but the real app is the FastAPI service in
src/chorus_api (JSON API under /api, React SPA at /). This launcher mounts a
trivial Gradio page at /gradio (to satisfy the SDK) and serves everything on
0.0.0.0:7860 with uvicorn, exactly as the Docker route does.
"""
import os
import sys

# Environment defaults must be set before torch / chorus are imported.
for _k, _v in {
    "CHORUS_ASR_DEVICE": "cpu",
    "CHORUS_ASR_MODEL": "small.en",
    "CHORUS_BEAM_SIZE": "5",
    "CHORUS_SAME_SOUND": "1",
    "CHORUS_DIGIT_CONTEXT": "1",
    "CHORUS_VAD": "1",
    "CHORUS_WARMUP": "1",
    "CHORUS_DB": "/tmp/chorus.db",
    "OMP_NUM_THREADS": "2",
    "MKL_NUM_THREADS": "2",
}.items():
    os.environ.setdefault(_k, _v)

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _ensure_nltk() -> None:
    """g2p_en 2.1.0 asks for the legacy tagger name at import, so fetch both."""
    import nltk

    needed = {
        "averaged_perceptron_tagger_eng": "taggers/averaged_perceptron_tagger_eng",
        "averaged_perceptron_tagger": "taggers/averaged_perceptron_tagger",
        "cmudict": "corpora/cmudict",
    }
    for pkg, path in needed.items():
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(pkg, quiet=True)


_ensure_nltk()

# ZeroGPU: `spaces` must be imported before torch (its docs/source say CUDA
# must not be initialised first). Outside ZeroGPU it is absent or a no-op.
try:
    import spaces
except ImportError:  # not on HF, or not installed
    spaces = None

import gradio as gr  # noqa: E402
import uvicorn  # noqa: E402

from chorus_api.app import app  # noqa: E402


def _gpu(fn):
    """Mark fn as a ZeroGPU function (no-op when `spaces` is unavailable).

    Chorus inference does NOT use it: the analyze path stays on CPU
    (CHORUS_ASR_DEVICE=cpu). It exists so a ZeroGPU Space has the decorated
    function the platform looks for.
    """
    return spaces.GPU(fn) if spaces is not None else fn


@_gpu
def _gpu_ping() -> str:
    return "ok"


def _build_demo() -> gr.Blocks:
    with gr.Blocks(title="Chorus") as demo:
        gr.Markdown("Chorus lives at [/](/) (the reading app); this page is only a placeholder.")
        out = gr.Textbox(label="GPU check", interactive=False)
        gr.Button("Ping").click(_gpu_ping, None, out, api_name="ping")
    return demo


_placeholder = _build_demo()

_n_before = len(app.router.routes)
app = gr.mount_gradio_app(app, _placeholder, path="/gradio")
# chorus_api registers a catch-all GET /{full_path:path} (SPA fallback) at app
# creation, and routes match in order, so a mount appended after it would be
# swallowed by the SPA shell. Move the newly added routes to the front.
_new = app.router.routes[_n_before:]
del app.router.routes[_n_before:]
app.router.routes[0:0] = _new


# ZeroGPU only reports its @spaces.GPU functions to the platform from inside
# gr.Blocks.launch() (spaces/zero/__init__.py hooks it). We serve with uvicorn,
# so launch a throwaway local Gradio on another port once, purely to fire that
# hook. Best effort: failure must never stop the real app.
if os.environ.get("SPACES_ZERO_GPU", "").lower() in ("1", "true", "t") and os.environ.get(
    "CHORUS_ZEROGPU_HOOK", "1"
) == "1":
    try:
        _build_demo().launch(
            prevent_thread_lock=True, server_name="127.0.0.1", server_port=7861,
            show_api=False, quiet=True,
        )
    except Exception as _e:  # noqa: BLE001
        print(f"[chorus] ZeroGPU startup hook skipped: {_e!r}", flush=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860, workers=1)
