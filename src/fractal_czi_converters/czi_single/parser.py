"""Parse CZI single-acquisition metadata into a single ``TiledImage``.

Each CZI file maps to one OME-Zarr image. Every scene becomes a positioned
field of view, and every mosaic sub-tile (CZI ``M`` dimension) within a scene
becomes its own positioned tile. Placement is expressed in absolute pixel
coordinates taken from the CZI subblock directory; ``ome-zarr-converters-tools``
stitches the tiles.

The module has two layers:

* a CZI scene-metadata layer (shared with the plate converter, in
  :mod:`fractal_czi_converters.common.czi_metadata`) that resolves each scene to
  a field-of-view name and rejects HCS plates - :func:`parse_single_acquisition`;
* a conversion layer that turns that mapping into ``ome-zarr-converters-tools``
  ``Tile`` / ``TiledImage`` models - :func:`parse_czi_single_acq_metadata`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import czifile
from ome_zarr_converters_tools import (
    ConverterOptions,
    SingleImage,
    Tile,
    TiledImage,
    tiles_aggregation_pipeline,
)

from fractal_czi_converters.common.czi_metadata import (
    check_single_acquisition,
    find_scene_elements,
    parse_fov,
    well_label,
)
from fractal_czi_converters.common.tile_builders import (
    build_acquisition_details,
    build_scene_tiles,
)

if TYPE_CHECKING:
    from fractal_czi_converters.czi_single.convert_czi_single_acq_init_task import (
        CziSingleAcqAcquisitionModel,
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


@dataclass(frozen=True)
class SingleAcquisitionInfo:
    """Parsed metadata for a single-acquisition CZI file."""

    path: str
    """Path to the parsed CZI file."""
    scenes: dict[int, SingleSceneInfo]
    """Map of scene key to :class:`SingleSceneInfo`."""

    @property
    def scene_to_fov(self) -> dict[int, str]:
        """Map scene key to field-of-view name."""
        return {key: info.fov_name for key, info in self.scenes.items()}


def parse_single_acquisition(path: str) -> SingleAcquisitionInfo:
    """Parse a single-acquisition CZI file into per-scene field-of-view info.

    Args:
        path: Path to the CZI file.

    Returns:
        A :class:`SingleAcquisitionInfo`.

    Raises:
        NotImplementedError: If the file is an HCS acquisition (its scenes span
            more than one well). Use the plate converter for those files.
        ValueError: If the file contains multiple independent acquisitions.
    """
    with czifile.CziFile(path) as czi:
        check_single_acquisition(czi)
        scene_keys = sorted(czi.scenes.keys())
        scene_elements = find_scene_elements(czi)

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
        raise NotImplementedError(
            f"{path} is an HCS (plate) acquisition spanning wells "
            f"{sorted(wells)}. Use the 'Convert CZI Plate to OME-Zarr' task."
        )

    scenes: dict[int, SingleSceneInfo] = {}
    for scene_key in scene_keys:
        elem = scene_elements.get(scene_key)
        fov_name = (
            parse_fov(elem, scene_key) if elem is not None else f"P{scene_key + 1}"
        )
        scenes[scene_key] = SingleSceneInfo(scene_key=scene_key, fov_name=fov_name)

    return SingleAcquisitionInfo(path=path, scenes=scenes)


# --------------------------------------------------------------------------- #
# Conversion layer (ome-zarr-converters-tools models)
# --------------------------------------------------------------------------- #
def parse_czi_single_acq_metadata(
    *,
    acquisition_model: CziSingleAcqAcquisitionModel,
    converter_options: ConverterOptions,
) -> list[TiledImage]:
    """Parse a CZI single-acquisition file into a single ``TiledImage``."""
    czi_path = acquisition_model.path
    zarr_name = acquisition_model.zarr_name or Path(czi_path).stem
    collection = SingleImage(image_path=zarr_name)

    acq_info = parse_single_acquisition(czi_path)

    tiles: list[Tile] = []
    with czifile.CziFile(czi_path) as czi:
        entries = czi.filtered_subblock_directory
        # Resolve axes once at the file level: a file is a time series if any of
        # its scenes has more than one time point. All tiles must share axes.
        is_time_series = any(
            czi.scenes[key].sizes.get("T", 1) > 1 for key in acq_info.scenes
        )
        ref_img = czi.scenes[next(iter(acq_info.scenes))]
        acquisition_details = build_acquisition_details(
            ref_img, is_time_series=is_time_series
        )

        for scene_key, scene_info in acq_info.scenes.items():
            tiles.extend(
                build_scene_tiles(
                    czi=czi,
                    entries=entries,
                    czi_path=czi_path,
                    scene_key=scene_key,
                    fov_name=scene_info.fov_name,
                    collection=collection,
                    acquisition_details=acquisition_details,
                    mosaic_mode=acquisition_model.mosaic_mode,
                )
            )

    logger.info(
        f"Built {len(tiles)} tile(s) from {czi_path} "
        f"(scenes: {sorted(acq_info.scenes)})"
    )

    return tiles_aggregation_pipeline(
        tiles=tiles,
        converter_options=converter_options,
        filters=acquisition_model.advanced.filters,
        validators=None,
        resource=None,
    )
