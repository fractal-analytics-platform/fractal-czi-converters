from pathlib import Path

import pytest

from fractal_czi_converters import convert_czi_plate

from .utils import DATA_DIR, run_converter_test

RAW_DIR = DATA_DIR / "Zeiss-CZI" / "raw"
SNAPSHOT_DIR = DATA_DIR / "Zeiss-CZI" / "snapshots"

# Small two-well plate committed for CI: wells C4/C5, each with two positional
# scenes (FOVs P1/P2). Exercises well grouping and both mosaic modes.
_PLATE_DATASET = "hcs_2w2p2c1z1t_pos"


@pytest.mark.parametrize(
    "init_task_kwargs, snapshot_path",
    [
        pytest.param(
            {
                "acquisitions": [
                    {
                        "path": str(RAW_DIR / f"{_PLATE_DATASET}.czi"),
                        "mosaic_mode": mode,
                    }
                ]
            },
            SNAPSHOT_DIR / f"{_PLATE_DATASET}_{mode}.yaml",
            id=f"{_PLATE_DATASET}-{mode}",
        )
        for mode in ("tiles", "assembled")
    ],
)
def test_czi_plate(
    tmp_path: Path,
    init_task_kwargs: dict,
    snapshot_path: Path,
    update_snapshots: bool,
    converter_options,
):
    run_converter_test(
        tmp_path=tmp_path,
        api_fn=convert_czi_plate,
        api_kwargs=init_task_kwargs,
        snapshot_path=snapshot_path,
        update_snapshots=update_snapshots,
        converter_options=converter_options,
        output_type="plate",
    )
