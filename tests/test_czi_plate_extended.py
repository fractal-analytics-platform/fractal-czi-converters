from pathlib import Path

import pytest

from fractal_czi_converters.common import image_in_plate_compute_task
from fractal_czi_converters.czi_plate.convert_czi_plate_init_task import (
    convert_czi_plate_init_task,
)

from .utils import run_converter_test

EXTENDED_DATA_DIR = Path(__file__).parent / "data-extended"
SNAPSHOT_DIR = EXTENDED_DATA_DIR / "Zeiss-CZI" / "snapshots"
RAW_DIR = EXTENDED_DATA_DIR / "Zeiss-CZI" / "raw"

# Two-well plate fixtures (wells C4/C5): position-, region- and
# manually-drawn-region acquisitions, plus multi-z/t variants.
_PLATE_DATASETS = [
    "hcs_2w2p2c1z1t_pos",
    "hcs_2w2p2c1z1t_rgn",
    "hcs_2w2p2c3z1t_rgn",
    "hcs_2w2p2c3z2t_rgn",
    "hcs_2w4p2c1z1t_pos-manually-drawn",
    "hcs_2w4p2c1z1t_rgn-manually-drawn",
]


@pytest.mark.extended
@pytest.mark.parametrize(
    "init_task_kwargs, snapshot_path",
    [
        pytest.param(
            {"acquisitions": [{"path": str(RAW_DIR / f"{name}.czi")}]},
            SNAPSHOT_DIR / f"{name}.yaml",
            id=name,
        )
        for name in _PLATE_DATASETS
    ],
)
def test_czi_plate_extended(
    tmp_path: Path,
    init_task_kwargs: dict,
    snapshot_path: Path,
    update_snapshots: bool,
    converter_options,
):
    run_converter_test(
        tmp_path=tmp_path,
        init_task_fn=convert_czi_plate_init_task,
        compute_task_fn=image_in_plate_compute_task,
        init_task_kwargs=init_task_kwargs,
        snapshot_path=snapshot_path,
        update_snapshots=update_snapshots,
        converter_options=converter_options,
        output_type="plate",
    )


@pytest.mark.extended
def test_czi_plate_multi_acquisition(
    tmp_path: Path,
    update_snapshots: bool,
    converter_options,
):
    """Two CZI files merge into one plate as separate acquisition rounds."""
    init_task_kwargs = {
        "acquisitions": [
            {
                "path": str(RAW_DIR / "hcs_2w2p2c1z1t_pos.czi"),
                "plate_name": "merged_plate",
                "acquisition_id": 0,
            },
            {
                "path": str(RAW_DIR / "hcs_2w2p2c3z1t_rgn.czi"),
                "plate_name": "merged_plate",
                "acquisition_id": 1,
            },
        ]
    }
    run_converter_test(
        tmp_path=tmp_path,
        init_task_fn=convert_czi_plate_init_task,
        compute_task_fn=image_in_plate_compute_task,
        init_task_kwargs=init_task_kwargs,
        snapshot_path=SNAPSHOT_DIR / "merged_plate_multi_acquisition.yaml",
        update_snapshots=update_snapshots,
        converter_options=converter_options,
        output_type="plate",
    )
