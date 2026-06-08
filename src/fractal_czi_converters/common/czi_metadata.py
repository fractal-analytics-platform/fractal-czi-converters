"""Shared CZI scene-metadata layer (XML only, no pixel data).

Reads the Zeiss CZI XML (via ``czifile`` + stdlib) and resolves per-scene
field-of-view names and well labels. Used by both the single-acquisition and the
plate (HCS) converters.

A scene carries a *well label* when it has a non-empty ``<ArrayName>`` or a
``<Shape>`` with a non-empty ``Name`` attribute (e.g. ``"C4"``, ``"B1"``). A bare
``<Shape>`` with ``RowIndex``/``ColumnIndex`` but an empty ``Name`` is region
geometry (manually drawn / rectangle scenes), *not* a well. See
``CZI_PARSER_NOTES.md`` §2-4 for the empirical findings behind these heuristics.
"""

from __future__ import annotations

import logging
import string
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


def check_single_acquisition(czi: Any) -> None:
    """Raise when the CZI encodes more than one independent acquisition.

    Multiple ``<ExperimentBlocks>`` or ``<AcquisitionBlock>`` elements indicate
    several independent acquisitions stored in one file, which these parsers do
    not support (it would silently mix their scenes). A single acquisition with
    many positions keeps one acquisition block and is handled normally.
    """
    root = czi.xml_element
    if root is None:
        return
    for tag in ("ExperimentBlocks", "AcquisitionBlock"):
        count = len(list(root.iter(tag)))
        if count > 1:
            raise ValueError(
                f"CZI file contains {count} <{tag}> elements, indicating "
                "multiple independent acquisitions in a single file. This "
                "parser only supports single-acquisition files (with one or "
                "more positions/scenes)."
            )


def find_scene_elements(czi: Any) -> dict[int, ET.Element]:
    """Map each ``<Scene>`` element to its scene key via the ``Index`` attribute.

    Falls back to document order when ``Index`` attributes are missing or
    duplicated.
    """
    root = czi.xml_element
    elements: list[ET.Element] = []
    if root is not None:
        for scenes in root.iter("Scenes"):
            elements.extend(scenes.findall("Scene"))

    by_index: dict[int, ET.Element] = {}
    for position, elem in enumerate(elements):
        index_text = elem.get("Index")
        try:
            key = int(index_text) if index_text is not None else position
        except ValueError:
            key = position
        if key in by_index:
            logger.warning(
                "Duplicate/ambiguous Scene Index %s; falling back to document "
                "order for scene-to-element mapping.",
                key,
            )
            return dict(enumerate(elements))
        by_index[key] = elem
    return by_index


def well_label(elem: ET.Element) -> str | None:
    """Return the well label of a ``<Scene>`` element, or ``None``.

    The label is a non-empty ``<ArrayName>`` (e.g. ``"C4"``) or a ``<Shape>``
    with a non-empty ``Name`` attribute (the well label). A bare ``<Shape>``
    with ``RowIndex``/``ColumnIndex`` but an empty ``Name`` is region geometry
    (manually drawn / rectangle scenes) and is *not* a well.
    """
    array_name = (elem.findtext("ArrayName") or "").strip()
    if array_name:
        return array_name
    shape = elem.find("Shape")
    if shape is not None:
        name = (shape.get("Name") or "").strip()
        if name:
            return name
    return None


def _row_letter(row_index: int) -> str:
    """1-based row index to a letter (1->"A", 3->"C"); ``R{n}`` fallback >26."""
    if 1 <= row_index <= 26:
        return string.ascii_uppercase[row_index - 1]
    return f"R{row_index}"


def parse_well(elem: ET.Element) -> tuple[str, int] | None:
    """Return ``(row_letter, column)`` for a well ``<Scene>``, or ``None``.

    A scene is only treated as a well when it carries a well *label* (see
    :func:`well_label`); a bare ``<Shape>`` with ``RowIndex``/``ColumnIndex`` and
    an empty ``Name`` is region geometry and yields ``None``.

    When the scene is a well, the row/column are resolved in order:

    1. ``<Shape>`` ``RowIndex``/``ColumnIndex`` (1-based; e.g. ``3``/``4`` ->
       ``("C", 4)``);
    2. otherwise the well label string parsed as ``"<letters><digits>"``
       (e.g. ``"C4"`` -> ``("C", 4)``).
    """
    label = well_label(elem)
    if label is None:
        return None

    shape = elem.find("Shape")
    if shape is not None:
        row_text = shape.findtext("RowIndex")
        col_text = shape.findtext("ColumnIndex")
        if row_text is not None and col_text is not None:
            try:
                return _row_letter(int(row_text)), int(col_text)
            except ValueError:
                pass

    # Fall back to parsing the label string, e.g. "C4" -> ("C", 4).
    letters = "".join(c for c in label if c.isalpha())
    digits = "".join(c for c in label if c.isdigit())
    if letters and digits:
        return letters.upper(), int(digits)

    logger.warning("Could not resolve row/column from well label %r.", label)
    return None


def parse_fov(elem: ET.Element, scene_key: int) -> str:
    """Extract the field-of-view name from a ``<Scene>`` element."""
    name = (elem.get("Name") or "").strip()
    return name if name else f"P{scene_key + 1}"
