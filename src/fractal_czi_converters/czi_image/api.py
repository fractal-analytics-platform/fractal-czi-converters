"""Python API for the CZI image converter."""

from ome_zarr_converters_tools import (
    ConverterOptions,
    OverwriteMode,
    RunnerType,
    exec_compound_task,
)
from ome_zarr_converters_tools.fractal import ImageListUpdateDict

from fractal_czi_converters.common import single_image_compute_task
from fractal_czi_converters.czi_image.convert_czi_image_init_task import (
    CziImageAcquisitionModel,
    convert_czi_image_init_task,
)


def convert_czi_image(
    *,
    zarr_dir: str,
    acquisitions: list[CziImageAcquisitionModel],
    converter_options: ConverterOptions | None = None,
    overwrite: OverwriteMode = OverwriteMode.NO_OVERWRITE,
    runner: RunnerType | None = None,
) -> list[ImageListUpdateDict]:
    """Convert a CZI file's scenes into a single OME-Zarr image.

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
        init_task_fn=convert_czi_image_init_task,
        compute_task_fn=single_image_compute_task,
        init_task_kwargs=init_task_kwargs,
        runner=runner,
    )
