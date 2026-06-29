"""Converter from CZI files (Zeiss Microscope) to OME-Zarr format."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fractal-czi-converters")
except PackageNotFoundError:
    __version__ = "uninstalled"

from fractal_czi_converters.czi_image import CziImageAcquisitionModel, convert_czi_image
from fractal_czi_converters.czi_plate import CziPlateAcquisitionModel, convert_czi_plate

__all__ = [
    "CziImageAcquisitionModel",
    "CziPlateAcquisitionModel",
    "convert_czi_image",
    "convert_czi_plate",
]
