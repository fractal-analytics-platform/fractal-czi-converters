"""Compute task for plate-based (HCS) CZI acquisitions."""

import logging

from ome_zarr_converters_tools import (
    ConvertParallelInitArgs,
    ImageInPlate,
    ImageListUpdateDict,
)
from pydantic import validate_call

from fractal_czi_converters.common._compute import run_czi_compute_task

logger = logging.getLogger(__name__)


@validate_call
def image_in_plate_compute_task(
    *,
    # Fractal parameters
    zarr_url: str,
    init_args: ConvertParallelInitArgs,
) -> ImageListUpdateDict:
    """Convert one CZI ``TiledImage`` into an OME-Zarr image inside a plate.

    Args:
        zarr_url (str): URL to the OME-Zarr image to populate.
        init_args (ConvertParallelInitArgs): Arguments from the init task.

    Returns:
        ImageListUpdateDict: The Fractal image-list update for the new image.
    """
    return run_czi_compute_task(
        zarr_url=zarr_url, init_args=init_args, collection_type=ImageInPlate
    )


if __name__ == "__main__":
    from fractal_task_tools.task_wrapper import run_fractal_task

    run_fractal_task(task_function=image_in_plate_compute_task, logger_name=logger.name)
