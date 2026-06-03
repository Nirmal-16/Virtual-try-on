"""
Lightweight PIL-only garment type classifier.

Finds the bounding box of non-background content and classifies the garment
as upper-body, lower-body, or full-body based on vertical position and span.

Classification map
------------------
"upper"   → shirt, kurta, blouse, jacket, coat, blazer (jacket only)
"lower"   → pants, jeans, skirt, lehenga-skirt, dhoti, palazzos
"overall" → suit, sherwani, saree, full lehenga, ball gown, dress, salwar-kameez
"""

from PIL import Image, ImageChops


def analyze_garment_type(image: Image.Image) -> str:
    """Return "upper", "lower", or "overall" for the given garment image."""

    # Work on a small thumbnail for speed (100 × 200 px)
    thumb = image.convert("RGBA").resize((100, 200), Image.LANCZOS)
    h = thumb.height

    r, g, b, a = thumb.split()

    # Mark pixels that are NOT near-white (these are "content" pixels)
    nr = r.point(lambda v: 255 if v < 235 else 0)
    ng = g.point(lambda v: 255 if v < 235 else 0)
    nb = b.point(lambda v: 255 if v < 235 else 0)
    # Mark pixels that are opaque (not transparent background)
    na = a.point(lambda v: 255 if v > 20 else 0)

    # A pixel is "content" if it is non-white in ANY channel AND visible
    content = ImageChops.lighter(ImageChops.lighter(nr, ng), nb)
    content = ImageChops.multiply(content, na)
    bbox = content.getbbox()

    # Fallback: JPEG images have no alpha → ignore alpha channel
    if not bbox:
        content = ImageChops.lighter(ImageChops.lighter(nr, ng), nb)
        bbox = content.getbbox()

    if not bbox:
        return "upper"  # can't determine — safe default

    left, top, right, bottom = bbox

    span   = (bottom - top) / h           # fraction of image height that has content
    center = (top + bottom) / (2 * h)     # 0 = top of image, 1 = bottom
    top_r  = top / h
    bot_r  = bottom / h

    # ── Full-body rules (checked first — most permissive) ─────────────────────
    # Rule 1: content spans more than 58% of the image height
    if span > 0.58:
        return "overall"

    # Rule 2: garment starts in the top quarter AND reaches the lower 80%
    if top_r < 0.25 and bot_r > 0.78:
        return "overall"

    # Rule 3: content is very wide (aspect ratio > 1.3) → likely a flared gown/lehenga
    content_w = right - left
    content_h = bottom - top
    if content_w > 0 and content_h > 0 and (content_w / content_h) > 1.3:
        return "overall"

    # ── Lower-body rules ─────────────────────────────────────────────────────
    # Content centre is below the mid-point, or garment starts in lower half
    if center > 0.55 or top_r > 0.42:
        return "lower"

    # ── Default: upper body ───────────────────────────────────────────────────
    return "upper"
