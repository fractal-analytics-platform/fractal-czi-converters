"""CZI image loaders implementing the ImageLoaderInterface."""

from typing import Any

import czifile
import numpy as np
from ome_zarr_converters_tools.models._loader import ImageLoaderInterface

_CANONICAL = ("T", "C", "Z", "Y", "X")


def _to_canonical_shape(arr: np.ndarray, dims: tuple[str, ...]) -> np.ndarray:
    """Reshape arr from czifile native dims to (T?,C,Z,Y,X), squeezing T if 1."""
    current = list(dims)
    for i, dim in enumerate(_CANONICAL):
        if dim not in current:
            arr = np.expand_dims(arr, axis=i)
            current.insert(i, dim)
    if current != list(_CANONICAL):
        perm = [current.index(d) for d in _CANONICAL]
        arr = np.transpose(arr, perm)
    # arr is now (T, C, Z, Y, X); squeeze T when T=1
    if arr.shape[0] == 1:
        arr = arr[0]
    return arr


class CziSceneLoader(ImageLoaderInterface):
    """Loader for a single scene within a CZI file."""

    file_path: str
    scene_key: int

    def load_data(self, resource: Any = None) -> np.ndarray:
        """Load the scene image data as a NumPy array."""
        with czifile.CziFile(self.file_path) as czi:
            img = czi.scenes[self.scene_key]
            arr = img.asarray()
            dims = img.dims
        return _to_canonical_shape(arr, dims)

    def find_data_type(self, resource: Any = None) -> str:
        """Find the dtype of the image data without loading pixel data."""
        with czifile.CziFile(self.file_path) as czi:
            return str(czi.scenes[self.scene_key].dtype)
