"""Unit tests for the ``split_scene`` decision and naming helpers.

These exercise the split logic in isolation (no pixel data / CZI file needed),
which is the only way to cover the ``"auto"`` tilescan branch: the committed
fixtures have no multi-scene tilescan file.
"""

import pytest
from ome_zarr_converters_tools import SingleImage

from fractal_czi_converters.czi_image._parser import (
    SingleAcquisitionInfo,
    SingleSceneInfo,
    _should_split,
    _split_scene_specs,
)


def _acq_info(scenes: dict[int, SingleSceneInfo]) -> SingleAcquisitionInfo:
    return SingleAcquisitionInfo(path="fake.czi", scenes=scenes)


def _scene(key: int, fov_name: str, *, is_tilescan: bool = False) -> SingleSceneInfo:
    return SingleSceneInfo(scene_key=key, fov_name=fov_name, is_tilescan=is_tilescan)


# (mode, scenes, expected_split)
_CASES = [
    # Single scene never splits, regardless of mode or tilescan-ness.
    ("auto", {0: _scene(0, "P1", is_tilescan=True)}, False),
    ("true", {0: _scene(0, "P1")}, False),
    ("false", {0: _scene(0, "P1", is_tilescan=True)}, False),
    # false never splits.
    ("false", {0: _scene(0, "P1", is_tilescan=True), 1: _scene(1, "P2")}, False),
    # true always splits a multi-scene file.
    ("true", {0: _scene(0, "P1"), 1: _scene(1, "P2")}, True),
    # auto: split multi-scene tilescans only.
    ("auto", {0: _scene(0, "P1"), 1: _scene(1, "P2")}, False),
    (
        "auto",
        {0: _scene(0, "P1", is_tilescan=True), 1: _scene(1, "P2")},
        True,
    ),
]


@pytest.mark.parametrize("mode, scenes, expected", _CASES)
def test_should_split(mode, scenes, expected):
    assert _should_split(mode, _acq_info(scenes)) is expected


def test_split_scene_specs_names_by_fov():
    acq = _acq_info({0: _scene(0, "TR1"), 1: _scene(1, "TR2")})
    specs = _split_scene_specs(acq, "myfile")
    paths = [spec.collection.image_path for spec in specs]
    assert paths == ["myfile_TR1", "myfile_TR2"]
    assert all(isinstance(s.collection, SingleImage) for s in specs)


def test_split_scene_specs_dedup_on_collision():
    # Two scenes share the same FOV label -> second falls back to scene key.
    acq = _acq_info({0: _scene(0, "P1"), 1: _scene(1, "P1")})
    specs = _split_scene_specs(acq, "myfile")
    paths = [spec.collection.image_path for spec in specs]
    assert paths == ["myfile_P1", "myfile_s1"]
    assert len(set(paths)) == 2
