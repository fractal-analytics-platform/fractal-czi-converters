"""Initialize the CZI single-acquisition to OME-Zarr conversion task."""

import logging

from ome_zarr_converters_tools import (
    ConverterOptions,
    OverwriteMode,
    setup_images_for_conversion,
)
from pydantic import model_validator, validate_call

from fractal_czi_converters.common import BaseAcquisitionModel, parse_acquisitions
from fractal_czi_converters.czi_single.parser import parse_czi_single_acq_metadata

logger = logging.getLogger("convert_czi_single_acq_task")


default_converter_options = ConverterOptions()


class CziSingleAcqAcquisitionModel(BaseAcquisitionModel):
    """Acquisition input model for CZI single-acquisition conversion.

    ``scene_index`` controls whether a single scene is converted (named mode)
    or every scene in the file is processed (wildcard mode).
    """

    scene_index: int | None = None
    """
    Optional S-coordinate of the scene to convert. If ``None``, all scenes
    in the CZI file are converted (wildcard mode).
    """
    zarr_name: str | None = None
    """
    Optional zarr output name override. ``None`` derives the name as
    ``{czi_stem}_{scene_name}`` or ``{czi_stem}_Scene_{scene_key}``.
    Cannot be used in wildcard mode (when ``scene_index`` is None).
    """

    @model_validator(mode="after")
    def _check_combo(self) -> "CziSingleAcqAcquisitionModel":
        if self.scene_index is None and self.zarr_name is not None:
            raise ValueError(
                "'zarr_name' can only be used when 'scene_index' is provided."
            )
        return self


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
