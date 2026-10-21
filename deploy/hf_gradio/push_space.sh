#!/usr/bin/env bash
# Assemble a clean copy of the files a Gradio-SDK Hugging Face Space needs and push it.
#
# Required env: HF_USER, SPACE_NAME, HF_TOKEN (a write token).
# Optional env: DRY_RUN=1  assemble and list the files, then stop before git push
#                          (HF_TOKEN is not needed in that mode).
#
# This script does NOT create the Space. Create it first in the web UI
# (already exists: TerminalRocketship34/Chorus, SDK Gradio, ZeroGPU).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$REPO/deploy/hf_gradio"
: "${HF_USER:?set HF_USER}"
: "${SPACE_NAME:?set SPACE_NAME}"
if [ "${DRY_RUN:-0}" != "1" ]; then
  : "${HF_TOKEN:?set HF_TOKEN}"
  export HF_TOKEN  # the credential helper below reads it from the environment
fi

# Build the React app (node lives on lustre on this cluster; harmless elsewhere).
NODE_BIN=/lustre/smuexa01/client/users/rbankapur/chorus_scratch/node/node-v22.20.0-linux-x64/bin
if [ -d "$NODE_BIN" ]; then export PATH="$NODE_BIN:$PATH"; fi
(cd "$REPO/web" && npm run build)

STAGE="$(mktemp -d)"
if [ "${DRY_RUN:-0}" != "1" ]; then
  trap 'rm -rf "$STAGE"' EXIT
fi

cp "$HERE/app.py" "$HERE/requirements.txt" "$HERE/packages.txt" "$HERE/README.md" "$STAGE/"
tar -C "$REPO" -cf - --exclude='__pycache__' --exclude='*.pyc' src \
  | tar -C "$STAGE" -xf -
# Only the built SPA is needed at runtime (src/chorus_api/app.py serves <root>/web/dist).
mkdir -p "$STAGE/web/dist"
tar -C "$REPO/web/dist" -cf - . | tar -C "$STAGE/web/dist" -xf -

echo "Assembled in $STAGE:"
(cd "$STAGE" && find . -type f | sort)
echo "Total size: $(du -sh "$STAGE" | cut -f1)"

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "DRY_RUN=1: stopping before git push (staging dir kept: $STAGE)"
  exit 0
fi

cd "$STAGE"
git init -q -b main
git config user.name "$(git -C "$REPO" config user.name)"
git config user.email "$(git -C "$REPO" config user.email)"
git add -A
git commit -q -m "Deploy Chorus to Hugging Face Space (Gradio SDK)"

# Token goes through a one-shot credential helper reading the environment, so
# it is never in the URL, the remote config, or the output.
git -c credential.helper= \
    -c "credential.helper=!f() { echo username=$HF_USER; echo password=\$HF_TOKEN; }; f" \
    push --force -q "https://huggingface.co/spaces/$HF_USER/$SPACE_NAME" main:main
echo "Pushed. Build logs: https://huggingface.co/spaces/$HF_USER/$SPACE_NAME"
