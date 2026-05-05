# comfyui-gemini

A minimal ComfyUI custom node that calls **Google Gemini Image** (Nano Banana / Gemini 3 Pro Image) **directly**, bypassing ComfyUI's official Gemini nodes (which route through the Comfy.org commercial API gateway with login + markup).

Two backends, auto-selected from environment variables on the ComfyUI server:

- **Vertex AI** — recommended for production. Higher quotas, GDPR-friendly EU regions, IAM-based auth via service account.
- **AI Studio** — simple Gemini Developer API key. Easiest to set up, but Tier 1 has a 250 RPD limit on `gemini-3-pro-image-preview`.

## Node

**`GeminiImageDirect`** — display name *"Gemini Image (Direct API)"* — category `Gemini`.

| input | type | notes |
|------|------|-------|
| `prompt` | STRING (multiline) | edit / generation prompt |
| `model` | COMBO | `gemini-3-pro-image-preview`, `gemini-3-1-flash-image-preview`, `gemini-2.5-flash-image`, `gemini-2.5-flash-image-preview` |
| `aspect_ratio` | COMBO | `16:9`, `9:16`, `1:1`, ... |
| `seed` | INT | best-effort determinism |
| `image` | IMAGE (optional) | reference / canvas image for edit mode |

Outputs:

- `image` — `IMAGE`
- `text` — `STRING` (any text the model returns alongside the image)

## Install

### Via ComfyUI Manager

1. Open ComfyUI → Manager → **Install via Git URL**
2. Paste this repo URL
3. Restart ComfyUI

### Manual

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/magiak/comfyui-gemini.git
pip install -r comfyui-gemini/requirements.txt
# restart ComfyUI
```

## Configuration

Set environment variables on the ComfyUI server. The node picks the backend automatically: if `GCP_PROJECT_ID` is set, Vertex AI is used; otherwise the AI Studio API key.

> ⚠️ For docker-compose, env-var changes need a **container recreate** (`docker compose up -d <service>`), not just `restart`.

### Option A — Vertex AI (recommended)

| env var | required | example |
|---|---|---|
| `GCP_PROJECT_ID` | yes | `designeo-marketing-ai` |
| `GCP_LOCATION` | no | `europe-west4` (default `us-central1`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | usually yes | `/secrets/vertex-sa.json` (service account key path) |

The service account needs the IAM role **Vertex AI User** (`roles/aiplatform.user`).

`docker-compose.yml` snippet:

```yaml
services:
  comfyui:
    volumes:
      - ./secrets/vertex-sa.json:/secrets/vertex-sa.json:ro
    environment:
      - GCP_PROJECT_ID=designeo-marketing-ai
      - GCP_LOCATION=europe-west4
      - GOOGLE_APPLICATION_CREDENTIALS=/secrets/vertex-sa.json
```

### Option B — AI Studio

| env var | required | example |
|---|---|---|
| `GEMINI_API_KEY` | yes | `AIzaSy...` |

Get the key at <https://aistudio.google.com/apikey>. The linked Google Cloud project must have billing enabled — Gemini image generation is not in the free tier.

## Pricing

Billed by Google directly (same on both backends, no Comfy.org markup):

- `gemini-3-pro-image-preview`: ~$0.13 / image
- `gemini-2.5-flash-image`: ~$0.04 / image

## Rate limits

AI Studio rate limits are tier-based and tighten on Tier 1. Indicative values for `gemini-3-pro-image-preview`:

| | Tier 1 | Tier 3 |
|---|---|---|
| RPM | 20 | 2 000 |
| RPD | 250 | unlimited |

Vertex AI quotas are project-level and significantly higher; check Google Cloud Console → IAM & Admin → Quotas.

## License

MIT
