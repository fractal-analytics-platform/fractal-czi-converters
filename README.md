# CZI to OME-Zarr Converters

[![CI (build and test)](https://github.com/fractal-analytics-platform/fractal-czi-converters/actions/workflows/build_and_test.yml/badge.svg)](https://github.com/fractal-analytics-platform/fractal-czi-converters/actions/workflows/build_and_test.yml)
[![codecov](https://codecov.io/gh/fractal-analytics-platform/fractal-czi-converters/graph/badge.svg)](https://codecov.io/gh/fractal-analytics-platform/fractal-czi-converters)

A collection of [Fractal](https://fractal-analytics-platform.github.io/) tasks
to convert Zeiss `.czi` files into [OME-Zarr](https://ngff.openmicroscopy.org/)
format.

## Tasks

| Task | Use case |
|---|---|
| `Convert CZI Plate to OME-Zarr` | Convert one or more `.czi` files containing a multi-well plate acquisition into an OME-Zarr HCS plate. |
| `Convert CZI to OME-Zarr` | Convert the scenes of a `.czi` file into a single standalone OME-Zarr image. |

Each task is a Fractal **compound task**: an init step parses the `.czi`
metadata and builds the parallelization list, and a compute step writes the
image data well-by-well (or image-by-image).

## Installation

```bash
pip install fractal-czi-converters
```

## Documentation

Full documentation — including the supported file layouts, all converter
parameters, and the condition-table format — is available at
<https://fractal-analytics-platform.github.io/fractal-czi-converters/>.

## Development

This project uses [pixi](https://pixi.sh/) for environment management and
[pre-commit](https://pre-commit.com/) for linting/formatting with
[Ruff](https://docs.astral.sh/ruff/).

```bash
# Install the development environment
pip install -e ".[dev]"

# Install the pre-commit hooks
pre-commit install

# Run the test suite
pytest

# Regenerate the Fractal manifest after changing task signatures
fractal-manifest create --package fractal_czi_converters
```
