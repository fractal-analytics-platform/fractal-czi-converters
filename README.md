# Fractal CZI Converters

[![CI (build and test)](https://github.com/fractal-analytics-platform/fractal-czi-converters/actions/workflows/build_and_test.yml/badge.svg)](https://github.com/fractal-analytics-platform/fractal-czi-converters/actions/workflows/build_and_test.yml)
[![codecov](https://codecov.io/gh/fractal-analytics-platform/fractal-czi-converters/graph/badge.svg)](https://codecov.io/gh/fractal-analytics-platform/fractal-czi-converters)

A collection of [Fractal](https://fractal-analytics-platform.github.io/) tasks
to convert Zeiss `.czi` files into [OME-Zarr](https://ngff.openmicroscopy.org/)
format.

## Tasks

| Task | Use case |
|---|---|
| `Convert CZI Plate to OME-Zarr` | Convert one or more `.czi` files containing a multi-well plate acquisition into an OME-Zarr HCS plate. |
| `Convert CZI Image to OME-Zarr` | Convert the scenes of a `.czi` file into a single standalone OME-Zarr image. |

Each task is a Fractal **compound task**: an init step parses the `.czi`
metadata and builds the parallelization list, and a compute step writes the
image data well-by-well (or image-by-image).

## Installation

```bash
pip install fractal-czi-converters
```

## Part of the OME-Zarr converters ecosystem

This converter is a thin, format-specific layer built on
[`ome-zarr-converters-tools`](https://github.com/BioVisionCenter/ome-zarr-converters-tools),
the shared engine that handles tiling, image registration, and OME-Zarr writing for
the whole Fractal converter family. Because they all share that engine, every
converter offers the same options, behavior, and development workflow.

Sibling converters built on the same tooling:

- [`fractal-lif-converters`](https://github.com/fractal-analytics-platform/fractal-lif-converters) — Leica `.lif`
- [`fractal-nd2-converters`](https://github.com/fractal-analytics-platform/fractal-nd2-converters) — Nikon `.nd2`
- [`fractal-uzh-converters`](https://github.com/fractal-analytics-platform/fractal-uzh-converters) — HCS plates (Operetta, ScanR, CQ3K, CellVoyager, ImageXpress, custom TIFF)

## Documentation

Full documentation — including the supported file layouts, all converter
parameters, and the condition-table format — is available at
<https://fractal-analytics-platform.github.io/fractal-czi-converters/>.
