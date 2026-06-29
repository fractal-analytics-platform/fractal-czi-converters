"""Python API for the CZI plate (HCS) converter."""

from ome_zarr_converters_tools import (
    ConverterOptions,
    OverwriteMode,
    RunnerType,
    exec_compound_task,
)
from ome_zarr_converters_tools.fractal import ImageListUpdateDict

from fractal_czi_converters.common import image_in_plate_compute_task
from fractal_czi_converters.czi_plate.convert_czi_plate_init_task import (
    CziPlateAcquisitionModel,
    convert_czi_plate_init_task,
)


def convert_czi_plate(
    *,
    zarr_dir: str,
    acquisitions: list[CziPlateAcquisitionModel],
    converter_options: ConverterOptions | None = None,
    overwrite: OverwriteMode = OverwriteMode.NO_OVERWRITE,
    runner: RunnerType | None = None,
) -> list[ImageListUpdateDict]:
    """Convert a CZI plate (HCS) dataset to OME-Zarr.

    Args:
        zarr_dir: Directory to store the Zarr files.
        acquisitions: List of raw CZI acquisitions to convert to OME-Zarr.
        converter_options: Advanced converter options.
        overwrite: Overwrite mode for existing data.
        runner: Execution strategy for compute tasks (default: sequential).

    Returns:
        List of image list update dicts for the converted Zarr images.
    """
    converter_options = converter_options or ConverterOptions()
    init_task_kwargs = {
        "zarr_dir": zarr_dir,
        "acquisitions": acquisitions,
        "converter_options": converter_options,
        "overwrite": overwrite,
    }
    return exec_compound_task(
        init_task_fn=convert_czi_plate_init_task,
        compute_task_fn=image_in_plate_compute_task,
        init_task_kwargs=init_task_kwargs,
        runner=runner,
    )
