from pathlib import Path

import pytest

from fractal_czi_converters.common import single_image_compute_task
from fractal_czi_converters.czi_single.convert_czi_single_acq_init_task import (
    convert_czi_single_acq_init_task,
)

from .utils import run_converter_test

EXTENDED_DATA_DIR = Path(__file__).parent / "data-extended"
SNAPSHOT_DIR = EXTENDED_DATA_DIR / "Zeiss-CZI" / "snapshots"
RAW_DIR = EXTENDED_DATA_DIR / "Zeiss-CZI" / "raw"

_SINGLE_IMAGE_DATASETS = [
    "img_2p4c40z1t_HighRes",
    "img_2p4c19z2t_TimeSeries",
    "img_1p5c55z1t_4i_Round1",
    "img_1p4c80z1t_4i_Round2",
    "img_1p4c14z2t_TimeSeries",
    "img_1p1c1z1t_Position",
    "img_1p2c1z1t_16Bit",
    "img_1p2c1z1t_Camera",
    "img_1p2c1z1t_Position",
    "img_1p2c3z1t_Position",
    "img_1p2c1z4t_TimeSeries",
    "img_1p2c3z4t_TimeSeries",
    "img_2p2c1z1t_Position",
    "img_1p2c1z1t_ManuallyDrawnRegion",
]


@pytest.mark.extended
@pytest.mark.parametrize(
    "init_task_kwargs, snapshot_path",
    [
        pytest.param(
            {"acquisitions": [{"path": str(RAW_DIR / f"{name}.czi")}]},
            SNAPSHOT_DIR / f"{name}.yaml",
        )
        for name in _SINGLE_IMAGE_DATASETS
    ],
)
def test_czi_single_acq_extended(
    tmp_path: Path,
    init_task_kwargs: dict,
    snapshot_path: Path,
    update_snapshots: bool,
    converter_options,
):
    run_converter_test(
        tmp_path=tmp_path,
        init_task_fn=convert_czi_single_acq_init_task,
        compute_task_fn=single_image_compute_task,
        init_task_kwargs=init_task_kwargs,
        snapshot_path=snapshot_path,
        update_snapshots=update_snapshots,
        converter_options=converter_options,
        output_type="single_image",
    )
