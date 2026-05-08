"""Tools to convert czi files to ome-zarr."""

import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
from bioio import BioImage
from ome_zarr_converters_tools import (
    AcquisitionDetails,
    AcquisitionOptions,
    ChannelInfo,
    ConverterOptions,
    SingleImage,
    Tile,
    TiledImage,
    tiles_aggregation_pipeline,
)
from ome_zarr_converters_tools.models._acquisition import DefaultColors
from ome_zarr_converters_tools.models._loader import ImageLoaderInterface
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Color cycle used when assigning default channel colors.
_DEFAULT_COLOR_CYCLE = [
    DefaultColors.blue,
    DefaultColors.green,
    DefaultColors.red,
    DefaultColors.cyan,
    DefaultColors.magenta,
    DefaultColors.yellow,
    DefaultColors.orange,
    DefaultColors.purple,
]


class CZIImageAcquisitionModel(BaseModel):
    """Model for Zeiss CZI single image acquisitions.

    Accepts a single .czi file or a folder of .czi files that do not
    follow a plate layout.
    """

    path: str
    """
    Path to the czi file, or a folder containing czi files.
    """
    image_name: str | None = None
    """
    Optional custom name for the output OME-Zarr image. If not provided,
    the name will be derived from the file or folder name.
    """
    advanced: AcquisitionOptions = Field(default_factory=AcquisitionOptions)
    """
    Advanced acquisition options.
    """

    @property
    def _sanitized_name(self) -> str:
        """Get the sanitized name from the path."""
        name = self.path.rstrip("/").split("/")[-1].split(".czi")[0]
        # Replace characters not allowed in Zarr names
        return re.sub(r"[^A-Za-z0-9\-_. ]", "_", name)

    @property
    def normalized_image_name(self) -> str:
        """Get the normalized image name."""
        if self.image_name is not None:
            return self.image_name
        return self._sanitized_name

    def get_zarr_name(self, czi_path: Path) -> str:
        """Get the sanitized zarr name for a czi file.

        For folders, appends the sanitized file stem to the image name.
        For single files, returns the image name directly.
        """
        if Path(self.path).is_dir():
            sanitized_stem = re.sub(r"[^A-Za-z0-9\-_. ]", "_", czi_path.stem)
            return self.normalized_image_name + "_" + sanitized_stem
        return self.normalized_image_name


class cziLoader(ImageLoaderInterface):
    """Custom loader for czi files."""

    file_path: str
    scene: int | None = None
    mosaic_tile: int | None = None

    def load_data(self, resource: Any = None) -> np.ndarray:
        """Load the tile data as a numpy array."""
        if resource is not None:
            path = f"{resource}/{self.file_path}"
        else:
            path = self.file_path

        img = BioImage(
            path,
            reconstruct_mosaic=False,
            include_subblock_metadata=True,
            use_aicspylibczi=True,
        )
        if self.scene is not None:
            img.set_scene(self.scene)

        data_xr = img.xarray_dask_data

        if "M" in data_xr.dims:
            data_xr = data_xr.isel(M=self.mosaic_tile)

        if not set(data_xr.dims).issubset(("T", "C", "Z", "Y", "X")):
            raise ValueError(
                f"Data can only have dimensions T, C, Z, Y, X. "
                f"Found: {data_xr.dims}"
            )
        if "Z" not in data_xr.dims:
            data_xr = data_xr.expand_dims(Z=1, axis=0)
        if "C" not in data_xr.dims:
            data_xr = data_xr.expand_dims(C=1, axis=0)
        if "T" not in data_xr.dims:
            data_xr = data_xr.expand_dims(T=1, axis=0)
        if data_xr.dims != ("T", "C", "Z", "Y", "X"):
            data_xr = data_xr.transpose("T", "C", "Z", "Y", "X")

        return data_xr.data.compute()


class _CZIMetadata(BaseModel):
    """Parsed metadata from a CZI file (single scene)."""

    shape_x: int
    shape_y: int
    shape_z: int
    shape_c: int
    shape_t: int
    acquisition_details: AcquisitionDetails
    positions: list[tuple[str, float, float, int | None]]
    """(fov_name, start_x_um, start_y_um, mosaic_tile_index)"""


def _parse_czi_metadata(
    czi_path: str | Path, scene_id: int = 0
) -> _CZIMetadata:
    """Parse metadata from a CZI file for a single scene.

    Args:
        czi_path: Path to the .czi file.
        scene_id: Scene index to parse.

    Returns:
        Parsed CZI metadata including shapes, acquisition details,
        and FOV positions.
    """
    img = BioImage(
        czi_path,
        reconstruct_mosaic=False,
        include_subblock_metadata=True,
        use_aicspylibczi=True,
    )
    img.set_scene(scene_id)

    shape_x = img.dims.X
    shape_y = img.dims.Y
    shape_z = img.dims.Z
    shape_c = img.dims.C
    shape_t = img.dims.T

    # Scale factors [um/px]
    scale_x = img.physical_pixel_sizes.X if img.physical_pixel_sizes.X else 1.0
    scale_y = img.physical_pixel_sizes.Y if img.physical_pixel_sizes.Y else 1.0
    scale_z = img.physical_pixel_sizes.Z if img.physical_pixel_sizes.Z else 1.0
    scale_t = img.time_interval if img.time_interval else 1.0

    # Build channel info with a simple color cycle
    channels = [
        ChannelInfo(
            channel_label=name,
            wavelength_id=None,
            colors=_DEFAULT_COLOR_CYCLE[i % len(_DEFAULT_COLOR_CYCLE)],
        )
        for i, name in enumerate(img.channel_names)
    ]

    acquisition_details = AcquisitionDetails(
        channels=channels,
        pixelsize=scale_x,
        z_spacing=scale_z,
        t_spacing=scale_t,
    )

    # Build per-FOV positions
    positions: list[tuple[str, float, float, int | None]] = []
    if "M" in img.dims.order:
        for m in range(img.dims.M):
            y_px, x_px = img.get_mosaic_tile_position(m, T=0, C=0, Z=0)
            start_x = x_px * scale_x
            start_y = y_px * scale_y
            positions.append((f"FOV_{m}", start_x, start_y, m))
    else:
        positions.append(("FOV_0", 0.0, 0.0, None))

    return _CZIMetadata(
        shape_x=shape_x,
        shape_y=shape_y,
        shape_z=shape_z,
        shape_c=shape_c,
        shape_t=shape_t,
        acquisition_details=acquisition_details,
        positions=positions,
    )


def _build_tiles(
    czi_path: str | Path,
    scene_id: int,
    collection: SingleImage,
    attributes: dict,
) -> list[Tile]:
    """Build tiles from a CZI file for a single scene."""
    meta = _parse_czi_metadata(czi_path, scene_id)

    return [
        Tile(
            fov_name=fov_name,
            start_x=start_x,
            start_y=start_y,
            start_z=0,
            length_x=meta.shape_x,
            length_y=meta.shape_y,
            length_z=meta.shape_z,
            length_c=meta.shape_c,
            length_t=meta.shape_t,
            attributes=attributes,
            collection=collection,
            image_loader=cziLoader(
                file_path=str(czi_path), scene=scene_id, mosaic_tile=m_idx
            ),
            acquisition_details=meta.acquisition_details,
        )
        for fov_name, start_x, start_y, m_idx in meta.positions
    ]


def _get_czi_files(path: str | Path) -> list[Path]:
    """Get list of czi files from a path.

    Args:
        path: Path to a single .czi file or a directory containing .czi files.

    Returns:
        Sorted list of czi file paths.
    """
    path = Path(path)
    if path.is_dir():
        paths = sorted(path.glob("*.czi"))
        if not paths:
            raise ValueError(f"No czi files found in directory {path}")
        return paths
    elif path.is_file():
        if path.suffix != ".czi":
            raise ValueError(f"File {path} is not a czi file")
        return [path]
    else:
        raise ValueError(f"Path {path} is neither a file nor a directory")


def parse_czi_image_acquisition(
    acquisition_model: CZIImageAcquisitionModel,
    converter_options: ConverterOptions,
) -> list[TiledImage]:
    """Parse czi image acquisition and return list of tiled images.

    Handles single .czi files and folders of .czi files (non-plate).
    Multi-scene CZI files are supported: each scene produces a separate
    OME-Zarr image.

    Args:
        acquisition_model: Acquisition input model containing path and options.
        converter_options: Converter options for tile processing.

    Returns:
        List of TiledImage objects ready for conversion.
    """
    czi_list = _get_czi_files(acquisition_model.path)

    all_tiles = []
    for czi_path in czi_list:
        img = BioImage(
            czi_path,
            reconstruct_mosaic=False,
            include_subblock_metadata=True,
            use_aicspylibczi=True,
        )
        num_scenes = len(img.scenes)

        for scene_id in range(num_scenes):
            zarr_name = acquisition_model.get_zarr_name(czi_path)
            if num_scenes > 1:
                zarr_name = f"{zarr_name}_scene{scene_id}"
            collection = SingleImage(image_path=zarr_name)

            tiles = _build_tiles(
                czi_path=czi_path,
                scene_id=scene_id,
                collection=collection,
                attributes={},
            )
            all_tiles.extend(tiles)

    logger.info(f"Built {len(all_tiles)} tiles")

    tiled_images = tiles_aggregation_pipeline(
        tiles=all_tiles,
        converter_options=converter_options,
        filters=acquisition_model.advanced.filters,
    )

    return tiled_images
