"""
Streaming response implementations for large datasets
"""

import asyncio
import csv
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from io import StringIO
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Optional, Union

from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask


class StreamingJSONResponse(StreamingResponse):
    """Stream JSON data for large datasets"""

    def __init__(
        self,
        data_generator: Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]],
        chunk_size: int = 1000,
        total_count: Optional[int] = None,
        include_metadata: bool = True,
        background: Optional[BackgroundTask] = None,
        **kwargs,
    ):
        self.data_generator = data_generator
        self.chunk_size = chunk_size
        self.total_count = total_count
        self.include_metadata = include_metadata

        super().__init__(
            content=self._stream_json(),
            media_type="application/json",
            background=background,
            **kwargs,
        )

    async def _stream_json(self) -> AsyncIterator[str]:
        """Stream JSON data in chunks"""

        # Start JSON response
        if self.include_metadata:
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "total_count": self.total_count,
                "chunk_size": self.chunk_size,
            }
            yield f'{{"metadata": {json.dumps(metadata)}, "data": ['
        else:
            yield '{"data": ['

        first_item = True
        item_count = 0

        # Stream data items
        if hasattr(self.data_generator, "__aiter__"):
            # Async generator
            async for item in self.data_generator:
                if not first_item:
                    yield ","
                yield json.dumps(item)
                first_item = False
                item_count += 1

                # Add newlines for readability in large responses
                if item_count % 100 == 0:
                    yield "\n"
        else:
            # Sync generator
            for item in self.data_generator:
                if not first_item:
                    yield ","
                yield json.dumps(item)
                first_item = False
                item_count += 1

                if item_count % 100 == 0:
                    yield "\n"

        # End JSON response
        if self.include_metadata:
            yield f'], "count": {item_count}}}'
        else:
            yield "]}"


class StreamingCSVResponse(StreamingResponse):
    """Stream CSV data for large datasets"""

    def __init__(
        self,
        data_generator: Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]],
        fieldnames: Optional[List[str]] = None,
        filename: Optional[str] = None,
        include_header: bool = True,
        delimiter: str = ",",
        background: Optional[BackgroundTask] = None,
        **kwargs,
    ):
        self.data_generator = data_generator
        self.fieldnames = fieldnames
        self.include_header = include_header
        self.delimiter = delimiter

        headers = kwargs.get("headers", {})
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        super().__init__(
            content=self._stream_csv(),
            media_type="text/csv",
            headers=headers,
            background=background,
            **kwargs,
        )

    async def _stream_csv(self) -> AsyncIterator[str]:
        """Stream CSV data"""

        buffer = StringIO()
        writer = None
        header_written = False

        if hasattr(self.data_generator, "__aiter__"):
            # Async generator
            async for item in self.data_generator:
                if writer is None:
                    # Initialize writer with fieldnames from first item
                    fieldnames = self.fieldnames or list(item.keys())
                    writer = csv.DictWriter(
                        buffer, fieldnames=fieldnames, delimiter=self.delimiter
                    )

                    if self.include_header and not header_written:
                        writer.writeheader()
                        yield buffer.getvalue()
                        buffer.seek(0)
                        buffer.truncate(0)
                        header_written = True

                writer.writerow(item)

                # Yield buffer content periodically
                if buffer.tell() > 8192:  # 8KB buffer
                    yield buffer.getvalue()
                    buffer.seek(0)
                    buffer.truncate(0)
        else:
            # Sync generator
            for item in self.data_generator:
                if writer is None:
                    fieldnames = self.fieldnames or list(item.keys())
                    writer = csv.DictWriter(
                        buffer, fieldnames=fieldnames, delimiter=self.delimiter
                    )

                    if self.include_header and not header_written:
                        writer.writeheader()
                        yield buffer.getvalue()
                        buffer.seek(0)
                        buffer.truncate(0)
                        header_written = True

                writer.writerow(item)

                if buffer.tell() > 8192:
                    yield buffer.getvalue()
                    buffer.seek(0)
                    buffer.truncate(0)

        # Yield remaining buffer content
        if buffer.tell() > 0:
            yield buffer.getvalue()


class StreamingXMLResponse(StreamingResponse):
    """Stream XML data for large datasets"""

    def __init__(
        self,
        data_generator: Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]],
        root_element: str = "data",
        item_element: str = "item",
        filename: Optional[str] = None,
        background: Optional[BackgroundTask] = None,
        **kwargs,
    ):
        self.data_generator = data_generator
        self.root_element = root_element
        self.item_element = item_element

        headers = kwargs.get("headers", {})
        if filename:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        super().__init__(
            content=self._stream_xml(),
            media_type="application/xml",
            headers=headers,
            background=background,
            **kwargs,
        )

    async def _stream_xml(self) -> AsyncIterator[str]:
        """Stream XML data"""

        # XML declaration and root element
        yield f'<?xml version="1.0" encoding="UTF-8"?>\n<{self.root_element}>\n'

        if hasattr(self.data_generator, "__aiter__"):
            # Async generator
            async for item in self.data_generator:
                yield self._dict_to_xml(item, self.item_element)
                yield "\n"
        else:
            # Sync generator
            for item in self.data_generator:
                yield self._dict_to_xml(item, self.item_element)
                yield "\n"

        # Close root element
        yield f"</{self.root_element}>"

    def _dict_to_xml(self, data: Dict[str, Any], element_name: str) -> str:
        """Convert dictionary to XML element"""
        element = ET.Element(element_name)

        for key, value in data.items():
            if isinstance(value, dict):
                sub_element = ET.SubElement(element, key)
                for sub_key, sub_value in value.items():
                    sub_sub_element = ET.SubElement(sub_element, sub_key)
                    sub_sub_element.text = str(sub_value)
            elif isinstance(value, list):
                for item in value:
                    sub_element = ET.SubElement(element, key)
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            sub_sub_element = ET.SubElement(sub_element, sub_key)
                            sub_sub_element.text = str(sub_value)
                    else:
                        sub_element.text = str(item)
            else:
                sub_element = ET.SubElement(element, key)
                sub_element.text = str(value) if value is not None else ""

        return ET.tostring(element, encoding="unicode")


class ChunkedDataResponse(StreamingResponse):
    """Generic chunked data response for any data type"""

    def __init__(
        self,
        data_source: Callable,
        chunk_size: int = 1000,
        formatter: Optional[Callable[[List[Any]], str]] = None,
        content_type: str = "application/json",
        background: Optional[BackgroundTask] = None,
        **kwargs,
    ):
        self.data_source = data_source
        self.chunk_size = chunk_size
        self.formatter = formatter or self._default_formatter

        super().__init__(
            content=self._stream_chunks(),
            media_type=content_type,
            background=background,
            **kwargs,
        )

    async def _stream_chunks(self) -> AsyncIterator[str]:
        """Stream data in chunks"""
        offset = 0

        while True:
            # Get chunk of data
            if asyncio.iscoroutinefunction(self.data_source):
                chunk = await self.data_source(offset=offset, limit=self.chunk_size)
            else:
                chunk = self.data_source(offset=offset, limit=self.chunk_size)

            if not chunk:
                break

            # Format and yield chunk
            formatted_chunk = self.formatter(chunk)
            yield formatted_chunk

            # If chunk is smaller than chunk_size, we've reached the end
            if len(chunk) < self.chunk_size:
                break

            offset += self.chunk_size

    def _default_formatter(self, chunk: List[Any]) -> str:
        """Default JSON formatter"""
        return json.dumps(chunk) + "\n"


class ServerSentEventsResponse(StreamingResponse):
    """Server-Sent Events response for real-time data streaming"""

    def __init__(
        self,
        event_generator: AsyncIterator[Dict[str, Any]],
        retry_timeout: int = 5000,
        background: Optional[BackgroundTask] = None,
        **kwargs,
    ):
        self.event_generator = event_generator
        self.retry_timeout = retry_timeout

        headers = kwargs.get("headers", {})
        headers.update(
            {
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            }
        )

        super().__init__(
            content=self._stream_events(),
            media_type="text/event-stream",
            headers=headers,
            background=background,
            **kwargs,
        )

    async def _stream_events(self) -> AsyncIterator[str]:
        """Stream Server-Sent Events"""

        # Send retry timeout
        yield f"retry: {self.retry_timeout}\n\n"

        async for event in self.event_generator:
            # Format SSE event
            event_id = event.get("id", "")
            event_type = event.get("event", "message")
            event_data = event.get("data", {})

            if event_id:
                yield f"id: {event_id}\n"

            yield f"event: {event_type}\n"
            yield f"data: {json.dumps(event_data)}\n\n"

    @staticmethod
    def create_event(
        event_type: str, data: Any, event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Helper method to create SSE event"""
        event = {"event": event_type, "data": data}

        if event_id:
            event["id"] = event_id

        return event


class ProgressStreamResponse(StreamingResponse):
    """Stream progress updates for long-running operations"""

    def __init__(
        self,
        operation: Callable,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        background: Optional[BackgroundTask] = None,
        **kwargs,
    ):
        self.operation = operation
        self.progress_callback = progress_callback

        super().__init__(
            content=self._stream_progress(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            background=background,
            **kwargs,
        )

    async def _stream_progress(self) -> AsyncIterator[str]:
        """Stream progress updates"""

        def progress_handler(current: int, total: int, message: str = ""):
            """Internal progress handler"""
            progress_data = {
                "current": current,
                "total": total,
                "percentage": (current / total * 100) if total > 0 else 0,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }

            return f"data: {json.dumps(progress_data)}\n\n"

        try:
            # Start operation
            yield 'event: start\ndata: {"status": "started"}\n\n'

            if asyncio.iscoroutinefunction(self.operation):
                result = await self.operation(progress_callback=progress_handler)
            else:
                result = self.operation(progress_callback=progress_handler)

            # Send completion event
            completion_data = {
                "status": "completed",
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }
            yield f"event: complete\ndata: {json.dumps(completion_data)}\n\n"

        except Exception as e:
            # Send error event
            error_data = {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
