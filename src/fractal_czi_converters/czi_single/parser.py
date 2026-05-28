"""Parse CZI single-acquisition metadata into ``TiledImage`` objects."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import czifile
from ome_zarr_converters_tools import (
    AcquisitionDetails,
    ConverterOptions,
    SingleImage,
    Tile,
    TiledImage,
    default_axes_builder,
    tiles_aggregation_pipeline,
)
from ome_zarr_converters_tools.models._acquisition import ChannelInfo

from fractal_czi_converters.common.loaders import CziSceneLoader

if TYPE_CHECKING:
    from fractal_czi_converters.czi_single.convert_czi_single_acq_init_task import (
        CziSingleAcqAcquisitionModel,
    )

logger = logging.getLogger(__name__)


def _parse_scene_names(czi: Any) -> dict[int, str]:
    """Extract scene names from CZI XML keyed by S-coordinate order.

    Maps the i-th scene element (0-based) to the i-th sorted S-coordinate.
    Returns an empty dict when no scene XML elements are found.
    """
    scene_keys = sorted(czi.scenes.keys())
    scene_elems = (
        czi.xml_element.findall(".//Scenes/Scene")
        if czi.xml_element is not None
        else []
    )
    names: dict[int, str] = {}
    for scene_key, elem in zip(scene_keys, scene_elems, strict=False):
        name = elem.get("Name", "").strip()
        if name:
            names[scene_key] = name
    return names


def _parse_stage_positions(czi: Any) -> dict[int, tuple[float, float]]:
    """Extract scene center positions (x, y) in µm keyed by S-coordinate order.

    Returns (0.0, 0.0) for scenes with no CenterPosition element.
    """
    scene_keys = sorted(czi.scenes.keys())
    scene_elems = (
        czi.xml_element.findall(".//Scenes/Scene")
        if czi.xml_element is not None
        else []
    )
    positions: dict[int, tuple[float, float]] = {}
    for scene_key, elem in zip(scene_keys, scene_elems, strict=False):
        cp = elem.findtext("CenterPosition")
        if cp:
            try:
                x, y = (float(v) for v in cp.split(","))
                positions[scene_key] = (x, y)
            except ValueError:
                positions[scene_key] = (0.0, 0.0)
        else:
            positions[scene_key] = (0.0, 0.0)
    return positions


def _derive_zarr_name(
    czi_stem: str, scene_key: int, scene_names: dict[int, str]
) -> str:
    """Derive zarr output name from file stem and scene metadata."""
    name = scene_names.get(scene_key, "").strip()
    if name:
        safe = name.replace(" ", "_").replace("/", "_")
        return f"{czi_stem}_{safe}"
    return f"{czi_stem}_Scene_{scene_key}"


def _get_pixel_sizes(img: Any) -> tuple[float, float, float]:
    """Return (pixel_size_x_um, pixel_size_y_um, z_spacing_um) from CziImage."""
    mpp = img.mpp  # (x_um, y_um) or None
    if mpp is not None:
        px, py = mpp
    else:
        px, py = 1.0, 1.0

    coord_scales = img.coord_scales  # dim → scale in meters
    pz = coord_scales.get("Z", 1e-6) * 1e6  # m → µm
    return px, py, pz


def _build_acquisition_details(img: Any) -> AcquisitionDetails:
    """Build AcquisitionDetails from a CziImage."""
    px, py, pz = _get_pixel_sizes(img)
    if abs(px - py) > 1e-9:
        logger.warning(
            f"Pixel size x ({px}) and y ({py}) are not equal. "
            "Using x size for pixelsize."
        )

    sizes = dict(img.sizes)
    shape_t = sizes.get("T", 1)

    channels = (
        [ChannelInfo(channel_label=name) for name in img.channels.keys()]
        if img.channels
        else None
    )

    return AcquisitionDetails(
        pixelsize=px,
        z_spacing=pz,
        t_spacing=1.0,
        channels=channels,
        axes=default_axes_builder(is_time_series=shape_t > 1),
        start_x_coo="world",
        length_x_coo="pixel",
        start_y_coo="world",
        length_y_coo="pixel",
        start_z_coo="pixel",
        length_z_coo="pixel",
        start_t_coo="pixel",
        length_t_coo="pixel",
    )


def _build_scene_tile(
    *,
    img: Any,
    scene_key: int,
    czi_path: str,
    zarr_name: str,
    stage_x_um: float,
    stage_y_um: float,
) -> Tile:
    """Build a single Tile for one CZI scene."""
    sizes = dict(img.sizes)
    shape_t = sizes.get("T", 1)
    shape_c = sizes.get("C", 1)
    shape_z = sizes.get("Z", 1)
    shape_y = sizes.get("Y", 1)
    shape_x = sizes.get("X", 1)

    loader = CziSceneLoader(file_path=czi_path, scene_key=scene_key)
    collection = SingleImage(image_path=zarr_name)
    acquisition_details = _build_acquisition_details(img)

    return Tile(
        fov_name="FOV_0",
        start_x=stage_x_um,
        start_y=stage_y_um,
        start_z=0,
        start_c=0,
        start_t=0,
        length_x=shape_x,
        length_y=shape_y,
        length_z=shape_z,
        length_c=shape_c,
        length_t=shape_t,
        collection=collection,
        image_loader=loader,
        acquisition_details=acquisition_details,
        attributes={},
    )


def parse_czi_single_acq_metadata(
    *,
    acquisition_model: CziSingleAcqAcquisitionModel,
    converter_options: ConverterOptions,
) -> list[TiledImage]:
    """Parse CZI single-acquisition metadata and return ``TiledImage`` objects."""
    czi_path = acquisition_model.path
    czi_stem = Path(czi_path).stem

    with czifile.CziFile(czi_path) as czi:
        all_scene_keys = list(czi.scenes.keys())
        scene_names = _parse_scene_names(czi)
        stage_positions = _parse_stage_positions(czi)

        if acquisition_model.scene_index is not None:
            if acquisition_model.scene_index not in czi.scenes:
                raise ValueError(
                    f"scene_index={acquisition_model.scene_index} not found in "
                    f"{czi_path}. Valid keys: {all_scene_keys}"
                )
            scene_keys_to_process = [acquisition_model.scene_index]
        else:
            scene_keys_to_process = all_scene_keys

        tiles: list[Tile] = []
        for scene_key in scene_keys_to_process:
            img = czi.scenes[scene_key]
            stage_x, stage_y = stage_positions.get(scene_key, (0.0, 0.0))

            if acquisition_model.zarr_name is not None:
                zarr_name = acquisition_model.zarr_name
            else:
                zarr_name = _derive_zarr_name(czi_stem, scene_key, scene_names)

            tile = _build_scene_tile(
                img=img,
                scene_key=scene_key,
                czi_path=czi_path,
                zarr_name=zarr_name,
                stage_x_um=stage_x,
                stage_y_um=stage_y,
            )
            tiles.append(tile)

    logger.info(
        f"Built {len(tiles)} tile(s) from {czi_path} (scenes: {scene_keys_to_process})"
    )

    return tiles_aggregation_pipeline(
        tiles=tiles,
        converter_options=converter_options,
        filters=acquisition_model.advanced.filters,
        validators=None,
        resource=None,
    )
