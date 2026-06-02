"""Abstract base class for scene generation providers."""

from abc import ABC, abstractmethod

from PIL import Image


class SceneProviderBase(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def generate(self, prompt: str, base_image: Image.Image) -> Image.Image:
        """Generate a scene image from a prompt and a base try-on image."""
        ...

    def validate_config(self) -> None:
        """Optional: called at construction to verify required credentials exist."""
