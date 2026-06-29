"""Regression tests for raw per-mosaic-tile loading.

``czi.scenes(scene=, roi=)`` assembles the mosaic (compositing overlapping
tiles, last-mosaic-index wins) and crops, so an ROI at a tile's bounding box
returns a *fused* crop whose seam contains the neighbouring tile's pixels.
``CziSceneLoader(mosaic_index=k)`` must instead return the genuine tile k data
(its own subblocks only), with no neighbour bleed in the overlap strip.
"""

import czifile
import numpy as np

from fractal_czi_converters.common._loaders import CziSceneLoader
from fractal_czi_converters.common._tile_builders import scene_tile_bboxes

from .utils import DATA_DIR

# Committed multi-mosaic file: one scene of four overlapping mosaic sub-tiles.
MOSAIC_CZI = DATA_DIR / "Zeiss-CZI" / "raw" / "img_4p2c1z1t_ManuallyDrawnRegion.czi"
SCENE = 0


def _raw_tile(czi, scene_key, mosaic_index):
    """Assemble a single mosaic tile straight from its subblocks (no ROI)."""
    entries = [
        e
        for e in czi.filtered_subblock_directory
        if e.pyramid_type == 0
        and e.scene_index in (scene_key, -1)
        and e.mosaic_index == mosaic_index
    ]
    dims = entries[0].dims
    xi, yi, ci = dims.index("X"), dims.index("Y"), dims.index("C")
    x0 = min(e.start[xi] for e in entries)
    y0 = min(e.start[yi] for e in entries)
    n_c = max(e.start[ci] for e in entries) + 1
    w = max(e.start[xi] + e.shape[xi] for e in entries) - x0
    h = max(e.start[yi] + e.shape[yi] for e in entries) - y0
    out = np.zeros((n_c, h, w), dtype=czi.scenes[scene_key].dtype)
    for e in entries:
        data = np.asarray(e.read_segment_data(czi).data(copy=False)).reshape(
            e.shape[yi], e.shape[xi]
        )
        out[
            e.start[ci],
            e.start[yi] - y0 : e.start[yi] - y0 + e.shape[yi],
            e.start[xi] - x0 : e.start[xi] - x0 + e.shape[xi],
        ] = data
    return out  # (C, Y, X)


def test_mosaic_tile_is_raw_not_fused():
    """Tile 0 must equal its own subblocks, not the fused ROI crop."""
    with czifile.CziFile(str(MOSAIC_CZI)) as czi:
        bboxes = scene_tile_bboxes(czi.filtered_subblock_directory, scene_key=SCENE)
        (mi0, bbox0), (mi1, bbox1) = bboxes[0], bboxes[1]

        raw0 = _raw_tile(czi, SCENE, mi0)  # (C, Y, X)
        raw1 = _raw_tile(czi, SCENE, mi1)
        fused = czi.scenes(scene=SCENE, roi=bbox0).asarray()  # (C, Y, X)

    # Loader output is canonical (C, Z, Y, X) with Z squeezed to 1.
    loaded = CziSceneLoader(
        file_path=str(MOSAIC_CZI), scene_key=SCENE, mosaic_index=mi0
    ).load_data()
    assert loaded.shape == (raw0.shape[0], 1, raw0.shape[1], raw0.shape[2])
    loaded_cyx = loaded[:, 0]

    # The loader returns the genuine tile, byte-for-byte.
    np.testing.assert_array_equal(loaded_cyx, raw0)

    # Overlap strip between tile 0 (y: y0..y0+h) and tile 1 (starts at bbox1.y).
    y0, h0 = bbox0[1], bbox0[3]
    overlap_lo = bbox1[1] - y0  # row in tile-0 coords where tile 1 begins
    overlap_hi = h0  # tile 0 extends to here
    assert 0 < overlap_lo < overlap_hi, "expected the tiles to overlap in Y"
    raw1_top = raw1[:, : overlap_hi - overlap_lo, :]

    # In the overlap the raw tile keeps tile-0 data; the fused crop shows tile 1.
    assert not np.array_equal(raw0[:, overlap_lo:overlap_hi], raw1_top), (
        "test precondition: tiles must differ in the overlap strip"
    )
    np.testing.assert_array_equal(
        fused[:, overlap_lo:overlap_hi], raw1_top
    )  # confirms the old ROI path bled the neighbour in
    assert not np.array_equal(
        loaded_cyx[:, overlap_lo:overlap_hi], fused[:, overlap_lo:overlap_hi]
    )


def test_mosaic_index_none_loads_full_scene():
    """``mosaic_index=None`` assembles the whole scene (unchanged behaviour)."""
    with czifile.CziFile(str(MOSAIC_CZI)) as czi:
        scene = czi.scenes[SCENE]
        _x0, _y0, w, h = scene.bbox

    loaded = CziSceneLoader(
        file_path=str(MOSAIC_CZI), scene_key=SCENE, mosaic_index=None
    ).load_data()
    assert loaded.shape[-2:] == (h, w)
