# Deploying to Hugging Face Spaces

1. **Create the Space** (web UI, huggingface.co/new-space): SDK Docker, template
   Blank, hardware CPU basic (free), visibility Public. The script never creates it.
2. **Create a token**: Settings > Access Tokens > New token, role Write.
3. **Push**:
   ```
   export HF_USER=<your-username> SPACE_NAME=<space-name> HF_TOKEN=<token>
   bash deploy/hf/push_space.sh
   ```
   Add `DRY_RUN=1` first to see exactly which files would be pushed (no token needed).
4. **Watch the build**: Space page > Logs > Build. Expect a long first build
   (torch CPU wheels, model downloads for base.en, small.en and MMS_FA, npm build).
5. **First cold start**: with `CHORUS_WARMUP=1` the app loads Whisper and the aligner
   before serving, so the Space shows "Starting" for a while, then the page loads.
   The first analysis after that is still slower than later ones.
6. **Switch to small.en**: Space Settings > Variables and secrets > New variable
   `CHORUS_ASR_MODEL` = `small.en`, then Restart the Space. (small.en is already
   cached in the image; no rebuild needed.) Watch RAM and latency on 2 vCPU.
7. **Data is ephemeral**: the SQLite DB lives in `/tmp/chorus.db`, so teacher-view
   data resets whenever the Space restarts or sleeps (free Spaces sleep after about
   48 h idle). Audio is never stored.
