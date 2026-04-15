"""Convert Zeiss CZI single image datasets to OME-Zarr."""

import logging

from ome_zarr_converters_tools import (
    ConverterOptions,
    OverwriteMode,
)
from ome_zarr_converters_tools.fractal._init_task import (
    build_parallelization_list,
)
from pydantic import validate_call

from fractal_czi_converters.czi_utils import (
    CZIImageAcquisitionModel,
    parse_czi_image_acquisition,
)

logger = logging.getLogger("convert_czi_single_image_task")

default_converter_options = ConverterOptions()


@validate_call
def init_task_convert_czi_single_image(
    *,
    # Fractal parameters
    zarr_dir: str,
    # Task parameters
    acquisitions: list[CZIImageAcquisitionModel],
    converter_options: ConverterOptions = default_converter_options,
    overwrite: OverwriteMode = OverwriteMode.NO_OVERWRITE,
):
    """Initialize the task to convert Zeiss CZI images to OME-Zarr.

    Use this task for standalone CZI files or folders of CZI files that
    do not follow a plate layout.

    Args:
        zarr_dir (str): Directory to store the Zarr files.
        acquisitions (list[CZIImageAcquisitionModel]): List of image
            acquisitions to convert to OME-Zarr.
        converter_options (ConverterOptions): Advanced converter options.
        overwrite (OverwriteMode): Overwrite mode for existing data.
            - "No Overwrite": Do not overwrite existing data.
            - "Overwrite": Remove and replace existing data.
            - "Extend": Extend existing data without removing it.
            Default is "No Overwrite".
    """
    tiled_images = []
    for acq in acquisitions:
        _tiled_images = parse_czi_image_acquisition(
            acquisition_model=acq,
            converter_options=converter_options,
        )
        if not _tiled_images:
            logger.warning(f"No images found in {acq.path}")
            continue
        logger.info(
            f"Found {len(_tiled_images)} images in acquisition {acq.path}"
        )
        tiled_images.extend(_tiled_images)

    if not tiled_images:
        raise ValueError("No images found in any of the provided acquisitions.")

    logger.info(f"Total {len(tiled_images)} images found in all acquisitions.")

    parallelization_list = build_parallelization_list(
        tiled_images=tiled_images,
        zarr_dir=zarr_dir,
        converter_options=converter_options,
        overwrite_mode=overwrite,
    )
    logger.info(
        f"Prepared parallelization list with {len(parallelization_list)} items."
    )
    return {"parallelization_list": parallelization_list}


if __name__ == "__main__":
    from fractal_task_tools.task_wrapper import run_fractal_task

    run_fractal_task(
        task_function=init_task_convert_czi_single_image,
        logger_name=logger.name,
    )
