import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import numpy as np
import yaml
from ngio import (
    OmeZarrContainer,
    open_ome_zarr_container,
    open_ome_zarr_plate,
)
from ome_zarr_converters_tools import ConverterOptions, OverwriteMode
from pydantic import BaseModel, Field, model_validator

DATA_DIR = Path(__file__).parent / "data"


class FingerprintModel(BaseModel):
    mean: float
    std: float
    min: float
    max: float
    hash: str

    @classmethod
    def from_array(cls, arr: np.ndarray, decimals=6):
        return cls(
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            hash=hashlib.sha256(np.round(arr, decimals).tobytes()).hexdigest(),
        )


class RoiAssertionModel(BaseModel):
    slice_repr: str
    finger_print: FingerprintModel
    yx_origin: list[float] | None = None


class TableAssertionModel(BaseModel):
    rois: dict[str, RoiAssertionModel] = Field(default_factory=dict)


class ImageAssertionModel(BaseModel):
    axes: tuple[str, ...]
    shape: tuple[int, ...]
    pixelsize: tuple[float, ...]
    channel_labels: list[str] = Field(default_factory=list)
    wavelength_ids: list[str | None] = Field(default_factory=list)
    types: dict[str, bool] = Field(default_factory=dict)
    attributes: dict[str, str | int | float] = Field(default_factory=dict)
    tables: dict[str, TableAssertionModel | None] = Field(default_factory=dict)


def deep_merge(a, b):
    result = a.copy()
    for key, value in b.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class PlateAssertionModel(BaseModel):
    wells: list[str]
    images: dict[str, ImageAssertionModel]

    @model_validator(mode="before")
    def validate_images(cls, values):
        common_assertions = values.pop("images_common", {})
        images = values.get("images", {})
        updated_image_assertions = {}
        for image_path, image_assertions in images.items():
            for key in image_assertions.keys():
                if key in common_assertions:
                    image_assertions = deep_merge(image_assertions, common_assertions)
            updated_image_assertions[image_path] = image_assertions
        values["images"] = updated_image_assertions
        return values


class MultiPlateAssertionModel(BaseModel):
    plates: dict[str, PlateAssertionModel]

    @property
    def expected_parallelization_list_length(self) -> int:
        return sum(len(plate.images) for plate in self.plates.values())

    def aggregated_types(self) -> dict[str, dict[str, bool]]:
        result = {}
        for plate_path, plate in self.plates.items():
            for image_path, img in plate.images.items():
                result[f"{plate_path}/{image_path}"] = img.types
        return result

    def aggregated_attributes(
        self,
    ) -> dict[str, dict[str, str | int | float]]:
        result = {}
        for plate_path, plate in self.plates.items():
            for image_path, img in plate.images.items():
                result[f"{plate_path}/{image_path}"] = img.attributes
        return result


class MultiSingleImageAssertionModel(BaseModel):
    images: dict[str, ImageAssertionModel]

    @property
    def expected_parallelization_list_length(self) -> int:
        return len(self.images)

    def aggregated_types(self) -> dict[str, dict[str, bool]]:
        return {name: img.types for name, img in self.images.items()}

    def aggregated_attributes(
        self,
    ) -> dict[str, dict[str, str | int | float]]:
        return {name: img.attributes for name, img in self.images.items()}


def _load_snapshot(yaml_path: Path) -> MultiPlateAssertionModel:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return MultiPlateAssertionModel(**data)


def _load_single_image_snapshot(yaml_path: Path) -> MultiSingleImageAssertionModel:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return MultiSingleImageAssertionModel(**data)


def _plate_after_init_checks(
    *,
    updates_list: list,
    multi_plate_assertions: MultiPlateAssertionModel,
    zarr_dir: Path,
):
    expected = multi_plate_assertions.expected_parallelization_list_length
    assert len(updates_list) == expected
    for plate_name, plate_assert in multi_plate_assertions.plates.items():
        plate_path = zarr_dir / plate_name
        plate = open_ome_zarr_plate(plate_path)
        wells = plate.get_wells().keys()
        assert set(wells) == set(plate_assert.wells)


def _single_image_after_init_checks(
    *,
    updates_list: list,
    assertions: MultiSingleImageAssertionModel,
):
    n = len(updates_list)
    expected = assertions.expected_parallelization_list_length
    assert n == expected, f"updates_list length {n} != expected {expected}"


def _image_list_updates_checks(
    *,
    image_list_updates: list[dict],
    aggregated_types: dict[str, dict[str, bool]],
    aggregated_attrs: dict[str, dict[str, str | int | float]],
    zarr_dir: Path,
):
    for updates in image_list_updates:
        assert "image_list_updates" in updates
        assert len(updates["image_list_updates"]) == 1
        upd = updates["image_list_updates"][0]
        zarr_url = Path(upd["zarr_url"])
        assert zarr_url.exists()
        image_path = zarr_url.relative_to(zarr_dir).as_posix()
        assert image_path in aggregated_types
        assert upd["types"] == aggregated_types[image_path]
        assert upd["attributes"] == aggregated_attrs[image_path], (
            f"{upd['attributes']} != {aggregated_attrs[image_path]}"
        )


def _check_roi_tables(
    ome_zarr_image: OmeZarrContainer,
    image_assertions: ImageAssertionModel,
):
    assert set(ome_zarr_image.list_tables()) == set(image_assertions.tables.keys()), (
        set(ome_zarr_image.list_tables())
    )
    image = ome_zarr_image.get_image()
    for table_name, table_assert in image_assertions.tables.items():
        if table_assert is None:
            continue
        roi_table = ome_zarr_image.get_roi_table(table_name)
        for roi_name, roi_assert in table_assert.rois.items():
            for roi in roi_table.rois():
                if roi.name == roi_name:
                    break
            else:
                raise AssertionError(f"ROI {roi_name} not found in table {table_name}")
            roi_pixel = roi.to_pixel(pixel_size=image.pixel_size)
            slices_repr = str(roi_pixel.slices)
            assert slices_repr == str(roi_assert.slice_repr), slices_repr
            roi_array = image.get_roi_as_numpy(roi)
            fingerprint = FingerprintModel.from_array(roi_array)
            assert fingerprint == roi_assert.finger_print, fingerprint
            if roi_assert.yx_origin is not None:
                y_origin = getattr(roi, "y_micrometer_original", None)
                x_origin = getattr(roi, "x_micrometer_original", None)
                assert [y_origin, x_origin] == roi_assert.yx_origin


def _check_image_against_assertion(
    *,
    ome_zarr_image: OmeZarrContainer,
    img_assert: ImageAssertionModel,
):
    image = ome_zarr_image.get_image()
    assert image.axes == img_assert.axes
    assert image.shape == img_assert.shape
    assert np.allclose(image.pixel_size.tzyx, img_assert.pixelsize)
    if img_assert.channel_labels:
        assert ome_zarr_image.channel_labels == list(img_assert.channel_labels)
    if img_assert.wavelength_ids:
        assert ome_zarr_image.wavelength_ids == list(img_assert.wavelength_ids)
    _check_roi_tables(
        ome_zarr_image=ome_zarr_image,
        image_assertions=img_assert,
    )


def _post_compute_checks(
    *, multi_plate_assertions: MultiPlateAssertionModel, zarr_dir: Path
):
    for plate_name, plate_assert in multi_plate_assertions.plates.items():
        plate_path = zarr_dir / plate_name
        plate = open_ome_zarr_plate(plate_path)
        for image_path, ome_zarr_image in plate.get_images().items():
            assert image_path in plate_assert.images
            img_assert = plate_assert.images[image_path]
            _check_image_against_assertion(
                ome_zarr_image=ome_zarr_image, img_assert=img_assert
            )


def _post_compute_checks_single_image(
    *, assertions: MultiSingleImageAssertionModel, zarr_dir: Path
):
    for zarr_name, img_assert in assertions.images.items():
        zarr_path = zarr_dir / zarr_name
        ome_zarr_image = open_ome_zarr_container(zarr_path)
        _check_image_against_assertion(
            ome_zarr_image=ome_zarr_image, img_assert=img_assert
        )


def _build_image_entry(
    *,
    ome_zarr_image: OmeZarrContainer,
    upd: dict | None,
) -> dict:
    image = ome_zarr_image.get_image()
    entry: dict = {
        "axes": list(image.axes),
        "shape": list(image.shape),
        "pixelsize": list(image.pixel_size.tzyx),
        "channel_labels": ome_zarr_image.channel_labels,
        "wavelength_ids": ome_zarr_image.wavelength_ids,
    }
    if upd is not None:
        if "types" in upd:
            entry["types"] = upd["types"]
        if "attributes" in upd:
            entry["attributes"] = upd["attributes"]

    table_names = ome_zarr_image.list_tables()
    if table_names:
        tables_dict = {}
        for table_name in table_names:
            try:
                roi_table = ome_zarr_image.get_roi_table(table_name)
            except Exception:
                tables_dict[table_name] = None
                continue
            rois_dict = {}
            for roi in roi_table.rois():
                roi_pixel = roi.to_pixel(pixel_size=image.pixel_size)
                roi_array = image.get_roi_as_numpy(roi)
                fp = FingerprintModel.from_array(roi_array)
                y_origin = getattr(roi, "y_micrometer_original", None)
                x_origin = getattr(roi, "x_micrometer_original", None)
                if y_origin is not None and x_origin is not None:
                    yx_origin = [y_origin, x_origin]
                else:
                    yx_origin = None
                rois_dict[roi.name] = {
                    "slice_repr": str(roi_pixel.slices),
                    "finger_print": fp.model_dump(),
                    "yx_origin": yx_origin,
                }
            tables_dict[table_name] = {"rois": rois_dict}
        entry["tables"] = tables_dict
    return entry


def _generate_snapshot(
    *,
    zarr_dir: Path,
    image_list_updates: list[dict],
    snapshot_path: Path,
) -> None:
    """Generate multi_plate_assertions dict from converted plates."""
    plate_names = sorted(
        {
            Path(upd["zarr_url"]).relative_to(zarr_dir).parts[0]
            for updates in image_list_updates
            for upd in updates.get("image_list_updates", [])
        }
    )

    updates_by_image: dict[str, dict] = {}
    for updates in image_list_updates:
        for upd in updates.get("image_list_updates", []):
            zarr_url = Path(upd["zarr_url"])
            rel = zarr_url.relative_to(zarr_dir).as_posix()
            updates_by_image[rel] = upd

    all_plates = {}
    for plate_name in plate_names:
        plate_path = zarr_dir / plate_name
        ome_zarr_plate = open_ome_zarr_plate(plate_path)
        wells = list(ome_zarr_plate.get_wells().keys())
        images_dict = {}

        for img_path, ome_zarr_image in ome_zarr_plate.get_images().items():
            full_path = f"{plate_name}/{img_path}"
            upd = updates_by_image.get(full_path)
            images_dict[img_path] = _build_image_entry(
                ome_zarr_image=ome_zarr_image, upd=upd
            )

        all_plates[plate_name] = {
            "wells": wells,
            "images": images_dict,
        }

    snapshot_data = {"plates": all_plates}
    MultiPlateAssertionModel(**snapshot_data)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w") as f:
        yaml.dump(
            snapshot_data,
            f,
            default_flow_style=False,
            sort_keys=False,
        )


def _generate_single_image_snapshot(
    *,
    zarr_dir: Path,
    image_list_updates: list[dict],
    snapshot_path: Path,
) -> None:
    """Generate multi_single_image_assertions dict from converted images."""
    zarr_names = sorted(
        {
            Path(upd["zarr_url"]).relative_to(zarr_dir).as_posix()
            for updates in image_list_updates
            for upd in updates.get("image_list_updates", [])
        }
    )

    updates_by_image: dict[str, dict] = {}
    for updates in image_list_updates:
        for upd in updates.get("image_list_updates", []):
            zarr_url = Path(upd["zarr_url"])
            rel = zarr_url.relative_to(zarr_dir).as_posix()
            updates_by_image[rel] = upd

    images_dict = {}
    for zarr_name in zarr_names:
        zarr_path = zarr_dir / zarr_name
        ome_zarr_image = open_ome_zarr_container(zarr_path)
        upd = updates_by_image.get(zarr_name)
        images_dict[zarr_name] = _build_image_entry(
            ome_zarr_image=ome_zarr_image, upd=upd
        )

    snapshot_data = {"images": images_dict}
    MultiSingleImageAssertionModel(**snapshot_data)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w") as f:
        yaml.dump(
            snapshot_data,
            f,
            default_flow_style=False,
            sort_keys=False,
        )


def run_converter_test(
    *,
    tmp_path: Path,
    api_fn: Callable,
    api_kwargs: dict,
    snapshot_path: Path,
    update_snapshots: bool,
    converter_options: ConverterOptions,
    output_type: Literal["plate", "single_image"] = "plate",
):
    """Run a converter end-to-end and check against snapshot assertions."""
    if update_snapshots:
        zarr_dir = snapshot_path.parent.parent / "output"
        zarr_dir.mkdir(parents=True, exist_ok=True)
        api_kwargs = api_kwargs | {"overwrite": OverwriteMode.OVERWRITE}
    else:
        zarr_dir = tmp_path / "output"

    updates_list = api_fn(
        zarr_dir=str(zarr_dir), **api_kwargs, converter_options=converter_options
    )

    if update_snapshots:
        if output_type == "plate":
            _generate_snapshot(
                zarr_dir=zarr_dir,
                image_list_updates=updates_list,
                snapshot_path=snapshot_path,
            )
        else:
            _generate_single_image_snapshot(
                zarr_dir=zarr_dir,
                image_list_updates=updates_list,
                snapshot_path=snapshot_path,
            )
        return

    if not snapshot_path.exists():
        raise FileNotFoundError(
            f"Snapshot file {snapshot_path} not found. "
            "Run with --update-snapshots to generate it."
        )

    if output_type == "plate":
        assertions = _load_snapshot(snapshot_path)
        _plate_after_init_checks(
            updates_list=updates_list,
            multi_plate_assertions=assertions,
            zarr_dir=zarr_dir,
        )
        _image_list_updates_checks(
            image_list_updates=updates_list,
            aggregated_types=assertions.aggregated_types(),
            aggregated_attrs=assertions.aggregated_attributes(),
            zarr_dir=zarr_dir,
        )
        _post_compute_checks(
            multi_plate_assertions=assertions,
            zarr_dir=zarr_dir,
        )
    else:
        assertions = _load_single_image_snapshot(snapshot_path)
        _single_image_after_init_checks(
            updates_list=updates_list,
            assertions=assertions,
        )
        _image_list_updates_checks(
            image_list_updates=updates_list,
            aggregated_types=assertions.aggregated_types(),
            aggregated_attrs=assertions.aggregated_attributes(),
            zarr_dir=zarr_dir,
        )
        _post_compute_checks_single_image(
            assertions=assertions,
            zarr_dir=zarr_dir,
        )
