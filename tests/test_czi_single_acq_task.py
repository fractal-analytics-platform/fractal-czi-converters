from pathlib import Path

import pytest

from fractal_czi_converters.common import single_image_compute_task
from fractal_czi_converters.czi_single.convert_czi_single_acq_init_task import (
    convert_czi_single_acq_init_task,
)

from .utils import DATA_DIR, run_converter_test

RAW_DIR = DATA_DIR / "Zeiss-CZI" / "raw"
SNAPSHOT_DIR = DATA_DIR / "Zeiss-CZI" / "snapshots"

# Small multi-mosaic single-acquisition file committed for CI: one scene made of
# four mosaic sub-tiles. Exercises both mosaic modes (per-tile FOVs vs a single
# czifile-assembled image).
_MOSAIC_DATASET = "img_4p2c1z1t_ManuallyDrawnRegion"


@pytest.mark.parametrize(
    "init_task_kwargs, snapshot_path",
    [
        pytest.param(
            {
                "acquisitions": [
                    {
                        "path": str(RAW_DIR / f"{_MOSAIC_DATASET}.czi"),
                        "mosaic_mode": mode,
                    }
                ]
            },
            SNAPSHOT_DIR / f"{_MOSAIC_DATASET}_{mode}.yaml",
            id=f"{_MOSAIC_DATASET}-{mode}",
        )
        for mode in ("tiles", "assembled")
    ],
)
def test_czi_single_acq(
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
