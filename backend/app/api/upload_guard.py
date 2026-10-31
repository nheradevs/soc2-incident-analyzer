"""Content validation of an uploaded workbook (RF8 / FSD §5).

The file name and the client-declared media type describe what the client *says*
the upload is; a renamed executable, an HTML page or an old binary workbook can
all carry the `.xlsx` suffix. This module asks the bytes instead.

An `.xlsx` workbook is an OPC package: a ZIP container that holds a
`[Content_Types].xml` part and the `xl/` workbook parts. The predicate is
therefore:

1. the payload does not start with the OLE2 signature (`\\xd0\\xcf\\x11\\xe0`),
   which is what an old `.xls` is;
2. the payload starts with the ZIP local file header signature (`PK\\x03\\x04`);
3. the container lists a `[Content_Types].xml` member;
4. the container lists at least one member under `xl/`.

Failing (3) or (4) means a ZIP that is not a workbook, which openpyxl would
reject later with a less precise message. The declared media type is never a
gate: `curl -F file=@export.xlsx` sends `application/octet-stream`.

Every message is Spanish because it is rendered verbatim in the UI.
"""

from __future__ import annotations

import io
from zipfile import BadZipFile, ZipFile

ZIP_LOCAL_HEADER = b"PK\x03\x04"
OLE2_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
CONTENT_TYPES_PART = "[Content_Types].xml"
WORKBOOK_PREFIX = "xl/"

NOT_A_ZIP_MESSAGE = (
    "El contenido del archivo no es un libro .xlsx válido: no es un contenedor ZIP. "
    "Verifique que el archivo no se haya renombrado desde otro formato."
)
OLD_XLS_MESSAGE = (
    "El archivo es un libro .xls antiguo (formato binario OLE2). "
    "Ábralo en Excel y guárdelo como .xlsx antes de subirlo."
)
NO_WORKBOOK_MESSAGE = (
    "El archivo es un ZIP, pero no contiene un libro de Excel: "
    "falta [Content_Types].xml o la parte xl/ del libro."
)

_ARCHIVE_ERRORS = (BadZipFile, OSError, ValueError)


class ContentError(ValueError):
    """The bytes are not an Excel workbook; `str(error)` is the Spanish message."""


def validate_workbook_payload(payload: bytes) -> None:
    """Raise `ContentError` unless `payload` is a ZIP holding an `xl/` workbook part."""
    if payload.startswith(OLE2_HEADER):
        raise ContentError(OLD_XLS_MESSAGE)
    if not payload.startswith(ZIP_LOCAL_HEADER):
        raise ContentError(NOT_A_ZIP_MESSAGE)

    try:
        with ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
    except _ARCHIVE_ERRORS as error:
        raise ContentError(NOT_A_ZIP_MESSAGE) from error

    has_content_types = CONTENT_TYPES_PART in names
    has_workbook_part = any(name.startswith(WORKBOOK_PREFIX) for name in names)
    if not (has_content_types and has_workbook_part):
        raise ContentError(NO_WORKBOOK_MESSAGE)
