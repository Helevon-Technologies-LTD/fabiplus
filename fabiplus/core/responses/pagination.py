"""
Advanced pagination responses for large datasets
"""

import asyncio
import json
import math
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Optional, Union

from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, func, select

from .streaming import StreamingJSONResponse


class PaginationMetadata(BaseModel):
    """Metadata for paginated responses"""

    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool
    next_page: Optional[int] = None
    prev_page: Optional[int] = None


class CursorMetadata(BaseModel):
    """Metadata for cursor-based pagination"""

    has_next: bool
    has_prev: bool
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    total_items: Optional[int] = None


class PaginatedResponse(JSONResponse):
    """Standard paginated response with offset/limit"""

    def __init__(
        self,
        data: List[Any],
        page: int = 1,
        per_page: int = 50,
        total_items: int = 0,
        include_metadata: bool = True,
        **kwargs,
    ):
        self.data = data
        self.page = page
        self.per_page = per_page
        self.total_items = total_items

        # Calculate pagination metadata
        total_pages = math.ceil(total_items / per_page) if per_page > 0 else 1
        has_next = page < total_pages
        has_prev = page > 1

        metadata = PaginationMetadata(
            page=page,
            per_page=per_page,
            total_items=total_items,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
            next_page=page + 1 if has_next else None,
            prev_page=page - 1 if has_prev else None,
        )

        # Construct response content
        if include_metadata:
            content = {
                "data": data,
                "metadata": metadata.model_dump(),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            content = {"data": data}

        super().__init__(content=content, **kwargs)

    @classmethod
    def from_query(
        cls, query, session: Session, page: int = 1, per_page: int = 50, **kwargs
    ):
        """Create paginated response from SQLModel query"""

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_items = session.exec(count_query).one()

        # Apply pagination to query
        offset = (page - 1) * per_page
        paginated_query = query.offset(offset).limit(per_page)

        # Execute query
        data = session.exec(paginated_query).all()

        return cls(
            data=data, page=page, per_page=per_page, total_items=total_items, **kwargs
        )


class CursorPaginatedResponse(JSONResponse):
    """Cursor-based pagination for large datasets"""

    def __init__(
        self,
        data: List[Any],
        cursor_field: str = "id",
        next_cursor: Optional[str] = None,
        prev_cursor: Optional[str] = None,
        has_next: bool = False,
        has_prev: bool = False,
        total_items: Optional[int] = None,
        include_metadata: bool = True,
        **kwargs,
    ):
        self.data = data
        self.cursor_field = cursor_field

        metadata = CursorMetadata(
            has_next=has_next,
            has_prev=has_prev,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            total_items=total_items,
        )

        if include_metadata:
            content = {
                "data": data,
                "metadata": metadata.model_dump(),
                "cursor_field": cursor_field,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            content = {"data": data}

        super().__init__(content=content, **kwargs)

    @classmethod
    def from_query(
        cls,
        query,
        session: Session,
        cursor: Optional[str] = None,
        limit: int = 50,
        cursor_field: str = "id",
        direction: str = "next",
        **kwargs,
    ):
        """Create cursor paginated response from SQLModel query"""

        # Apply cursor filtering
        if cursor:
            if direction == "next":
                query = query.where(
                    getattr(query.column_descriptions[0]["type"], cursor_field) > cursor
                )
            else:  # prev
                query = query.where(
                    getattr(query.column_descriptions[0]["type"], cursor_field) < cursor
                )
                query = query.order_by(
                    getattr(query.column_descriptions[0]["type"], cursor_field).desc()
                )

        # Get one extra item to check if there's a next page
        data = session.exec(query.limit(limit + 1)).all()

        has_next = len(data) > limit
        if has_next:
            data = data[:-1]  # Remove the extra item

        # Determine cursors
        next_cursor = None
        prev_cursor = None

        if data:
            if has_next:
                next_cursor = str(getattr(data[-1], cursor_field))
            if cursor:  # If we have a cursor, there's a previous page
                prev_cursor = str(getattr(data[0], cursor_field))

        return cls(
            data=data,
            cursor_field=cursor_field,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            has_next=has_next,
            has_prev=bool(cursor),
            **kwargs,
        )


class StreamingPaginatedResponse(StreamingJSONResponse):
    """Streaming response with automatic pagination for very large datasets"""

    def __init__(
        self,
        query_function: Callable,
        page_size: int = 1000,
        total_count: Optional[int] = None,
        include_progress: bool = True,
        **kwargs,
    ):
        self.query_function = query_function
        self.page_size = page_size
        self.include_progress = include_progress

        super().__init__(
            data_generator=self._paginated_generator(),
            chunk_size=page_size,
            total_count=total_count,
            **kwargs,
        )

    async def _paginated_generator(self) -> AsyncIterator[Dict[str, Any]]:
        """Generate data with automatic pagination"""

        page = 1
        total_yielded = 0

        while True:
            # Get page of data
            if asyncio.iscoroutinefunction(self.query_function):
                page_data = await self.query_function(
                    page=page, per_page=self.page_size
                )
            else:
                page_data = self.query_function(page=page, per_page=self.page_size)

            if not page_data:
                break

            # Yield each item in the page
            for item in page_data:
                if self.include_progress:
                    # Add progress information to each item
                    yield {
                        **item,
                        "_pagination": {
                            "page": page,
                            "item_in_page": (total_yielded % self.page_size) + 1,
                            "total_yielded": total_yielded + 1,
                        },
                    }
                else:
                    yield item

                total_yielded += 1

            # If page is smaller than page_size, we've reached the end
            if len(page_data) < self.page_size:
                break

            page += 1


class InfiniteScrollResponse(JSONResponse):
    """Response optimized for infinite scroll interfaces"""

    def __init__(
        self,
        data: List[Any],
        last_id: Optional[str] = None,
        has_more: bool = False,
        batch_size: int = 20,
        **kwargs,
    ):
        self.data = data
        self.last_id = last_id
        self.has_more = has_more
        self.batch_size = batch_size

        content = {
            "data": data,
            "pagination": {
                "last_id": last_id,
                "has_more": has_more,
                "batch_size": batch_size,
                "count": len(data),
            },
            "timestamp": datetime.now().isoformat(),
        }

        super().__init__(content=content, **kwargs)

    @classmethod
    def from_query(
        cls,
        query,
        session: Session,
        last_id: Optional[str] = None,
        batch_size: int = 20,
        id_field: str = "id",
        **kwargs,
    ):
        """Create infinite scroll response from query"""

        # Apply last_id filtering
        if last_id:
            query = query.where(
                getattr(query.column_descriptions[0]["type"], id_field) > last_id
            )

        # Get one extra item to check if there are more
        data = session.exec(query.limit(batch_size + 1)).all()

        has_more = len(data) > batch_size
        if has_more:
            data = data[:-1]  # Remove the extra item

        # Get the last ID for next request
        new_last_id = str(getattr(data[-1], id_field)) if data else None

        return cls(
            data=data,
            last_id=new_last_id,
            has_more=has_more,
            batch_size=batch_size,
            **kwargs,
        )


class SearchPaginatedResponse(PaginatedResponse):
    """Paginated response with search metadata"""

    def __init__(
        self,
        data: List[Any],
        search_query: str,
        search_fields: List[str],
        search_time_ms: float,
        facets: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        **kwargs,
    ):
        self.search_query = search_query
        self.search_fields = search_fields
        self.search_time_ms = search_time_ms
        self.facets = facets or {}
        self.suggestions = suggestions or []

        super().__init__(data=data, **kwargs)

        # Add search metadata to response
        if isinstance(self.body, bytes):
            content = json.loads(self.body.decode())
        else:
            content = self.body

        content["search"] = {
            "query": search_query,
            "fields": search_fields,
            "time_ms": search_time_ms,
            "facets": facets,
            "suggestions": suggestions,
        }

        self.body = json.dumps(content).encode()


class AggregatedPaginatedResponse(PaginatedResponse):
    """Paginated response with aggregation data"""

    def __init__(
        self,
        data: List[Any],
        aggregations: Dict[str, Any],
        group_by: Optional[str] = None,
        **kwargs,
    ):
        self.aggregations = aggregations
        self.group_by = group_by

        super().__init__(data=data, **kwargs)

        # Add aggregation metadata to response
        if isinstance(self.body, bytes):
            content = json.loads(self.body.decode())
        else:
            content = self.body

        content["aggregations"] = aggregations
        if group_by:
            content["group_by"] = group_by

        self.body = json.dumps(content).encode()
