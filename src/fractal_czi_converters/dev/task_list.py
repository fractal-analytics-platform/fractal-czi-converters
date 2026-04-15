"""Contains the list of tasks available to fractal."""

from fractal_task_tools.task_models import ConverterCompoundTask

AUTHORS = "Flurin Sturzenegger"

TASK_LIST = [
    ConverterCompoundTask(
        name="Convert Zeiss CZI Image to OME-Zarr",
        executable_init="init_task_convert_czi_single_image.py",
        executable="compute_task_single_image.py",
        meta_init={"cpus_per_task": 1, "mem": 4000},
        meta={"cpus_per_task": 1, "mem": 4000},
        category="Conversion",
        modality="Other",
        tags=[
            "Zeiss",
            "CZI",
            "Image converter",
        ],
        docs_info="file:docs_info/czi_image_task.md",
    ),
]
