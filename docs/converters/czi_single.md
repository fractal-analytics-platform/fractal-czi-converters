# CZI Single Acquisition

Converts the scenes of a Zeiss CZI file into a single standalone OME-Zarr image (not a plate structure).

## Expected File Structure

The whole CZI file is converted into **one** OME-Zarr image. Every **scene** (the CZI `S` dimension) in the file becomes a positioned **field of view** inside that image:

```
Acquisition.czi
├── Scene "P1"   → FOV P1
├── Scene "P2"   → FOV P2
└── ...
```

The fields of view are placed according to their stage positions and assembled into a single image by `ome-zarr-converters-tools` (see [Tiling Mode](index.md#tiling-mode)).

### Mosaic Scenes

If a scene is itself a mosaic (the CZI `M` dimension), the sub-tiles are handled according to the [`Mosaic Mode`](index.md#mosaic-mode) option — either kept as separate, stitchable FOVs (`tiles`, the default, named `P1_m0`, `P1_m1`, ...) or pre-assembled by `czifile` into a single FOV (`assembled`).

## Metadata

The converter extracts the following from the CZI file:

- Scene name and stage positions (X, Y, Z)
- Channel names and IDs
- Pixel size (XY and Z spacing in micrometers)
- Timepoint indices
- Mosaic tile layout (for mosaic scenes)

## Task Parameters

| Field | Type | Default | Description |
|---|---|---|---|
| `Path` | `str` | *required* | Path to the `.czi` file. |
| `Zarr Name` | `str` or `null` | `null` | Custom name for the output OME-Zarr image. Defaults to the CZI file name. |
| `Mosaic Mode` | `str` | `"tiles"` | How to handle mosaic scenes: `tiles` or `assembled`. See [Converters Overview](index.md#mosaic-mode). |
| `Advanced` | `AcquisitionOptions` | `{}` | Advanced options: channel/pixel-size overrides, stage corrections, and filters. See [Converters Overview](index.md). |

!!! warning "Limitations"
    - This converter has been tested on a limited set of CZI acquisitions and may not handle all formats.
    - A CZI file must contain a single acquisition; files with multiple independent acquisitions are rejected.
