"""Mock scene provider — no API keys required, works offline."""

from PIL import Image, ImageDraw, ImageFont

from app.providers.base import SceneProviderBase
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MockSceneProvider(SceneProviderBase):
    @property
    def name(self) -> str:
        return "mock"

    async def generate(self, prompt: str, base_image: Image.Image) -> Image.Image:
        logger.info("mock_scene_generate", size=base_image.size)

        w, h = base_image.size
        scene = Image.new("RGB", (w, h))

        # Draw a warm golden gradient background
        draw = ImageDraw.Draw(scene)
        for y in range(h):
            ratio = y / h
            r = int(180 + ratio * 60)
            g = int(120 + ratio * 40)
            b = int(40 + ratio * 20)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # Paste a thumbnail of the try-on image in the centre
        thumb_w, thumb_h = w // 2, h // 2
        thumb = base_image.resize((thumb_w, thumb_h), Image.LANCZOS)
        x_offset = (w - thumb_w) // 2
        y_offset = (h - thumb_h) // 2
        scene.paste(thumb, (x_offset, y_offset))

        # Overlay text label
        try:
            font = ImageFont.truetype("arial.ttf", max(14, w // 30))
        except (OSError, IOError):
            font = ImageFont.load_default()

        label = "Indian Wedding Scene (Mock)"
        draw.text((10, 10), label, fill=(255, 255, 200), font=font)

        logger.info("mock_scene_done")
        return scene
