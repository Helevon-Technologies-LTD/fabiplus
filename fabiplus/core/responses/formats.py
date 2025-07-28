"""
Custom format responses for different file types
"""

import asyncio
import io
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, BinaryIO, Callable, Dict, List, Optional, Union

from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask


class ExcelResponse(StreamingResponse):
    """Generate Excel files from data"""

    def __init__(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]],
        filename: str = "export.xlsx",
        sheet_names: Optional[List[str]] = None,
        include_index: bool = False,
        background: Optional[BackgroundTask] = None,
        **kwargs: Any,
    ) -> None:
        self.data = data
        self.filename = filename
        self.sheet_names = sheet_names
        self.include_index = include_index

        headers = kwargs.get("headers", {})
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        super().__init__(
            content=self._generate_excel(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
            background=background,
            **kwargs,
        )

    async def _generate_excel(self) -> AsyncGenerator[bytes, None]:
        """Generate Excel file content"""
        try:
            from io import BytesIO

            import pandas as pd

            buffer = BytesIO()

            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                if isinstance(self.data, dict):
                    # Multiple sheets
                    for i, (sheet_name, sheet_data) in enumerate(self.data.items()):
                        df = pd.DataFrame(sheet_data)
                        actual_sheet_name = (
                            self.sheet_names[i]
                            if self.sheet_names and i < len(self.sheet_names)
                            else sheet_name
                        )
                        df.to_excel(
                            writer,
                            sheet_name=actual_sheet_name,
                            index=self.include_index,
                        )
                else:
                    # Single sheet
                    df = pd.DataFrame(self.data)
                    sheet_name = self.sheet_names[0] if self.sheet_names else "Sheet1"
                    df.to_excel(writer, sheet_name=sheet_name, index=self.include_index)

            buffer.seek(0)

            # Stream the content
            while True:
                chunk = buffer.read(8192)
                if not chunk:
                    break
                yield chunk

        except ImportError:
            # Fallback if pandas/openpyxl not available
            yield b"Error: pandas and openpyxl required for Excel export"


class PDFResponse(StreamingResponse):
    """Generate PDF files from data"""

    def __init__(
        self,
        content: Union[str, Dict[str, Any]],
        filename: str = "document.pdf",
        template: Optional[str] = None,
        orientation: str = "portrait",
        page_size: str = "A4",
        background: Optional[BackgroundTask] = None,
        **kwargs: Any,
    ) -> None:
        self.content = content
        self.filename = filename
        self.template = template
        self.orientation = orientation
        self.page_size = page_size

        headers = kwargs.get("headers", {})
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        super().__init__(
            content=self._generate_pdf(),
            media_type="application/pdf",
            headers=headers,
            background=background,
            **kwargs,
        )

    async def _generate_pdf(self) -> AsyncGenerator[bytes, None]:
        """Generate PDF content"""
        try:
            from io import BytesIO

            from reportlab.lib.pagesizes import A4, letter
            from reportlab.pdfgen import canvas

            buffer = BytesIO()

            # Set page size
            page_size_map = {"A4": A4, "letter": letter}
            size = page_size_map.get(self.page_size, A4)

            # Create PDF
            p = canvas.Canvas(buffer, pagesize=size)

            if isinstance(self.content, str):
                # Simple text content
                text_lines = self.content.split("\n")
                y_position = size[1] - 50  # Start from top

                for line in text_lines:
                    p.drawString(50, y_position, line)
                    y_position -= 20

                    # Start new page if needed
                    if y_position < 50:
                        p.showPage()
                        y_position = size[1] - 50

            elif isinstance(self.content, dict):
                # Structured content
                y_position = size[1] - 50

                for key, value in self.content.items():
                    p.drawString(50, y_position, f"{key}: {value}")
                    y_position -= 20

                    if y_position < 50:
                        p.showPage()
                        y_position = size[1] - 50

            p.save()
            buffer.seek(0)

            # Stream the content
            while True:
                chunk = buffer.read(8192)
                if not chunk:
                    break
                yield chunk

        except ImportError:
            # Fallback if reportlab not available
            yield b"Error: reportlab required for PDF generation"


class ImageResponse(Response):
    """Generate images from data (charts, graphs, etc.)"""

    def __init__(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        chart_type: str = "bar",
        width: int = 800,
        height: int = 600,
        format: str = "PNG",
        filename: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.data = data
        self.chart_type = chart_type
        self.width = width
        self.height = height
        self.format = format.upper()

        # Generate image content
        content = self._generate_image()

        # Set headers
        headers = kwargs.get("headers", {})
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        media_type = f"image/{format.lower()}"

        super().__init__(
            content=content, media_type=media_type, headers=headers, **kwargs
        )

    def _generate_image(self) -> bytes:
        """Generate image content"""
        try:
            import matplotlib
            import matplotlib.pyplot as plt

            matplotlib.use("Agg")  # Use non-interactive backend
            from io import BytesIO

            buffer = BytesIO()

            # Create figure
            fig, ax = plt.subplots(figsize=(self.width / 100, self.height / 100))

            if isinstance(self.data, list) and self.data:
                # Extract data for plotting
                if isinstance(self.data[0], dict):
                    keys = list(self.data[0].keys())
                    if len(keys) >= 2:
                        x_data = [item[keys[0]] for item in self.data]
                        y_data = [item[keys[1]] for item in self.data]

                        if self.chart_type == "bar":
                            ax.bar(x_data, y_data)
                        elif self.chart_type == "line":
                            ax.plot(x_data, y_data)
                        elif self.chart_type == "scatter":
                            ax.scatter(x_data, y_data)

                        ax.set_xlabel(keys[0])
                        ax.set_ylabel(keys[1])

            plt.title(f"{self.chart_type.title()} Chart")
            plt.tight_layout()

            # Save to buffer
            plt.savefig(buffer, format=self.format, dpi=100, bbox_inches="tight")
            plt.close()

            buffer.seek(0)
            return buffer.getvalue()

        except ImportError:
            # Fallback if matplotlib not available
            return b"Error: matplotlib required for image generation"


class ZipResponse(StreamingResponse):
    """Create ZIP archives from multiple files/data"""

    def __init__(
        self,
        files: Dict[str, Union[bytes, str, BinaryIO]],
        filename: str = "archive.zip",
        compression: int = zipfile.ZIP_DEFLATED,
        background: Optional[BackgroundTask] = None,
        **kwargs: Any,
    ) -> None:
        self.files = files
        self.filename = filename
        self.compression = compression

        headers = kwargs.get("headers", {})
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        super().__init__(
            content=self._generate_zip(),
            media_type="application/zip",
            headers=headers,
            background=background,
            **kwargs,
        )

    async def _generate_zip(self) -> AsyncGenerator[bytes, None]:
        """Generate ZIP file content"""
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, "w", compression=self.compression) as zip_file:
            for filename, content in self.files.items():
                if isinstance(content, str):
                    # String content
                    zip_file.writestr(filename, content.encode("utf-8"))
                elif isinstance(content, bytes):
                    # Bytes content
                    zip_file.writestr(filename, content)
                elif hasattr(content, "read"):
                    # File-like object
                    zip_file.writestr(filename, content.read())
                else:
                    # Convert to string
                    zip_file.writestr(filename, str(content).encode("utf-8"))

        buffer.seek(0)

        # Stream the content
        while True:
            chunk = buffer.read(8192)
            if not chunk:
                break
            yield chunk


class CustomFormatResponse(StreamingResponse):
    """Generic custom format response with user-defined formatter"""

    def __init__(
        self,
        data: Any,
        formatter: Callable[[Any], bytes],
        content_type: str,
        filename: Optional[str] = None,
        background: Optional[BackgroundTask] = None,
        **kwargs: Any,
    ) -> None:
        self.data = data
        self.formatter = formatter

        headers = kwargs.get("headers", {})
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        super().__init__(
            content=self._generate_content(),
            media_type=content_type,
            headers=headers,
            background=background,
            **kwargs,
        )

    async def _generate_content(self) -> AsyncGenerator[bytes, None]:
        """Generate content using custom formatter"""
        try:
            if asyncio.iscoroutinefunction(self.formatter):
                content = await self.formatter(self.data)
            else:
                content = self.formatter(self.data)

            if isinstance(content, str):
                yield content.encode("utf-8")
            elif isinstance(content, bytes):
                yield content
            elif hasattr(content, "__iter__"):
                # Iterable content
                for chunk in content:
                    if isinstance(chunk, str):
                        yield chunk.encode("utf-8")
                    elif isinstance(chunk, bytes):
                        yield chunk
                    else:
                        yield str(chunk).encode("utf-8")
            else:
                yield str(content).encode("utf-8")

        except Exception as e:
            yield f"Error in custom formatter: {str(e)}".encode("utf-8")


import asyncio


class TemplatedResponse(StreamingResponse):
    """Response using Jinja2 templates"""

    def __init__(
        self,
        template_name: str,
        context: Dict[str, Any],
        content_type: str = "text/html",
        filename: Optional[str] = None,
        template_dir: Optional[str] = None,
        background: Optional[BackgroundTask] = None,
        **kwargs: Any,
    ) -> None:
        self.template_name = template_name
        self.context = context
        self.template_dir = template_dir

        headers = kwargs.get("headers", {})
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        super().__init__(
            content=self._render_template(),
            media_type=content_type,
            headers=headers,
            background=background,
            **kwargs,
        )

    async def _render_template(self) -> AsyncGenerator[bytes, None]:
        """Render template with context"""
        try:
            from jinja2 import Environment, FileSystemLoader, Template

            if self.template_dir:
                # Load from file
                env = Environment(loader=FileSystemLoader(self.template_dir))
                template = env.get_template(self.template_name)
            else:
                # Treat template_name as template string
                template = Template(self.template_name)

            rendered = template.render(**self.context)
            yield rendered.encode("utf-8")

        except ImportError:
            yield b"Error: jinja2 required for template rendering"
        except Exception as e:
            yield f"Template rendering error: {str(e)}".encode("utf-8")
