"""Contains the list of tasks available to fractal."""

from fractal_task_tools.task_models import ConverterCompoundTask

AUTHORS = "Lorenzo Cerrone"
DOCS_LINK = "https://github.com/fractal-analytics-platform/fractal-czi-converters"


TASK_LIST = [
    ConverterCompoundTask(
        name="Convert CZI to OME-Zarr",
        executable_init="czi_single/convert_czi_single_acq_init_task.py",
        executable="common/single_image_compute_task.py",
        meta_init={"cpus_per_task": 1, "mem": 4000},
        meta={"cpus_per_task": 1, "mem": 12000},
        category="Conversion",
        tags=["Zeiss", "Single Image Converter"],
    ),
]
