#!/usr/bin/env bash
# Interactive deploy to the Hugging Face Space: asks for a write token (hidden),
# checks which account and permission it has, then runs push_space.sh.
# The token is never printed or saved.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export HF_USER="${HF_USER:-TerminalRocketship34}"
export SPACE_NAME="${SPACE_NAME:-Chorus}"

echo "Deploying to https://huggingface.co/spaces/$HF_USER/$SPACE_NAME"
echo "Paste your Hugging Face WRITE token and press Enter."
echo "(Nothing will show while you paste. That is normal.)"
read -r -s -p "Token: " HF_TOKEN
echo
if [ -z "${HF_TOKEN}" ]; then
  echo "No token entered. Run the command again and paste the token before pressing Enter."
  exit 1
fi
export HF_TOKEN

echo "Checking the token..."
python - <<'PY'
import os, sys
from huggingface_hub import whoami
try:
    w = whoami(token=os.environ["HF_TOKEN"])
except Exception:
    print("That token was not accepted by Hugging Face. It may be mistyped or deleted.")
    print("Create a new one at https://huggingface.co/settings/tokens (Write tab) and try again.")
    sys.exit(1)
name = w.get("name")
role = (w.get("auth", {}).get("accessToken", {}) or {}).get("role")
print(f"Token account: {name}   Token type: {role}")
want = os.environ["HF_USER"]
if name != want:
    print(f"This token belongs to '{name}', but the Space belongs to '{want}'.")
    print(f"Sign in to huggingface.co as {want} and create the token there.")
    sys.exit(1)
if role == "fineGrained":
    print("This is a fine-grained token. It can upload only if it has write access to your")
    print("repositories. If the upload below says 'not authorized', create a token on the")
    print("Write tab instead (https://huggingface.co/settings/tokens) and run this again.")
elif role != "write":
    print("This token cannot upload. Create a new token on the Write tab at")
    print("https://huggingface.co/settings/tokens and run this again.")
    sys.exit(1)
print("Uploading...")
PY

bash "$HERE/push_space.sh"
