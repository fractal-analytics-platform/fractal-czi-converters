# Changelog

## [Unreleased]

### Features
- Add **Convert CZI to OME-Zarr** task to convert the scenes of a Zeiss CZI file into a single OME-Zarr image.
- Add **Convert CZI Plate to OME-Zarr** task to convert multi-well plate CZI acquisitions into an OME-Zarr HCS plate, with support for merging multiple CZI files into one plate via shared plate name and distinct acquisition IDs.
- Support mosaic scenes (CZI `M` dimension) via the `mosaic_mode` option (`tiles` / `assembled`).
- Support condition tables to attach experimental metadata to plate wells.

### Chores
- Build on `ome-zarr-converters-tools>=0.9,<0.10`, `fractal-task-tools>=0.5.0,<0.6.0`, and `ngio>=0.5.8,<0.6.0`.
- Read CZI files with `czifile`.
- Add GitHub Actions CI (build, test, coverage, PyPI release) and MkDocs documentation.
