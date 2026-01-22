"""
Data Converter - handles ETS, XLSX, XLS, CSV
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .base import BaseConverter, ConversionResult

logger = logging.getLogger(__name__)


class DataConverter(BaseConverter):
    """Converter for data/spreadsheet formats"""

    @property
    def supported_input_formats(self) -> set:
        return {"ets", "xlsx", "xls", "csv", "tsv", "json"}

    @property
    def supported_output_formats(self) -> set:
        return {"xlsx", "csv", "json", "xml", "html", "md", "pdf"}

    async def convert(
        self,
        input_path: Path,
        output_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Convert data file to specified format"""
        start_time = datetime.now()
        options = options or {}

        try:
            self.validate_input(input_path)
            input_format = input_path.suffix.lstrip(".").lower()
            output_format = output_format.lower()

            output_path = self.get_output_path(input_path, output_format)

            # Load data into pandas DataFrame
            df = self._load_data(input_path, input_format, options)

            # Export to target format
            self._export_data(df, output_path, output_format, options)

            elapsed = (datetime.now() - start_time).total_seconds()

            return ConversionResult(
                success=True,
                input_path=input_path,
                output_path=output_path,
                input_format=input_format,
                output_format=output_format,
                conversion_time=elapsed,
                file_size=self.get_file_size(output_path),
            )

        except Exception as e:
            logger.error(f"Data conversion failed: {e}")
            return ConversionResult(
                success=False,
                input_path=input_path,
                input_format=input_path.suffix.lstrip("."),
                output_format=output_format,
                error_message=str(e),
            )

    def _load_data(
        self, input_path: Path, input_format: str, options: dict
    ) -> pd.DataFrame:
        """Load data from various formats into DataFrame"""
        encoding = options.get("encoding", "utf-8")

        if input_format == "csv":
            return pd.read_csv(
                input_path, encoding=encoding, sep=options.get("delimiter", ",")
            )

        elif input_format == "tsv":
            return pd.read_csv(input_path, encoding=encoding, sep="\t")

        elif input_format in ("xlsx", "xls"):
            sheet_name = options.get("sheet", 0)
            return pd.read_excel(input_path, sheet_name=sheet_name)

        elif input_format == "json":
            return pd.read_json(input_path, encoding=encoding)

        elif input_format == "ets":
            # ETS format - treat as CSV with specific handling
            return pd.read_csv(
                input_path, encoding=encoding, sep=options.get("delimiter", "\t")
            )

        else:
            raise ValueError(f"Unsupported input format: {input_format}")

    def _export_data(
        self, df: pd.DataFrame, output_path: Path, output_format: str, options: dict
    ):
        """Export DataFrame to various formats"""
        if output_format == "csv":
            df.to_csv(
                output_path, index=options.get("include_index", False), encoding="utf-8"
            )

        elif output_format == "xlsx":
            df.to_excel(
                output_path,
                index=options.get("include_index", False),
                sheet_name=options.get("sheet_name", "Sheet1"),
            )

        elif output_format == "json":
            orient = options.get("orient", "records")
            df.to_json(output_path, orient=orient, indent=2, force_ascii=False)

        elif output_format == "xml":
            xml_content = self._df_to_xml(df, options)
            output_path.write_text(xml_content, encoding="utf-8")

        elif output_format == "html":
            html = df.to_html(
                index=options.get("include_index", False), classes="table table-striped"
            )
            full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Data Table</title>
<style>
.table {{ border-collapse: collapse; width: 100%; }}
.table th, .table td {{
    border: 1px solid #ddd; padding: 8px; text-align: left;
}}
.table th {{ background-color: #4CAF50; color: white; }}
.table-striped tr:nth-child(even) {{ background-color: #f2f2f2; }}
</style>
</head>
<body>
{html}
</body>
</html>"""
            output_path.write_text(full_html, encoding="utf-8")

        elif output_format == "md":
            md_content = df.to_markdown(index=options.get("include_index", False))
            output_path.write_text(md_content, encoding="utf-8")

        elif output_format == "pdf":
            self._df_to_pdf(df, output_path, options)

        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _df_to_xml(self, df: pd.DataFrame, options: dict) -> str:
        """Convert DataFrame to XML string"""
        root_name = options.get("root_name", "data")
        row_name = options.get("row_name", "row")

        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append(f"<{root_name}>")

        for _, row in df.iterrows():
            lines.append(f"  <{row_name}>")
            for col, val in row.items():
                safe_col = str(col).replace(" ", "_")
                safe_val = str(val) if pd.notna(val) else ""
                lines.append(f"    <{safe_col}>{safe_val}</{safe_col}>")
            lines.append(f"  </{row_name}>")

        lines.append(f"</{root_name}>")
        return "\n".join(lines)

    def _df_to_pdf(self, df: pd.DataFrame, output_path: Path, options: dict):
        """Convert DataFrame to PDF"""
        from weasyprint import HTML

        html = df.to_html(index=options.get("include_index", False), classes="table")

        styled_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: Arial, sans-serif; padding: 20px; }}
.table {{ border-collapse: collapse; width: 100%; font-size: 10px; }}
.table th, .table td {{
    border: 1px solid #333; padding: 6px; text-align: left;
}}
.table th {{ background-color: #4CAF50; color: white; }}
.table tr:nth-child(even) {{ background-color: #f9f9f9; }}
</style>
</head>
<body>
<h1>{options.get("title", "Data Export")}</h1>
{html}
</body>
</html>"""

        HTML(string=styled_html).write_pdf(str(output_path))

    async def get_data_info(self, input_path: Path) -> dict:
        """Get data file information"""
        try:
            input_format = input_path.suffix.lstrip(".").lower()
            df = self._load_data(input_path, input_format, {})

            return {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "dtypes": {str(k): str(v) for k, v in df.dtypes.items()},
                "memory_usage": int(df.memory_usage(deep=True).sum()),
                "null_counts": df.isnull().sum().to_dict(),
            }
        except Exception as e:
            logger.error(f"Failed to get data info: {e}")
            return {}
