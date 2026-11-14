"""Pure renderer factory consumed by the platform export service."""

from analogforge.ports.passport_renderer import PassportRenderer

from .renderer import DeterministicPassportRenderer


def create_passport_renderer() -> PassportRenderer:
    return DeterministicPassportRenderer()


__all__ = ["create_passport_renderer"]
