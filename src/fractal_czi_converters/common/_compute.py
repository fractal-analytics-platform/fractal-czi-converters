"""Shared body for the CZI compute tasks.

Both the single-image and the plate compute tasks convert one ``TiledImage`` to
OME-Zarr; they differ only in their ``collection_type``. This holds the common
work so the two task modules stay thin wrappers (kept as separate files because
``dev/task_list.py`` references each by path).
"""

import logging
import time

from ome_zarr_converters_tools import (
    ConvertParallelInitArgs,
    ImageInPlate,
    ImageListUpdateDict,
    SingleImage,
    generic_compute_task,
)

from fractal_czi_converters.common._loaders import CziSceneLoader

logger = logging.getLogger(__name__)


def run_czi_compute_task(
    *,
    zarr_url: str,
    init_args: ConvertParallelInitArgs,
    collection_type: type[SingleImage] | type[ImageInPlate],
) -> ImageListUpdateDict:
    """Convert one ``TiledImage`` to OME-Zarr, timing and logging the result."""
    timer = time.time()
    img_list_update = generic_compute_task(
        zarr_url=zarr_url,
        init_args=init_args,
        collection_type=collection_type,
        image_loader_type=CziSceneLoader,
    )
    zarr_output = img_list_update["image_list_updates"][0]["zarr_url"]
    run_time = time.time() - timer
    logger.info(f"Successfully converted: {zarr_output}, in {run_time:.2f}[s]")
    return img_list_update
