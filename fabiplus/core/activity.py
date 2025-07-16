"""
FABI+ Framework Activity Logging System
Tracks user activities and system events for admin monitoring
"""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel as PydanticBaseModel
from sqlmodel import Field, Relationship, Session, SQLModel, select

from .models import BaseModel, ModelRegistry, User


class ActivityType(str, Enum):
    """Types of activities that can be logged"""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    ADMIN_ACCESS = "admin_access"
    API_CALL = "api_call"
    ERROR = "error"
    SYSTEM = "system"


class ActivityLevel(str, Enum):
    """Activity importance levels"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Activity(BaseModel, table=True):
    """Activity log model for tracking user and system activities"""

    __tablename__ = "activities"

    # Core fields
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)

    # Activity details
    activity_type: ActivityType = Field(index=True)
    level: ActivityLevel = Field(default=ActivityLevel.NORMAL, index=True)
    action: str = Field(
        max_length=100, index=True
    )  # e.g., "create_customer", "login_admin"
    description: str = Field(max_length=500)  # Human-readable description

    # User context
    user_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="users.id", index=True
    )
    user_email: Optional[str] = Field(
        default=None, max_length=255
    )  # Denormalized for performance
    user_ip: Optional[str] = Field(default=None, max_length=45)  # IPv4/IPv6
    user_agent: Optional[str] = Field(default=None, max_length=500)

    # Object context
    object_type: Optional[str] = Field(
        default=None, max_length=100, index=True
    )  # Model name
    object_id: Optional[str] = Field(
        default=None, max_length=100, index=True
    )  # Object ID
    object_repr: Optional[str] = Field(
        default=None, max_length=200
    )  # String representation

    # Request context
    method: Optional[str] = Field(default=None, max_length=10)  # HTTP method
    path: Optional[str] = Field(default=None, max_length=500)  # Request path
    status_code: Optional[int] = Field(default=None, index=True)
    response_time: Optional[float] = Field(default=None)  # Response time in seconds

    # Additional metadata
    extra_data: Optional[str] = Field(default=None)  # JSON string for additional data

    # Relationships (commented out to avoid circular dependency issues)
    # user: Optional[User] = Relationship(back_populates="activities")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), uuid.UUID: lambda v: str(v)}

    def __str__(self):
        return f"{self.action} by {self.user_email or 'System'} at {self.timestamp}"

    @property
    def metadata_dict(self) -> Dict[str, Any]:
        """Parse extra_data JSON string to dictionary"""
        if self.extra_data:
            try:
                return json.loads(self.extra_data)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    @metadata_dict.setter
    def metadata_dict(self, value: Dict[str, Any]):
        """Set extra_data from dictionary"""
        if value:
            self.extra_data = json.dumps(value, default=str)
        else:
            self.extra_data = None


class ActivityLogger:
    """Service class for logging activities"""

    @staticmethod
    def log_activity(
        activity_type: ActivityType,
        action: str,
        description: str,
        user: Optional[User] = None,
        user_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        object_type: Optional[str] = None,
        object_id: Optional[str] = None,
        object_repr: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        status_code: Optional[int] = None,
        response_time: Optional[float] = None,
        level: ActivityLevel = ActivityLevel.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        session: Optional[Session] = None,
    ) -> Activity:
        """Log an activity to the database"""

        # Create activity record
        activity = Activity(
            activity_type=activity_type,
            level=level,
            action=action,
            description=description,
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            user_ip=user_ip,
            user_agent=user_agent,
            object_type=object_type,
            object_id=str(object_id) if object_id else None,
            object_repr=object_repr,
            method=method,
            path=path,
            status_code=status_code,
            response_time=response_time,
        )

        if metadata:
            activity.metadata_dict = metadata

        # Save to database
        if session is None:
            with ModelRegistry.get_session() as db_session:
                db_session.add(activity)
                db_session.commit()
                db_session.refresh(activity)
        else:
            session.add(activity)
            session.commit()
            session.refresh(activity)

        return activity

    @staticmethod
    def log_model_activity(
        activity_type: ActivityType,
        model_instance: Any,
        user: Optional[User] = None,
        request_context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Activity:
        """Log activity for model operations (CRUD)"""

        # Generate action and description
        model_name = model_instance.__class__.__name__.lower()
        action = f"{activity_type.value}_{model_name}"

        action_map = {
            ActivityType.CREATE: f"Created {model_name}",
            ActivityType.UPDATE: f"Updated {model_name}",
            ActivityType.DELETE: f"Deleted {model_name}",
            ActivityType.READ: f"Viewed {model_name}",
        }

        description = action_map.get(
            activity_type, f"{activity_type.value.title()} {model_name}"
        )

        # Get object representation
        object_repr = str(model_instance)
        if hasattr(model_instance, "name"):
            object_repr = model_instance.name
        elif hasattr(model_instance, "title"):
            object_repr = model_instance.title
        elif hasattr(model_instance, "email"):
            object_repr = model_instance.email

        # Extract request context
        request_data = request_context or {}

        return ActivityLogger.log_activity(
            activity_type=activity_type,
            action=action,
            description=f"{description}: {object_repr}",
            user=user,
            user_ip=request_data.get("user_ip"),
            user_agent=request_data.get("user_agent"),
            object_type=model_name,
            object_id=getattr(model_instance, "id", None),
            object_repr=object_repr,
            method=request_data.get("method"),
            path=request_data.get("path"),
            status_code=request_data.get("status_code"),
            response_time=request_data.get("response_time"),
            metadata=metadata,
        )

    @staticmethod
    def log_auth_activity(
        activity_type: ActivityType,
        user: User,
        request_context: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> Activity:
        """Log authentication activities"""

        action_map = {
            ActivityType.LOGIN: "User login",
            ActivityType.LOGOUT: "User logout",
            ActivityType.ADMIN_ACCESS: "Admin access",
        }

        action = f"{activity_type.value}_{user.username}"
        description = f"{action_map.get(activity_type, 'Auth activity')}: {user.email}"

        if not success:
            description += " (FAILED)"
            level = ActivityLevel.HIGH
        else:
            level = ActivityLevel.NORMAL

        request_data = request_context or {}

        return ActivityLogger.log_activity(
            activity_type=activity_type,
            action=action,
            description=description,
            user=user,
            user_ip=request_data.get("user_ip"),
            user_agent=request_data.get("user_agent"),
            method=request_data.get("method"),
            path=request_data.get("path"),
            status_code=request_data.get("status_code"),
            level=level,
            metadata={"success": success},
        )

    @staticmethod
    def get_recent_activities(
        limit: int = 50,
        user_id: Optional[uuid.UUID] = None,
        activity_type: Optional[ActivityType] = None,
        level: Optional[ActivityLevel] = None,
        object_type: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> List[Activity]:
        """Get recent activities with optional filtering"""

        def _query(db_session: Session) -> List[Activity]:
            query = select(Activity).order_by(Activity.timestamp.desc())

            if user_id:
                query = query.where(Activity.user_id == user_id)
            if activity_type:
                query = query.where(Activity.activity_type == activity_type)
            if level:
                query = query.where(Activity.level == level)
            if object_type:
                query = query.where(Activity.object_type == object_type)

            query = query.limit(limit)
            return db_session.exec(query).all()

        if session:
            return _query(session)
        else:
            with ModelRegistry.get_session() as db_session:
                return _query(db_session)


# Register the Activity model
ModelRegistry.register(Activity)
