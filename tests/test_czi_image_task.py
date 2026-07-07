from pathlib import Path

import pytest
from ome_zarr_converters_tools.testing import run_converter_test

from fractal_czi_converters import convert_czi_image

from .utils import DATA_DIR

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
            SNAPSHOT_DIR / f"{_MOSAIC_DATASET}_{mode}.json",
            id=f"{_MOSAIC_DATASET}-{mode}",
        )
        for mode in ("tiles", "assembled")
    ],
)
def test_czi_image(
    tmp_path: Path,
    init_task_kwargs: dict,
    snapshot_path: Path,
    update_snapshots: bool,
    converter_options,
):
    run_converter_test(
        tmp_path=tmp_path,
        api_fn=convert_czi_image,
        api_kwargs=init_task_kwargs,
        snapshot_path=snapshot_path,
        update_snapshots=update_snapshots,
        converter_options=converter_options,
        output_type="single_image",
    )
