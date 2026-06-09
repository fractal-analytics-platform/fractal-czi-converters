"""Initialize the CZI single-acquisition to OME-Zarr conversion task."""

import logging

from ome_zarr_converters_tools import (
    ConverterOptions,
    OverwriteMode,
)
from pydantic import validate_call

from fractal_czi_converters.common import BaseAcquisitionModel, run_convert_init
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

    Returns:
        dict: ``{"parallelization_list": [...]}`` for the compute task.
    """
    return run_convert_init(
        zarr_dir=zarr_dir,
        acquisitions=acquisitions,
        parse_function=parse_czi_single_acq_metadata,
        converter_options=converter_options,
        overwrite=overwrite,
        collection_type="SingleImage",
    )


if __name__ == "__main__":
    from fractal_task_tools.task_wrapper import run_fractal_task

    run_fractal_task(
        task_function=convert_czi_single_acq_init_task, logger_name=logger.name
    )
