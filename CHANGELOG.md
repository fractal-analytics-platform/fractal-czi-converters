# Changelog

## [v0.1.1]

### Chores
- Align repository tooling with `ome-zarr-converters-tools`: adopt its `.pre-commit-config.yaml` (`validate-pyproject` v0.25, `crate-ci/typos`, `astral-sh/ruff-pre-commit` v0.15.17, `nbstripout`) with a per-repo `_typos.toml`, add a `chores` pixi task, bump GitHub Actions pins (`checkout` v7, `codecov-action` v7, `action-gh-release` v3, `setup-python` v6), and add a terse `CLAUDE.md`.

## [v0.1.0]

### Changed
- **Breaking**: renamed the `Convert CZI to OME-Zarr` task to **`Convert CZI Image to OME-Zarr`**; renamed the `czi_single` package to `czi_image`, `CziSingleAcqAcquisitionModel` to `CziImageAcquisitionModel`, and `convert_czi_single_acq_init_task` to `convert_czi_image_init_task`.

### Features
- Add **Convert CZI Image to OME-Zarr** task to convert the scenes of a Zeiss CZI file into a single OME-Zarr image.
- Add **Convert CZI Plate to OME-Zarr** task to convert multi-well plate CZI acquisitions into an OME-Zarr HCS plate, with support for merging multiple CZI files into one plate via shared plate name and distinct acquisition IDs.
- Support mosaic scenes (CZI `M` dimension) via the `mosaic_mode` option (`tiles` / `assembled`).
- Support condition tables to attach experimental metadata to plate wells.
- Add Python API functions (`convert_czi_image`, `convert_czi_plate`) for programmatic use outside Fractal.

### Chores
- Build on `ome-zarr-converters-tools>=0.10.0,<0.11.0`, `fractal-task-tools>=0.5.0,<0.6.0`, and `ngio>=0.5.8,<0.6.0`.
- Read CZI files with `czifile`.
- Add GitHub Actions CI (build, test, coverage, PyPI release) and MkDocs documentation.
- Remove the local `SingleImage` setup handler — built into `ome-zarr-converters-tools>=0.10.0`.

### Docs
- Add "How to Run the Converters" page and per-converter Python API sections.
