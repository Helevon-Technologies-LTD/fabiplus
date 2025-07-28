"""
FABI+ Framework Admin UI Routes
Web interface for admin functionality using HTMX and Jinja2 templates
"""

import asyncio
import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union, get_args, get_origin

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import func, select

from ..conf.settings import settings
from ..core.auth import auth_backend
from ..core.models import BaseModel, ModelRegistry, User
from ..core.views import FilterParams, PaginationParams, SortParams
from .routes import AdminView


def process_form_data(
    data: Dict[str, Any], model_class: Type[BaseModel]
) -> Dict[str, Any]:
    """Process form data to convert string values to appropriate types"""
    processed_data = {}

    # Get model field information
    for field_name, field_info in model_class.model_fields.items():
        if field_name not in data:
            continue

        field_value = data[field_name]
        field_annotation = getattr(
            field_info, "annotation", getattr(field_info, "type_", str)
        )

        # Handle Optional types
        origin = get_origin(field_annotation)
        if origin is Union:
            args = get_args(field_annotation)
            # Remove NoneType from Union to get the actual type
            non_none_args = [arg for arg in args if arg is not type(None)]
            if non_none_args:
                field_annotation = non_none_args[0]

        # Skip empty strings for optional fields
        if field_value == "" and origin is Union:
            continue

        # Process based on field type
        try:
            if field_annotation is bool:
                # Handle boolean fields
                if field_name + "_unchecked" in data:
                    # This is a checkbox field
                    processed_data[field_name] = field_value == "true"
                else:
                    # Direct boolean value
                    processed_data[field_name] = (
                        field_value.lower() in ("true", "1", "on", "yes")
                        if isinstance(field_value, str)
                        else bool(field_value)
                    )

            elif field_annotation is int:
                # Handle integer fields
                if field_value != "":
                    processed_data[field_name] = int(field_value)

            elif field_annotation is float:
                # Handle float fields
                if field_value != "":
                    processed_data[field_name] = float(field_value)

            elif field_annotation is Decimal:
                # Handle decimal fields
                if field_value != "":
                    processed_data[field_name] = Decimal(str(field_value))

            elif field_annotation is date:
                # Handle date fields
                if field_value != "":
                    if isinstance(field_value, str):
                        processed_data[field_name] = datetime.strptime(
                            field_value, "%Y-%m-%d"
                        ).date()
                    else:
                        processed_data[field_name] = field_value

            elif field_annotation is datetime:
                # Handle datetime fields
                if field_value != "":
                    if isinstance(field_value, str):
                        # Handle datetime-local format
                        processed_data[field_name] = datetime.strptime(
                            field_value, "%Y-%m-%dT%H:%M"
                        )
                    else:
                        processed_data[field_name] = field_value

            elif field_annotation is uuid.UUID:
                # Handle UUID fields
                if field_value != "":
                    processed_data[field_name] = (
                        uuid.UUID(field_value)
                        if isinstance(field_value, str)
                        else field_value
                    )

            else:
                # Handle string and other fields
                if field_value != "":
                    processed_data[field_name] = field_value

        except (ValueError, TypeError):
            # If conversion fails, keep the original value and let the model validation handle it
            if field_value != "":
                processed_data[field_name] = field_value

    # Remove the _unchecked fields that were used for boolean processing
    processed_data = {
        k: v for k, v in processed_data.items() if not k.endswith("_unchecked")
    }

    return processed_data


# Setup templates
ADMIN_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(ADMIN_TEMPLATES_DIR))


# Helper function to get current user from session/cookie
async def get_current_user_optional(request: Request) -> Optional[User]:
    """Get current user from session cookie, return None if not authenticated"""
    try:
        # Try to get token from cookie
        token = request.cookies.get("admin_token")
        if not token:
            return None

        # Verify token and get user
        from jose import JWTError, jwt

        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None

        # Get user from database
        with ModelRegistry.get_session() as session:
            user = session.get(User, user_id)
            if not user or not user.is_staff:
                return None
            return user

    except (JWTError, Exception):
        return None


# Helper function to require authentication
async def require_staff_user(request: Request):
    """Require staff user authentication, redirect to login if not authenticated"""
    user = await get_current_user_optional(request)
    if not user:
        # Redirect to login page
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": f"{settings.ADMIN_PREFIX}/login/"},
        )
    return user


def get_dashboard_data(current_user):
    """Get dashboard data for sidebar navigation"""
    models = ModelRegistry.get_all_models()
    dashboard_data = {"user": current_user, "models": [], "statistics": {}}

    # Get model statistics
    for model_name, model_class in models.items():
        admin_view = AdminView(model_class)
        model_info = admin_view.get_model_info()

        # Get count for this model
        try:
            with ModelRegistry.get_session() as session:
                count = session.exec(
                    select(func.count()).select_from(model_class)
                ).first()
                model_info["count"] = count or 0
        except Exception:
            model_info["count"] = 0

        model_info["url"] = f"{settings.ADMIN_PREFIX}/{model_name}/"
        dashboard_data["models"].append(model_info)

    # Add system monitoring for superusers
    dashboard_data["system_tools"] = []
    if current_user and current_user.is_superuser:
        dashboard_data["system_tools"] = [
            {
                "name": "activities",
                "verbose_name": "Activities",
                "url": f"{settings.ADMIN_PREFIX}/activities/",
                "icon": "bi-activity",
                "description": "Monitor user activities and system events",
            },
            {
                "name": "logs",
                "verbose_name": "Server Logs",
                "url": f"{settings.ADMIN_PREFIX}/logs/",
                "icon": "bi-terminal",
                "description": "View live server logs",
            },
            {
                "name": "settings",
                "verbose_name": "System Settings",
                "url": f"{settings.ADMIN_PREFIX}/settings/",
                "icon": "bi-gear",
                "description": "Configure application settings",
            },
            {
                "name": "analytics",
                "verbose_name": "Analytics",
                "url": f"{settings.ADMIN_PREFIX}/analytics/",
                "icon": "bi-graph-up",
                "description": "View system analytics and reports",
            },
            {
                "name": "security",
                "verbose_name": "Security",
                "url": f"{settings.ADMIN_PREFIX}/security/",
                "icon": "bi-shield-check",
                "description": "Monitor security and access logs",
            },
        ]

    return dashboard_data


# Create UI router (no global auth dependency)
ui_router = APIRouter(
    prefix="",  # No prefix - will be mounted with prefix by main router
    tags=["admin-ui"],
    include_in_schema=False,  # Hide from OpenAPI docs
)


@ui_router.get("/", response_class=HTMLResponse)
async def admin_dashboard_ui(request: Request):
    """Admin dashboard web interface"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/login/", status_code=status.HTTP_302_FOUND
        )

    models = ModelRegistry.get_all_models()
    dashboard_data = {"user": current_user, "models": [], "statistics": {}}

    # Get model statistics and recent activities
    recent_activities = []
    dashboard_stats = {}

    for model_name, model_class in models.items():
        admin_view = AdminView(model_class)
        model_info = admin_view.get_model_info()

        # Get count for this model
        try:
            with ModelRegistry.get_session() as session:
                count = session.exec(
                    select(func.count()).select_from(model_class)
                ).first()
                model_info["count"] = count or 0
                dashboard_stats[model_name] = count or 0
        except Exception:
            model_info["count"] = 0
            dashboard_stats[model_name] = 0

        model_info["url"] = f"{settings.ADMIN_PREFIX}/{model_name}/"
        dashboard_data["models"].append(model_info)

    # Get recent activities for superusers
    if current_user.is_superuser:
        try:
            from ..core.activity import Activity, ActivityLogger

            recent_activities = ActivityLogger.get_recent_activities(limit=10)

            # Get activity statistics
            with ModelRegistry.get_session() as session:
                total_activities = session.exec(
                    select(func.count()).select_from(Activity)
                ).first()
                today_start = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                today_activities = session.exec(
                    select(func.count())
                    .select_from(Activity)
                    .where(Activity.timestamp >= today_start)
                ).first()

                dashboard_stats.update(
                    {
                        "total_activities": total_activities or 0,
                        "today_activities": today_activities or 0,
                    }
                )
        except Exception as e:
            print(f"Error getting activities: {e}")

    # Get dashboard data with system tools
    dashboard_data = get_dashboard_data(current_user)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "dashboard_data": dashboard_data,
            "dashboard_stats": dashboard_stats,
            "recent_activities": recent_activities,
            "title": "Admin Dashboard",
        },
    )


@ui_router.get("/login/", response_class=HTMLResponse)
async def admin_login_ui(request: Request):
    """Admin login page"""
    # Check if already authenticated
    user = await get_current_user_optional(request)
    if user:
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/", status_code=status.HTTP_302_FOUND
        )

    return templates.TemplateResponse(
        "auth/login.html", {"request": request, "title": "Admin Login"}
    )


@ui_router.post("/login/")
async def admin_login_post(request: Request):
    """Handle admin login form submission"""
    import logging

    logger = logging.getLogger(__name__)

    logger.info("Admin login POST endpoint reached")

    try:
        # Get form data manually with timeout and error handling
        logger.info("About to parse form data...")

        # Check content type first
        content_type = request.headers.get("content-type", "")
        logger.info(f"Request content-type: {content_type}")

        if not content_type.startswith("application/x-www-form-urlencoded"):
            logger.error(f"Invalid content-type for form data: {content_type}")
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "error": "Invalid form submission",
                    "title": "Admin Login",
                },
            )

        # Debug request headers and body
        logger.info(f"Request headers: {dict(request.headers)}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request URL: {request.url}")

        # Check if body is already consumed
        logger.info("Checking if request body is available...")

        # Try to read body with detailed error handling
        try:
            logger.info("About to call request.body()...")
            import asyncio

            body = await asyncio.wait_for(request.body(), timeout=2.0)
            logger.info(f"Raw body received successfully, length: {len(body)}")

            if len(body) == 0:
                logger.error("Request body is empty!")
                return templates.TemplateResponse(
                    "auth/login.html",
                    {
                        "request": request,
                        "error": "No form data received",
                        "title": "Admin Login",
                    },
                )

            # Parse URL-encoded form data manually
            from urllib.parse import parse_qs

            body_str = body.decode("utf-8")
            logger.info(f"Body string: {body_str}")

            parsed_data = parse_qs(body_str)
            logger.info(f"Parsed form data: {parsed_data}")

            # Extract username and password (parse_qs returns lists)
            username = parsed_data.get("username", [None])[0]
            password = parsed_data.get("password", [None])[0]

        except asyncio.TimeoutError:
            logger.error("request.body() timed out after 2 seconds")
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "error": "Request body timeout",
                    "title": "Admin Login",
                },
            )
        except Exception as e:
            logger.error(f"Manual form parsing failed: {str(e)}", exc_info=True)
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "error": f"Failed to parse form data: {str(e)}",
                    "title": "Admin Login",
                },
            )

        logger.info(
            f"Extracted username: {username}, password present: {bool(password)}"
        )
        logger.info(f"Admin login attempt - Username: {username}")

        if not username or not password:
            logger.error("Missing username or password in form data")
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "error": "Username and password are required",
                    "title": "Admin Login",
                },
            )

        # Authenticate user
        logger.info(f"Calling auth_backend.authenticate_user for: {username}")
        user = auth_backend.authenticate_user(username, password)

        if not user:
            logger.warning(f"Authentication failed for admin login: {username}")
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "error": "Invalid username or password",
                    "title": "Admin Login",
                },
            )

        logger.info(f"User authenticated: {user.username}, checking staff permissions")

        # Check if user is staff
        if not user.is_staff:
            logger.warning(f"User {user.username} is not staff - denying admin access")
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "error": "You don't have permission to access the admin interface",
                    "title": "Admin Login",
                },
            )

        logger.info(f"Creating access token for admin user: {user.username}")

        # Create access token
        access_token = auth_backend.create_access_token(
            data={"sub": str(user.id), "username": user.username}
        )

        logger.info(
            f"Admin login successful for: {user.username}, redirecting to admin dashboard"
        )

        # Redirect to admin dashboard with token in cookie
        response = RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/", status_code=status.HTTP_302_FOUND
        )
        response.set_cookie(
            key="admin_token",
            value=access_token,
            httponly=True,
            secure=settings.ENVIRONMENT == "production",
            samesite="lax",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        return response

    except Exception as e:
        logger.error(f"Admin login exception for {username}: {str(e)}")
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": f"Login failed: {str(e)}",
                "title": "Admin Login",
            },
        )


@ui_router.get("/logout/")
async def admin_logout(request: Request):
    """Admin logout"""
    response = RedirectResponse(
        url=f"{settings.ADMIN_PREFIX}/login/", status_code=status.HTTP_302_FOUND
    )
    response.delete_cookie("admin_token")
    return response


# Special admin routes (must come before generic model routes)
@ui_router.get("/activities/", response_class=HTMLResponse)
async def admin_activities_ui(
    request: Request,
    page: int = 1,
    activity_type: Optional[str] = None,
    level: Optional[str] = None,
    user_email: Optional[str] = None,
    object_type: Optional[str] = None,
    time_filter: Optional[str] = None,
):
    """Activities monitoring page for superusers"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user or not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required"
        )

    # Import here to avoid circular imports
    from ..core.activity import ActivityLevel, ActivityLogger, ActivityType

    # Get dashboard data
    dashboard_data = get_dashboard_data(current_user)

    # Get activities with filters
    activities = ActivityLogger.get_recent_activities(
        limit=50,
        activity_type=ActivityType(activity_type) if activity_type else None,
        level=ActivityLevel(level) if level else None,
    )

    # Get activity statistics
    with ModelRegistry.get_session() as session:
        from datetime import datetime, timezone

        # from datetime import timedelta  # Currently unused
        from ..core.activity import Activity

        total_count = session.exec(select(func.count()).select_from(Activity)).first()
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_count = session.exec(
            select(func.count())
            .select_from(Activity)
            .where(Activity.timestamp >= today_start)
        ).first()
        high_priority_count = session.exec(
            select(func.count())
            .select_from(Activity)
            .where(Activity.level.in_(["high", "critical"]))
        ).first()
        error_count = session.exec(
            select(func.count())
            .select_from(Activity)
            .where(Activity.activity_type == "error")
        ).first()

    stats = {
        "total": total_count,
        "today": today_count,
        "high_priority": high_priority_count,
        "errors": error_count,
    }

    return templates.TemplateResponse(
        "activities.html",
        {
            "request": request,
            "user": current_user,
            "dashboard_data": dashboard_data,
            "activities": activities,
            "stats": stats,
            "title": "System Activities - Admin",
        },
    )


@ui_router.get("/logs/", response_class=HTMLResponse)
async def admin_logs_ui(request: Request):
    """Live server logs monitoring page for superusers"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user or not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required"
        )

    # Get dashboard data
    dashboard_data = get_dashboard_data(current_user)

    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "user": current_user,
            "dashboard_data": dashboard_data,
            "title": "Live Server Logs - Admin",
        },
    )


@ui_router.get("/settings/", response_class=HTMLResponse)
async def admin_settings_ui(request: Request):
    """System settings page for superusers"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user or not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required"
        )

    # Get dashboard data
    dashboard_data = get_dashboard_data(current_user)

    # Get current settings from environment/config
    from ..conf.settings import settings as app_settings

    current_settings = {
        "general": {
            "app_name": getattr(app_settings, "APP_NAME", "FABI+ Admin"),
            "app_description": getattr(
                app_settings,
                "APP_DESCRIPTION",
                "FastAPI + Django-style admin interface",
            ),
            "timezone": getattr(app_settings, "TIMEZONE", "UTC"),
            "debug_mode": getattr(app_settings, "DEBUG", True),
            "maintenance_mode": getattr(app_settings, "MAINTENANCE_MODE", False),
        },
        "database": {
            "db_echo": getattr(app_settings, "DB_ECHO", True),
            "pool_size": getattr(app_settings, "DB_POOL_SIZE", 10),
        },
        "security": {
            "session_timeout": getattr(app_settings, "SESSION_TIMEOUT_MINUTES", 60),
            "max_login_attempts": getattr(app_settings, "MAX_LOGIN_ATTEMPTS", 5),
            "force_https": getattr(app_settings, "FORCE_HTTPS", False),
            "csrf_protection": getattr(app_settings, "CSRF_PROTECTION", True),
            "activity_logging": getattr(app_settings, "ACTIVITY_LOGGING_ENABLED", True),
        },
        "email": {
            "smtp_host": getattr(app_settings, "SMTP_HOST", ""),
            "smtp_port": getattr(app_settings, "SMTP_PORT", 587),
            "smtp_tls": getattr(app_settings, "SMTP_TLS", True),
            "smtp_username": getattr(app_settings, "SMTP_USERNAME", ""),
            "from_email": getattr(app_settings, "FROM_EMAIL", ""),
        },
        "logging": {
            "log_level": getattr(app_settings, "LOG_LEVEL", "INFO"),
            "log_file_size": getattr(app_settings, "LOG_FILE_SIZE_MB", 10),
            "log_backup_count": getattr(app_settings, "LOG_BACKUP_COUNT", 5),
            "log_to_file": getattr(app_settings, "LOG_TO_FILE", True),
            "log_requests": getattr(app_settings, "LOG_REQUESTS", True),
        },
    }

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": current_user,
            "dashboard_data": dashboard_data,
            "current_settings": current_settings,
            "title": "System Settings - Admin",
        },
    )


@ui_router.get("/analytics/", response_class=HTMLResponse)
async def admin_analytics_ui(request: Request):
    """System analytics page for superusers"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user or not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required"
        )

    # Get dashboard data
    dashboard_data = get_dashboard_data(current_user)

    # Get real analytics data
    analytics_data = {}

    try:
        from ..core.activity import Activity

        with ModelRegistry.get_session() as session:
            # Get model counts
            models = ModelRegistry.get_all_models()
            model_stats = {}
            total_records = 0

            for model_name, model_class in models.items():
                try:
                    count = session.exec(
                        select(func.count()).select_from(model_class)
                    ).first()
                    model_stats[model_name] = count or 0
                    total_records += count or 0
                except Exception:
                    model_stats[model_name] = 0

            # Get activity statistics
            total_activities = session.exec(
                select(func.count()).select_from(Activity)
            ).first()

            # Get activities by type
            activity_types = session.exec(
                select(Activity.activity_type, func.count(Activity.id)).group_by(
                    Activity.activity_type
                )
            ).all()

            # Get recent activity trends (last 7 days)
            from datetime import datetime, timedelta

            week_ago = datetime.now() - timedelta(days=7)
            daily_activities = session.exec(
                select(func.date(Activity.timestamp), func.count(Activity.id))
                .where(Activity.timestamp >= week_ago)
                .group_by(func.date(Activity.timestamp))
                .order_by(func.date(Activity.timestamp))
            ).all()

            analytics_data = {
                "total_users": model_stats.get("user", 0),
                "total_records": total_records,
                "total_activities": total_activities or 0,
                "model_stats": model_stats,
                "activity_types": dict(activity_types) if activity_types else {},
                "daily_activities": dict(daily_activities) if daily_activities else {},
            }

    except Exception as e:
        print(f"Error getting analytics data: {e}")
        # Fallback to basic data
        analytics_data = {
            "total_users": 0,
            "total_records": 0,
            "total_activities": 0,
            "model_stats": {},
            "activity_types": {},
            "daily_activities": {},
        }

    return templates.TemplateResponse(
        "analytics.html",
        {
            "request": request,
            "user": current_user,
            "dashboard_data": dashboard_data,
            "analytics_data": analytics_data,
            "title": "System Analytics - Admin",
        },
    )


@ui_router.get("/security/", response_class=HTMLResponse)
async def admin_security_ui(request: Request):
    """Security monitoring page for superusers"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user or not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required"
        )

    # Get dashboard data
    dashboard_data = get_dashboard_data(current_user)

    # Get real security data
    security_data = {}

    try:
        from ..core.activity import Activity, ActivityType

        with ModelRegistry.get_session() as session:
            # Get failed login attempts
            failed_logins = session.exec(
                select(func.count())
                .select_from(Activity)
                .where(Activity.activity_type == ActivityType.LOGIN)
                .where(Activity.status_code >= 400)
            ).first()

            # Get recent security events
            security_events = session.exec(
                select(Activity)
                .where(
                    Activity.activity_type.in_(
                        [ActivityType.LOGIN, ActivityType.LOGOUT, ActivityType.ERROR]
                    )
                )
                .order_by(Activity.timestamp.desc())
                .limit(20)
            ).all()

            # Get unique active users (recent logins)
            from datetime import datetime, timedelta

            recent_time = datetime.now() - timedelta(hours=24)
            active_sessions = session.exec(
                select(func.count(func.distinct(Activity.user_email)))
                .select_from(Activity)
                .where(Activity.activity_type == ActivityType.LOGIN)
                .where(Activity.timestamp >= recent_time)
                .where(Activity.status_code < 400)
            ).first()

            # Get blocked IPs (simulated from failed attempts)
            blocked_ips = session.exec(
                select(Activity.user_ip, func.count(Activity.id))
                .where(Activity.status_code >= 400)
                .where(Activity.user_ip.isnot(None))
                .group_by(Activity.user_ip)
                .having(func.count(Activity.id) >= 3)
                .limit(10)
            ).all()

            security_data = {
                "failed_logins": failed_logins or 0,
                "active_sessions": active_sessions or 0,
                "blocked_ips": len(blocked_ips) if blocked_ips else 0,
                "security_events": security_events,
                "blocked_ip_list": blocked_ips,
            }

    except Exception as e:
        print(f"Error getting security data: {e}")
        security_data = {
            "failed_logins": 0,
            "active_sessions": 0,
            "blocked_ips": 0,
            "security_events": [],
            "blocked_ip_list": [],
        }

    return templates.TemplateResponse(
        "security.html",
        {
            "request": request,
            "user": current_user,
            "dashboard_data": dashboard_data,
            "security_data": security_data,
            "title": "Security Monitoring - Admin",
        },
    )


# Activities API route (must come before generic model routes)
@ui_router.get("/activities/api/")
async def admin_activities_api(
    request: Request,
    page: int = 1,
    activity_type: Optional[str] = None,
    level: Optional[str] = None,
    user_email: Optional[str] = None,
    object_type: Optional[str] = None,
    time_filter: Optional[str] = None,
):
    """API endpoint for activities data"""

    try:
        # Check authentication manually
        current_user = await get_current_user_optional(request)
        if not current_user or not current_user.is_superuser:
            return {
                "activities": [],
                "page": page,
                "total": 0,
                "error": "Superuser access required",
            }
        # Import here to avoid circular imports
        from ..core.activity import ActivityLevel, ActivityLogger, ActivityType

        # Convert string parameters to enums if provided
        activity_type_enum = None
        if activity_type:
            try:
                activity_type_enum = ActivityType(activity_type.upper())
            except ValueError:
                pass

        level_enum = None
        if level:
            try:
                level_enum = ActivityLevel(level.upper())
            except ValueError:
                pass

        # Get activities with filters
        limit = 50
        if time_filter == "today":
            limit = 100
        elif time_filter == "week":
            limit = 200

        activities = ActivityLogger.get_recent_activities(
            limit=limit, activity_type=activity_type_enum, level=level_enum
        )

        # Apply additional filters
        if user_email:
            activities = [
                a
                for a in activities
                if a.user_email and user_email.lower() in a.user_email.lower()
            ]

        if object_type:
            activities = [
                a
                for a in activities
                if a.object_type and object_type.lower() in a.object_type.lower()
            ]

        if time_filter:
            from datetime import datetime, timedelta

            now = datetime.now()

            if time_filter == "today":
                start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                activities = [a for a in activities if a.timestamp >= start_time]
            elif time_filter == "week":
                start_time = now - timedelta(days=7)
                activities = [a for a in activities if a.timestamp >= start_time]
            elif time_filter == "month":
                start_time = now - timedelta(days=30)
                activities = [a for a in activities if a.timestamp >= start_time]

        # Convert to dict format
        activities_data = []
        for activity in activities:
            activities_data.append(
                {
                    "id": str(activity.id),
                    "timestamp": activity.timestamp.isoformat(),
                    "activity_type": activity.activity_type,
                    "level": activity.level,
                    "action": activity.action,
                    "description": activity.description,
                    "user_email": activity.user_email,
                    "user_ip": activity.user_ip,
                    "object_type": activity.object_type,
                    "object_id": activity.object_id,
                    "object_repr": activity.object_repr,
                    "method": activity.method,
                    "path": activity.path,
                    "status_code": activity.status_code,
                    "response_time": activity.response_time,
                    "formatted_time": activity.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        return {
            "activities": activities_data,
            "page": page,
            "total": len(activities_data),
            "filters": {
                "activity_type": activity_type,
                "level": level,
                "user_email": user_email,
                "object_type": object_type,
                "time_filter": time_filter,
            },
        }

    except Exception as e:
        print(f"Error in activities API: {e}")
        return {"activities": [], "page": page, "total": 0, "error": str(e)}


@ui_router.get("/{model_name}/", response_class=HTMLResponse)
async def admin_model_list_ui(
    request: Request,
    model_name: str,
    page: int = 1,
    size: int = 20,
    search: Optional[str] = None,
):
    """Model list view web interface"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/login/", status_code=status.HTTP_302_FOUND
        )

    model_class = ModelRegistry.get_model(model_name)
    if not model_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found",
        )

    admin_view = AdminView(model_class)
    model_info = admin_view.get_model_info()

    # Setup pagination and filtering
    pagination = PaginationParams(page=page, page_size=size)

    # Create filter and sort params without passing explicit None values
    # This avoids the Query object issue
    filters = FilterParams.__new__(FilterParams)
    filters.filters = {}

    sorting = SortParams.__new__(SortParams)
    sorting.ordering = None

    # Add search filter if provided
    if search:
        filters.filters = {"search": search}

    # Get paginated results using direct database access
    # We can't use admin_view.list() because it uses FastAPI dependency injection
    # So we'll implement the logic directly here
    with ModelRegistry.get_session() as session:
        # Get base query
        query = admin_view.get_queryset(session, current_user)

        # Apply filters
        if filters.filters:
            query = admin_view.apply_filters(query, filters.filters)

        # Apply ordering
        query = admin_view.apply_ordering(query, sorting.ordering)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_count = session.exec(count_query).one()

        # Apply pagination
        paginated_query = query.offset(pagination.offset).limit(pagination.page_size)
        results_data = session.exec(paginated_query).all()

        # Convert to dict
        results_list = [item.model_dump() for item in results_data]

        # Calculate pagination links
        next_page = None
        previous_page = None

        if pagination.offset + pagination.page_size < total_count:
            next_page = f"page={pagination.page + 1}"

        if pagination.page > 1:
            previous_page = f"page={pagination.page - 1}"

        results = {
            "count": total_count,
            "next": next_page,
            "previous": previous_page,
            "results": results_list,
            "total": total_count,
        }

    # Get dashboard data for sidebar
    dashboard_data = get_dashboard_data(current_user)

    return templates.TemplateResponse(
        "model_list.html",
        {
            "request": request,
            "user": current_user,
            "dashboard_data": dashboard_data,
            "model_info": model_info,
            "model_name": model_name,
            "results": results,
            "search": search,
            "pagination": {
                "page": page,
                "size": size,
                "total": results.get("total", 0),
                "pages": (results.get("total", 0) + size - 1) // size,
            },
            "title": f"{model_info['verbose_name_plural']} - Admin",
        },
    )


@ui_router.get("/{model_name}/add/", response_class=HTMLResponse)
async def admin_model_add_ui(request: Request, model_name: str):
    """Model add form web interface"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/login/", status_code=status.HTTP_302_FOUND
        )

    model_class = ModelRegistry.get_model(model_name)
    if not model_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found",
        )

    admin_view = AdminView(model_class)
    model_info = admin_view.get_model_info()

    # Get dashboard data for sidebar
    dashboard_data = get_dashboard_data(current_user)

    return templates.TemplateResponse(
        "model_form.html",
        {
            "request": request,
            "user": current_user,
            "dashboard_data": dashboard_data,
            "model_info": model_info,
            "model_name": model_name,
            "object": None,
            "action": "add",
            "title": f"Add {model_info['verbose_name']} - Admin",
        },
    )


@ui_router.get("/{model_name}/{item_id}/", response_class=HTMLResponse)
async def admin_model_detail_ui(request: Request, model_name: str, item_id: uuid.UUID):
    """Model detail/edit form web interface"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/login/", status_code=status.HTTP_302_FOUND
        )

    model_class = ModelRegistry.get_model(model_name)
    if not model_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found",
        )

    admin_view = AdminView(model_class)
    model_info = admin_view.get_model_info()

    # Get database session
    session = ModelRegistry.get_session()

    # Get object data
    try:
        object_data = admin_view.retrieve(
            item_id, session=session, current_user=current_user
        )
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model_info['verbose_name']} not found",
        )

    # Get dashboard data for sidebar
    dashboard_data = get_dashboard_data(current_user)

    return templates.TemplateResponse(
        "model_form.html",
        {
            "request": request,
            "user": current_user,
            "dashboard_data": dashboard_data,
            "model_info": model_info,
            "model_name": model_name,
            "object": object_data,
            "action": "change",
            "title": f"Change {model_info['verbose_name']} - Admin",
        },
    )


@ui_router.post("/{model_name}/add/")
async def admin_model_add_post(request: Request, model_name: str):
    """Handle model add form submission"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/login/", status_code=status.HTTP_302_FOUND
        )

    model_class = ModelRegistry.get_model(model_name)
    if not model_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found",
        )

    # Get form data
    form_data = await request.form()
    data = dict(form_data)

    # Process form data for proper types
    data = process_form_data(data, model_class)

    admin_view = AdminView(model_class)

    # Get database session
    session = ModelRegistry.get_session()

    try:
        # Create object
        admin_view.create(data, session=session, current_user=current_user)

        # Redirect to model list with success message
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/{model_name}/?success=created",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as e:
        # Return form with error
        model_info = admin_view.get_model_info()
        dashboard_data = get_dashboard_data(current_user)
        return templates.TemplateResponse(
            "model_form.html",
            {
                "request": request,
                "user": current_user,
                "dashboard_data": dashboard_data,
                "model_info": model_info,
                "model_name": model_name,
                "object": data,
                "action": "add",
                "error": str(e),
                "title": f"Add {model_info['verbose_name']} - Admin",
            },
        )


@ui_router.post("/{model_name}/{item_id}/")
async def admin_model_update_post(
    request: Request, model_name: str, item_id: uuid.UUID
):
    """Handle model update form submission"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/login/", status_code=status.HTTP_302_FOUND
        )

    model_class = ModelRegistry.get_model(model_name)
    if not model_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found",
        )

    # Get form data
    form_data = await request.form()
    data = dict(form_data)

    # Process form data for proper types
    data = process_form_data(data, model_class)

    admin_view = AdminView(model_class)

    # Get database session
    session = ModelRegistry.get_session()

    try:
        # Update object
        admin_view.update(item_id, data, session=session, current_user=current_user)

        # Redirect to model list with success message
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/{model_name}/?success=updated",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as e:
        # Return form with error
        model_info = admin_view.get_model_info()
        object_data = admin_view.retrieve(
            item_id, session=session, current_user=current_user
        )
        dashboard_data = get_dashboard_data(current_user)

        return templates.TemplateResponse(
            "model_form.html",
            {
                "request": request,
                "user": current_user,
                "dashboard_data": dashboard_data,
                "model_info": model_info,
                "model_name": model_name,
                "object": {**object_data, **data},  # Merge with form data
                "action": "change",
                "error": str(e),
                "title": f"Change {model_info['verbose_name']} - Admin",
            },
        )


@ui_router.delete("/{model_name}/{item_id}/")
async def admin_model_delete_ui(request: Request, model_name: str, item_id: uuid.UUID):
    """Model delete endpoint for admin UI"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/login/", status_code=status.HTTP_302_FOUND
        )

    model_class = ModelRegistry.get_model(model_name)
    if not model_class:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model '{model_name}' not found",
        )

    admin_view = AdminView(model_class)

    # Get database session
    session = ModelRegistry.get_session()

    try:
        # Delete object
        admin_view.delete(item_id, session=session, current_user=current_user)

        # Redirect to model list with success message
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/{model_name}/",
            status_code=status.HTTP_302_FOUND,
        )

    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting object: {str(e)}",
        )


@ui_router.get("/{model_name}/field-choices/{field_name}/")
async def admin_field_choices_ui(
    request: Request, model_name: str, field_name: str, search: Optional[str] = None
):
    """Get choices for foreign key fields (for HTMX/AJAX)"""

    # Check authentication manually
    current_user = await get_current_user_optional(request)
    if not current_user:
        return {"choices": []}

    model_class = ModelRegistry.get_model(model_name)
    if not model_class:
        return {"choices": []}

    # Get related model for foreign key field
    if not field_name.endswith("_id"):
        return {"choices": []}

    # Get the base field name (remove '_id')
    base_field_name = field_name[:-3]
    related_model_name = base_field_name

    # Try to get the related model
    related_model_class = ModelRegistry.get_model(related_model_name)
    if not related_model_class:
        return {"choices": []}

    # Get choices from related model
    with ModelRegistry.get_session() as session:
        query = select(related_model_class)

        # Add search filter if provided
        if search:
            # Try to search in common fields
            search_fields = [
                "name",
                "title",
                "username",
                "email",
                "first_name",
                "last_name",
            ]
            search_conditions = []
            for search_field in search_fields:
                if hasattr(related_model_class, search_field):
                    field_attr = getattr(related_model_class, search_field)
                    search_conditions.append(field_attr.ilike(f"%{search}%"))

            if search_conditions:
                from sqlmodel import or_

                query = query.where(or_(*search_conditions))

        # Limit results
        query = query.limit(50)
        results = session.exec(query).all()

        choices = []
        for item in results:
            # Try to get a meaningful display name
            display_name = str(item)
            if hasattr(item, "name"):
                display_name = item.name
            elif hasattr(item, "title"):
                display_name = item.title
            elif hasattr(item, "username"):
                display_name = item.username
            elif hasattr(item, "email"):
                display_name = item.email
            elif hasattr(item, "first_name") and hasattr(item, "last_name"):
                display_name = f"{item.first_name} {item.last_name}"

            choices.append({"value": str(item.id), "label": display_name})

        return {"choices": choices}


@ui_router.websocket("/logs/live")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for live log streaming"""

    try:
        # For now, accept all connections (we'll add proper auth later)
        await websocket.accept()

        # Send initial connection message
        await websocket.send_text(
            json.dumps({"type": "connection", "message": "Connected to live logs"})
        )

        # Send real log entries from recent activities
        try:
            from ..core.activity import ActivityLogger

            recent_activities = ActivityLogger.get_recent_activities(limit=20)

            for activity in recent_activities:
                log_entry = {
                    "timestamp": activity.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "level": activity.level.upper() if activity.level else "INFO",
                    "logger": (
                        f"fabiplus.{activity.activity_type.lower()}"
                        if activity.activity_type
                        else "fabiplus.system"
                    ),
                    "message": activity.description,
                    "raw_line": f"{activity.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {activity.activity_type} - {activity.description}",
                    "user": activity.user_email or "system",
                    "ip": activity.user_ip or "unknown",
                    "method": activity.method or "",
                    "path": activity.path or "",
                    "status": activity.status_code or 0,
                }

                await websocket.send_text(
                    json.dumps({"type": "log_entry", "data": log_entry})
                )
                await asyncio.sleep(0.1)  # Small delay between entries

        except Exception as e:
            print(f"Error sending activity logs: {e}")

        # Keep connection alive and handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle client commands
                if message.get("type") == "filter":
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "info",
                                "message": f"Filter applied: {message.get('level', 'all')}",
                            }
                        )
                    )
                elif message.get("type") == "refresh":
                    # Send fresh activity data
                    recent_activities = ActivityLogger.get_recent_activities(limit=10)
                    for activity in recent_activities:
                        log_entry = {
                            "timestamp": activity.timestamp.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "level": (
                                activity.level.upper() if activity.level else "INFO"
                            ),
                            "logger": (
                                f"fabiplus.{activity.activity_type.lower()}"
                                if activity.activity_type
                                else "fabiplus.system"
                            ),
                            "message": activity.description,
                            "raw_line": f"{activity.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {activity.activity_type} - {activity.description}",
                        }

                        await websocket.send_text(
                            json.dumps({"type": "log_entry", "data": log_entry})
                        )

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket error: {e}")
                break

    except Exception as e:
        print(f"WebSocket connection error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
