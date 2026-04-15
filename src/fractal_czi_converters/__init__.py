"""A collection of fractal tasks to convert Zeiss CZI files to OME-Zarr"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fractal-czi-converters")
except PackageNotFoundError:
    __version__ = "uninstalled"
