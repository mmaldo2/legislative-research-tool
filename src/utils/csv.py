"""Shared CSV utilities — sanitization, formatting, and response helpers."""

import csv
import io
import re
from collections.abc import Sequence

from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# OWASP CSV injection: cells starting with =, +, -, @, tab, CR, pipe, semicolon
CSV_FORMULA_RE = re.compile(r"^[=+\-@\t\r|;]")


def sanitize_csv(value: str) -> str:
    """Prepend a single quote to values that could trigger spreadsheet formula injection."""
    if CSV_FORMULA_RE.match(value):
        return "'" + value
    return value


def trend_to_csv(data: Sequence[BaseModel], columns: list[str]) -> str:
    """Convert trend data points to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for point in data:
        row = [sanitize_csv(str(getattr(point, col, ""))) for col in columns]
        writer.writerow(row)
    output.seek(0)
    return output.getvalue()


def csv_response(csv_content: str, filename: str) -> StreamingResponse:
    """Create a StreamingResponse with CSV content and RFC 6266 quoted filename."""
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
