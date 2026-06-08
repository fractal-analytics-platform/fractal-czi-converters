"""Initialize the CZI plate (HCS) to OME-Zarr conversion task."""

import logging
from pathlib import Path
from typing import Literal

from ome_zarr_converters_tools import (
    ConverterOptions,
    OverwriteMode,
    setup_images_for_conversion,
)
from pydantic import Field, validate_call

from fractal_czi_converters.common import BaseAcquisitionModel, parse_acquisitions
from fractal_czi_converters.czi_plate.parser import parse_czi_plate_metadata

logger = logging.getLogger("convert_czi_plate_task")


default_converter_options = ConverterOptions()


class CziPlateAcquisitionModel(BaseAcquisitionModel):
    """Acquisition input model for CZI plate (HCS) conversion.

    Each CZI file's scenes are grouped by well to build an OME-Zarr plate. Pass
    several acquisitions with the same ``plate_name`` and distinct
    ``acquisition_id`` values to merge multiple files (e.g. 4i rounds) into one
    plate.
    """

    plate_name: str | None = None
    """
    Optional plate name override. None derives the name from the CZI file stem.
    Set the same value across acquisitions to merge them into one plate.
    """
    acquisition_id: int = Field(default=0, ge=0)
    """
    Acquisition identifier within the plate. Use distinct values to place
    multiple CZI files into the same plate as separate acquisition rounds.
    """
    mosaic_mode: Literal["tiles", "assembled"] = "tiles"
    """
    How to handle a scene that is a mosaic (CZI "M" dimension):

    * "tiles" (default): each mosaic sub-tile becomes its own positioned
      field of view ("P1_m0", "P1_m1", ...) and "ome-zarr-converters-tools"
      stitches them.
    * "assembled": each scene is converted as a single field of view;
      "czifile" assembles the mosaic when reading the scene.
    """

    @property
    def normalized_plate_name(self) -> str:
        """Return the explicit plate name, falling back to the CZI file stem."""
        if self.plate_name is not None:
            return self.plate_name
        return Path(self.path).stem


@validate_call
def convert_czi_plate_init_task(
    *,
    # Fractal parameters
    zarr_dir: str,
    # Task parameters
    acquisitions: list[CziPlateAcquisitionModel],
    converter_options: ConverterOptions = default_converter_options,
    overwrite: OverwriteMode = OverwriteMode.NO_OVERWRITE,
):
    """Initialize the task to convert a CZI plate (HCS) dataset to OME-Zarr.

    Args:
        zarr_dir (str): Directory to store the Zarr files.
        acquisitions (list[CziPlateAcquisitionModel]): List of raw acquisitions
            to convert to OME-Zarr.
        converter_options (ConverterOptions): Advanced converter options.
        overwrite (OverwriteMode): Overwrite mode for existing data.
    """
    tiled_images = parse_acquisitions(
        parse_function=parse_czi_plate_metadata,
        acquisitions=acquisitions,
        converter_options=converter_options,
    )

    parallelization_list = setup_images_for_conversion(
        tiled_images=tiled_images,
        zarr_dir=zarr_dir,
        converter_options=converter_options,
        collection_type="ImageInPlate",
        overwrite_mode=overwrite,
        ngff_version=converter_options.omezarr_options.ngff_version,
    )
    logger.info(
        f"Prepared parallelization list with {len(parallelization_list)} items."
    )
    return {"parallelization_list": parallelization_list}


if __name__ == "__main__":
    from fractal_task_tools.task_wrapper import run_fractal_task

    run_fractal_task(task_function=convert_czi_plate_init_task, logger_name=logger.name)
