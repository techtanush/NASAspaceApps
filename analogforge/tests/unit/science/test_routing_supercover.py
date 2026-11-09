"""DDA (solver) versus slab clipping (verifier): two different algorithms, one geometry."""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_routing_support import make_grid  # noqa: E402

from analogforge.science.routing.supercover import supercover  # noqa: E402
from analogforge.science.routing.verify import slab_cells, unsafe_cells  # noqa: E402

GRID = make_grid(np.zeros((40, 40)), cell_size_m=60.0)


def _dda(x0: float, y0: float, x1: float, y1: float) -> dict[tuple[int, int], float]:
    hits = supercover(
        x0, y0, x1, y1, cell_size_m=GRID.cell_size_m, origin_x_m=GRID.origin_x_m, origin_y_m=GRID.origin_y_m
    )
    merged: dict[tuple[int, int], float] = {}
    for h in hits:
        merged[(h.row, h.col)] = merged.get((h.row, h.col), 0.0) + h.length_m
    return merged


def _slab(x0: float, y0: float, x1: float, y1: float) -> dict[tuple[int, int], float]:
    return {(r, c): length for r, c, length in slab_cells(x0, y0, x1, y1, GRID)}


def test_orthogonal_neighbour_step_touches_two_cells_half_each() -> None:
    x0, y0 = GRID.center_xy(5, 5)
    x1, y1 = GRID.center_xy(5, 6)
    for cells in (_dda(x0, y0, x1, y1), _slab(x0, y0, x1, y1)):
        assert set(cells) == {(5, 5), (5, 6)}
        assert cells[(5, 5)] == pytest.approx(30.0) and cells[(5, 6)] == pytest.approx(30.0)


def test_diagonal_step_is_a_supercover_of_four_cells() -> None:
    x0, y0 = GRID.center_xy(5, 5)
    x1, y1 = GRID.center_xy(6, 6)
    for cells in (_dda(x0, y0, x1, y1), _slab(x0, y0, x1, y1)):
        assert set(cells) == {(5, 5), (6, 6), (5, 6), (6, 5)}
        assert cells[(5, 6)] == pytest.approx(0.0, abs=1e-9) and cells[(6, 5)] == pytest.approx(0.0, abs=1e-9)
        assert cells[(5, 5)] == pytest.approx(60.0 * math.sqrt(2) / 2)


def test_zero_length_segment_and_axis_aligned_boundary() -> None:
    x, y = GRID.center_xy(3, 3)
    assert set(_dda(x, y, x, y)) == {(3, 3)} == set(_slab(x, y, x, y))
    # a long axis-aligned segment crosses every cell of the row
    x0, y0 = GRID.center_xy(7, 0)
    x1, y1 = GRID.center_xy(7, 39)
    cells = _dda(x0, y0, x1, y1)
    assert len(cells) == 40 and sum(cells.values()) == pytest.approx(39 * 60.0)


@pytest.mark.parametrize("seed", range(6))
def test_dda_and_slab_agree_on_random_segments(seed: int) -> None:
    rng = random.Random(seed)  # noqa: S311 - seeded test data, not cryptography
    for _ in range(300):
        x0 = GRID.origin_x_m + rng.uniform(0.5, 39.5) * 60.0
        y0 = GRID.origin_y_m - rng.uniform(0.5, 39.5) * 60.0
        angle = rng.uniform(0, 2 * math.pi)
        length = rng.uniform(1.0, 600.0)
        x1, y1 = x0 + length * math.cos(angle), y0 + length * math.sin(angle)
        if not (GRID.origin_x_m < x1 < GRID.origin_x_m + 2400 and GRID.origin_y_m - 2400 < y1 < GRID.origin_y_m):
            continue
        a, b = _dda(x0, y0, x1, y1), _slab(x0, y0, x1, y1)
        positive_a = {k: v for k, v in a.items() if v > 1e-9}
        positive_b = {k: v for k, v in b.items() if v > 1e-9}
        assert positive_a.keys() == positive_b.keys()
        for key, value in positive_a.items():
            assert value == pytest.approx(positive_b[key], abs=1e-6)
        assert sum(positive_a.values()) == pytest.approx(length, abs=1e-6)  # lengths tile the segment


def test_all_eight_neighbour_directions_agree_everywhere() -> None:
    for row in range(1, 39):
        for col in range(1, 39, 7):
            for d_row, d_col in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
                x0, y0 = GRID.center_xy(row, col)
                x1, y1 = GRID.center_xy(row + d_row, col + d_col)
                a, b = _dda(x0, y0, x1, y1), _slab(x0, y0, x1, y1)
                assert a.keys() == b.keys()
                for key in a:
                    assert a[key] == pytest.approx(b[key], abs=1e-9)


def test_dilation_masks_agree_between_the_two_implementations() -> None:
    from scipy import ndimage

    rng = np.random.default_rng(3)
    valid = rng.random((30, 30)) > 0.08
    land = rng.random((30, 30)) > 0.04
    grid = make_grid(np.full((30, 30), 3.0), valid=valid, land=land)
    for dilation in (0.0, 59.0, 60.0, 61.0, 100.0, 180.0):
        ours = unsafe_cells(grid, dilation)
        bad = ~(valid & land)
        if dilation > 0 and bad.any():
            dist = ndimage.distance_transform_edt(~bad) * grid.cell_size_m
            expected = bad | (dist <= dilation + 1e-9)
        else:
            expected = bad
        assert (ours == expected).all(), dilation
