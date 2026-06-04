"""Virtual try-on service — mock, fal.ai, Replicate, HF Spaces, or local CatVTON."""

import asyncio
import base64
import io
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx
from PIL import Image

from app.services.image_service import ImageService
from app.storage.job_store import JobStoreBase
from app.utils.errors import TryOnError
from app.utils.garment_analyzer import analyze_garment_type
from app.utils.image_utils import pil_to_bytes, resize_for_model
from app.utils.logger import get_logger

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)

# Maps internal cloth_type → fal.ai fashn/tryon category
_FAL_CATEGORY = {
    "upper":   "tops",
    "lower":   "bottoms",
    "overall": "one-pieces",
}

# Maps internal cloth_type → CatVTON / HF Spaces cloth_type string
_HF_CLOTH_TYPE = {
    "upper":   "upper",
    "lower":   "lower",
    "overall": "overall",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_data_url(image: Image.Image, max_dim: int = 768) -> str:
    img = resize_for_model(image, max_dim)
    b64 = base64.b64encode(pil_to_bytes(img, fmt="PNG")).decode()
    return f"data:image/png;base64,{b64}"


def _image_from_url_sync(url: str) -> Image.Image:
    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


# ── Service ────────────────────────────────────────────────────────────────────

class TryOnService:
    def __init__(
        self,
        image_service: ImageService,
        job_store: JobStoreBase,
        model_id: str,
        device: str,
        hf_token: str,
        fal_api_key: str = "",
        fal_model: str = "fashn/tryon",
        replicate_api_token: str = "",
    ) -> None:
        self._image_service = image_service
        self._job_store = job_store
        self._model_id = model_id.lower()
        self._device = device
        self._hf_token = hf_token
        self._fal_api_key = fal_api_key
        self._fal_model = fal_model
        self._replicate_api_token = replicate_api_token
        self._pipeline: Optional[object] = None

        self._mock          = self._model_id == "mock"
        self._use_fal       = self._model_id == "fal"
        self._use_replicate = self._model_id == "replicate"
        self._use_hf_spaces = self._model_id == "hf_spaces"

    # ── Mock ──────────────────────────────────────────────────────────────────

    def _run_mock(
        self, person: Image.Image, dress: Image.Image, cloth_type: str = "upper"
    ) -> Image.Image:
        """Composite the dress onto the correct body region based on cloth_type."""
        w, h = person.size
        person_rgba = person.copy().convert("RGBA")

        # Region boundaries and maximum width per garment type
        if cloth_type == "lower":
            region_top = int(h * 0.50)
            region_h   = int(h * 0.46)
            max_w      = int(w * 0.68)
        elif cloth_type == "overall":
            region_top = int(h * 0.15)   # near shoulder
            region_h   = int(h * 0.83)   # all the way to feet
            max_w      = w               # full person width — ball gowns can be wide
        else:  # upper
            region_top = int(h * 0.30)
            region_h   = int(h * 0.48)
            max_w      = int(w * 0.72)

        # Scale dress: height first so the garment fills the region vertically.
        # Only shrink if it would exceed max_w.
        dress_aspect = dress.width / dress.height
        thumb_h = region_h
        thumb_w = int(thumb_h * dress_aspect)
        if thumb_w > max_w:
            thumb_w = max_w
            thumb_h = int(thumb_w / dress_aspect)

        thumb = dress.resize((thumb_w, thumb_h), Image.LANCZOS).convert("RGBA")

        x = (w - thumb_w) // 2
        y = region_top

        overlay = Image.new("RGBA", person_rgba.size, (0, 0, 0, 0))
        overlay.paste(thumb, (x, y))
        result = Image.alpha_composite(person_rgba, overlay)
        return result.convert("RGB")

    # ── fal.ai ────────────────────────────────────────────────────────────────

    async def _run_fal_tryon(
        self, person: Image.Image, dress: Image.Image, cloth_type: str = "upper"
    ) -> Image.Image:
        if not self._fal_api_key:
            raise TryOnError(
                "FLUX_API_KEY is required for fal.ai try-on (set CATVTON_MODEL_ID=fal)."
            )

        logger.info("fal_tryon_start", model=self._fal_model, cloth_type=cloth_type)

        person_url = _to_data_url(person, 768)
        dress_url  = _to_data_url(dress,  768)

        if "fashn" in self._fal_model:
            payload = {
                "model_image":        person_url,
                "garment_image":      dress_url,
                "category":           _FAL_CATEGORY.get(cloth_type, "tops"),
                "mode":               "quality",   # best accuracy
                "garment_photo_type": "auto",
                "nsfw_filter":        False,
                "num_samples":        1,
            }
        else:
            payload = {
                "human_image_url":   person_url,
                "garment_image_url": dress_url,
                "cloth_type":        _HF_CLOTH_TYPE.get(cloth_type, "upper body"),
            }

        headers = {
            "Authorization": f"Key {self._fal_api_key}",
            "Content-Type":  "application/json",
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"https://fal.run/{self._fal_model}",
                json=payload,
                headers=headers,
            )
            if resp.status_code != 200:
                raise TryOnError(
                    f"fal.ai try-on failed ({resp.status_code}): {resp.text[:400]}"
                )
            data = resp.json()

        try:
            if "images" in data:
                # v1.5+ response: {"images": [{"url": "..."}]}
                result_url: str = data["images"][0]["url"]
            elif "output" in data:
                # legacy response: {"output": [{"url": "..."}]}
                result_url = data["output"][0]["url"]
            elif "image" in data:
                # cat-vton response: {"image": {"url": "..."}}
                result_url = data["image"]["url"]
            else:
                raise TryOnError(f"Unexpected fal.ai response keys: {list(data.keys())}")
        except (KeyError, IndexError) as exc:
            raise TryOnError(f"Could not parse fal.ai response: {data}") from exc

        async with httpx.AsyncClient(timeout=60.0) as client:
            img_resp = await client.get(result_url, follow_redirects=True)
            img_resp.raise_for_status()

        result = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        logger.info("fal_tryon_done", model=self._fal_model)
        return result

    # ── Replicate ─────────────────────────────────────────────────────────────

    async def _run_replicate_tryon(
        self, person: Image.Image, dress: Image.Image, cloth_type: str = "upper"
    ) -> Image.Image:
        if not self._replicate_api_token:
            raise TryOnError(
                "REPLICATE_API_TOKEN is required (set CATVTON_MODEL_ID=replicate)."
            )

        logger.info("replicate_tryon_start", cloth_type=cloth_type)

        # Human-readable garment descriptions per type
        garment_desc = {
            "upper":   "Indian upper garment — shirt, kurta, blouse, or jacket",
            "lower":   "Indian lower garment — pants, skirt, or lehenga",
            "overall": "Indian full-body outfit — saree, lehenga, dress, or sherwani",
        }.get(cloth_type, "Indian wedding garment")

        person_url = _to_data_url(person, 768)
        dress_url  = _to_data_url(dress,  768)

        headers = {
            "Authorization": f"Token {self._replicate_api_token}",
            "Content-Type":  "application/json",
        }

        payload = {
            "version": "906425dbca90663ff5427624839572cc56ea7d380343d13e2a4c4b09d3f0c30f",
            "input": {
                "human_img":       person_url,
                "garm_img":        dress_url,
                "garment_des":     garment_desc,
                "is_checked":      True,
                "is_checked_crop": False,
                "denoise_steps":   30,
                "seed":            42,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.replicate.com/v1/predictions",
                json=payload,
                headers=headers,
            )
            if resp.status_code not in (200, 201):
                raise TryOnError(
                    f"Replicate prediction create failed ({resp.status_code}): {resp.text[:400]}"
                )
            prediction = resp.json()

        prediction_id = prediction["id"]
        poll_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        logger.info("replicate_polling", prediction_id=prediction_id)

        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(60):
                await asyncio.sleep(5)
                poll_resp = await client.get(poll_url, headers=headers)
                poll_resp.raise_for_status()
                result = poll_resp.json()
                state = result.get("status")
                if state == "succeeded":
                    break
                if state in ("failed", "canceled"):
                    raise TryOnError(
                        f"Replicate prediction {state}: {result.get('error', 'unknown')}"
                    )
            else:
                raise TryOnError("Replicate try-on timed out after 5 minutes.")

        output = result.get("output")
        if not output:
            raise TryOnError(f"Replicate returned empty output: {result}")

        result_url = output[0] if isinstance(output, list) else output
        async with httpx.AsyncClient(timeout=60.0) as client:
            img_resp = await client.get(result_url, follow_redirects=True)
            img_resp.raise_for_status()

        scene = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        logger.info("replicate_tryon_done")
        return scene

    # ── Local model (CatVTON via diffusers) ──────────────────────────────────

    def _load_pipeline(self) -> object:
        if self._pipeline is not None:
            return self._pipeline
        logger.info("catvton_loading", model=self._model_id)
        try:
            import torch

            try:
                from diffusers import CatVTONPipeline  # type: ignore[attr-defined]
                dtype = torch.float16 if self._device == "cuda" else torch.float32
                pipe = CatVTONPipeline.from_pretrained(
                    self._model_id,
                    torch_dtype=dtype,
                    token=self._hf_token or None,
                    use_safetensors=True,
                ).to(self._device)
            except (ImportError, AttributeError):
                logger.warning(
                    "CatVTONPipeline not found; falling back to StableDiffusionInpaintPipeline. "
                    "Upgrade to diffusers>=0.31 for native CatVTON support."
                )
                from diffusers import StableDiffusionInpaintPipeline
                dtype = torch.float16 if self._device == "cuda" else torch.float32
                pipe = StableDiffusionInpaintPipeline.from_pretrained(
                    "runwayml/stable-diffusion-inpainting",
                    torch_dtype=dtype,
                    token=self._hf_token or None,
                ).to(self._device)

            self._pipeline = pipe
            logger.info("catvton_loaded")
        except Exception as exc:
            raise TryOnError(
                f"Failed to load local model '{self._model_id}': {exc}\n"
                "Use Python 3.11/3.12 and install requirements-ml.txt."
            ) from exc
        return self._pipeline

    def _run_local_inference(
        self, person: Image.Image, dress: Image.Image, cloth_type: str = "upper"
    ) -> Image.Image:
        import torch

        pipe = self._load_pipeline()
        person_r = resize_for_model(person, 1024)
        dress_r  = resize_for_model(dress,  768)

        try:
            mask = Image.new("L", person_r.size, 255)
            result = pipe(  # type: ignore[operator]
                image=person_r,
                condition_image=dress_r,
                mask=mask,
                cloth_type=cloth_type,
                num_inference_steps=50,
                guidance_scale=2.5,
                generator=torch.Generator(device=self._device).manual_seed(42),
            ).images[0]
        except TypeError:
            mask = Image.new("L", person_r.size, 255)
            result = pipe(  # type: ignore[operator]
                prompt=f"person wearing {cloth_type} garment, photorealistic, full body",
                image=person_r,
                mask_image=mask,
                num_inference_steps=30,
                guidance_scale=7.5,
            ).images[0]
        return result

    # ── Background task entry point ───────────────────────────────────────────

    async def run_tryon(self, job_id: str) -> None:
        job = self._job_store.get(job_id)
        try:
            logger.info("tryon_start", job_id=job_id, mode=self._model_id)

            person = await self._image_service.load_image(job.person_image_path)  # type: ignore[arg-type]
            dress  = await self._image_service.load_image(job.dress_image_path)   # type: ignore[arg-type]

            # Auto-detect garment type from the dress image
            cloth_type = analyze_garment_type(dress)
            logger.info("garment_type_detected", job_id=job_id, cloth_type=cloth_type)

            if self._mock:
                loop = asyncio.get_event_loop()
                result_image: Image.Image = await loop.run_in_executor(
                    _executor, self._run_mock, person, dress, cloth_type
                )
            elif self._use_fal:
                result_image = await self._run_fal_tryon(person, dress, cloth_type)
            elif self._use_replicate:
                result_image = await self._run_replicate_tryon(person, dress, cloth_type)
            elif self._use_hf_spaces:
                from app.providers.hf_spaces_tryon_provider import run_hf_spaces_tryon
                result_image = await run_hf_spaces_tryon(
                    person, dress, self._hf_token or None, cloth_type
                )
            else:
                loop = asyncio.get_event_loop()
                result_image = await loop.run_in_executor(
                    _executor, self._run_local_inference, person, dress, cloth_type
                )

            saved_path = await self._image_service.save_output_image(
                job_id, "tryon_result.png", result_image
            )

            job.tryon_result_path = saved_path
            job.status = "tryon_done"
            job.touch()
            self._job_store.save(job)
            logger.info("tryon_done", job_id=job_id, cloth_type=cloth_type)

        except Exception as exc:
            logger.exception("tryon_failed", job_id=job_id, error=str(exc))
            job.mark_failed(str(exc))
            self._job_store.save(job)
