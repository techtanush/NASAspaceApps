#!/usr/bin/env python3
"""Deterministic placeholder surface imagery for the Mars and Moon globes.

These are stylised stand-ins, not measurements. They exist so the globe experience can be built and reviewed while real
global maps (for example NASA/USGS Mars and Moon mosaics) are supplied separately. The UI labels them as placeholders.
Noise is evaluated in 3-D from longitude/latitude so there is no seam at the antimeridian and no pinching at the poles.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parents[2] / "apps/web/public/globe"
WIDTH, HEIGHT = 2048, 1024


def sphere_points() -> np.ndarray:
    lon = (np.arange(WIDTH) + 0.5) / WIDTH * 2 * np.pi - np.pi
    lat = np.pi / 2 - (np.arange(HEIGHT) + 0.5) / HEIGHT * np.pi
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    return np.stack(
        [np.cos(lat_grid) * np.cos(lon_grid), np.cos(lat_grid) * np.sin(lon_grid), np.sin(lat_grid)], axis=-1
    )


def lattice_noise(points: np.ndarray, frequency: float, seed: int) -> np.ndarray:
    """Smooth value noise on the unit sphere (trilinear interpolation of a hashed integer lattice)."""
    scaled = points * frequency + seed * 17.13
    base = np.floor(scaled).astype(np.int64)
    fraction = scaled - base
    fade = fraction * fraction * (3 - 2 * fraction)

    def corner(dx: int, dy: int, dz: int) -> np.ndarray:
        x, y, z = base[..., 0] + dx, base[..., 1] + dy, base[..., 2] + dz
        hashed = (x * 374761393 + y * 668265263 + z * 2147483647 + seed * 1274126177) & 0xFFFFFFFF
        hashed = ((hashed ^ (hashed >> 13)) * 1274126177) & 0xFFFFFFFF
        return (hashed & 0xFFFF).astype(np.float64) / 65535.0

    fx, fy, fz = fade[..., 0], fade[..., 1], fade[..., 2]
    x00 = corner(0, 0, 0) * (1 - fx) + corner(1, 0, 0) * fx
    x10 = corner(0, 1, 0) * (1 - fx) + corner(1, 1, 0) * fx
    x01 = corner(0, 0, 1) * (1 - fx) + corner(1, 0, 1) * fx
    x11 = corner(0, 1, 1) * (1 - fx) + corner(1, 1, 1) * fx
    return (x00 * (1 - fy) + x10 * fy) * (1 - fz) + (x01 * (1 - fy) + x11 * fy) * fz


def fractal(points: np.ndarray, base_frequency: float, octaves: int, seed: int, gain: float = 0.5) -> np.ndarray:
    total = np.zeros(points.shape[:2])
    amplitude, norm = 1.0, 0.0
    for octave in range(octaves):
        total += amplitude * lattice_noise(points, base_frequency * 2**octave, seed + octave)
        norm += amplitude
        amplitude *= gain
    return total / norm


def craters(points: np.ndarray, count: int, seed: int, largest_deg: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    height = np.zeros(points.shape[:2])
    for _ in range(count):
        centre = rng.normal(size=3)
        centre /= np.linalg.norm(centre)
        radius = np.radians(largest_deg) * rng.pareto(2.2) ** 0.6 / 6 + np.radians(0.35)
        radius = min(radius, np.radians(largest_deg))
        angle = np.arccos(np.clip(points @ centre, -1, 1))
        near = angle < radius * 1.7
        if not near.any():
            continue
        r = angle[near] / radius
        profile = np.where(r < 1, -(1 - r**2) * 0.9, 0.0) + np.exp(-((r - 1.05) ** 2) / 0.02) * 0.45
        height[near] += profile * rng.uniform(0.5, 1.0) * min(1.0, radius / np.radians(2.0) + 0.25)
    return height


def to_image(rgb: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(rgb * 255, 0, 255).astype(np.uint8), "RGB")


def ramp(value: np.ndarray, stops: list[tuple[float, tuple[float, float, float]]]) -> np.ndarray:
    positions = np.array([stop[0] for stop in stops])
    channels = np.array([stop[1] for stop in stops])
    return np.stack([np.interp(value, positions, channels[:, i]) for i in range(3)], axis=-1)


def mars(points: np.ndarray) -> tuple[Image.Image, Image.Image]:
    macro = fractal(points, 1.6, 4, 11)
    detail = fractal(points, 9.0, 5, 23)
    rim = craters(points, 520, 5, 9.0)
    height = np.clip(0.55 * macro + 0.25 * detail + 0.28 * rim, 0, 1)
    albedo = fractal(points, 2.6, 4, 41)
    base = ramp(
        height,
        [
            (0.0, (0.20, 0.10, 0.07)),
            (0.35, (0.46, 0.22, 0.12)),
            (0.60, (0.69, 0.36, 0.20)),
            (0.85, (0.82, 0.55, 0.36)),
            (1.0, (0.90, 0.72, 0.55)),
        ],
    )
    dark_regions = np.clip((0.46 - albedo) * 3.2, 0, 1)[..., None]
    colour = base * (1 - 0.45 * dark_regions) * (0.88 + 0.24 * detail[..., None])
    latitude = np.arcsin(points[..., 2])
    cap = np.clip((np.abs(latitude) - np.radians(76) + (detail - 0.5) * 0.12) * 14, 0, 1)[..., None]
    colour = colour * (1 - cap) + np.array([0.93, 0.92, 0.9]) * cap
    return to_image(colour), to_image(np.repeat(height[..., None], 3, axis=-1))


def moon(points: np.ndarray) -> tuple[Image.Image, Image.Image]:
    macro = fractal(points, 1.3, 3, 71)
    detail = fractal(points, 11.0, 5, 83)
    rim = craters(points, 900, 9, 7.0)
    maria = np.clip((0.5 - fractal(points, 1.1, 3, 97)) * 4.0, 0, 1) * np.clip(macro * 1.6 - 0.3, 0, 1)
    height = np.clip(0.5 * macro + 0.2 * detail + 0.3 * rim - 0.18 * maria + 0.1, 0, 1)
    grey = 0.42 + 0.28 * detail + 0.22 * rim - 0.2 * maria
    grey = np.clip(grey, 0.08, 0.95)
    colour = np.stack([grey * 1.0, grey * 0.99, grey * 0.96], axis=-1)
    return to_image(colour), to_image(np.repeat(height[..., None], 3, axis=-1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    points = sphere_points()
    for name, build in (("mars", mars), ("moon", moon)):
        colour, relief = build(points)
        colour.save(OUT / f"{name}-placeholder.jpg", quality=84, optimize=True)
        relief.convert("L").save(OUT / f"{name}-relief.jpg", quality=80, optimize=True)
        print(f"wrote {name}-placeholder.jpg and {name}-relief.jpg")


if __name__ == "__main__":
    main()
