"""Parse CZI single-acquisition metadata into a single ``TiledImage``.

Each CZI file maps to one OME-Zarr image. Every scene becomes a positioned
field of view, and every mosaic sub-tile (CZI ``M`` dimension) within a scene
becomes its own positioned tile. Placement is expressed in absolute pixel
coordinates taken from the CZI subblock directory; ``ome-zarr-converters-tools``
stitches the tiles.

The module has two layers:

* a CZI scene-metadata layer (XML only, ``czifile`` + stdlib) that resolves each
  scene to a field-of-view name and rejects HCS plates -
  :func:`parse_single_acquisition`;
* a conversion layer that turns that mapping into ``ome-zarr-converters-tools``
  ``Tile`` / ``TiledImage`` models - :func:`parse_czi_single_acq_metadata`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

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
    import xml.etree.ElementTree as ET

    from fractal_czi_converters.czi_single.convert_czi_single_acq_init_task import (
        CziSingleAcqAcquisitionModel,
    )

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# CZI scene-metadata layer
#
# Reads the Zeiss CZI XML (via ``czifile``) and resolves each scene of a
# single-acquisition file to a field-of-view name. A scene carries a *well
# label* when it has a non-empty ``<ArrayName>`` or a ``<Shape>`` with a
# non-empty ``Name`` attribute; a file is treated as an HCS plate (out of scope)
# only when its scenes span more than one distinct well label. A bare
# ``<Shape>`` with ``RowIndex``/``ColumnIndex`` but an empty ``Name`` is region
# geometry (manually drawn / rectangle scenes), not a well.
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


def _well_label(elem: ET.Element) -> str | None:
    """Return the well label of a ``<Scene>`` element, or ``None``.

    The label is a non-empty ``<ArrayName>`` (e.g. ``"C4"``) or a ``<Shape>``
    with a non-empty ``Name`` attribute (the well label). A bare ``<Shape>``
    with ``RowIndex``/``ColumnIndex`` but an empty ``Name`` is region geometry
    (manually drawn / rectangle scenes) and is *not* a well.
    """
    array_name = (elem.findtext("ArrayName") or "").strip()
    if array_name:
        return array_name
    shape = elem.find("Shape")
    if shape is not None:
        name = (shape.get("Name") or "").strip()
        if name:
            return name
    return None


def _parse_fov(elem: ET.Element, scene_key: int) -> str:
    """Extract the field-of-view name from a ``<Scene>`` element."""
    name = (elem.get("Name") or "").strip()
    return name if name else f"P{scene_key + 1}"


def _check_single_acquisition(czi: Any) -> None:
    """Raise when the CZI encodes more than one independent acquisition.

    Multiple ``<ExperimentBlocks>`` or ``<AcquisitionBlock>`` elements indicate
    several independent acquisitions stored in one file, which this parser does
    not support (it would silently mix their scenes). A single acquisition with
    many positions keeps one acquisition block and is handled normally.
    """
    root = czi.xml_element
    if root is None:
        return
    for tag in ("ExperimentBlocks", "AcquisitionBlock"):
        count = len(list(root.iter(tag)))
        if count > 1:
            raise ValueError(
                f"CZI file contains {count} <{tag}> elements, indicating "
                "multiple independent acquisitions in a single file. This "
                "parser only supports single-acquisition files (with one or "
                "more positions/scenes)."
            )


def _find_scene_elements(czi: Any) -> dict[int, ET.Element]:
    """Map each ``<Scene>`` element to its scene key via the ``Index`` attribute.

    Falls back to document order when ``Index`` attributes are missing or
    duplicated.
    """
    root = czi.xml_element
    elements: list[ET.Element] = []
    if root is not None:
        for scenes in root.iter("Scenes"):
            elements.extend(scenes.findall("Scene"))

    by_index: dict[int, ET.Element] = {}
    for position, elem in enumerate(elements):
        index_text = elem.get("Index")
        try:
            key = int(index_text) if index_text is not None else position
        except ValueError:
            key = position
        if key in by_index:
            logger.warning(
                "Duplicate/ambiguous Scene Index %s; falling back to document "
                "order for scene-to-element mapping.",
                key,
            )
            return dict(enumerate(elements))
        by_index[key] = elem
    return by_index


def parse_single_acquisition(path: str) -> SingleAcquisitionInfo:
    """Parse a single-acquisition CZI file into per-scene field-of-view info.

    Args:
        path: Path to the CZI file.

    Returns:
        A :class:`SingleAcquisitionInfo`.

    Raises:
        NotImplementedError: If the file is an HCS acquisition (its scenes span
            more than one well). Plate support is out of scope.
        ValueError: If the file contains multiple independent acquisitions.
    """
    with czifile.CziFile(path) as czi:
        _check_single_acquisition(czi)
        scene_keys = sorted(czi.scenes.keys())
        scene_elements = _find_scene_elements(czi)

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
        and (label := _well_label(elem)) is not None
    }
    if len(wells) > 1:
        raise NotImplementedError(
            f"{path} is an HCS (plate) acquisition spanning wells "
            f"{sorted(wells)}. HCS plate conversion is not supported yet."
        )

    scenes: dict[int, SingleSceneInfo] = {}
    for scene_key in scene_keys:
        elem = scene_elements.get(scene_key)
        fov_name = (
            _parse_fov(elem, scene_key) if elem is not None else f"P{scene_key + 1}"
        )
        scenes[scene_key] = SingleSceneInfo(scene_key=scene_key, fov_name=fov_name)

    return SingleAcquisitionInfo(path=path, scenes=scenes)


# --------------------------------------------------------------------------- #
# Conversion layer (ome-zarr-converters-tools models)
# --------------------------------------------------------------------------- #
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


def _build_acquisition_details(img: Any, *, is_time_series: bool) -> AcquisitionDetails:
    """Build AcquisitionDetails from a CziImage (pixel-space positioning).

    ``is_time_series`` is resolved at the file level so that every tile of a
    file shares identical axes (required by ``ome-zarr-converters-tools``),
    even when individual scenes have a single time point.
    """
    px, py, pz = _get_pixel_sizes(img)
    if abs(px - py) > 1e-9:
        logger.warning(
            f"Pixel size x ({px}) and y ({py}) are not equal. "
            "Using x size for pixelsize."
        )

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


def _scene_tile_bboxes(
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
        acquisition_details = _build_acquisition_details(
            ref_img, is_time_series=is_time_series
        )

        for scene_key, scene_info in acq_info.scenes.items():
            img = czi.scenes[scene_key]
            sizes = dict(img.sizes)

            # (fov_name, (x, y, w, h), roi) per tile to build for this scene.
            scene_tiles: list[
                tuple[str, tuple[int, int, int, int], tuple[int, int, int, int] | None]
            ]
            if acquisition_model.mosaic_mode == "assembled":
                # One field of view per scene; czifile assembles any internal
                # mosaic when the scene is read (no ROI cropping).
                scene_tiles = [(scene_info.fov_name, img.bbox, None)]
            else:
                # One field of view per mosaic sub-tile. Each loader reads only
                # its ROI; see CziSceneLoader for the per-tile memory/decode
                # trade-off. A scene with a single tile (no real mosaic) keeps
                # its plain FOV name (``P1``, not ``P1_m0``) and loads the whole
                # scene (no ROI crop).
                scene_bboxes = _scene_tile_bboxes(entries, scene_key)
                scene_tiles = []
                for mosaic_index, bbox in scene_bboxes:
                    if len(scene_bboxes) > 1:
                        scene_tiles.append(
                            (f"{scene_info.fov_name}_m{mosaic_index}", bbox, bbox)
                        )
                    else:
                        scene_tiles.append((scene_info.fov_name, bbox, None))

            for fov_name, (x, y, w, h), roi in scene_tiles:
                tiles.append(
                    Tile(
                        fov_name=fov_name,
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
                            file_path=czi_path, scene_key=scene_key, roi=roi
                        ),
                        acquisition_details=acquisition_details,
                        attributes={},
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
