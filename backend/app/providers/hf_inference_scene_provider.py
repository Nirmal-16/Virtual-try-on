"""
Scene provider using free HF Spaces (FLUX.1-schnell → SDXL fallback).

Strategy
--------
1. Build a background-only prompt from the user's SCENE_PROMPT_TEMPLATE
2. Call black-forest-labs/FLUX.1-schnell (free, fast, beautiful) via gradio_client
3. Fallback to hysts/SDXL if FLUX fails
4. Composite the try-on person on the generated background with soft-edge blending
"""

import asyncio
import io as _io
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx
from PIL import Image, ImageDraw, ImageFilter

from app.providers.base import SceneProviderBase
from app.utils.logger import get_logger

logger = get_logger(__name__)
_executor = ThreadPoolExecutor(max_workers=1)


# ── Background generation prompt ──────────────────────────────────────────────

_BG_PREFIX = (
    "Indian wedding mandap stage background only, no people, empty stage, "
    "luxurious floral arch with pink roses white orchids fresh marigolds, "
    "golden ornate pillars, crystal chandelier, warm string fairy lights, "
    "cream and gold silk drapes, grand wedding backdrop, "
    "cinematic soft golden lighting, warm bokeh, "
    "photorealistic, ultra detailed, 8K, professional wedding photography, "
)

_BG_NEGATIVE = (
    "people, person, face, body, low quality, blurry, cartoon, "
    "watermark, text, logo, ugly, deformed"
)


def _build_bg_prompt(user_prompt: str) -> str:
    """Extract scene/atmosphere keywords from user prompt, prepend bg-only prefix."""
    # Keep first 300 chars of user prompt for style keywords
    style = user_prompt[:300] if len(user_prompt) > 300 else user_prompt
    return f"{_BG_PREFIX}{style}"


# ── Result image extractor (same as try-on provider) ─────────────────────────

def _image_from_result(result) -> Optional[Image.Image]:
    if result is None:
        return None
    if isinstance(result, (list, tuple)):
        for item in result:
            img = _image_from_result(item)
            if img is not None:
                return img
        return None
    if hasattr(result, "path"):
        p = getattr(result, "path", None)
        if p and os.path.exists(str(p)):
            return Image.open(str(p)).convert("RGB")
    if hasattr(result, "url"):
        u = getattr(result, "url", None)
        if u:
            r = httpx.get(u, timeout=120, follow_redirects=True)
            r.raise_for_status()
            return Image.open(_io.BytesIO(r.content)).convert("RGB")
    if isinstance(result, dict):
        for key in ("path", "name", "tmp_path", "filepath"):
            p = result.get(key)
            if p and os.path.exists(str(p)):
                return Image.open(str(p)).convert("RGB")
        for key in ("url", "src"):
            u = result.get(key)
            if u:
                r = httpx.get(u, timeout=120, follow_redirects=True)
                r.raise_for_status()
                return Image.open(_io.BytesIO(r.content)).convert("RGB")
    if isinstance(result, str):
        if os.path.exists(result):
            return Image.open(result).convert("RGB")
        if result.startswith("http"):
            r = httpx.get(result, timeout=120, follow_redirects=True)
            r.raise_for_status()
            return Image.open(_io.BytesIO(r.content)).convert("RGB")
    if isinstance(result, (bytes, bytearray)):
        return Image.open(_io.BytesIO(result)).convert("RGB")
    return None


# ── Space predict functions ───────────────────────────────────────────────────

def _predict_flux(client, prompt: str) -> Optional[Image.Image]:
    """black-forest-labs/FLUX.1-schnell — fast, beautiful, free."""
    attempts = [
        dict(api_name="/infer"),
        dict(fn_index=0),
    ]
    for kwargs in attempts:
        try:
            raw = client.predict(
                prompt,   # prompt
                0,        # seed
                True,     # randomize_seed
                1024,     # width
                1024,     # height
                4,        # num_inference_steps
                **kwargs,
            )
            img = _image_from_result(raw)
            if img:
                return img
        except Exception as exc:
            logger.warning("flux_predict_attempt_failed", kwargs=str(kwargs), error=str(exc))
    return None


def _predict_sdxl(client, prompt: str) -> Optional[Image.Image]:
    """hysts/SDXL fallback."""
    attempts = [
        dict(api_name="/run"),
        dict(api_name="/predict"),
        dict(fn_index=0),
    ]
    for kwargs in attempts:
        try:
            raw = client.predict(prompt, _BG_NEGATIVE, 42, 1024, 1024, 7.5, 20, **kwargs)
            img = _image_from_result(raw)
            if img:
                return img
        except Exception:
            try:
                raw = client.predict(prompt, **kwargs)
                img = _image_from_result(raw)
                if img:
                    return img
            except Exception as exc:
                logger.warning("sdxl_predict_failed", error=str(exc))
    return None


_SCENE_SPACES = [
    ("black-forest-labs/FLUX.1-schnell", _predict_flux),
    ("hysts/SDXL",                       _predict_sdxl),
]


# ── Soft-edge composite ───────────────────────────────────────────────────────

def _soft_edge_mask(w: int, h: int, feather: int = 30) -> Image.Image:
    """Rectangular alpha mask with softened edges."""
    mask = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(mask)
    for i in range(feather):
        v = int(255 * (i / feather) ** 2)
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=v)
    return mask.filter(ImageFilter.GaussianBlur(radius=feather // 3))


def _composite(background: Image.Image, person: Image.Image) -> Image.Image:
    """Paste person at bottom-centre of background with soft edge blending."""
    bg_w, bg_h = background.size

    # Scale person to 60% of background width
    p_w = int(bg_w * 0.60)
    p_h = int(person.height * (p_w / person.width))
    if p_h > int(bg_h * 0.90):
        p_h = int(bg_h * 0.90)
        p_w = int(person.width * (p_h / person.height))

    person_rs = person.resize((p_w, p_h), Image.LANCZOS)

    x = (bg_w - p_w) // 2
    y = bg_h - p_h - int(bg_h * 0.03)

    bg_rgba     = background.convert("RGBA")
    person_rgba = person_rs.convert("RGBA")

    # If person has real transparency (product photo / removed bg) use it directly
    alpha_vals = person_rgba.split()[3].getextrema()
    has_transparency = alpha_vals[0] < 200

    if has_transparency:
        mask = person_rgba.split()[3]
    else:
        # Real photo with solid background → soft-edge rectangular blend
        mask = _soft_edge_mask(p_w, p_h, feather=25)

    bg_rgba.paste(person_rgba, (x, y), mask=mask)
    return bg_rgba.convert("RGB")


# ── Provider class ────────────────────────────────────────────────────────────

class HFInferenceSceneProvider(SceneProviderBase):
    def __init__(self, hf_token: str = "") -> None:
        self._hf_token = hf_token or None

    @property
    def name(self) -> str:
        return "hf_inference"

    async def generate(self, prompt: str, base_image: Image.Image) -> Image.Image:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _executor, self._generate_sync, prompt, base_image
        )

    def _generate_sync(self, prompt: str, base_image: Image.Image) -> Image.Image:
        try:
            from gradio_client import Client
        except ImportError as exc:
            raise RuntimeError(
                "gradio_client not installed. Run: pip install gradio-client>=1.0.0"
            ) from exc

        bg_prompt = _build_bg_prompt(prompt)
        background: Optional[Image.Image] = None

        for space, predict_fn in _SCENE_SPACES:
            logger.info("hf_scene_trying", space=space)
            try:
                client = Client(space)
                background = predict_fn(client, bg_prompt)
                if background is not None:
                    logger.info("hf_scene_generated", space=space)
                    break
            except Exception as exc:
                logger.warning("hf_scene_space_failed", space=space, error=str(exc))
                continue

        if background is None:
            logger.warning("hf_scene_all_failed_using_fallback")
            background = _mandap_fallback(1024, 1024)

        return _composite(background, base_image)


# ── PIL fallback — Indian wedding mandap ─────────────────────────────────────

def _mandap_fallback(w: int, h: int) -> Image.Image:
    """High-quality PIL wedding mandap (used only when all HF spaces fail)."""
    import math
    from PIL import ImageDraw

    img  = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)

    # Warm cream-to-gold gradient background
    for y in range(h):
        t = y / h
        r = int(255 - t * 30)
        g = int(245 - t * 60)
        b = int(210 - t * 80)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # ── Backdrop curtain ────────────────────────────────────────────────────
    curtain_cols = [
        (255, 215, 120), (240, 190, 80), (255, 215, 120),
        (240, 190, 80),  (255, 215, 120),
    ]
    cw = w // len(curtain_cols)
    for i, col in enumerate(curtain_cols):
        x0 = i * cw
        draw.rectangle([x0, 0, x0 + cw, int(h * 0.65)], fill=col)
        # Curtain folds
        for fold_x in range(x0 + 20, x0 + cw, 40):
            draw.line([(fold_x, 0), (fold_x, int(h * 0.65))],
                      fill=(max(col[0]-30, 0), max(col[1]-30, 0), max(col[2]-30, 0)), width=3)

    # ── Floral arch ─────────────────────────────────────────────────────────
    PINK   = (255, 160, 180)
    ROSE   = (220,  80, 100)
    WHITE  = (255, 250, 245)
    YELLOW = (255, 220,  60)
    GREEN  = (100, 160,  60)
    PEACH  = (255, 190, 140)

    arch_cx = w // 2
    arch_cy = int(h * 0.55)
    arch_rx = int(w * 0.44)
    arch_ry = int(h * 0.42)

    def flower(d, cx, cy, outer, inner, centre):
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            px = int(cx + 14 * math.cos(rad))
            py = int(cy + 14 * math.sin(rad))
            d.ellipse([px-10, py-10, px+10, py+10], fill=outer)
        d.ellipse([cx-10, cy-10, cx+10, cy+10], fill=inner)
        d.ellipse([cx-5,  cy-5,  cx+5,  cy+5],  fill=centre)

    # Arch spine (green leaves)
    for angle_deg in range(0, 181, 3):
        rad = math.radians(angle_deg)
        ax  = int(arch_cx - arch_rx * math.cos(rad))
        ay  = int(arch_cy - arch_ry * math.sin(rad))
        draw.ellipse([ax-12, ay-12, ax+12, ay+12], fill=GREEN)

    # Flowers on arch
    flower_colors = [
        (PINK, ROSE, YELLOW),
        (WHITE, PEACH, YELLOW),
        (ROSE, PINK, WHITE),
        (PEACH, PINK, YELLOW),
    ]
    for i, angle_deg in enumerate(range(0, 181, 8)):
        rad = math.radians(angle_deg)
        ax  = int(arch_cx - arch_rx * math.cos(rad))
        ay  = int(arch_cy - arch_ry * math.sin(rad))
        outer, inner, centre = flower_colors[i % len(flower_colors)]
        flower(draw, ax, ay, outer, inner, centre)

    # ── String fairy lights ──────────────────────────────────────────────────
    GOLD_WIRE   = (180, 140, 40)
    LIGHT_WARM  = (255, 230, 120)
    LIGHT_GLOW  = (255, 200,  60)
    anchor_y    = int(h * 0.08)
    for strand in range(4):
        y_offset = strand * 18
        for x in range(0, w + 30, 30):
            sway = int(18 * math.sin(x * math.pi / (w / 3)))
            ly   = anchor_y + y_offset + sway
            if x >= 30:
                prev_sway = int(18 * math.sin((x-30) * math.pi / (w / 3)))
                prev_ly   = anchor_y + y_offset + prev_sway
                draw.line([(x-30, prev_ly), (x, ly)], fill=GOLD_WIRE, width=1)
            draw.ellipse([x-7, ly-7, x+7, ly+7], fill=LIGHT_WARM)
            draw.ellipse([x-4, ly-4, x+4, ly+4], fill=LIGHT_GLOW)

    # ── Gold pillars ─────────────────────────────────────────────────────────
    GOLD_DARK  = (160, 120, 30)
    GOLD_MID   = (200, 160, 50)
    GOLD_LIGHT = (240, 200, 80)
    pw = int(w * 0.085)
    for x0, x1 in [(0, pw), (w - pw, w)]:
        draw.rectangle([x0, int(h*0.08), x1, h], fill=GOLD_DARK)
        draw.rectangle([x0, int(h*0.08), x1, int(h*0.08)+20], fill=GOLD_LIGHT)
        for by in range(int(h*0.12), h, int(h*0.10)):
            draw.rectangle([x0, by, x1, by+8], fill=GOLD_MID)
            draw.rectangle([x0, by+2, x1, by+5], fill=GOLD_LIGHT)

    # ── Marigold garlands on pillars ─────────────────────────────────────────
    MARIGOLD = (255, 165, 0)
    MARIGOLD2= (255, 130, 0)
    for px in [pw // 2, w - pw // 2]:
        for gy in range(int(h * 0.12), int(h * 0.70), 28):
            draw.ellipse([px-9, gy-9, px+9, gy+9], fill=MARIGOLD)
            draw.ellipse([px-5, gy-5, px+5, gy+5], fill=MARIGOLD2)
            draw.ellipse([px-2, gy-2, px+2, gy+2], fill=YELLOW)

    # ── Floor ────────────────────────────────────────────────────────────────
    floor_y = int(h * 0.80)
    for y in range(floor_y, h):
        t = (y - floor_y) / (h - floor_y)
        r = int(200 + t * 30)
        g = int(170 + t * 20)
        b = int(100 + t * 10)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Marble lines on floor
    for line_x in range(pw, w - pw, int(w * 0.12)):
        draw.line([(line_x, floor_y), (line_x, h)],
                  fill=(180, 150, 90), width=1)

    # ── Diyas on floor ───────────────────────────────────────────────────────
    CLAY   = (190, 140, 50)
    FLAME1 = (255, 110, 0)
    FLAME2 = (255, 230, 60)
    for dx in range(int(pw * 1.5), w - int(pw * 1.5), int(w * 0.08)):
        dy = floor_y + 14
        draw.ellipse([dx-10, dy-6, dx+10, dy+8], fill=CLAY)
        draw.ellipse([dx-6,  dy-22, dx+6, dy-6], fill=FLAME1)
        draw.ellipse([dx-3,  dy-20, dx+3, dy-10], fill=FLAME2)

    # ── Soft vignette ────────────────────────────────────────────────────────
    vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for r in range(min(w, h) // 2, 0, -4):
        alpha = int(40 * (1 - r / (min(w, h) // 2)))
        vd.ellipse(
            [w//2 - r, h//2 - r, w//2 + r, h//2 + r],
            outline=(0, 0, 0, alpha), width=4
        )
    img = Image.alpha_composite(img.convert("RGBA"), vignette).convert("RGB")

    return img
