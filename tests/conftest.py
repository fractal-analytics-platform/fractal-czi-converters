"""Test configuration for fractal-czi-converters."""

import hashlib
import logging
import urllib.request
import zipfile
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"

# TODO: replace with the Zenodo record holding the CZI test data once it is
# uploaded. The dict structure mirrors fractal-nd2-converters/tests/conftest.py.
ZENODO_RECORD_URL = (
    "https://zenodo.org/api/records/PLACEHOLDER/files"
)
ZENODO_FILES: dict[str, dict] = {
    # "<filename>.zip": {"md5": "<md5-hash>"},
}


def _download_zenodo_data() -> None:
    """Download and extract test data from Zenodo if not already present."""
    for filename, meta in ZENODO_FILES.items():
        extracted_dir = DATA_DIR / filename.replace(".zip", "")
        if extracted_dir.exists():
            return

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = DATA_DIR / filename
        url = f"{ZENODO_RECORD_URL}/{filename}/content"

        logger.info(f"Downloading {filename} from Zenodo...")
        urllib.request.urlretrieve(url, zip_path)

        # Verify MD5
        md5 = hashlib.md5(zip_path.read_bytes()).hexdigest()
        if md5 != meta["md5"]:
            zip_path.unlink()
            raise RuntimeError(
                f"MD5 mismatch for {filename}: "
                f"expected {meta['md5']}, got {md5}"
            )

        # Extract and remove zip
        logger.info(f"Extracting {filename}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(DATA_DIR)
        zip_path.unlink()


def pytest_addoption(parser):
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Regenerate assertion snapshot YAMLs",
    )


def pytest_configure(config):
    """Download test data from Zenodo before test collection."""
    _download_zenodo_data()


@pytest.fixture
def update_snapshots(request):
    return request.config.getoption("--update-snapshots")
