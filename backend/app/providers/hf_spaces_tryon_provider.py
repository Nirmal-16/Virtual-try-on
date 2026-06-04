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

def _image_from_result(result) -> Optional[Image.Image]:  # noqa: C901
    """Try every known shape gradio_client may return and extract a PIL Image."""
    if result is None:
        return None

    # ── Direct PIL Image ─────────────────────────────────────────────────────
    if isinstance(result, Image.Image):
        return result.convert("RGB")

    # ── numpy array ──────────────────────────────────────────────────────────
    try:
        import numpy as np
        if isinstance(result, np.ndarray):
            return Image.fromarray(result.astype("uint8")).convert("RGB")
    except ImportError:
        pass

    # ── List / tuple — recurse, first valid image wins ───────────────────────
    if isinstance(result, (list, tuple)):
        for item in result:
            img = _image_from_result(item)
            if img is not None:
                return img
        return None

    # ── Object with .value (Gradio component wrapper) ────────────────────────
    if hasattr(result, "value") and not isinstance(result, dict):
        img = _image_from_result(getattr(result, "value"))
        if img is not None:
            return img

    # ── FileData / any object with .path or .url ─────────────────────────────
    for attr in ("path", "file_path", "tmp_path"):
        p = getattr(result, attr, None)
        if p:
            p = str(p)
            if p.startswith("http"):
                try:
                    return _fetch(p)
                except Exception:
                    pass
            else:
                try:
                    return Image.open(p).convert("RGB")
                except Exception:
                    pass

    for attr in ("url", "src", "file_url"):
        u = getattr(result, attr, None)
        if u:
            try:
                return _fetch(str(u))
            except Exception:
                pass

    # ── Dict ─────────────────────────────────────────────────────────────────
    if isinstance(result, dict):
        for key in ("path", "name", "tmp_path", "filepath", "file_path"):
            p = result.get(key)
            if p:
                p = str(p)
                if p.startswith("http"):
                    try:
                        return _fetch(p)
                    except Exception:
                        pass
                else:
                    try:
                        return Image.open(p).convert("RGB")
                    except Exception:
                        pass
        for key in ("url", "src", "file_url", "image_url"):
            u = result.get(key)
            if u:
                try:
                    return _fetch(str(u))
                except Exception:
                    pass

    # ── Plain string — try as path then as URL ────────────────────────────────
    if isinstance(result, str) and result:
        if result.startswith("http"):
            try:
                return _fetch(result)
            except Exception:
                pass
        else:
            try:
                return Image.open(result).convert("RGB")
            except Exception:
                pass

    # ── Raw bytes ─────────────────────────────────────────────────────────────
    if isinstance(result, (bytes, bytearray)):
        try:
            return Image.open(_io.BytesIO(result)).convert("RGB")
        except Exception:
            pass

    # Log what we got so the terminal shows the actual type for debugging
    logger.warning(
        "hf_result_unrecognized",
        result_type=type(result).__name__,
        result_repr=repr(result)[:400],
    )
    return None


def _fetch(url: str) -> Image.Image:
    r = httpx.get(url, timeout=120, follow_redirects=True)
    r.raise_for_status()
    return Image.open(_io.BytesIO(r.content)).convert("RGB")


# ── Space-specific predict functions ──────────────────────────────────────────

def _log_api(client, space: str) -> None:
    """Log available endpoints for debugging."""
    try:
        info = client.view_api(return_format="dict") or {}
        eps  = list(info.get("named_endpoints", {}).keys())
        logger.info("space_endpoints", space=space, endpoints=eps)
    except Exception as exc:
        logger.warning("view_api_failed", space=space, error=str(exc))


def _predict_idm_vton(
    client, person_path: str, dress_path: str, cloth_type: str = "upper"
) -> Optional[Image.Image]:
    """yisol/IDM-VTON — image-editor dict input, /tryon endpoint."""
    from gradio_client import handle_file
    _log_api(client, "IDM-VTON")

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


def _predict_with_fallback(
    client,
    space_tag: str,
    input_variants: list,
    endpoint_names: list[str],
) -> Optional[Image.Image]:
    """Shared helper: try named endpoints, then no-name default."""
    for ep in endpoint_names:
        for inputs in input_variants:
            try:
                raw = client.predict(*inputs, api_name=ep)
                logger.info(f"{space_tag}_raw", ep=ep, raw_type=type(raw).__name__,
                            raw_repr=repr(raw)[:300])
                img = _image_from_result(raw)
                if img is not None:
                    return img
            except Exception as exc:
                logger.warning(f"{space_tag}_ep_failed", ep=ep, error=str(exc)[:100])

    # No named endpoints found or all failed — try without api_name
    for inputs in input_variants:
        try:
            raw = client.predict(*inputs)
            logger.info(f"{space_tag}_raw_default", raw_type=type(raw).__name__,
                        raw_repr=repr(raw)[:300])
            img = _image_from_result(raw)
            if img is not None:
                return img
        except Exception as exc:
            logger.warning(f"{space_tag}_default_failed", error=str(exc)[:100])

    return None


def _predict_ootd(
    client, person_path: str, dress_path: str, cloth_type: str = "upper"
) -> Optional[Image.Image]:
    """levihsu/OOTDiffusion."""
    from gradio_client import handle_file

    cat_map = {"upper": "upperbody", "lower": "lowerbody", "overall": "dress"}
    cat = cat_map.get(cloth_type, "upperbody")

    endpoint_names: list[str] = []
    try:
        info = client.view_api(return_format="dict") or {}
        endpoint_names = list(info.get("named_endpoints", {}).keys())
    except Exception:
        pass

    pf, df = handle_file(person_path), handle_file(dress_path)
    variants = [
        [pf, df, cat],
        [pf, df, cat, 20, 2.0, 42],
        [pf, df],
    ]
    return _predict_with_fallback(client, "ootd", variants, endpoint_names)


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

    pf, df = handle_file(person_path), handle_file(dress_path)
    variants = [
        [pf, df],
        [pf, df, cloth_type],
        [pf, df, cloth_type, 20, 2.5, 42],
    ]
    return _predict_with_fallback(client, "kolors", variants, endpoint_names)


def _predict_catvton(
    client, person_path: str, dress_path: str, cloth_type: str = "upper"
) -> Optional[Image.Image]:
    """zhengchong/CatVTON — discover endpoint, fall back to no-name call."""
    from gradio_client import handle_file

    endpoint_names: list[str] = []
    try:
        info = client.view_api(return_format="dict") or {}
        endpoint_names = list(info.get("named_endpoints", {}).keys())
        logger.info("catvton_endpoints", endpoints=endpoint_names)
    except Exception as e:
        logger.warning("catvton_view_api_failed", error=str(e))

    pf = handle_file(person_path)
    df = handle_file(dress_path)

    # CatVTON ONLY accepts these exact cloth_type values — no aliases
    valid_ct = cloth_type if cloth_type in ("upper", "lower", "overall") else "upper"

    # Endpoint discovered from logs: /submit_function_flux
    # Fallback to any other discovered endpoint, then no-name default
    preferred = ["/submit_function_flux"] + [
        ep for ep in endpoint_names if ep != "/submit_function_flux"
    ]
    if not preferred:
        preferred = endpoint_names or []

    input_variants = [
        (pf, df, valid_ct),
        (pf, df, valid_ct, 30, 2.5, 42),
        (pf, df, valid_ct, 50, 2.5, 42),
        (pf, df),
    ]

    for ep in preferred:
        for inputs in input_variants:
            try:
                raw = client.predict(*inputs, api_name=ep)
                logger.info("catvton_raw", ep=ep, raw_type=type(raw).__name__,
                            raw_repr=repr(raw)[:300])
                img = _image_from_result(raw)
                if img is not None:
                    logger.info("catvton_success", endpoint=ep)
                    return img
            except Exception as exc:
                logger.warning("catvton_ep_failed", ep=ep, error=str(exc)[:120])
                continue

    # Last resort — call without api_name (gradio picks the first function)
    for inputs in input_variants:
        try:
            raw = client.predict(*inputs)
            logger.info("catvton_raw_default", raw_type=type(raw).__name__,
                        raw_repr=repr(raw)[:300])
            img = _image_from_result(raw)
            if img is not None:
                logger.info("catvton_success_default")
                return img
        except Exception as exc:
            logger.warning("catvton_default_failed", error=str(exc)[:120])
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

    # gradio_client reads HF_TOKEN from env — set it before creating any Client
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token
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
                # Try passing token via headers (gradio_client >= 1.0)
                try:
                    auth_headers = (
                        {"Authorization": f"Bearer {hf_token}"}
                        if hf_token else {}
                    )
                    client = Client(space, headers=auth_headers)
                except TypeError:
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
