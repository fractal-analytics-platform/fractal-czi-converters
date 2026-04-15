"""Color utility functions."""

from ome_zarr_converters_tools.models._acquisition import DefaultColors


def wavelength_to_default_color(wavelength: float) -> DefaultColors:
    """Map wavelength (nm) to the closest DefaultColors enum value.

    Args:
        wavelength: Wavelength in nanometers (nm)

    Returns:
        The closest matching DefaultColors enum value
    """
    # Map wavelength ranges to DefaultColors based on visible spectrum
    if wavelength < 380:  # UV -> magenta
        return DefaultColors.magenta
    elif wavelength < 450:  # Violet/Blue
        return DefaultColors.blue
    elif wavelength < 495:  # Cyan
        return DefaultColors.cyan
    elif wavelength < 520:  # Green
        return DefaultColors.green
    elif wavelength < 560:  # Lime/Yellow-green
        return DefaultColors.lime
    elif wavelength < 590:  # Yellow
        return DefaultColors.yellow
    elif wavelength < 620:  # Orange
        return DefaultColors.orange
    elif wavelength < 750:  # Red
        return DefaultColors.red
    else:  # Far red/IR -> magenta
        return DefaultColors.magenta
