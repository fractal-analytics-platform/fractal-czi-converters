"""Contains the list of tasks available to fractal."""

from fractal_task_tools.task_models import ConverterCompoundTask

AUTHORS = "Lorenzo Cerrone"
DOCS_LINK = "https://github.com/fractal-analytics-platform/fractal-czi-converters"


TASK_LIST = [
    ConverterCompoundTask(
        name="Convert CZI Image to OME-Zarr",
        executable_init="czi_image/convert_czi_image_init_task.py",
        executable="common/single_image_compute_task.py",
        meta_init={"cpus_per_task": 1, "mem": 4000},
        meta={"cpus_per_task": 1, "mem": 12000},
        category="Conversion",
        tags=["Zeiss", "Image Converter"],
    ),
    ConverterCompoundTask(
        name="Convert CZI Plate to OME-Zarr",
        executable_init="czi_plate/convert_czi_plate_init_task.py",
        executable="common/image_in_plate_compute_task.py",
        meta_init={"cpus_per_task": 1, "mem": 4000},
        meta={"cpus_per_task": 1, "mem": 12000},
        category="Conversion",
        modality="HCS",
        tags=["Zeiss", "Plate converter"],
    ),
]
