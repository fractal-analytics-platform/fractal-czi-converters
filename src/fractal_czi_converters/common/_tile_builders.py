"""Build ``ome-zarr-converters-tools`` tiles from CZI scenes.

Shared conversion layer for both the single-acquisition and the plate (HCS)
converters. Each scene becomes one or more positioned :class:`Tile`s; the
mosaic dimension (CZI ``M``) is handled per ``mosaic_mode``. Placement is
expressed in absolute pixel coordinates taken from the CZI subblock directory;
``ome-zarr-converters-tools`` stitches the tiles.

The only difference between the two converters at this layer is the ``collection``
passed in (``SingleImage`` vs ``ImageInPlate``); everything about mosaic handling,
ROI bounding boxes, ``_m{idx}`` suffixes and the ``Tile(...)`` construction lives
here so it is written once.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, cast

import czifile
from ome_zarr_converters_tools import (
    AcquisitionDetails,
    ConverterOptions,
    ImageInPlate,
    SingleImage,
    Tile,
    TiledImage,
    default_axes_builder,
    tiles_aggregation_pipeline,
)
from ome_zarr_converters_tools.models._acquisition import ChannelInfo

from fractal_czi_converters.common._loaders import CziSceneLoader

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SceneConversionSpec:
    """One scene to convert: its key, FOV name, and target collection."""

    scene_key: int
    """The S-coordinate key, matching ``czifile.CziFile.scenes`` keys."""
    fov_name: str
    """Field-of-view name for the scene, e.g. ``"P1"``."""
    collection: SingleImage | ImageInPlate
    """Output collection the scene's tiles belong to."""


def get_pixel_sizes(img: Any) -> tuple[float, float, float]:
    """Return (pixel_size_x_um, pixel_size_y_um, z_spacing_um) from CziImage."""
    mpp = img.mpp  # (x_um, y_um) or None
    if mpp is not None:
        px, py = mpp
    else:
        px, py = 1.0, 1.0

    coord_scales = img.coord_scales  # dim -> scale in meters
    pz = coord_scales.get("Z", 1e-6) * 1e6  # m -> um
    return px, py, pz


def _channel_wavelength_id(info: Any) -> str | None:
    """Derive a channel's ``wavelength_id`` from its CZI channel metadata.

    ``czifile`` exposes per-channel metadata as a dict keyed by the channel
    name (the same name used as the channel label). The excitation wavelength is
    used as the identifier for a fluorescence channel; transmitted-light
    channels (e.g. T-PMT) carry no wavelength, so this returns ``None`` and the
    label is used instead.
    """
    if not isinstance(info, dict):
        return None
    excitation = info.get("ExcitationWavelength")
    if excitation is None:
        return None
    # Excitation comes through as a float (e.g. 493.0); drop the trailing ".0".
    return f"{excitation:g}"


def build_acquisition_details(img: Any, *, is_time_series: bool) -> AcquisitionDetails:
    """Build AcquisitionDetails from a CziImage (pixel-space positioning).

    ``is_time_series`` is resolved at the file level so that every tile of a
    file shares identical axes (required by ``ome-zarr-converters-tools``),
    even when individual scenes have a single time point.
    """
    px, py, pz = get_pixel_sizes(img)
    if abs(px - py) > 1e-9:
        logger.warning(
            f"Pixel size x ({px}) and y ({py}) are not equal. "
            "Using x size for pixelsize."
        )

    channels = (
        [
            ChannelInfo(
                channel_label=name,
                wavelength_id=_channel_wavelength_id(info),
            )
            for name, info in img.channels.items()
        ]
        if img.channels
        else None
    )

    return AcquisitionDetails(
        pixelsize=px,
        z_spacing=pz,
        t_spacing=1.0,
        channels=channels,
        axes=default_axes_builder(is_time_series=is_time_series),
        start_x_coo="pixel",
        length_x_coo="pixel",
        start_y_coo="pixel",
        length_y_coo="pixel",
        start_z_coo="pixel",
        length_z_coo="pixel",
        start_t_coo="pixel",
        length_t_coo="pixel",
    )


def scene_tile_bboxes(
    entries: Any, scene_key: int
) -> list[tuple[int, tuple[int, int, int, int]]]:
    """Return ``(mosaic_index, (x, y, w, h))`` for each tile of a scene.

    Groups the scene's subblock directory entries by mosaic index and computes
    each tile's absolute-pixel bounding box. A scene without a mosaic dimension
    yields a single ``(-1, bbox)`` entry covering the whole scene.
    """
    by_mosaic: dict[int, list[Any]] = {}
    for entry in entries:
        if entry.scene_index not in (scene_key, -1):
            continue
        by_mosaic.setdefault(entry.mosaic_index, []).append(entry)

    bboxes: list[tuple[int, tuple[int, int, int, int]]] = []
    for mosaic_index in sorted(by_mosaic):
        x0 = y0 = None
        x1 = y1 = None
        for entry in by_mosaic[mosaic_index]:
            dims = entry.dims
            ix, iy = dims.index("X"), dims.index("Y")
            sx, sy = entry.start[ix], entry.start[iy]
            ex, ey = sx + entry.shape[ix], sy + entry.shape[iy]
            x0 = sx if x0 is None else min(x0, sx)
            y0 = sy if y0 is None else min(y0, sy)
            x1 = ex if x1 is None else max(x1, ex)
            y1 = ey if y1 is None else max(y1, ey)

        x0 = cast("int", x0)
        y0 = cast("int", y0)
        x1 = cast("int", x1)
        y1 = cast("int", y1)
        roi = (x0, y0, x1 - x0, y1 - y0)
        bboxes.append((mosaic_index, roi))
    return bboxes


def build_scene_tiles(
    *,
    czi: Any,
    entries: Any,
    czi_path: str,
    scene_key: int,
    fov_name: str,
    collection: SingleImage | ImageInPlate,
    acquisition_details: AcquisitionDetails,
    mosaic_mode: Literal["tiles", "assembled"],
) -> list[Tile]:
    """Build the positioned tiles for a single CZI scene.

    Args:
        czi: Open ``czifile.CziFile``.
        entries: ``czi.filtered_subblock_directory`` (passed in so it is read
            once per file by the caller).
        czi_path: Path to the CZI file (for the per-tile loaders).
        scene_key: The S-coordinate key of the scene.
        fov_name: Base field-of-view name for the scene. In ``"tiles"`` mode a
            real multi-tile mosaic appends ``_m{idx}`` to it.
        collection: The output collection (``SingleImage`` or ``ImageInPlate``)
            shared by every tile of the image.
        acquisition_details: Shared, file-level acquisition details.
        mosaic_mode: ``"tiles"`` (one FOV per mosaic sub-tile) or ``"assembled"``
            (one FOV per scene; ``czifile`` assembles the mosaic on read).
    """
    img = czi.scenes[scene_key]
    sizes = dict(img.sizes)

    # (fov_name, (x, y, w, h), mosaic_index) per tile to build for this scene.
    scene_tiles: list[tuple[str, tuple[int, int, int, int], int | None]]
    if mosaic_mode == "assembled":
        # One field of view per scene; czifile assembles any internal mosaic
        # when the scene is read (no per-tile selection).
        scene_tiles = [(fov_name, img.bbox, None)]
    else:
        # One field of view per mosaic sub-tile. Each loader reads only that
        # tile's own subblocks by mosaic index (not a spatial ROI, which would
        # fuse overlapping neighbours -- see CziSceneLoader). A scene with a
        # single tile (no real mosaic) keeps its plain FOV name and loads the
        # whole scene.
        scene_bboxes = scene_tile_bboxes(entries, scene_key)
        scene_tiles = []
        for mosaic_index, bbox in scene_bboxes:
            if len(scene_bboxes) > 1:
                scene_tiles.append((f"{fov_name}_m{mosaic_index}", bbox, mosaic_index))
            else:
                scene_tiles.append((fov_name, bbox, None))

    tiles: list[Tile] = []
    for tile_fov, (x, y, w, h), tile_mosaic_index in scene_tiles:
        tiles.append(
            Tile(
                fov_name=tile_fov,
                start_x=x,
                start_y=y,
                start_z=0,
                start_c=0,
                start_t=0,
                length_x=w,
                length_y=h,
                length_z=sizes.get("Z", 1),
                length_c=sizes.get("C", 1),
                length_t=sizes.get("T", 1),
                collection=collection,
                image_loader=CziSceneLoader(
                    file_path=czi_path,
                    scene_key=scene_key,
                    mosaic_index=tile_mosaic_index,
                ),
                acquisition_details=acquisition_details,
                attributes={},
            )
        )
    return tiles


def build_tiled_images(
    *,
    czi_path: str,
    scenes: list[SceneConversionSpec],
    mosaic_mode: Literal["tiles", "assembled"],
    converter_options: ConverterOptions,
    filters: Any,
) -> list[TiledImage]:
    """Build the ``TiledImage``s for one CZI file from resolved scene specs.

    Shared conversion driver for both converters: it opens the file once,
    resolves file-level axes (a file is a time series if any scene has more than
    one time point), builds every scene's positioned tiles via
    :func:`build_scene_tiles`, and runs the aggregation pipeline. The single and
    plate parsers differ only in how they produce ``scenes`` (one shared
    :class:`SingleImage` vs a per-scene :class:`ImageInPlate`).
    """
    tiles: list[Tile] = []
    with czifile.CziFile(czi_path) as czi:
        entries = czi.filtered_subblock_directory
        scene_keys = [spec.scene_key for spec in scenes]
        is_time_series = any(
            czi.scenes[key].sizes.get("T", 1) > 1 for key in scene_keys
        )
        ref_img = czi.scenes[scene_keys[0]]
        acquisition_details = build_acquisition_details(
            ref_img, is_time_series=is_time_series
        )

        for spec in scenes:
            tiles.extend(
                build_scene_tiles(
                    czi=czi,
                    entries=entries,
                    czi_path=czi_path,
                    scene_key=spec.scene_key,
                    fov_name=spec.fov_name,
                    collection=spec.collection,
                    acquisition_details=acquisition_details,
                    mosaic_mode=mosaic_mode,
                )
            )

    return tiles_aggregation_pipeline(
        tiles=tiles,
        converter_options=converter_options,
        filters=filters,
        validators=None,
        resource=None,
    )
