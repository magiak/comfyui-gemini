"""ComfyUI custom node: GeminiImageDirect.

Calls Google Gemini Image (Nano Banana / Gemini 3 Pro Image) DIRECTLY using a
GEMINI_API_KEY environment variable on the ComfyUI server. Bypasses ComfyUI's
official Gemini nodes, which route through the Comfy.org commercial API
gateway (markup + login required).

Inputs:
  prompt       (STRING, multiline)  Edit / generation prompt.
  model        (COMBO)               gemini-3-pro-image-preview |
                                     gemini-3-1-flash-image-preview |
                                     gemini-2.5-flash-image
  aspect_ratio (COMBO)               16:9, 9:16, 1:1, ...
  seed         (INT)                 Best-effort determinism (Gemini honors loosely).
  image        (IMAGE, optional)     Reference / canvas image to edit.

Output:
  IMAGE  - generated image as ComfyUI tensor.
  STRING - any text the model returned alongside the image (usually empty).

Setup on the ComfyUI server (one-time):
  1. Install via ComfyUI Manager > Install via Git URL: <repo URL>
  2. Set environment variable GEMINI_API_KEY (docker-compose / systemd / shell).
  3. Restart ComfyUI.

The Gemini API key is read at call time from os.environ["GEMINI_API_KEY"]
(falls back to GOOGLE_API_KEY).
"""
from __future__ import annotations

import io
import os

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
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY env var not set on the ComfyUI server. "
                "Set it in your ComfyUI startup (docker-compose / systemd / shell)."
            )

        client = genai.Client(api_key=api_key)

        contents = [prompt]
        if image is not None:
            pil = _tensor_to_pil(image)
            contents.append(pil)

        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            seed=seed,
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        if not response.candidates:
            raise RuntimeError(f"Gemini returned no candidates: {response}")

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
        raise RuntimeError(f"Gemini returned no image. Model said: {joined}")


NODE_CLASS_MAPPINGS = {"GeminiImageDirect": GeminiImageDirect}
NODE_DISPLAY_NAME_MAPPINGS = {"GeminiImageDirect": "Gemini Image (Direct API)"}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
