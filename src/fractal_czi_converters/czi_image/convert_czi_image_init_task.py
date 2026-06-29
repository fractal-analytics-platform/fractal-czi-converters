"""Initialize the CZI image to OME-Zarr conversion task."""

import logging
from typing import Literal

from ome_zarr_converters_tools import (
    ConverterOptions,
    OverwriteMode,
)
from pydantic import validate_call

from fractal_czi_converters.common import BaseAcquisitionModel, run_convert_init
from fractal_czi_converters.czi_image._parser import parse_czi_image_metadata

logger = logging.getLogger("convert_czi_image_task")


default_converter_options = ConverterOptions()


class CziImageAcquisitionModel(BaseAcquisitionModel):
    """Acquisition input model for CZI image conversion.

    The whole CZI file is converted into a single OME-Zarr image: every scene
    becomes a positioned field of view inside that image.
    """

    zarr_name: str | None = None
    """
    Optional zarr output name override. None derives the name from the CZI
    file stem.
    """
    split_scene: Literal["auto", "true", "false"] = "auto"
    """
    Whether to split a multi-scene CZI file into one OME-Zarr image per scene:

    * "auto" (default): split only when the file has more than one scene and
      those scenes are tilescans (a scene made of several mosaic sub-tiles).
      Plain multi-position files stay merged into a single positioned image.
    * "true": always split, one OME-Zarr image per scene.
    * "false": never split; every scene becomes a field of view inside a single
      OME-Zarr image.

    When splitting, each image is named "{zarr_name}_{fov_name}".
    """


@validate_call
def convert_czi_image_init_task(
    *,
    # Fractal parameters
    zarr_dir: str,
    # Task parameters
    acquisitions: list[CziImageAcquisitionModel],
    converter_options: ConverterOptions = default_converter_options,
    overwrite: OverwriteMode = OverwriteMode.NO_OVERWRITE,
):
    """Initialize the task to convert a CZI file's scenes to an OME-Zarr image.

    Args:
        zarr_dir (str): Directory to store the Zarr files.
        acquisitions (list[CziImageAcquisitionModel]): List of raw
            acquisitions to convert to OME-Zarr.
        converter_options (ConverterOptions): Advanced converter options.
        overwrite (OverwriteMode): Overwrite mode for existing data.

    Returns:
        dict: ``{"parallelization_list": [...]}`` for the compute task.
    """
    return run_convert_init(
        zarr_dir=zarr_dir,
        acquisitions=acquisitions,
        parse_function=parse_czi_image_metadata,
        converter_options=converter_options,
        overwrite=overwrite,
        collection_type="SingleImage",
    )


if __name__ == "__main__":
    from fractal_task_tools.task_wrapper import run_fractal_task

    run_fractal_task(task_function=convert_czi_image_init_task, logger_name=logger.name)
