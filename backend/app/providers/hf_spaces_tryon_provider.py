"""
HuggingFace Spaces virtual try-on — free, no GPU / API key needed.

Spaces tried in order (first healthy one wins):
  1. yisol/IDM-VTON          — /tryon API, well-known
  2. levihsu/OOTDiffusion    — OOTDiffusion, reliable free space
  3. Kwai-Kolors/Kolors-Virtual-Try-On — Kolors model
  4. zhengchong/CatVTON      — original CatVTON
"""

import asyncio
import io as _io
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx
from PIL import Image

from app.utils.errors import TryOnError
from app.utils.image_utils import resize_for_model
from app.utils.logger import get_logger

logger = get_logger(__name__)
_executor = ThreadPoolExecutor(max_workers=1)


# ── Result parser ──────────────────────────────────────────────────────────────
# gradio_client >= 1.0 may return: PIL Image, FileData, dict, str path, URL, bytes

def _image_from_result(result) -> Optional[Image.Image]:
    if result is None:
        return None

    # Direct PIL Image (gradio_client >= 1.0 sometimes returns this)
    if isinstance(result, Image.Image):
        return result.convert("RGB")

    # List / tuple — recurse, return first valid image
    if isinstance(result, (list, tuple)):
        for item in result:
            img = _image_from_result(item)
            if img is not None:
                return img
        return None

    # gradio_client FileData object (.path / .url attributes)
    if hasattr(result, "path"):
        p = getattr(result, "path", None)
        if p and os.path.exists(str(p)):
            return Image.open(str(p)).convert("RGB")
    if hasattr(result, "url"):
        u = getattr(result, "url", None)
        if u:
            return _fetch(u)

    # Dict {"path": ..., "url": ...}
    if isinstance(result, dict):
        for key in ("path", "name", "tmp_path", "filepath"):
            p = result.get(key)
            if p and os.path.exists(str(p)):
                return Image.open(str(p)).convert("RGB")
        for key in ("url", "src"):
            u = result.get(key)
            if u:
                return _fetch(u)

    # Plain string — local path or URL
    if isinstance(result, str):
        if os.path.exists(result):
            return Image.open(result).convert("RGB")
        if result.startswith("http"):
            return _fetch(result)

    # Raw bytes
    if isinstance(result, (bytes, bytearray)):
        return Image.open(_io.BytesIO(result)).convert("RGB")

    return None


def _fetch(url: str) -> Image.Image:
    r = httpx.get(url, timeout=120, follow_redirects=True)
    r.raise_for_status()
    return Image.open(_io.BytesIO(r.content)).convert("RGB")


# ── Space-specific predict functions ──────────────────────────────────────────

def _predict_idm_vton(
    client, person_path: str, dress_path: str, cloth_type: str = "upper"
) -> Optional[Image.Image]:
    """yisol/IDM-VTON — image-editor dict input, /tryon endpoint."""
    from gradio_client import handle_file

    garment_desc = {
        "upper":   "upper body garment",
        "lower":   "lower body garment",
        "overall": "full body outfit",
    }.get(cloth_type, "garment")

    # Try dict format first (original IDM-VTON API), then plain file fallback
    inputs_variants = [
        [
            {"background": handle_file(person_path), "layers": [], "composite": None},
            handle_file(dress_path),
            garment_desc, True, False, 30, 42,
        ],
        [
            handle_file(person_path),
            handle_file(dress_path),
            garment_desc, True, False, 30, 42,
        ],
    ]

    for inputs in inputs_variants:
        for kwargs in [{"api_name": "/tryon"}, {"fn_index": 0}]:
            try:
                raw = client.predict(*inputs, **kwargs)
                img = _image_from_result(raw)
                if img is not None:
                    logger.info("idm_vton_success")
                    return img
            except Exception as exc:
                logger.warning("idm_vton_attempt", error=str(exc)[:120])
    return None


def _predict_ootd(
    client, person_path: str, dress_path: str, cloth_type: str = "upper"
) -> Optional[Image.Image]:
    """levihsu/OOTDiffusion — category-aware API."""
    from gradio_client import handle_file

    cat_map = {"upper": "upperbody", "lower": "lowerbody", "overall": "dress"}
    category = cat_map.get(cloth_type, "upperbody")

    # Discover endpoints first
    endpoint_names: list[str] = []
    try:
        info = client.view_api(return_format="dict") or {}
        endpoint_names = list(info.get("named_endpoints", {}).keys())
    except Exception:
        pass

    input_variants = [
        [handle_file(person_path), handle_file(dress_path), category],
        [handle_file(person_path), handle_file(dress_path), category, 20, 2.0, 42],
        [handle_file(person_path), handle_file(dress_path)],
    ]

    for ep in (endpoint_names or ["/run", "/predict", "/infer"]):
        for inputs in input_variants:
            try:
                raw = client.predict(*inputs, api_name=ep)
                img = _image_from_result(raw)
                if img is not None:
                    logger.info("ootd_success", endpoint=ep)
                    return img
            except Exception:
                continue
    return None


def _predict_kolors(
    client, person_path: str, dress_path: str, cloth_type: str = "upper"
) -> Optional[Image.Image]:
    """Kwai-Kolors/Kolors-Virtual-Try-On."""
    from gradio_client import handle_file

    endpoint_names: list[str] = []
    try:
        info = client.view_api(return_format="dict") or {}
        endpoint_names = list(info.get("named_endpoints", {}).keys())
    except Exception:
        pass

    input_variants = [
        [handle_file(person_path), handle_file(dress_path)],
        [handle_file(person_path), handle_file(dress_path), cloth_type],
        [handle_file(person_path), handle_file(dress_path), cloth_type, 20, 2.5, 42],
    ]

    for ep in (endpoint_names or ["/tryon", "/run", "/predict"]):
        for inputs in input_variants:
            try:
                raw = client.predict(*inputs, api_name=ep)
                img = _image_from_result(raw)
                if img is not None:
                    logger.info("kolors_success", endpoint=ep)
                    return img
            except Exception:
                continue
    return None


def _predict_catvton(
    client, person_path: str, dress_path: str, cloth_type: str = "upper"
) -> Optional[Image.Image]:
    """zhengchong/CatVTON — discover endpoint dynamically."""
    from gradio_client import handle_file

    endpoint_names: list[str] = []
    try:
        info = client.view_api(return_format="dict") or {}
        endpoint_names = list(info.get("named_endpoints", {}).keys())
        logger.info("catvton_endpoints", endpoints=endpoint_names)
    except Exception:
        pass

    ct_aliases = {
        "upper":   ["upper", "tops", "upper body"],
        "lower":   ["lower", "bottoms", "lower body"],
        "overall": ["overall", "full", "dresses"],
    }.get(cloth_type, ["upper"])

    input_variants = (
        [(handle_file(person_path), handle_file(dress_path), ct) for ct in ct_aliases]
        + [(handle_file(person_path), handle_file(dress_path), ct, 30, 2.5, 42)
           for ct in ct_aliases]
        + [(handle_file(person_path), handle_file(dress_path))]
    )

    for ep in endpoint_names:
        for inputs in input_variants:
            try:
                raw = client.predict(*inputs, api_name=ep)
                img = _image_from_result(raw)
                if img is not None:
                    logger.info("catvton_success", endpoint=ep)
                    return img
            except Exception:
                continue
    return None


# ── Space registry ────────────────────────────────────────────────────────────

_SPACES = [
    ("yisol/IDM-VTON",                    _predict_idm_vton),
    ("levihsu/OOTDiffusion",              _predict_ootd),
    ("Kwai-Kolors/Kolors-Virtual-Try-On", _predict_kolors),
    ("zhengchong/CatVTON",                _predict_catvton),
]


# ── Main sync runner ──────────────────────────────────────────────────────────

def _run_hf_spaces_sync(
    person: Image.Image,
    dress: Image.Image,
    hf_token: Optional[str],
    cloth_type: str = "upper",
) -> Image.Image:
    try:
        from gradio_client import Client
    except ImportError as exc:
        raise TryOnError(
            "gradio_client not installed. Run: pip install gradio-client>=1.0.0"
        ) from exc

    if hf_token:
        try:
            from huggingface_hub import login as hf_login
            hf_login(token=hf_token, add_to_git_credential=False)
        except Exception:
            pass

    with tempfile.TemporaryDirectory() as tmp:
        person_path = os.path.join(tmp, "person.png")
        dress_path  = os.path.join(tmp, "dress.png")
        resize_for_model(person, 768).save(person_path, format="PNG")
        resize_for_model(dress,  768).save(dress_path,  format="PNG")

        errors: list[str] = []

        for space, predict_fn in _SPACES:
            logger.info("hf_spaces_trying", space=space, cloth_type=cloth_type)
            try:
                client = Client(space)
                img = predict_fn(client, person_path, dress_path, cloth_type)
                if img is not None:
                    logger.info("hf_spaces_done", space=space)
                    return img
                errors.append(f"{space}: returned no image")
            except TryOnError:
                raise
            except Exception as exc:
                msg = f"{space}: {str(exc)[:120]}"
                logger.warning("hf_spaces_space_error", error=msg)
                errors.append(msg)

        raise TryOnError(
            "All free HF Spaces failed.\n"
            + "\n".join(f"  • {e}" for e in errors)
            + "\n\nTips:\n"
            "  • Spaces may be sleeping — wait 2 min and retry\n"
            "  • Set CATVTON_MODEL_ID=mock in backend/.env for instant offline preview"
        )


async def run_hf_spaces_tryon(
    person: Image.Image,
    dress: Image.Image,
    hf_token: Optional[str] = None,
    cloth_type: str = "upper",
) -> Image.Image:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _run_hf_spaces_sync,
        person,
        dress,
        hf_token,
        cloth_type,
    )
