# CZI Plate

Converts a Zeiss CZI file (or several CZI files) containing a multi-well plate acquisition into an OME-Zarr HCS plate.

## Expected File Structure

A plate CZI file holds **scenes** (the CZI `S` dimension), each carrying a **well label** in its metadata (the `<ArrayName>` / `<Shape Name>` element, e.g. `"C4"`). The converter:

1. Resolves the row/column of each scene from its well label.
2. Groups scenes by well.
3. Turns every scene into a **field of view** inside its well's image.

```
Plate.czi
├── Scene "B2"   → well B2, FOV P1
├── Scene "B2"   → well B2, FOV P2
├── Scene "C4"   → well C4, FOV P1
└── ...
```

Scenes that do **not** carry a well label (e.g. region-geometry or non-plate scenes) are discarded and logged, so a mixed file still converts cleanly.

!!! info "Field-of-view names"
    The scene `Name` is used as the FOV label when it is a real field-of-view name. When the scene `Name` is empty, simply repeats the well label, or collides with an already-used name, the converter falls back to `FOV_{index}`.

### Mosaic Wells

If a well's scene is itself a mosaic (the CZI `M` dimension), the sub-tiles are handled according to the [`Mosaic Mode`](index.md#mosaic-mode) option — either kept as separate, stitchable FOVs (`tiles`, the default) or pre-assembled by `czifile` (`assembled`).

## Combining Multiple Acquisitions

To merge several CZI files into one plate (e.g. 4i / multiplexed rounds), pass multiple acquisition objects with the **same `Plate Name`** but **distinct `Acquisition Id`** values. Each file is added to the plate as a separate acquisition round.

## Metadata

The converter extracts the following from the CZI file:

- Well position (row and column) from the scene label
- Field-of-view index and stage positions (X, Y, Z)
- Channel names and IDs
- Pixel size (XY and Z spacing in micrometers)
- Timepoint indices
- Mosaic tile layout (for mosaic scenes)

## Task Parameters

| Field | Type | Default | Description |
|---|---|---|---|
| `Path` | `str` | *required* | Path to the `.czi` file. |
| `Plate Name` | `str` or `null` | `null` | Custom name for the output OME-Zarr plate. Defaults to the CZI file name. Use the same value across acquisitions to merge them into one plate. |
| `Acquisition Id` | `int` | `0` | Acquisition identifier for combining multiple acquisitions into a single plate. |
| `Mosaic Mode` | `str` | `"tiles"` | How to handle mosaic scenes: `tiles` or `assembled`. See [Converters Overview](index.md#mosaic-mode). |
| `Advanced` | `AcquisitionOptions` | `{}` | Advanced options: condition table, channel/pixel-size overrides, stage corrections, and filters. See [Converters Overview](index.md). |

!!! warning "Limitations"
    - This converter has been tested on a limited set of CZI acquisitions and may not handle all formats.
    - A CZI file must contain a single acquisition; files with multiple independent acquisitions are rejected.
    - A file with no well-labelled scenes is not a plate — use the [CZI Single Acquisition](czi_single.md) task instead.
