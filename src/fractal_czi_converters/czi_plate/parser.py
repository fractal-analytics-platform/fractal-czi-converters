"""Parse CZI plate (HCS) metadata into per-well ``TiledImage`` objects.

A plate CZI file holds scenes that belong to different wells. Each scene carries
a well label (``<ArrayName>`` or ``<Shape Name>``, e.g. ``"C4"``) from which the
row/column are resolved; scenes are grouped by well, and every scene becomes a
field of view inside its well's :class:`ImageInPlate`. Mosaic sub-tiles (CZI
``M``) are handled exactly as in the single-acquisition converter via the shared
:func:`fractal_czi_converters.common.tile_builders.build_scene_tiles`.

Multiple CZI files can be merged into one plate by passing several acquisitions
with the same ``plate_name`` and distinct ``acquisition_id`` values (4i-style
multi-round acquisitions).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import czifile
from ome_zarr_converters_tools import (
    ConverterOptions,
    ImageInPlate,
    TiledImage,
)

from fractal_czi_converters.common.czi_metadata import (
    check_single_acquisition,
    find_scene_elements,
    parse_well,
    well_label,
)
from fractal_czi_converters.common.tile_builders import (
    SceneConversionSpec,
    build_tiled_images,
)

if TYPE_CHECKING:
    from fractal_czi_converters.czi_plate.convert_czi_plate_init_task import (
        CziPlateAcquisitionModel,
    )

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlateSceneInfo:
    """Resolved metadata for one scene of a plate file."""

    scene_key: int
    """The S-coordinate key, matching ``czifile.CziFile.scenes`` keys."""
    row: str
    """Well row letter, e.g. ``"C"``."""
    column: int
    """Well column number, e.g. ``4``."""
    fov_name: str
    """Field-of-view name within the well, e.g. ``"P1"`` or ``"FOV_0"``."""


def _resolve_plate_scenes(path: str) -> list[PlateSceneInfo]:
    """Resolve every well scene of a plate CZI file.

    Scenes without a well label (region geometry / non-plate scenes) are
    discarded and logged. FOV names within a well use the scene ``Name`` when it
    is a real field-of-view label, falling back to ``FOV_{idx}`` when the scene
    ``Name`` is empty, the well label itself (some ``rgn`` files), or collides
    with an already-used name.

    Raises:
        ValueError: If the file contains multiple independent acquisitions, or
            if no scene carries a well label (not a plate).
    """
    with czifile.CziFile(path) as czi:
        check_single_acquisition(czi)
        scene_keys = sorted(czi.scenes.keys())
        scene_elements = find_scene_elements(czi)

    # Group scenes by well, preserving scene order for FOV assignment.
    wells: dict[tuple[str, int], list[tuple[int, str]]] = {}
    discarded: list[int] = []
    for scene_key in scene_keys:
        elem = scene_elements.get(scene_key)
        if elem is None:
            discarded.append(scene_key)
            continue
        well = parse_well(elem)
        if well is None:
            discarded.append(scene_key)
            continue
        label = well_label(elem)
        raw_name = (elem.get("Name") or "").strip()
        # The scene Name is a usable FOV label unless it is empty or simply
        # repeats the well label (seen in some "rgn" files).
        candidate = raw_name if raw_name and raw_name != label else ""
        wells.setdefault(well, []).append((scene_key, candidate))

    if not wells:
        raise ValueError(
            f"{path} carries no well labels; it is not an HCS plate. Use the "
            "'Convert CZI to OME-Zarr' (single-acquisition) task instead."
        )
    if discarded:
        logger.info(
            "Discarded %d non-well scene(s) from %s: %s",
            len(discarded),
            path,
            discarded,
        )

    scenes: list[PlateSceneInfo] = []
    for (row, column), entries in wells.items():
        used: set[str] = set()
        for idx, (scene_key, candidate) in enumerate(entries):
            if candidate and candidate not in used:
                fov_name = candidate
            else:
                fov_name = f"FOV_{idx}"
            used.add(fov_name)
            scenes.append(
                PlateSceneInfo(
                    scene_key=scene_key, row=row, column=column, fov_name=fov_name
                )
            )
    return scenes


def parse_czi_plate_metadata(
    *,
    acquisition_model: CziPlateAcquisitionModel,
    converter_options: ConverterOptions,
) -> list[TiledImage]:
    """Parse a CZI plate file into one ``TiledImage`` per well."""
    czi_path = acquisition_model.path
    plate_name = acquisition_model.plate_name or Path(czi_path).stem
    acquisition_id = acquisition_model.acquisition_id

    plate_scenes = _resolve_plate_scenes(czi_path)
    scenes = [
        SceneConversionSpec(
            scene_key=scene.scene_key,
            fov_name=scene.fov_name,
            collection=ImageInPlate(
                plate_name=plate_name,
                row=scene.row,
                column=scene.column,
                acquisition=acquisition_id,
            ),
        )
        for scene in plate_scenes
    ]

    wells = sorted({(s.row, s.column) for s in plate_scenes})
    logger.info(f"Converting {czi_path} as plate '{plate_name}' (wells: {wells})")
    return build_tiled_images(
        czi_path=czi_path,
        scenes=scenes,
        mosaic_mode=acquisition_model.mosaic_mode,
        converter_options=converter_options,
        filters=acquisition_model.advanced.filters,
    )
