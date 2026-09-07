"""IPO template -> 章/节/目 folders processor
(port of Swift Processors/IPOTemplateProcessor.swift).

Columns A (Chapter), B (Subsection), C (Detail); data starts at Excel row 3.
Uses only the first worksheet.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from .. import console, file_system, sequence_prefix, string_transform
from ..excel_parser import collect_cells, open_workbook


class IPOTemplateProcessor:
    def __init__(
        self,
        excel_file: str,
        input_fn: Callable[[], str] = input,
    ) -> None:
        self.excel_file = excel_file
        self.input_fn = input_fn

    def process(self) -> None:
        wb = open_workbook(self.excel_file)
        try:
            if not wb.sheetnames:
                raise ValueError("No worksheets found.")
            ws = wb[wb.sheetnames[0]]

            data, max_row = collect_cells(ws)

            def get_cell_value(row: int, col: int) -> str:
                # col is 1-based here (1=A,2=B,3=C).
                return data.get((row, col - 1), "")

            stem = os.path.splitext(os.path.basename(self.excel_file))[0]
            top_folder_name = string_transform.sanitize(stem)
            top_folder = os.path.join(
                os.path.dirname(os.path.abspath(self.excel_file)),
                top_folder_name,
            )
            count: list[int] = [0]
            if not file_system.create_folder_safely(at=top_folder, count=count):
                raise ValueError("Failed to create top-level folder.")

            if max_row < 3:
                console.info("No data rows found (needs at least row 3).")
                return

            current_chapter_folder: str | None = None
            current_subsection_folder: str | None = None
            current_a_val = ""
            current_b_val = ""

            for row in range(3, max_row + 1):
                raw_a = get_cell_value(row, 1)
                raw_b = get_cell_value(row, 2)
                raw_c = get_cell_value(row, 3)
                val_a = raw_a.strip()
                val_b = raw_b.strip()
                val_c = raw_c.strip()

                if not val_a and not val_b and not val_c:
                    continue

                # Chapter: A has value, B and C are empty.
                if val_a and not val_b and not val_c:
                    folder_name = string_transform.sanitize(val_a)
                    if not folder_name:
                        continue
                    chapter_url = os.path.join(top_folder, folder_name)
                    if not file_system.create_folder_safely(
                        at=chapter_url, count=count
                    ):
                        continue
                    current_chapter_folder = chapter_url
                    current_subsection_folder = None
                    current_a_val = ""
                    current_b_val = ""
                    continue

                # Subsection: A and B both have values.
                if val_a and val_b:
                    if current_chapter_folder is None:
                        continue
                    if (
                        current_subsection_folder is None
                        or val_a != current_a_val
                        or val_b != current_b_val
                    ):
                        folder_name = string_transform.sanitize(
                            f"{string_transform.sanitize(val_a)} "
                            f"{string_transform.sanitize(val_b)}"
                        )
                        if not folder_name:
                            continue
                        sub_url = os.path.join(
                            current_chapter_folder, folder_name
                        )
                        if not file_system.create_folder_safely(
                            at=sub_url, count=count
                        ):
                            continue
                        current_subsection_folder = sub_url
                        current_a_val = val_a
                        current_b_val = val_b

                # Detail: C has value.
                if val_c:
                    if current_subsection_folder is None:
                        continue
                    folder_name = string_transform.sanitize(val_c)
                    if not folder_name:
                        continue
                    detail_url = os.path.join(
                        current_subsection_folder, folder_name
                    )
                    file_system.create_folder_safely(at=detail_url, count=count)
        finally:
            wb.close()

        console.success(
            f"Folder creation completed, created {count[0]} folders in total"
        )
        seq = sequence_prefix.add_sequence_prefix(top_folder)
        if seq:
            console.info(f"Added numeric prefixes to {seq} ordinal directories.")
        console.info(f"Folder structure located at: {top_folder}")
