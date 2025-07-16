"""
FABI+ Analytics Plugin
Example plugin that adds analytics endpoints and middleware
"""

import json
import time
from collections import defaultdict, deque
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.auth import User, get_current_staff_user


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """
    Analytics middleware to track API usage
    """

    def __init__(self, app):
        super().__init__(app)
        self.request_stats = defaultdict(int)
        self.response_times = deque(maxlen=1000)  # Keep last 1000 requests
        self.error_count = defaultdict(int)
        self.endpoint_stats = defaultdict(lambda: {"count": 0, "avg_time": 0})

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Track request
        endpoint = f"{request.method} {request.url.path}"
        self.request_stats[endpoint] += 1

        try:
            response = await call_next(request)

            # Track response time
            process_time = time.time() - start_time
            self.response_times.append(process_time)

            # Update endpoint stats
            stats = self.endpoint_stats[endpoint]
            stats["count"] += 1
            stats["avg_time"] = (
                stats["avg_time"] * (stats["count"] - 1) + process_time
            ) / stats["count"]

            # Track errors
            if response.status_code >= 400:
                self.error_count[f"{response.status_code}"] += 1

            return response

        except Exception as e:
            # Track exceptions
            self.error_count["500"] += 1
            raise


# Global analytics middleware instance
analytics_middleware = AnalyticsMiddleware(None)


def create_analytics_router() -> APIRouter:
    """Create analytics router with endpoints"""

    router = APIRouter(prefix="/analytics", tags=["Analytics"])

    @router.get("/stats")
    async def get_analytics_stats(current_user: User = Depends(get_current_staff_user)):
        """Get analytics statistics (staff only)"""

        # Calculate average response time
        avg_response_time = 0
        if analytics_middleware.response_times:
            avg_response_time = sum(analytics_middleware.response_times) / len(
                analytics_middleware.response_times
            )

        return {
            "total_requests": sum(analytics_middleware.request_stats.values()),
            "avg_response_time": round(avg_response_time, 3),
            "error_count": dict(analytics_middleware.error_count),
            "top_endpoints": dict(
                sorted(
                    analytics_middleware.request_stats.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ),
            "endpoint_performance": dict(analytics_middleware.endpoint_stats),
        }

    @router.get("/requests")
    async def get_request_stats(current_user: User = Depends(get_current_staff_user)):
        """Get detailed request statistics"""

        return {
            "request_stats": dict(analytics_middleware.request_stats),
            "total_requests": sum(analytics_middleware.request_stats.values()),
        }

    @router.get("/performance")
    async def get_performance_stats(
        current_user: User = Depends(get_current_staff_user),
    ):
        """Get performance statistics"""

        response_times = list(analytics_middleware.response_times)

        if not response_times:
            return {"message": "No performance data available"}

        # Calculate percentiles
        sorted_times = sorted(response_times)
        length = len(sorted_times)

        p50 = sorted_times[int(length * 0.5)]
        p90 = sorted_times[int(length * 0.9)]
        p95 = sorted_times[int(length * 0.95)]
        p99 = sorted_times[int(length * 0.99)]

        return {
            "total_requests": length,
            "avg_response_time": round(sum(response_times) / length, 3),
            "min_response_time": round(min(response_times), 3),
            "max_response_time": round(max(response_times), 3),
            "percentiles": {
                "p50": round(p50, 3),
                "p90": round(p90, 3),
                "p95": round(p95, 3),
                "p99": round(p99, 3),
            },
        }

    @router.get("/errors")
    async def get_error_stats(current_user: User = Depends(get_current_staff_user)):
        """Get error statistics"""

        return {
            "error_count": dict(analytics_middleware.error_count),
            "total_errors": sum(analytics_middleware.error_count.values()),
        }

    @router.post("/reset")
    async def reset_analytics(current_user: User = Depends(get_current_staff_user)):
        """Reset analytics data (staff only)"""

        analytics_middleware.request_stats.clear()
        analytics_middleware.response_times.clear()
        analytics_middleware.error_count.clear()
        analytics_middleware.endpoint_stats.clear()

        return {"message": "Analytics data reset successfully"}

    return router


def register_plugin(app):
    """
    Register the analytics plugin with the FastAPI app
    This function is called automatically when the plugin is loaded
    """

    # Add analytics middleware
    global analytics_middleware
    analytics_middleware = AnalyticsMiddleware(app)
    app.add_middleware(AnalyticsMiddleware)

    # Add analytics router
    analytics_router = create_analytics_router()
    app.include_router(analytics_router)

    print("✅ Analytics plugin registered successfully")


# Plugin metadata
PLUGIN_NAME = "Analytics"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "API analytics and monitoring plugin"
PLUGIN_AUTHOR = "FABI+ Team"
