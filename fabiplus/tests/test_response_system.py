"""
Tests for FABI+ Response Types & Streaming System
Tests streaming responses, pagination, format responses, and large dataset handling
"""

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fabiplus.core.responses.formats import (
    CustomFormatResponse,
    ExcelResponse,
    ImageResponse,
    PDFResponse,
    ZipResponse,
)
from fabiplus.core.responses.pagination import (
    CursorPaginatedResponse,
    InfiniteScrollResponse,
    PaginatedResponse,
    StreamingPaginatedResponse,
)
from fabiplus.core.responses.streaming import (
    ChunkedDataResponse,
    ServerSentEventsResponse,
    StreamingCSVResponse,
    StreamingJSONResponse,
    StreamingXMLResponse,
)


class TestStreamingResponses:
    """Test streaming response implementations"""

    def test_streaming_json_response_creation(self):
        """Test StreamingJSONResponse creation"""

        def data_generator():
            for i in range(5):
                yield {"id": i, "name": f"Item {i}"}

        response = StreamingJSONResponse(
            data_generator=data_generator(), chunk_size=2, total_count=5
        )

        assert response.media_type == "application/json"
        assert response.status_code == 200

    async def test_streaming_json_content(self):
        """Test StreamingJSONResponse content generation"""

        async def async_data_generator():
            for i in range(3):
                yield {"id": i, "value": f"test_{i}"}

        response = StreamingJSONResponse(
            data_generator=async_data_generator(), include_metadata=True
        )

        # Collect streamed content
        content_chunks = []
        async for chunk in response.body_iterator:
            content_chunks.append(chunk)

        full_content = "".join(content_chunks)

        # Verify it's valid JSON
        parsed = json.loads(full_content)
        assert "metadata" in parsed
        assert "data" in parsed
        assert len(parsed["data"]) == 3
        assert parsed["count"] == 3

    def test_streaming_csv_response_creation(self):
        """Test StreamingCSVResponse creation"""

        def data_generator():
            yield {"name": "John", "age": 30}
            yield {"name": "Jane", "age": 25}

        response = StreamingCSVResponse(
            data_generator=data_generator(), filename="test.csv", include_header=True
        )

        assert response.media_type == "text/csv"
        assert "attachment" in response.headers["Content-Disposition"]

    async def test_streaming_csv_content(self):
        """Test StreamingCSVResponse content generation"""

        def data_generator():
            yield {"name": "Alice", "score": 95}
            yield {"name": "Bob", "score": 87}

        response = StreamingCSVResponse(
            data_generator=data_generator(), include_header=True
        )

        # Collect streamed content
        content_chunks = []
        async for chunk in response.body_iterator:
            content_chunks.append(chunk)

        full_content = "".join(content_chunks)
        lines = full_content.strip().split("\n")

        # Should have header + 2 data rows
        assert len(lines) >= 2
        assert "name" in lines[0]  # Header
        assert "Alice" in full_content
        assert "Bob" in full_content

    def test_streaming_xml_response_creation(self):
        """Test StreamingXMLResponse creation"""

        def data_generator():
            yield {"id": 1, "title": "Test Item"}

        response = StreamingXMLResponse(
            data_generator=data_generator(), root_element="items", item_element="item"
        )

        assert response.media_type == "application/xml"

    async def test_server_sent_events_response(self):
        """Test ServerSentEventsResponse"""

        async def event_generator():
            yield {"event": "message", "data": {"text": "Hello"}}
            yield {"event": "update", "data": {"count": 42}}

        response = ServerSentEventsResponse(event_generator=event_generator())

        assert response.media_type == "text/event-stream"
        assert "no-cache" in response.headers["Cache-Control"]

    async def test_chunked_data_response(self):
        """Test ChunkedDataResponse"""

        def data_source(offset=0, limit=10):
            # Simulate database query
            data = [
                {"id": i, "value": f"item_{i}"} for i in range(offset, offset + limit)
            ]
            return data[:3] if offset == 0 else []  # Return 3 items first, then empty

        response = ChunkedDataResponse(data_source=data_source, chunk_size=10)

        assert response.media_type == "application/json"


class TestPaginationResponses:
    """Test pagination response implementations"""

    def test_paginated_response_creation(self):
        """Test PaginatedResponse creation"""

        data = [{"id": i, "name": f"Item {i}"} for i in range(10)]

        response = PaginatedResponse(data=data, page=1, per_page=10, total_items=50)

        assert response.status_code == 200

        # Parse response content
        content = json.loads(response.body.decode())
        assert "data" in content
        assert "metadata" in content
        assert content["metadata"]["total_pages"] == 5
        assert content["metadata"]["has_next"] is True

    def test_cursor_paginated_response_creation(self):
        """Test CursorPaginatedResponse creation"""

        data = [{"id": i, "name": f"Item {i}"} for i in range(5)]

        response = CursorPaginatedResponse(
            data=data, cursor_field="id", next_cursor="5", has_next=True, has_prev=False
        )

        content = json.loads(response.body.decode())
        assert content["metadata"]["next_cursor"] == "5"
        assert content["metadata"]["has_next"] is True

    def test_infinite_scroll_response_creation(self):
        """Test InfiniteScrollResponse creation"""

        data = [{"id": i, "content": f"Post {i}"} for i in range(20)]

        response = InfiniteScrollResponse(
            data=data, last_id="19", has_more=True, batch_size=20
        )

        content = json.loads(response.body.decode())
        assert content["pagination"]["last_id"] == "19"
        assert content["pagination"]["has_more"] is True
        assert content["pagination"]["count"] == 20

    async def test_streaming_paginated_response(self):
        """Test StreamingPaginatedResponse"""

        def query_function(page=1, per_page=10):
            # Simulate paginated data source
            start = (page - 1) * per_page
            if start >= 25:  # Total of 25 items
                return []

            end = min(start + per_page, 25)
            return [{"id": i, "data": f"item_{i}"} for i in range(start, end)]

        response = StreamingPaginatedResponse(
            query_function=query_function, page_size=10, total_count=25
        )

        assert response.media_type == "application/json"


class TestFormatResponses:
    """Test format response implementations"""

    def test_excel_response_creation(self):
        """Test ExcelResponse creation"""

        data = [
            {"name": "John", "age": 30, "city": "New York"},
            {"name": "Jane", "age": 25, "city": "Los Angeles"},
        ]

        response = ExcelResponse(data=data, filename="test.xlsx")

        assert (
            response.media_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "test.xlsx" in response.headers["Content-Disposition"]

    def test_pdf_response_creation(self):
        """Test PDFResponse creation"""

        content = "This is a test PDF document.\nWith multiple lines."

        response = PDFResponse(content=content, filename="test.pdf")

        assert response.media_type == "application/pdf"
        assert "test.pdf" in response.headers["Content-Disposition"]

    def test_image_response_creation(self):
        """Test ImageResponse creation"""

        data = [
            {"category": "A", "value": 10},
            {"category": "B", "value": 20},
            {"category": "C", "value": 15},
        ]

        response = ImageResponse(
            data=data, chart_type="bar", width=800, height=600, format="PNG"
        )

        assert response.media_type == "image/png"

    def test_zip_response_creation(self):
        """Test ZipResponse creation"""

        files = {
            "file1.txt": "Content of file 1",
            "file2.txt": b"Binary content of file 2",
            "data.json": json.dumps({"key": "value"}),
        }

        response = ZipResponse(files=files, filename="archive.zip")

        assert response.media_type == "application/zip"
        assert "archive.zip" in response.headers["Content-Disposition"]

    def test_custom_format_response_creation(self):
        """Test CustomFormatResponse creation"""

        def custom_formatter(data):
            # Custom format: pipe-separated values
            lines = []
            for item in data:
                line = "|".join(str(v) for v in item.values())
                lines.append(line)
            return "\n".join(lines)

        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]

        response = CustomFormatResponse(
            data=data,
            formatter=custom_formatter,
            content_type="text/plain",
            filename="custom.txt",
        )

        assert response.media_type == "text/plain"
        assert "custom.txt" in response.headers["Content-Disposition"]


class TestResponseIntegration:
    """Integration tests for response system"""

    def setup_method(self):
        """Setup test FastAPI app"""
        self.app = FastAPI()
        self.client = TestClient(self.app)

    def test_streaming_json_endpoint(self):
        """Test streaming JSON endpoint integration"""

        @self.app.get("/stream-json")
        async def stream_json():
            def data_gen():
                for i in range(100):
                    yield {"id": i, "value": f"item_{i}"}

            return StreamingJSONResponse(data_generator=data_gen(), chunk_size=10)

        response = self.client.get("/stream-json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_paginated_endpoint(self):
        """Test paginated endpoint integration"""

        @self.app.get("/paginated")
        async def paginated_data(page: int = 1, per_page: int = 10):
            # Mock data
            total_items = 100
            start = (page - 1) * per_page
            end = start + per_page
            data = [
                {"id": i, "name": f"Item {i}"}
                for i in range(start, min(end, total_items))
            ]

            return PaginatedResponse(
                data=data, page=page, per_page=per_page, total_items=total_items
            )

        response = self.client.get("/paginated?page=2&per_page=5")
        assert response.status_code == 200

        data = response.json()
        assert data["metadata"]["page"] == 2
        assert data["metadata"]["per_page"] == 5
        assert len(data["data"]) == 5

    def test_csv_export_endpoint(self):
        """Test CSV export endpoint integration"""

        @self.app.get("/export-csv")
        async def export_csv():
            def data_gen():
                for i in range(10):
                    yield {
                        "id": i,
                        "name": f"User {i}",
                        "email": f"user{i}@example.com",
                    }

            return StreamingCSVResponse(data_generator=data_gen(), filename="users.csv")

        response = self.client.get("/export-csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"
        assert "users.csv" in response.headers["content-disposition"]


class TestPerformance:
    """Performance tests for response system"""

    async def test_large_dataset_streaming(self):
        """Test streaming performance with large datasets"""

        async def large_data_generator():
            for i in range(10000):  # 10K items
                yield {"id": i, "data": f"item_{i}" * 10}  # Larger items

        response = StreamingJSONResponse(
            data_generator=large_data_generator(), chunk_size=1000
        )

        # Test that response is created quickly
        assert response.media_type == "application/json"

        # Test streaming (would need actual timing in real scenario)
        chunk_count = 0
        async for chunk in response.body_iterator:
            chunk_count += 1
            if chunk_count > 5:  # Just test first few chunks
                break

        assert chunk_count > 0

    def test_pagination_performance(self):
        """Test pagination performance"""

        # Large dataset
        large_data = [{"id": i, "value": f"item_{i}"} for i in range(1000)]

        response = PaginatedResponse(
            data=large_data, page=1, per_page=50, total_items=10000
        )

        assert response.status_code == 200

        # Response should be created quickly even with large total_items
        content = json.loads(response.body.decode())
        assert len(content["data"]) == 1000  # All data included
        assert content["metadata"]["total_items"] == 10000


class TestErrorHandling:
    """Test error handling in response system"""

    async def test_streaming_error_handling(self):
        """Test error handling in streaming responses"""

        async def failing_generator():
            yield {"id": 1, "data": "good"}
            raise ValueError("Something went wrong")
            yield {"id": 2, "data": "never reached"}

        response = StreamingJSONResponse(data_generator=failing_generator())

        # Should handle errors gracefully
        chunks = []
        try:
            async for chunk in response.body_iterator:
                chunks.append(chunk)
        except Exception:
            pass  # Expected to fail

        # Should have gotten at least the first chunk
        assert len(chunks) > 0

    def test_format_response_error_handling(self):
        """Test error handling in format responses"""

        # Test with invalid data for Excel
        invalid_data = {"not": "a list"}

        response = ExcelResponse(data=invalid_data, filename="test.xlsx")

        # Should create response even with invalid data
        assert (
            response.media_type
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
