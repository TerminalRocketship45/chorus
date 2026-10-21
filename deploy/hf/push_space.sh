#!/usr/bin/env bash
# Assemble a clean copy of the files Hugging Face Spaces needs and push it.
#
# Required env: HF_USER, SPACE_NAME, HF_TOKEN (a write token).
# Optional env: DRY_RUN=1  assemble and list the files, then stop before git push
#                          (HF_TOKEN is not needed in that mode).
#
# This script does NOT create the Space. Create it first in the web UI
# (huggingface.co/new-space: SDK Docker, Blank, CPU basic, Public).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
: "${HF_USER:?set HF_USER}"
: "${SPACE_NAME:?set SPACE_NAME}"
if [ "${DRY_RUN:-0}" != "1" ]; then
  : "${HF_TOKEN:?set HF_TOKEN}"
  export HF_TOKEN  # the credential helper below reads it from the environment
fi

STAGE="$(mktemp -d)"
if [ "${DRY_RUN:-0}" != "1" ]; then
  trap 'rm -rf "$STAGE"' EXIT
fi

cp "$REPO/Dockerfile" "$REPO/.dockerignore" "$REPO/requirements.txt" "$STAGE/"
cp "$REPO/deploy/hf/README.md" "$STAGE/README.md"
mkdir -p "$STAGE/web"
tar -C "$REPO" -cf - --exclude='__pycache__' --exclude='*.pyc' src \
  | tar -C "$STAGE" -xf -
tar -C "$REPO/web" -cf - --exclude='node_modules' --exclude='dist' . \
  | tar -C "$STAGE/web" -xf -

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
git commit -q -m "Deploy Chorus to Hugging Face Space"

# Token goes through a one-shot credential helper reading the environment, so
# it is never in the URL, the remote config, or the output.
git -c credential.helper= \
    -c "credential.helper=!f() { echo username=$HF_USER; echo password=\$HF_TOKEN; }; f" \
    push --force -q "https://huggingface.co/spaces/$HF_USER/$SPACE_NAME" main:main
echo "Pushed. Build logs: https://huggingface.co/spaces/$HF_USER/$SPACE_NAME"
