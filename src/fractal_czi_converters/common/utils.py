"""Common utilities for fractal CZI converters."""

import logging
from typing import Protocol

from ome_zarr_converters_tools import (
    AcquisitionOptions,
    ConverterOptions,
    TiledImage,
)
from pydantic import BaseModel, Field

logger = logging.getLogger("czi_converters_compute_task")


class BaseAcquisitionModel(BaseModel):
    """Base model for acquisitions."""

    path: str
    """Path to the acquisition CZI file."""
    advanced: AcquisitionOptions = Field(default_factory=AcquisitionOptions)
    """Advanced acquisition options."""


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
