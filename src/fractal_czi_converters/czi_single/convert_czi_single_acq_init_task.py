"""Initialize the CZI single-acquisition to OME-Zarr conversion task."""

import logging
from typing import Literal

from ome_zarr_converters_tools import (
    ConverterOptions,
    OverwriteMode,
    setup_images_for_conversion,
)
from pydantic import validate_call

from fractal_czi_converters.common import BaseAcquisitionModel, parse_acquisitions
from fractal_czi_converters.czi_single.parser import parse_czi_single_acq_metadata

logger = logging.getLogger("convert_czi_single_acq_task")


default_converter_options = ConverterOptions()


class CziSingleAcqAcquisitionModel(BaseAcquisitionModel):
    """Acquisition input model for CZI single-acquisition conversion.

    The whole CZI file is converted into a single OME-Zarr image: every scene
    becomes a positioned field of view inside that image.
    """

    zarr_name: str | None = None
    """
    Optional zarr output name override. None derives the name from the CZI
    file stem.
    """
    mosaic_mode: Literal["tiles", "assembled"] = "tiles"
    """
    How to handle a scene that is a mosaic (CZI "M" dimension):

    * "tiles" (default): each mosaic sub-tile becomes its own positioned
      field of view ("P1_m0", "P1_m1", ...) and "ome-zarr-converters-tools"
      stitches them.
    * "assembled": each scene is converted as a single field of view
      ("P1"); "czifile" assembles the mosaic when reading the scene.
    """


@validate_call
def convert_czi_single_acq_init_task(
    *,
    # Fractal parameters
    zarr_dir: str,
    # Task parameters
    acquisitions: list[CziSingleAcqAcquisitionModel],
    converter_options: ConverterOptions = default_converter_options,
    overwrite: OverwriteMode = OverwriteMode.NO_OVERWRITE,
):
    """Initialize the task to convert a CZI single-acquisition dataset to OME-Zarr.

    Args:
        zarr_dir (str): Directory to store the Zarr files.
        acquisitions (list[CziSingleAcqAcquisitionModel]): List of raw
            acquisitions to convert to OME-Zarr.
        converter_options (ConverterOptions): Advanced converter options.
        overwrite (OverwriteMode): Overwrite mode for existing data.
    """
    tiled_images = parse_acquisitions(
        parse_function=parse_czi_single_acq_metadata,
        acquisitions=acquisitions,
        converter_options=converter_options,
    )

    parallelization_list = setup_images_for_conversion(
        tiled_images=tiled_images,
        zarr_dir=zarr_dir,
        converter_options=converter_options,
        collection_type="SingleImage",
        overwrite_mode=overwrite,
        ngff_version=converter_options.omezarr_options.ngff_version,
    )
    logger.info(
        f"Prepared parallelization list with {len(parallelization_list)} items."
    )
    return {"parallelization_list": parallelization_list}


if __name__ == "__main__":
    from fractal_task_tools.task_wrapper import run_fractal_task

    run_fractal_task(
        task_function=convert_czi_single_acq_init_task, logger_name=logger.name
    )
