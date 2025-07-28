"""
App template engine
Creates Django-style app structure with models, views, admin, and tests
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import BaseLoader, Environment


class AppTemplate:
    """Template engine for creating FABI+ apps"""

    def __init__(
        self,
        app_name: str,
        template_type: str = "default",
        orm_backend: str = "sqlmodel",
    ) -> None:
        self.app_name = app_name
        self.template_type = template_type
        self.orm_backend = orm_backend
        self.jinja_env = Environment(loader=BaseLoader())

        # Initialize ORM backend
        self.orm_instance: Optional[Any] = None
        try:
            from fabiplus.core.orm import ORMRegistry

            self.orm_class = ORMRegistry.get_backend(orm_backend)
            self.orm_instance = self.orm_class(app_name)
        except Exception:
            # Fallback to default if ORM not available
            self.orm_instance = None

    def create_app(self, app_dir: Path, force: bool = False) -> None:
        """Create a new FABI+ app"""

        if app_dir.exists() and force:
            import shutil

            shutil.rmtree(app_dir)

        app_dir.mkdir(parents=True, exist_ok=True)

        # Create app files
        self._create_app_files(app_dir)

    def generate_model_code(
        self,
        app_dir: Path,
        model_name: str,
        fields: List[Tuple[str, str]],
        generate_admin: bool = True,
        generate_views: bool = True,
        generate_tests: bool = True,
    ) -> None:
        """Generate model code and related files"""

        context = self._get_template_context()
        context.update(
            {
                "model_name": model_name,
                "model_name_lower": model_name.lower(),
                "model_name_plural": f"{model_name.lower()}s",
                "fields": fields,
            }
        )

        # Update models.py
        self._append_to_models(app_dir, context)

        if generate_admin:
            self._append_to_admin(app_dir, context)

        if generate_views:
            self._append_to_views(app_dir, context)

        if generate_tests:
            self._append_to_tests(app_dir, context)

    def _create_app_files(self, app_dir: Path) -> None:
        """Create app files"""

        context = self._get_template_context()

        files = {
            "__init__.py": "",
            "models.py": self._get_models_template(),
            "views.py": self._get_views_template(),
            "admin.py": self._get_admin_template(),
            "serializers.py": self._get_serializers_template(),
            "urls.py": self._get_urls_template(),
            "tests.py": self._get_tests_template(),
            "apps.py": self._get_apps_template(),
        }

        for file_name, template_content in files.items():
            file_path = app_dir / file_name

            if template_content:
                rendered_content = self.jinja_env.from_string(template_content).render(
                    context
                )
                file_path.write_text(rendered_content)
            else:
                file_path.touch()

    def _get_template_context(self) -> Dict[str, Any]:
        """Get template context variables"""
        context = {
            "app_name": self.app_name,
            "app_name_title": self.app_name.title(),
            "app_name_upper": self.app_name.upper(),
            "template_type": self.template_type,
            "orm_backend": self.orm_backend,
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "created_year": datetime.now().year,
        }

        # Add ORM-specific context
        if self.orm_instance:
            context.update(
                {
                    "base_model_import": self.orm_instance.get_base_model_import(),
                    "admin_integration": self.orm_instance.get_admin_integration_code(),
                }
            )

        return context

    def _get_models_template(self) -> str:
        if self.orm_backend == "sqlmodel":
            return '''"""
{{ app_name_title }} Models
Database models for the {{ app_name }} app (SQLModel backend)
"""

from typing import Optional
from sqlmodel import Field
from fabiplus.core.models import BaseModel, register_model


# Add your models here
# Example:
# @register_model
# class MyModel(BaseModel, table=True):
#     """Example model"""
#
#     name: str = Field(max_length=100, description="Name")
#     description: Optional[str] = Field(default="", description="Description")
#     is_active: bool = Field(default=True, description="Is active")
#
#     class Config:
#         _verbose_name = "My Model"
#         _verbose_name_plural = "My Models"
#
#     def __str__(self):
#         return self.name
#
# Example with foreign key relationship:
# @register_model
# class Post(BaseModel, table=True):
#     """Blog post model"""
#
#     title: str = Field(max_length=200, description="Post title")
#     content: str = Field(description="Post content")
#     # Foreign key to User model (note: use table name "users", not "user")
#     author_id: uuid.UUID = Field(foreign_key="users.id", description="Post author")
#
#     class Config:
#         _verbose_name = "Post"
#         _verbose_name_plural = "Posts"
#
#     def __str__(self):
#         return self.title
'''
        elif self.orm_backend == "sqlalchemy":
            return '''"""
{{ app_name_title }} Models
Database models for the {{ app_name }} app (SQLAlchemy backend)
"""

from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from fabiplus.core.models import BaseModel, register_model

Base = declarative_base()


# Add your models here
# Example:
# @register_model
# class MyModel(Base):
#     """Example model"""
#     __tablename__ = "{{ app_name }}_mymodel"
#
#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(String(100), nullable=False, comment="Name")
#     description = Column(Text, nullable=True, default="", comment="Description")
#     is_active = Column(Boolean, default=True, comment="Is active")
#
#     def __str__(self):
#         return self.name
'''
        elif self.orm_backend == "tortoise":
            return '''"""
{{ app_name_title }} Models
Database models for the {{ app_name }} app (Tortoise ORM backend)
"""

from typing import Optional
from tortoise.models import Model
from tortoise import fields
from fabiplus.core.models import register_model


# Add your models here
# Example:
# @register_model
# class MyModel(Model):
#     """Example model"""
#
#     class Meta:
#         table = "{{ app_name }}_mymodel"
#         app = "{{ app_name }}"
#
#     id = fields.IntField(pk=True)
#     name = fields.CharField(max_length=100, description="Name")
#     description = fields.TextField(default="", description="Description")
#     is_active = fields.BooleanField(default=True, description="Is active")
#     created_at = fields.DatetimeField(auto_now_add=True)
#     updated_at = fields.DatetimeField(auto_now=True)
#
#     def __str__(self):
#         return self.name
'''
        else:
            # Default to SQLModel
            return self._get_models_template()

    def _get_views_template(self) -> str:
        return '''"""
{{ app_name_title }} Views
API views for the {{ app_name }} app
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fabiplus.core.views import GenericAPIView, AuthenticatedGenericAPIView
from fabiplus.core.auth import get_current_active_user, User

from .models import {{ app_name_title }}Item

# Create router for this app
router = APIRouter(prefix="/{{ app_name }}", tags=["{{ app_name_title }}"])


class {{ app_name_title }}ItemView(GenericAPIView):
    """Custom view for {{ app_name_title }}Item"""
    
    model = {{ app_name_title }}Item
    
    def get_queryset(self, session, user=None):
        """Custom queryset - can be overridden for filtering"""
        query = super().get_queryset(session, user)
        # Add custom filtering here
        return query


# Custom endpoints can be added here
@router.get("/custom/")
async def custom_endpoint():
    """Custom endpoint for {{ app_name }} app"""
    return {"message": "Custom endpoint for {{ app_name }}"}


@router.get("/stats/")
async def get_stats():
    """Get statistics for {{ app_name }} app"""
    # Add your custom logic here
    return {
        "total_items": 0,
        "active_items": 0,
    }
'''

    def _get_admin_template(self) -> str:
        return '''"""
{{ app_name_title }} Admin
Admin configuration for the {{ app_name }} app
"""

from fabiplus.admin.routes import AdminView
# from .models import YourModel


# Example admin configuration:
# class YourModelAdmin(AdminView):
#     """Admin configuration for YourModel"""
#
#     model = YourModel
#
#     # Customize admin behavior here
#     list_display = ["name", "description", "is_active", "created_at"]
#     list_filter = ["is_active", "created_at"]
#     search_fields = ["name", "description"]
#     ordering = ["-created_at"]
#
#     def get_queryset(self, session, user=None):
#         """Custom admin queryset"""
#         query = super().get_queryset(session, user)
#         # Add admin-specific filtering here
#         return query


# Register admin views
admin_views = {
    # "yourmodel": YourModelAdmin,
}
'''

    def _get_serializers_template(self) -> str:
        return '''"""
{{ app_name_title }} Serializers
Pydantic schemas for the {{ app_name }} app
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class {{ app_name_title }}ItemBase(BaseModel):
    """Base schema for {{ app_name_title }}Item"""
    name: str = Field(..., max_length=100, description="Item name")
    description: Optional[str] = Field("", description="Item description")
    is_active: bool = Field(True, description="Is item active")


class {{ app_name_title }}ItemCreate({{ app_name_title }}ItemBase):
    """Schema for creating {{ app_name_title }}Item"""
    pass


class {{ app_name_title }}ItemUpdate({{ app_name_title }}ItemBase):
    """Schema for updating {{ app_name_title }}Item"""
    name: Optional[str] = Field(None, max_length=100, description="Item name")
    is_active: Optional[bool] = Field(None, description="Is item active")


class {{ app_name_title }}ItemResponse({{ app_name_title }}ItemBase):
    """Schema for {{ app_name_title }}Item response"""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
'''

    def _get_urls_template(self) -> str:
        return '''"""
{{ app_name_title }} URLs
URL routing for the {{ app_name }} app
"""

from fastapi import APIRouter
from .views import router as {{ app_name }}_router

# Main router for this app
router = APIRouter()

# Include app-specific routes
router.include_router({{ app_name }}_router)

# Additional URL patterns can be added here
'''

    def _get_tests_template(self) -> str:
        return '''"""
{{ app_name_title }} Tests
Test cases for the {{ app_name }} app
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from fabiplus.core.app import create_app
from .models import {{ app_name_title }}Item


@pytest.fixture(name="session")
def session_fixture():
    """Create test database session"""
    engine = create_engine(
        "sqlite://", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create test client"""
    def get_session_override():
        return session

    app = create_app()
    
    from fabiplus.core.models import ModelRegistry
    app.dependency_overrides[ModelRegistry.get_session] = get_session_override
    
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_create_{{ app_name }}_item(session: Session):
    """Test creating {{ app_name_title }}Item"""
    item = {{ app_name_title }}Item(
        name="Test Item",
        description="Test description",
        is_active=True
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    
    assert item.id is not None
    assert item.name == "Test Item"
    assert item.is_active is True


def test_{{ app_name }}_api_endpoints(client: TestClient):
    """Test {{ app_name }} API endpoints"""
    # Test custom endpoint
    response = client.get("/api/{{ app_name }}/custom/")
    assert response.status_code == 200
    
    data = response.json()
    assert "message" in data


def test_{{ app_name }}_stats_endpoint(client: TestClient):
    """Test {{ app_name }} stats endpoint"""
    response = client.get("/api/{{ app_name }}/stats/")
    assert response.status_code == 200
    
    data = response.json()
    assert "total_items" in data
    assert "active_items" in data


class Test{{ app_name_title }}Item:
    """Test class for {{ app_name_title }}Item model"""
    
    def test_model_creation(self, session: Session):
        """Test model creation"""
        item = {{ app_name_title }}Item(name="Test")
        session.add(item)
        session.commit()
        
        assert item.id is not None
        assert str(item) == "Test"
    
    def test_model_fields(self):
        """Test model fields"""
        item = {{ app_name_title }}Item(name="Test")
        
        assert hasattr(item, "name")
        assert hasattr(item, "description")
        assert hasattr(item, "is_active")
        assert hasattr(item, "created_at")
        assert hasattr(item, "updated_at")
'''

    def _get_apps_template(self) -> str:
        return '''"""
{{ app_name_title }} App Configuration
Django-style app configuration for {{ app_name }}
"""

from fabiplus.core.apps import AppConfig


class {{ app_name_title }}Config(AppConfig):
    """Configuration for {{ app_name }} app"""
    
    name = "{{ app_name }}"
    verbose_name = "{{ app_name_title }}"
    
    def ready(self):
        """App initialization"""
        # Import models to register them
        from . import models
        
        # Import admin to register admin views
        from . import admin
        
        # Any other app initialization code
        pass


# Default app config
default_app_config = "{{ app_name }}.apps.{{ app_name_title }}Config"
'''

    def _append_to_models(self, app_dir: Path, context: Dict[str, Any]) -> None:
        """Append model code to models.py"""
        models_file = app_dir / "models.py"

        model_template = '''

@register_model
class {{ model_name }}(BaseModel, table=True):
    """{{ model_name }} model"""
    
{% for field_name, field_type in fields %}
    {{ field_name }}: {{ field_type }}{% if not loop.last %}
{% endif %}
{% endfor %}
    
    class Config:
        _verbose_name = "{{ model_name }}"
        _verbose_name_plural = "{{ model_name }}s"
    
    def __str__(self):
        return f"{{ model_name }} {self.id}"
'''

        rendered_model = self.jinja_env.from_string(model_template).render(context)

        with open(models_file, "a") as f:
            f.write(rendered_model)

    def _append_to_admin(self, app_dir: Path, context: Dict[str, Any]) -> None:
        """Append admin code to admin.py"""
        admin_file = app_dir / "admin.py"

        admin_template = '''

class {{ model_name }}Admin(AdminView):
    """Admin for {{ model_name }}"""
    
    model = {{ model_name }}
    list_display = [{% for field_name, _ in fields %}"{{ field_name }}"{% if not loop.last %}, {% endif %}{% endfor %}]

admin_views["{{ model_name_lower }}"] = {{ model_name }}Admin
'''

        rendered_admin = self.jinja_env.from_string(admin_template).render(context)

        with open(admin_file, "a") as f:
            f.write(rendered_admin)

    def _append_to_views(self, app_dir: Path, context: Dict[str, Any]) -> None:
        """Append view code to views.py"""
        views_file = app_dir / "views.py"

        view_template = '''

class {{ model_name }}View(GenericAPIView):
    """View for {{ model_name }}"""
    
    model = {{ model_name }}

@router.get("/{{ model_name_lower }}/")
async def list_{{ model_name_lower }}():
    """List {{ model_name }} objects"""
    view = {{ model_name }}View()
    return view.list()
'''

        rendered_view = self.jinja_env.from_string(view_template).render(context)

        with open(views_file, "a") as f:
            f.write(rendered_view)

    def _append_to_tests(self, app_dir: Path, context: Dict[str, Any]) -> None:
        """Append test code to tests.py"""
        tests_file = app_dir / "tests.py"

        test_template = '''

def test_{{ model_name_lower }}_creation():
    """Test {{ model_name }} creation"""
    {{ model_name_lower }} = {{ model_name }}(
{% for field_name, field_type in fields %}
        {{ field_name }}="test_value"{% if not loop.last %},{% endif %}
{% endfor %}
    )
    assert {{ model_name_lower }}.id is not None
'''

        rendered_test = self.jinja_env.from_string(test_template).render(context)

        with open(tests_file, "a") as f:
            f.write(rendered_test)
