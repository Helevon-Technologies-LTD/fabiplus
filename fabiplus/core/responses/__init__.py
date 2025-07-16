"""
Advanced response types and streaming system for FABI+ framework
Handles large datasets, file downloads, real-time streaming, and custom response formats
"""

from .formats import (
    CustomFormatResponse,
    ExcelResponse,
    ImageResponse,
    PDFResponse,
    ZipResponse,
)
from .pagination import (
    CursorPaginatedResponse,
    PaginatedResponse,
    StreamingPaginatedResponse,
)
from .streaming import (
    ChunkedDataResponse,
    ServerSentEventsResponse,
    StreamingCSVResponse,
    StreamingJSONResponse,
    StreamingXMLResponse,
)

# from .compression import (
#     CompressedResponse,
#     GzipResponse,
#     BrotliResponse
# )

# from .caching import (
#     CachedResponse,
#     ETagResponse,
#     ConditionalResponse
# )

# from .realtime import (
#     WebSocketResponse,
#     EventStreamResponse,
#     ProgressResponse
# )

__all__ = [
    # Streaming responses
    "StreamingJSONResponse",
    "StreamingCSVResponse",
    "StreamingXMLResponse",
    "ChunkedDataResponse",
    "ServerSentEventsResponse",
    # Pagination responses
    "PaginatedResponse",
    "CursorPaginatedResponse",
    "StreamingPaginatedResponse",
    # Format responses
    "ExcelResponse",
    "PDFResponse",
    "ImageResponse",
    "ZipResponse",
    "CustomFormatResponse",
    # # Compression responses
    # "CompressedResponse",
    # "GzipResponse",
    # "BrotliResponse",
    # # Caching responses
    # "CachedResponse",
    # "ETagResponse",
    # "ConditionalResponse",
    # # Real-time responses
    # "WebSocketResponse",
    # "EventStreamResponse",
    # "ProgressResponse",
]
