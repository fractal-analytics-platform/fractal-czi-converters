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
    """Loader for a scene (or a mosaic sub-tile of a scene) within a CZI file.

    Memory/performance note (mosaic tiles): when ``roi`` is set we load one
    mosaic tile via ``czifile``'s ROI crop. ``asarray`` allocates only an
    ROI-sized output array (the tile, not the whole scene), so memory stays
    bounded by the tile and the converter never holds all regions at once (the
    ``BY_FOV`` writer streams one tile at a time). However, ``czifile`` decodes
    *every* subblock of the scene and discards the ones outside the ROI only
    after decoding. Loading an N-tile mosaic therefore costs ~O(N^2) subblock
    decodes (CPU/IO, not memory). This is fine for the few-tiles-per-scene case
    we target; revisit (e.g. a subblock-targeted loader) if large mosaics
    become common.
    """

    file_path: str
    scene_key: int
    roi: tuple[int, int, int, int] | None = None
    """Absolute-pixel ``(x, y, width, height)`` crop, or ``None`` for the whole
    scene. Used to address an individual mosaic tile within a scene."""

    def load_data(self, resource: Any = None) -> np.ndarray:
        """Load the scene (or ROI crop) image data as a NumPy array."""
        with czifile.CziFile(self.file_path) as czi:
            img = czi.scenes(scene=self.scene_key, roi=self.roi)
            arr = img.asarray()
            dims = img.dims
        return _to_canonical_shape(arr, dims)

    def find_data_type(self, resource: Any = None) -> str:
        """Find the dtype of the image data without loading pixel data."""
        with czifile.CziFile(self.file_path) as czi:
            return str(czi.scenes[self.scene_key].dtype)
