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
    """Loader for a scene (or one raw mosaic tile of a scene) within a CZI file.

    Why not an ``roi`` crop for mosaic tiles: ``czi.scenes(scene=, roi=)`` does
    *not* hand back the raw subblock at that location. It runs the full mosaic
    assembly (the same one a whole-scene read performs) and then crops to the
    ROI. Mosaic tiles are usually acquired with stage overlap, so in the overlap
    strips ``czifile`` composites neighbouring tiles with last-mosaic-index-wins
    overwrite. An ROI at a tile's bounding box therefore (a) pulls in the
    neighbouring tile's subblocks and (b) returns their pixels at the seam --
    i.e. a *fused* crop, not the genuine per-tile acquisition.

    To load a single tile faithfully we instead select that tile's own subblock
    directory entries (``mosaic_index``) and let ``czifile`` assemble just those.
    A single mosaic index's subblocks do not overlap each other, so there is no
    fusion ambiguity and no neighbour bleed. ``asarray`` allocates only a
    tile-sized output array, so memory stays bounded by the tile (the ``BY_FOV``
    writer streams one tile at a time).
    """

    file_path: str
    scene_key: int
    mosaic_index: int | None = None
    """CZI mosaic (``M``) index of the tile to load, or ``None`` for the whole
    scene (``czifile`` assembles any internal mosaic on read)."""

    def load_data(self, resource: Any = None) -> np.ndarray:
        """Load the scene (or a single raw mosaic tile) as a NumPy array."""
        with czifile.CziFile(self.file_path) as czi:
            if self.mosaic_index is None:
                img = czi.scenes(scene=self.scene_key)
            else:
                # Assemble only this tile's subblocks; bypasses the spatial-ROI
                # path that would fuse overlapping neighbours (see class docs).
                entries = tuple(
                    e
                    for e in czi.filtered_subblock_directory
                    if e.pyramid_type == 0
                    and e.scene_index in (self.scene_key, -1)
                    and e.mosaic_index == self.mosaic_index
                )
                if not entries:
                    raise ValueError(
                        f"No subblocks for scene {self.scene_key}, "
                        f"mosaic {self.mosaic_index} in {self.file_path}"
                    )
                img = czifile.CziImage(czi, entries)
            arr = img.asarray()
            dims = img.dims
        return _to_canonical_shape(arr, dims)

    def find_data_type(self, resource: Any = None) -> str:
        """Find the dtype of the image data without loading pixel data."""
        with czifile.CziFile(self.file_path) as czi:
            return str(czi.scenes[self.scene_key].dtype)
