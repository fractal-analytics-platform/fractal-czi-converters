"""Acquisition input models and the shared init-task driver.

Holds the acquisition models common to both converters and the helpers that turn
a list of acquisitions into a Fractal parallelization list. Used by the two
``convert_*_init_task`` entrypoints.
"""

import logging
from typing import Literal, Protocol

from ome_zarr_converters_tools import (
    AcquisitionOptions,
    ConverterOptions,
    OverwriteMode,
    TiledImage,
    setup_images_for_conversion,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BaseAcquisitionModel(BaseModel):
    """Base model for acquisitions."""

    path: str
    """Path to the acquisition CZI file."""
    advanced: AcquisitionOptions = Field(default_factory=AcquisitionOptions)
    """Advanced acquisition options."""
    mosaic_mode: Literal["tiles", "assembled"] = "tiles"
    """
    How to handle a scene that is a mosaic (CZI "M" dimension):

    * "tiles" (default): each mosaic sub-tile becomes its own positioned
      field of view ("P1_m0", "P1_m1", ...) and "ome-zarr-converters-tools"
      stitches them.
    * "assembled": each scene is converted as a single field of view ("P1");
      "czifile" assembles the mosaic when reading the scene.
    """


class ParserProtocol[T: BaseAcquisitionModel](Protocol):
    """Protocol for acquisition metadata parser."""

    def __call__(
        self,
        *,
        acquisition_model: T,
        converter_options: ConverterOptions,
    ) -> list[TiledImage]:
        """Parse the acquisition metadata and return tiled images."""
        ...


def parse_acquisitions[T: BaseAcquisitionModel](
    *,
    parse_function: ParserProtocol[T],
    acquisitions: list[T],
    converter_options: ConverterOptions,
) -> list[TiledImage]:
    """Parse the acquisitions metadata and return tiled images.

    Args:
        parse_function (Callable): Function to parse the acquisition metadata
            and return tiled images.
        acquisitions (list[T]): List of acquisition models.
        converter_options (ConverterOptions): Converter options.

    Returns:
        list[TiledImage]: List of tiled images.
    """
    if not acquisitions:
        raise ValueError("Acquisitions list is empty.")

    tiled_images = []
    for acq in acquisitions:
        _tiled_images = parse_function(
            acquisition_model=acq,
            converter_options=converter_options,
        )

        if not _tiled_images:
            logger.warning(f"No images found in {acq.path}")
            continue
        else:
            logger.info(f"Found {len(_tiled_images)} images in acquisition {acq.path}")
        tiled_images.extend(_tiled_images)

    if len(tiled_images) == 0:
        raise ValueError("No images found in any of the provided acquisitions.")
    logger.info(f"Total {len(tiled_images)} images found in all acquisitions.")
    return tiled_images


def run_convert_init[T: BaseAcquisitionModel](
    *,
    zarr_dir: str,
    acquisitions: list[T],
    parse_function: ParserProtocol[T],
    converter_options: ConverterOptions,
    overwrite: OverwriteMode,
    collection_type: Literal["SingleImage", "ImageInPlate"],
) -> dict:
    """Run an init task: parse acquisitions and build the parallelization list.

    Shared body of the single-acquisition and plate init tasks; they differ only
    in their ``parse_function`` and ``collection_type``.

    Returns:
        dict: ``{"parallelization_list": [...]}`` for the Fractal compute task.
    """
    tiled_images = parse_acquisitions(
        parse_function=parse_function,
        acquisitions=acquisitions,
        converter_options=converter_options,
    )

    parallelization_list = setup_images_for_conversion(
        tiled_images=tiled_images,
        zarr_dir=zarr_dir,
        converter_options=converter_options,
        collection_type=collection_type,
        overwrite_mode=overwrite,
        ngff_version=converter_options.omezarr_options.ngff_version,
    )
    logger.info(
        f"Prepared parallelization list with {len(parallelization_list)} items."
    )
    return {"parallelization_list": parallelization_list}
