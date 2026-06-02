"""Stateless PIL helper functions for image processing."""

import io

from PIL import Image

from app.utils.errors import ValidationError


def bytes_to_pil(data: bytes) -> Image.Image:
    """Convert raw bytes to a PIL Image."""
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise ValidationError(f"Cannot decode image bytes: {exc}") from exc


def pil_to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    """Serialise a PIL Image to bytes in the given format."""
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


def resize_for_model(image: Image.Image, max_dim: int = 1024) -> Image.Image:
    """Resize image so neither dimension exceeds max_dim, preserving aspect ratio."""
    w, h = image.size
    if w <= max_dim and h <= max_dim:
        return image
    scale = min(max_dim / w, max_dim / h)
    new_w, new_h = int(w * scale), int(h * scale)
    return image.resize((new_w, new_h), Image.LANCZOS)


def validate_image_bytes(
    data: bytes,
    allowed_types: list[str],
    max_size_mb: float,
) -> None:
    """Raise ValidationError if data fails type or size checks."""
    size_mb = len(data) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValidationError(
            f"Image size {size_mb:.1f} MB exceeds the {max_size_mb} MB limit."
        )
    try:
        img = Image.open(io.BytesIO(data))
        mime = Image.MIME.get(img.format or "", "")
        if mime not in allowed_types:
            raise ValidationError(
                f"Unsupported image type '{mime}'. Allowed: {allowed_types}"
            )
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Could not read image: {exc}") from exc


def save_pil_to_path(image: Image.Image, path: str) -> None:
    """Save a PIL Image to an absolute filesystem path."""
    image.save(path, format="PNG")
