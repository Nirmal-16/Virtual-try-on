"""Mock scene provider — draws an Indian wedding mandap entirely with PIL."""

import math

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.providers.base import SceneProviderBase
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Colour palette ─────────────────────────────────────────────────────────────
_MAROON       = (110, 15, 25)
_DEEP_RED     = (75, 8, 12)
_GOLD         = (212, 175, 55)
_LIGHT_GOLD   = (255, 215, 0)
_DARK_GOLD    = (155, 120, 20)
_ORANGE       = (255, 130, 0)
_MARIGOLD     = (255, 165, 0)
_YELLOW       = (255, 235, 80)
_CREAM        = (255, 245, 215)
_SILK_RED     = (185, 20, 35)
_SILK_GOLD    = (200, 160, 40)
_FLOOR        = (55, 8, 8)
_DIYA_BODY    = (190, 140, 50)
_FLAME_OUTER  = (255, 110, 0)
_FLAME_INNER  = (255, 230, 60)


class MockSceneProvider(SceneProviderBase):
    @property
    def name(self) -> str:
        return "mock"

    async def generate(self, prompt: str, base_image: Image.Image) -> Image.Image:
        logger.info("mock_scene_generate", size=base_image.size)
        w, h = base_image.size

        # 1. Build the mandap background
        scene = self._draw_mandap(w, h)

        # 2. Composite the try-on person image into the centre of the scene
        #    Scale it to fill ~55 % of width, bottom-anchored above the floor
        floor_h = max(h // 10, 40)
        person_w = int(w * 0.55)
        person_h = int(base_image.height * (person_w / base_image.width))
        max_person_h = h - floor_h - int(h * 0.12)  # leave space for canopy
        if person_h > max_person_h:
            person_h = max_person_h
            person_w = int(base_image.width * (person_h / base_image.height))

        person_resized = base_image.resize((person_w, person_h), Image.LANCZOS)
        x_person = (w - person_w) // 2
        y_person = h - floor_h - person_h
        scene.paste(person_resized, (x_person, y_person))

        # 3. Re-draw the border on top so it covers any person overflow
        draw = ImageDraw.Draw(scene)
        self._draw_border(draw, w, h)

        logger.info("mock_scene_done")
        return scene

    # ── Scene construction ─────────────────────────────────────────────────────

    def _draw_mandap(self, w: int, h: int) -> Image.Image:
        img = Image.new("RGB", (w, h), _DEEP_RED)
        draw = ImageDraw.Draw(img)

        self._draw_background(draw, w, h)
        self._draw_canopy(draw, w, h)
        self._draw_marigold_garland(draw, w, h)
        self._draw_arch(draw, w, h)
        self._draw_hanging_lights(draw, w, h)
        self._draw_pillars(draw, w, h)
        self._draw_floor_and_diyas(draw, w, h)
        self._draw_border(draw, w, h)

        return img

    def _draw_background(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """Radial-style maroon gradient from centre."""
        cx, cy = w // 2, h // 2
        for y in range(h):
            ratio = y / h
            r = int(_MAROON[0] - ratio * 35)
            g = int(_MAROON[1])
            b = int(_MAROON[2])
            draw.line([(0, y), (w, y)], fill=(max(r, 40), g, b))

    def _draw_canopy(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """Alternating gold and red draped-fabric triangles along the top."""
        canopy_drop = max(h // 9, 40)
        n_segments  = 12
        seg_w       = w // n_segments
        for i in range(n_segments + 1):
            x0   = i * seg_w
            x1   = x0 + seg_w
            xmid = x0 + seg_w // 2
            color = _SILK_GOLD if i % 2 == 0 else _SILK_RED
            draw.polygon([(x0, 0), (x1, 0), (xmid, canopy_drop)], fill=color)
            # Gold edge line on each segment
            draw.line([(x0, 0), (xmid, canopy_drop)], fill=_GOLD, width=2)
            draw.line([(x1, 0), (xmid, canopy_drop)], fill=_GOLD, width=2)

        # Horizontal gold trim at canopy base
        trim_y = canopy_drop
        draw.rectangle([0, trim_y, w, trim_y + 6], fill=_GOLD)
        draw.rectangle([0, trim_y + 8, w, trim_y + 11], fill=_LIGHT_GOLD)

    def _draw_marigold_garland(
        self, draw: ImageDraw.ImageDraw, w: int, h: int
    ) -> None:
        """Wavy marigold garland hanging below the canopy."""
        canopy_drop = max(h // 9, 40)
        base_y      = canopy_drop + 18
        for x in range(0, w + 10, 18):
            sway = int(12 * math.sin(x * math.pi / 55))
            cy   = base_y + sway
            # Outer petals
            draw.ellipse([x - 9, cy - 9, x + 9, cy + 9], fill=_ORANGE)
            # Inner petals
            draw.ellipse([x - 5, cy - 5, x + 5, cy + 5], fill=_MARIGOLD)
            # Centre dot
            draw.ellipse([x - 2, cy - 2, x + 2, cy + 2], fill=_YELLOW)

    def _draw_arch(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """Two curved marigold arches framing the scene."""
        pillar_w = max(w // 12, 18)
        arch_cx  = w // 2
        arch_cy  = int(h * 0.52)
        arch_rx  = w // 2 - pillar_w - 4
        arch_ry  = int(h * 0.38)

        for angle_deg in range(0, 181, 6):
            rad = math.radians(angle_deg)
            ax  = int(arch_cx - arch_rx * math.cos(rad))
            ay  = int(arch_cy - arch_ry * math.sin(rad))
            draw.ellipse([ax - 10, ay - 10, ax + 10, ay + 10], fill=_ORANGE)
            draw.ellipse([ax - 5,  ay - 5,  ax + 5,  ay + 5],  fill=_YELLOW)

        # Inner arch (slightly smaller, gold)
        inner_rx = arch_rx - 14
        inner_ry = arch_ry - 12
        for angle_deg in range(0, 181, 8):
            rad = math.radians(angle_deg)
            ax  = int(arch_cx - inner_rx * math.cos(rad))
            ay  = int(arch_cy - inner_ry * math.sin(rad))
            draw.ellipse([ax - 5, ay - 5, ax + 5, ay + 5], fill=_GOLD)

    def _draw_hanging_lights(
        self, draw: ImageDraw.ImageDraw, w: int, h: int
    ) -> None:
        """String lights hanging in a gentle catenary curve."""
        canopy_drop = max(h // 9, 40)
        anchor_y    = canopy_drop + 38
        spacing     = 32
        for x in range(0, w + spacing, spacing):
            sway = int(20 * math.sin(x * math.pi / (w / 4)))
            ly   = anchor_y + 30 + sway
            # Wire
            if x >= spacing:
                prev_sway = int(20 * math.sin((x - spacing) * math.pi / (w / 4)))
                prev_ly   = anchor_y + 30 + prev_sway
                draw.line(
                    [(x - spacing, prev_ly), (x, ly)],
                    fill=_DARK_GOLD, width=1,
                )
            # Bulb glow (outer ring)
            draw.ellipse([x - 6, ly - 6, x + 6, ly + 6], fill=_ORANGE)
            # Bulb centre
            draw.ellipse([x - 3, ly - 3, x + 3, ly + 3], fill=_YELLOW)

    def _draw_pillars(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """Gold ornamental pillars on both sides."""
        pw       = max(w // 12, 18)
        top_y    = int(h * 0.13)
        base_col = _DARK_GOLD
        trim_col = _GOLD
        hi_col   = _LIGHT_GOLD

        for x0, x1 in [(0, pw), (w - pw, w)]:
            # Pillar body
            draw.rectangle([x0, top_y, x1, h], fill=base_col)
            # Capital (top decorative block)
            draw.rectangle([x0, top_y, x1, top_y + 14], fill=trim_col)
            draw.rectangle([x0, top_y + 5, x1, top_y + 8], fill=hi_col)
            # Horizontal ring bands every ~10 % of height
            band_h = max(h // 10, 20)
            for band_y in range(top_y + 20, h, band_h):
                draw.rectangle([x0, band_y, x1, band_y + 6],  fill=trim_col)
                draw.rectangle([x0, band_y + 1, x1, band_y + 3], fill=hi_col)
            # Pillar base
            draw.rectangle([x0, h - 16, x1, h], fill=trim_col)

    def _draw_floor_and_diyas(
        self, draw: ImageDraw.ImageDraw, w: int, h: int
    ) -> None:
        """Decorative floor platform with a row of lit diyas."""
        pw      = max(w // 12, 18)
        floor_h = max(h // 10, 40)
        floor_y = h - floor_h

        # Floor slab
        draw.rectangle([0, floor_y, w, h], fill=_FLOOR)
        draw.rectangle([0, floor_y, w, floor_y + 6], fill=_DARK_GOLD)

        # Diyas (oil lamps) evenly spaced across the floor
        spacing = max((w - 2 * pw) // 14, 30)
        for dx in range(pw + spacing // 2, w - pw, spacing):
            dy_base = floor_y + 10
            # Clay bowl
            draw.ellipse([dx - 9, dy_base - 5, dx + 9, dy_base + 7],
                         fill=_DIYA_BODY)
            draw.ellipse([dx - 9, dy_base - 5, dx + 9, dy_base],
                         fill=(220, 165, 60))
            # Flame — outer
            draw.ellipse(
                [dx - 5, dy_base - 22, dx + 5, dy_base - 5],
                fill=_FLAME_OUTER,
            )
            # Flame — inner hot centre
            draw.ellipse(
                [dx - 2, dy_base - 20, dx + 2, dy_base - 9],
                fill=_FLAME_INNER,
            )

    def _draw_border(self, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
        """Double gold frame border."""
        draw.rectangle([0, 0, w - 1, h - 1], outline=_GOLD,       width=7)
        draw.rectangle([9, 9, w - 10, h - 10], outline=_LIGHT_GOLD, width=2)
