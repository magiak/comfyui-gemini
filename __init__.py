"""ComfyUI custom node: GeminiImageDirect.

Calls Google Gemini Image (Nano Banana / Gemini 3 Pro Image) DIRECTLY,
bypassing ComfyUI's official Gemini nodes (which route through the Comfy.org
commercial API gateway with a markup + login).

Two backends, auto-selected from environment:

1. Vertex AI (recommended for production / GDPR / higher quotas)
   - Set GCP_PROJECT_ID  (required)  e.g. "designeo-marketing-ai"
   - Set GCP_LOCATION    (optional)  e.g. "europe-west4" (default "us-central1")
   - Set GOOGLE_APPLICATION_CREDENTIALS to a service account JSON path
     (or use ADC via `gcloud auth application-default login`).
   - Service account needs IAM role: roles/aiplatform.user.

2. AI Studio (simple Gemini Developer API key)
   - Set GEMINI_API_KEY (or GOOGLE_API_KEY) — get one from
     https://aistudio.google.com/apikey
   - Used as fallback when GCP_PROJECT_ID is not set.

Inputs:
  prompt       (STRING, multiline)  Edit / generation prompt.
  model        (COMBO)               gemini-3-pro-image-preview |
                                     gemini-3-1-flash-image-preview |
                                     gemini-2.5-flash-image
  aspect_ratio (COMBO)               16:9, 9:16, 1:1, ...
  seed         (INT)                 Best-effort determinism.
  image        (IMAGE, optional)     Reference / canvas image to edit.

Output:
  IMAGE  - generated image as ComfyUI tensor.
  STRING - any text the model returned alongside the image.

Setup on the ComfyUI server (one-time):
  1. Install via ComfyUI Manager > Install via Git URL.
  2. Set the environment variables above.
  3. Restart ComfyUI (docker-compose up -d to re-create the container —
     plain `restart` does NOT pick up new env vars).
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path


def _ensure_deps() -> None:
    """Auto-install requirements.txt deps if missing.

    Survives docker-compose container recreate (which wipes site-packages
    even though pip_cache is mounted). Runs once at module import.
    """
    try:
        import google.genai  # noqa: F401
        return
    except ImportError:
        pass
    req = Path(__file__).parent / "requirements.txt"
    print(f"[comfyui-gemini] google-genai missing, installing {req}...", flush=True)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(req)],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    print("[comfyui-gemini] install complete.", flush=True)


_ensure_deps()


import numpy as np
import torch
from PIL import Image


SUPPORTED_MODELS = (
    "gemini-3-pro-image-preview",
    "gemini-3-1-flash-image-preview",
    "gemini-2.5-flash-image",
    "gemini-2.5-flash-image-preview",
)

SUPPORTED_ASPECTS = (
    "16:9",
    "9:16",
    "1:1",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "21:9",
    "4:5",
    "5:4",
)


def _tensor_to_pil(tensor: torch.Tensor) -> Image.Image:
    """ComfyUI IMAGE tensor [B, H, W, C] in 0..1 -> PIL Image (first batch item)."""
    arr = tensor[0].clamp(0, 1).cpu().numpy()
    arr = (arr * 255).astype(np.uint8)
    if arr.shape[-1] == 4:
        return Image.fromarray(arr, mode="RGBA").convert("RGB")
    return Image.fromarray(arr, mode="RGB")


def _pil_to_tensor(pil: Image.Image) -> torch.Tensor:
    """PIL Image -> ComfyUI IMAGE tensor [1, H, W, 3] in 0..1."""
    if pil.mode != "RGB":
        pil = pil.convert("RGB")
    arr = np.asarray(pil, dtype=np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def _make_client():
    """Build a genai.Client based on env vars.

    Vertex AI mode if GCP_PROJECT_ID is set; otherwise AI Studio with API key.
    """
    from google import genai

    project_id = os.environ.get("GCP_PROJECT_ID")
    if project_id:
        location = os.environ.get("GCP_LOCATION", "us-central1")
        return genai.Client(vertexai=True, project=project_id, location=location), f"vertex({project_id}/{location})"

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No Gemini auth configured on the ComfyUI server. "
            "Set GCP_PROJECT_ID (+ GOOGLE_APPLICATION_CREDENTIALS) for Vertex AI, "
            "or GEMINI_API_KEY for AI Studio. See node docstring."
        )
    return genai.Client(api_key=api_key), "ai_studio"


class GeminiImageDirect:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "model": (list(SUPPORTED_MODELS), {"default": "gemini-3-pro-image-preview"}),
                "aspect_ratio": (list(SUPPORTED_ASPECTS), {"default": "16:9"}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 0xFFFFFFFFFFFFFFFF, "control_after_generate": True}),
            },
            "optional": {
                "image": ("IMAGE", {}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "text")
    FUNCTION = "generate"
    CATEGORY = "Gemini"

    def generate(self, prompt: str, model: str, aspect_ratio: str, seed: int, image=None):
        from google.genai import types

        client, backend = _make_client()

        contents = [prompt]
        if image is not None:
            pil = _tensor_to_pil(image)
            contents.append(pil)

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            seed=int(seed) & 0x7FFFFFFF,
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        if not response.candidates:
            raise RuntimeError(f"[{backend}] Gemini returned no candidates: {response}")

        parts = response.candidates[0].content.parts or []
        texts = []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                pil = Image.open(io.BytesIO(inline.data))
                return (_pil_to_tensor(pil), " ".join(texts))
            text = getattr(part, "text", None)
            if text:
                texts.append(text)

        joined = " | ".join(texts) or "<no image, no text>"
        raise RuntimeError(f"[{backend}] Gemini returned no image. Model said: {joined}")


NODE_CLASS_MAPPINGS = {"GeminiImageDirect": GeminiImageDirect}
NODE_DISPLAY_NAME_MAPPINGS = {"GeminiImageDirect": "Gemini Image (Direct API)"}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
