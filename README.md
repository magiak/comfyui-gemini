# comfyui-gemini

A minimal ComfyUI custom node that calls **Google Gemini Image** (Nano Banana / Gemini 3 Pro Image) **directly** using a `GEMINI_API_KEY` environment variable.

Bypasses ComfyUI's official Gemini nodes, which route through the **Comfy.org commercial API gateway** (requires login, adds markup). With this node you call Google directly using your own Google AI Studio / Vertex API key.

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

Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in the ComfyUI server's environment:

- **docker-compose**: `environment: GEMINI_API_KEY=...`
- **systemd**: `Environment="GEMINI_API_KEY=..."` in the unit file
- **plain shell**: `export GEMINI_API_KEY=...` before launching ComfyUI

The key is read at call time from `os.environ`. Get a key at <https://aistudio.google.com/apikey>. The linked Google Cloud project must have billing enabled — Gemini Image generation is not in the free tier.

## Pricing

Billed by Google directly:

- `gemini-3-pro-image-preview`: ~$0.13 / image
- `gemini-2.5-flash-image`: ~$0.04 / image

No Comfy.org markup.

## License

MIT
