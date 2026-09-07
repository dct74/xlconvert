"""Error handling (port of Swift Core/Errors.swift).

Swift AppError.errorDescription semantics:
  .backupFailed(msg)  / .abort(msg)      -> msg
  .fileSystemError(e)                    -> "File system error: <e>"
  .excelParsingError(e)                  -> "Excel parsing error: <e>"
"""

from __future__ import annotations


class XlError(Exception):
    """Base error; str() mirrors AppError.errorDescription."""


class BackupError(XlError):
    def __init__(self, message: str):
        super().__init__(message)


class AbortError(XlError):
    def __init__(self, message: str):
        super().__init__(message)


class FileSystemError(XlError):
    def __init__(self, underlying: object):
        super().__init__(f"File system error: {underlying}")


class ExcelParsingError(XlError):
    def __init__(self, underlying: object):
        super().__init__(f"Excel parsing error: {underlying}")


def excel_parsing_wrap(error: object) -> ExcelParsingError:
    return ExcelParsingError(error)
