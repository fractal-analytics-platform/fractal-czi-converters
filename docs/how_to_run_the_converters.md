# How to Run the Converters

In addition to running them as Fractal tasks, the converters in this package
are available as plain Python functions, so you can run them from a script or
notebook without a Fractal server.

## Installation

```bash
pip install fractal-czi-converters
```

## Importing the Converters

```python
from fractal_czi_converters import (
    CziImageAcquisitionModel,
    CziPlateAcquisitionModel,
    convert_czi_image,
    convert_czi_plate,
)
```

- `convert_czi_image` — converts a CZI file's scenes into a single OME-Zarr image. See [CZI Image](converters/czi_image.md).
- `convert_czi_plate` — converts one or more CZI files into an OME-Zarr HCS plate. See [CZI Plate](converters/czi_plate.md).

## Common Parameters

Both functions share the same signature shape:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `zarr_dir` | `str` | *required* | Directory where the output OME-Zarr will be created. |
| `acquisitions` | `list[CziImageAcquisitionModel \| CziPlateAcquisitionModel]` | *required* | List of acquisitions to convert. See [Converters Overview](converters/index.md#acquisition-parameters). |
| `converter_options` | `ConverterOptions \| None` | `None` | Advanced converter options (tiling, writer mode, OME-Zarr settings). `None` uses the defaults. See [Converters Overview](converters/index.md#converter-options). |
| `overwrite` | `OverwriteMode` | `OverwriteMode.NO_OVERWRITE` | What to do if the output already exists: `NO_OVERWRITE`, `OVERWRITE`, or `EXTEND`. |
| `runner` | `RunnerType \| None` | `None` | Execution strategy for the per-image/per-well compute step. `None` runs sequentially. |

Both functions return a list of image-list update dicts describing the
converted Zarr images, one per converted image (CZI Image) or well (CZI
Plate).

### Runners

By default, the compute step runs sequentially. To parallelize it, pass a
runner from `ome_zarr_converters_tools`:

```python
from ome_zarr_converters_tools import ThreadedRunner, MultiprocessingRunner

# Run the compute step in 4 threads
convert_czi_image(..., runner=ThreadedRunner(num_threads=4))

# Run the compute step in 4 processes
convert_czi_plate(..., runner=MultiprocessingRunner(num_processes=4))
```

## Example: Convert a CZI File to a Single OME-Zarr Image

```python
from fractal_czi_converters import CziImageAcquisitionModel, convert_czi_image

convert_czi_image(
    zarr_dir="/path/to/zarr_dir",
    acquisitions=[
        CziImageAcquisitionModel(path="/path/to/Acquisition.czi"),
    ],
)
```

## Example: Convert a CZI Plate to an OME-Zarr HCS Plate

```python
from fractal_czi_converters import CziPlateAcquisitionModel, convert_czi_plate

convert_czi_plate(
    zarr_dir="/path/to/zarr_dir",
    acquisitions=[
        CziPlateAcquisitionModel(path="/path/to/Plate.czi"),
    ],
)
```

## Example: Merge Multiple CZI Files Into One Plate

To merge several CZI files into a single OME-Zarr plate (e.g. 4i /
multiplexed rounds), pass multiple acquisitions with the same `plate_name`
and distinct `acquisition_id` values:

```python
from fractal_czi_converters import CziPlateAcquisitionModel, convert_czi_plate

convert_czi_plate(
    zarr_dir="/path/to/zarr_dir",
    acquisitions=[
        CziPlateAcquisitionModel(
            path="/path/to/Round1.czi",
            plate_name="merged_plate",
            acquisition_id=0,
        ),
        CziPlateAcquisitionModel(
            path="/path/to/Round2.czi",
            plate_name="merged_plate",
            acquisition_id=1,
        ),
    ],
)
```
