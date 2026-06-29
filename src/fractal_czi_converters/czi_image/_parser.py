"""Parse CZI image metadata into ``TiledImage``s.

A CZI file maps to one OME-Zarr image by default: every scene becomes a
positioned field of view, and every mosaic sub-tile (CZI ``M`` dimension) within
a scene becomes its own positioned tile. Placement is expressed in absolute
pixel coordinates taken from the CZI subblock directory;
``ome-zarr-converters-tools`` stitches the tiles. When ``split_scene`` is set
(or ``"auto"`` detects multi-scene tilescans), each scene becomes its own
OME-Zarr image instead - see :func:`_should_split`.

The module has two layers:

* a CZI scene-metadata layer (shared with the plate converter, in
  :mod:`fractal_czi_converters.common._czi_metadata`) that resolves each scene to
  a field-of-view name and rejects HCS plates - :func:`parse_single_acquisition`;
* a conversion layer that turns that mapping into ``ome-zarr-converters-tools``
  ``Tile`` / ``TiledImage`` models - :func:`parse_czi_image_metadata`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import czifile
from ome_zarr_converters_tools import (
    ConverterOptions,
    SingleImage,
    TiledImage,
)

from fractal_czi_converters.common._czi_metadata import (
    check_single_acquisition,
    find_scene_elements,
    parse_fov,
    well_label,
)
from fractal_czi_converters.common._tile_builders import (
    SceneConversionSpec,
    build_tiled_images,
)

if TYPE_CHECKING:
    from fractal_czi_converters.czi_image.convert_czi_image_init_task import (
        CziImageAcquisitionModel,
    )

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# CZI scene-metadata layer
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SingleSceneInfo:
    """Resolved metadata for a single scene of a single-acquisition file."""

    scene_key: int
    """The S-coordinate key, matching ``czifile.CziFile.scenes`` keys."""
    fov_name: str
    """Field-of-view name, e.g. ``"P1"``."""
    is_tilescan: bool = False
    """Whether the scene is a mosaic tilescan (more than one mosaic sub-tile)."""


@dataclass(frozen=True)
class SingleAcquisitionInfo:
    """Parsed metadata for a single-acquisition CZI file."""

    path: str
    """Path to the parsed CZI file."""
    scenes: dict[int, SingleSceneInfo]
    """Map of scene key to :class:`SingleSceneInfo`."""


def _mosaic_counts(entries: Any) -> dict[int, int]:
    """Return the number of distinct mosaic sub-tiles per scene index.

    Groups the subblock directory entries by ``scene_index`` and counts the
    distinct ``mosaic_index`` values. A scene with more than one is a tilescan.
    The ``-1`` key covers files without an explicit ``S`` dimension (a single
    unindexed scene). Mirrors the grouping used by
    :func:`fractal_czi_converters.common._tile_builders.scene_tile_bboxes`.
    """
    by_scene: dict[int, set[int]] = defaultdict(set)
    for entry in entries:
        by_scene[entry.scene_index].add(entry.mosaic_index)
    return {scene_index: len(indices) for scene_index, indices in by_scene.items()}


def parse_single_acquisition(path: str) -> SingleAcquisitionInfo:
    """Parse a single-acquisition CZI file into per-scene field-of-view info.

    Args:
        path: Path to the CZI file.

    Returns:
        A :class:`SingleAcquisitionInfo`.

    Raises:
        ValueError: If the file is an HCS acquisition (its scenes span more than
            one well; use the plate converter), or if the file contains multiple
            independent acquisitions.
    """
    with czifile.CziFile(path) as czi:
        check_single_acquisition(czi)
        scene_keys = sorted(czi.scenes.keys())
        scene_elements = find_scene_elements(czi)
        mosaic_counts = _mosaic_counts(czi.filtered_subblock_directory)

    xml_keys = set(scene_elements)
    if xml_keys and xml_keys != set(scene_keys):
        logger.warning(
            "Scene keys from XML %s do not match czifile scenes %s for %s.",
            sorted(xml_keys),
            scene_keys,
            path,
        )

    # A file is treated as an HCS plate only when its scenes span more than one
    # distinct well. A single well label (or none) is a regular single
    # acquisition: a region/position captured within one well still converts to
    # a single image.
    wells = {
        label
        for key in scene_keys
        if (elem := scene_elements.get(key)) is not None
        and (label := well_label(elem)) is not None
    }
    if len(wells) > 1:
        raise ValueError(
            f"{path} is an HCS (plate) acquisition spanning wells "
            f"{sorted(wells)}. Use the 'Convert CZI Plate to OME-Zarr' task."
        )

    scenes: dict[int, SingleSceneInfo] = {}
    for scene_key in scene_keys:
        elem = scene_elements.get(scene_key)
        fov_name = (
            parse_fov(elem, scene_key) if elem is not None else f"P{scene_key + 1}"
        )
        # Files without an explicit ``S`` dimension expose their tiles under the
        # ``-1`` scene index; fall back to it for the lone scene.
        mosaic_count = mosaic_counts.get(scene_key, mosaic_counts.get(-1, 1))
        scenes[scene_key] = SingleSceneInfo(
            scene_key=scene_key,
            fov_name=fov_name,
            is_tilescan=mosaic_count > 1,
        )

    return SingleAcquisitionInfo(path=path, scenes=scenes)


# --------------------------------------------------------------------------- #
# Conversion layer (ome-zarr-converters-tools models)
# --------------------------------------------------------------------------- #
def _should_split(
    mode: Literal["auto", "true", "false"], acq_info: SingleAcquisitionInfo
) -> bool:
    """Decide whether to emit one OME-Zarr image per scene.

    A single-scene file is always kept as one image (splitting would only rename
    it). ``"auto"`` splits a multi-scene file only when its scenes are tilescans.
    """
    if mode == "false" or len(acq_info.scenes) <= 1:
        return False
    if mode == "true":
        return True
    return any(info.is_tilescan for info in acq_info.scenes.values())


def _split_scene_specs(
    acq_info: SingleAcquisitionInfo, zarr_name: str
) -> list[SceneConversionSpec]:
    """One ``SingleImage`` per scene, named ``{zarr_name}_{fov_name}``.

    Names are de-duplicated by falling back to ``{zarr_name}_s{scene_key}`` when
    two scenes share a field-of-view label.
    """
    used: set[str] = set()
    specs: list[SceneConversionSpec] = []
    for key, info in acq_info.scenes.items():
        image_path = f"{zarr_name}_{info.fov_name}"
        if image_path in used:
            image_path = f"{zarr_name}_s{key}"
        used.add(image_path)
        specs.append(
            SceneConversionSpec(
                scene_key=key,
                fov_name=info.fov_name,
                collection=SingleImage(image_path=image_path),
            )
        )
    return specs


def parse_czi_image_metadata(
    *,
    acquisition_model: CziImageAcquisitionModel,
    converter_options: ConverterOptions,
) -> list[TiledImage]:
    """Parse a CZI file's scenes into one or more ``TiledImage``s.

    Every scene becomes a positioned field of view in a single OME-Zarr image,
    unless ``split_scene`` requests (or ``"auto"`` detects) one image per scene.
    """
    czi_path = acquisition_model.path
    zarr_name = acquisition_model.zarr_name or Path(czi_path).stem

    acq_info = parse_single_acquisition(czi_path)
    if _should_split(acquisition_model.split_scene, acq_info):
        scenes = _split_scene_specs(acq_info, zarr_name)
        logger.info(
            f"Converting {czi_path} as {len(scenes)} images "
            f"(one per scene: {sorted(acq_info.scenes)})"
        )
    else:
        collection = SingleImage(image_path=zarr_name)
        scenes = [
            SceneConversionSpec(
                scene_key=key, fov_name=info.fov_name, collection=collection
            )
            for key, info in acq_info.scenes.items()
        ]
        logger.info(
            f"Converting {czi_path} as single image '{zarr_name}' "
            f"(scenes: {sorted(acq_info.scenes)})"
        )

    return build_tiled_images(
        czi_path=czi_path,
        scenes=scenes,
        mosaic_mode=acquisition_model.mosaic_mode,
        converter_options=converter_options,
        filters=acquisition_model.advanced.filters,
    )
