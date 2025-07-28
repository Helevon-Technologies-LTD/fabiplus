"""
Project template engine
Creates Django-style project structure with FABI+ configuration
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from jinja2 import BaseLoader, Environment


class ProjectTemplate:
    """Template engine for creating FABI+ projects"""

    def __init__(
        self,
        project_name: str,
        template_type: str = "default",
        include_docker: bool = False,
        orm_backend: str = "sqlmodel",
        auth_backend: str = "oauth2",
        show_admin_routes: bool = False,
    ):
        self.project_name = project_name
        self.template_type = template_type
        self.include_docker = include_docker
        self.orm_backend = orm_backend
        self.auth_backend = auth_backend
        self.show_admin_routes = show_admin_routes
        self.jinja_env = Environment(loader=BaseLoader())

        # Initialize ORM backend
        from fabiplus.core.orm import ORMRegistry

        self.orm_class = ORMRegistry.get_backend(orm_backend)
        self.orm_instance = self.orm_class(project_name)

    def create_project(self, project_dir: Path, force: bool = False):
        """Create a new FABI+ project"""

        if project_dir.exists() and force:
            shutil.rmtree(project_dir)

        project_dir.mkdir(parents=True, exist_ok=True)

        # Create project structure
        self._create_project_structure(project_dir)
        self._create_project_files(project_dir)
        self._create_migration_config(project_dir)
        self._create_main_app(project_dir)

    def init_existing_project(self, project_dir: Path):
        """Initialize FABI+ in existing directory"""
        self._create_project_files(project_dir)

    def _create_project_structure(self, project_dir: Path):
        """Create basic project directory structure"""

        directories = [
            "",  # Root directory
            self.project_name,  # Main project package
            "apps",  # Apps directory
            "tests",  # Project-wide tests
        ]

        for directory in directories:
            if directory:
                (project_dir / directory).mkdir(exist_ok=True)
                # Create __init__.py for Python packages
                if directory in [self.project_name, "apps", "tests"]:
                    (project_dir / directory / "__init__.py").touch()

    def _create_project_files(self, project_dir: Path):
        """Create project configuration files"""

        context = self._get_template_context()

        files = {
            "pyproject.toml": self._get_pyproject_template(),
            "manage.py": self._get_manage_template(),
            ".env.example": self._get_env_template(),
            ".gitignore": self._get_gitignore_template(),
            "README.md": self._get_readme_template(),
            f"{self.project_name}/settings.py": self._get_settings_template(),
            f"{self.project_name}/urls.py": self._get_urls_template(),
            f"{self.project_name}/__init__.py": "",
            f"{self.project_name}/wsgi.py": self._get_wsgi_template(),
            f"{self.project_name}/asgi.py": self._get_asgi_template(),
        }

        # Add Docker files only if include_docker is True
        if self.include_docker:
            files.update(
                {
                    "Dockerfile": self._get_dockerfile_template(),
                    "docker-compose.yml": self._get_docker_compose_template(),
                    ".dockerignore": self._get_dockerignore_template(),
                }
            )

        for file_path, template_content in files.items():
            full_path = project_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            if template_content:
                rendered_content = self.jinja_env.from_string(template_content).render(
                    context
                )
                full_path.write_text(rendered_content)
            else:
                full_path.touch()

    def _create_migration_config(self, project_dir: Path):
        """Create migration configuration files"""
        migration_files = self.orm_instance.generate_migration_config(project_dir)

        for file_path, content in migration_files.items():
            full_path = project_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

    def _create_main_app(self, project_dir: Path):
        """Create main application directory"""
        from .app import AppTemplate

        app_template = AppTemplate("core", "minimal", orm_backend=self.orm_backend)
        app_dir = project_dir / "apps" / "core"
        app_template.create_app(app_dir, force=True)

    def _get_template_context(self) -> Dict[str, Any]:
        """Get template context variables"""
        return {
            "project_name": self.project_name,
            "project_name_title": self.project_name.title(),
            "project_name_upper": self.project_name.upper(),
            "template_type": self.template_type,
            "orm_backend": self.orm_backend,
            "auth_backend": self.auth_backend,
            "show_admin_routes": self.show_admin_routes,
            "orm_dependencies": self.orm_instance.dependencies,
            "orm_optional_dependencies": self.orm_instance.optional_dependencies,
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "created_year": datetime.now().year,
        }

    def _get_pyproject_template(self) -> str:
        return """[tool.poetry]
name = "{{ project_name }}"
version = "0.1.0"
description = "{{ project_name_title }} - FABI+ API Project ({{ orm_backend|upper }} backend)"
authors = ["Your Name <your.email@example.com>"]
readme = "README.md"
packages = [{include = "{{ project_name }}"}, {include = "apps"}]

[tool.poetry.dependencies]
python = "^3.10"
{% for dep in orm_dependencies -%}
{% if ">=" in dep -%}
{% set parts = dep.split(">=") -%}
{% if "[" in parts[0] -%}
"{{ parts[0] }}" = ">={{ parts[1] }}"
{% else -%}
{{ parts[0] }} = ">={{ parts[1] }}"
{% endif -%}
{% elif "==" in dep -%}
{% set parts = dep.split("==") -%}
{% if "[" in parts[0] -%}
"{{ parts[0] }}" = "=={{ parts[1] }}"
{% else -%}
{{ parts[0] }} = "=={{ parts[1] }}"
{% endif -%}
{% elif "=" in dep -%}
{% set parts = dep.split("=") -%}
{% if "[" in parts[0] -%}
"{{ parts[0] }}" = "{{ parts[1] }}"
{% else -%}
{{ parts[0] }} = "{{ parts[1] }}"
{% endif -%}
{% else -%}
{% if "[" in dep -%}
"{{ dep }}" = "^0.1.0"
{% else -%}
{{ dep }} = "^0.1.0"
{% endif -%}
{% endif -%}
{% endfor %}

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
httpx = "^0.25.0"
black = "^23.11.0"
isort = "^5.12.0"
flake8 = "^6.1.0"

{% if orm_optional_dependencies -%}
[tool.poetry.extras]
{% for extra_name, extra_deps in orm_optional_dependencies.items() -%}
{{ extra_name }} = [{% for dep in extra_deps %}"{{ dep }}"{% if not loop.last %}, {% endif %}{% endfor %}]
{% endfor -%}
{% endif %}

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.black]
line-length = 88
target-version = ['py310']

[tool.isort]
profile = "black"
known_first_party = ["{{ project_name }}", "apps"]

{% if orm_backend == "tortoise" -%}
[tool.aerich]
tortoise_orm = "{{ project_name }}.settings.TORTOISE_ORM"
location = "./migrations"
src_folder = "./"
{% endif -%}
"""

    def _get_manage_template(self) -> str:
        return '''#!/usr/bin/env python3
"""
{{ project_name_title }} Management Script
"""

import os
import sys
from pathlib import Path

# Add project to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set default settings module
os.environ.setdefault("FABIPLUS_SETTINGS_MODULE", "{{ project_name }}.settings")

if __name__ == "__main__":
    from fabiplus.cli.main import main
    main()
'''

    def _get_settings_template(self) -> str:
        orm_settings = self.orm_instance.generate_settings_code()
        return f'''"""
{{{{ project_name_title }}}} Settings
FABI+ project configuration with {{{{ orm_backend|upper }}}} backend
"""

import os
from fabiplus.conf.settings import *

# Helper function for environment variables
def env(key, default=None):
    return os.getenv(key, default)

# Project specific settings
APP_NAME = "{{{{ project_name_title }}}} API"
DEBUG = True

# ORM Backend Configuration
ORM_BACKEND = "{{{{ orm_backend }}}}"

# Authentication Backend Configuration
AUTH_BACKEND = "{{{{ auth_backend }}}}"

# JWT Configuration (if using JWT backend)
JWT_SECRET_KEY = env("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7

# OAuth2 Configuration (default)
OAUTH2_TOKEN_URL = "/auth/token"
OAUTH2_SCOPES = {{"read": "Read access", "write": "Write access", "admin": "Admin access"}}

# Admin Routes Visibility
ADMIN_ROUTES_IN_DOCS = {{{{ show_admin_routes|string|title }}}}

{orm_settings}

# Installed Apps
INSTALLED_APPS = [
    "apps.core",
    # Add your apps here:
    # "apps.blog",
    # "apps.users",
]

# API Configuration
API_PREFIX = "/api/v1"

# Admin Configuration
ADMIN_ENABLED = True
ADMIN_PREFIX = "/admin"

# Security
SECRET_KEY = "{{{{ project_name }}}}-dev-secret-key-change-in-production"

# CORS
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
'''

    def _get_urls_template(self) -> str:
        return '''"""
{{ project_name_title }} URL Configuration
"""

from fastapi import APIRouter
from fabiplus.api.auto import get_api_router
from fabiplus.admin.routes import admin_router

# Main router
router = APIRouter()

# Include auto-generated API routes
api_router = get_api_router()
router.include_router(api_router)

# Include admin routes
router.include_router(admin_router)

# Custom routes can be added here
@router.get("/")
async def root():
    return {
        "message": "Welcome to {{ project_name_title }} API",
        "version": "1.0.0",
        "docs": "/docs",
        "admin": "/admin"
    }
'''

    def _get_readme_template(self) -> str:
        return """# {{ project_name_title }}

{{ project_name_title }} - A FABI+ API Project

## Quick Start

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Setup environment:
   ```bash
   cp .env.example .env
   ```

3. Run migrations:
   ```bash
   poetry run python manage.py db migrate
   ```

4. Create superuser:
   ```bash
   poetry run python manage.py user create
   ```

5. Start development server:
   ```bash
   poetry run python manage.py server run
   ```

6. Visit your API:
   - API Documentation: http://localhost:8000/docs
   - Admin Interface: http://localhost:8000/admin

## Project Structure

```
{{ project_name }}/
├── {{ project_name }}/          # Main project package
│   ├── settings.py      # Project settings
│   ├── urls.py          # URL configuration
│   └── wsgi.py          # WSGI application
├── apps/                # Project apps
│   └── core/            # Core app
├── manage.py            # Management script
├── pyproject.toml       # Poetry configuration
└── README.md            # This file
```

## Development

- Create new app: `poetry run python manage.py app startapp myapp`
- Run tests: `poetry run pytest`
- Format code: `poetry run black .`

## Deployment

See deployment documentation for production setup.
"""

    def _get_env_template(self) -> str:
        return """# {{ project_name_title }} Environment Configuration

# Application
APP_NAME="{{ project_name_title }} API"
DEBUG=true
ENVIRONMENT=development

# Database
DATABASE_URL=sqlite:///./{{ project_name }}.db

# Security
SECRET_KEY={{ project_name }}-dev-secret-key-change-in-production

# Server
HOST=127.0.0.1
PORT=8000

# CORS
CORS_ORIGINS=["http://localhost:3000"]
"""

    def _get_gitignore_template(self) -> str:
        return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Environment
.env
.env.local
.env.production

# Database
*.db
*.sqlite3

# Logs
*.log

# Media
media/

# OS
.DS_Store
Thumbs.db
"""

    def _get_dockerfile_template(self) -> str:
        return """FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry config virtualenvs.create false \\
    && poetry install --no-dev

# Copy project
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "manage.py", "server", "run", "--host", "0.0.0.0"]
"""

    def _get_docker_compose_template(self) -> str:
        return """version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://{{ project_name }}:password@db:5432/{{ project_name }}
    depends_on:
      - db
    volumes:
      - .:/app

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB={{ project_name }}
      - POSTGRES_USER={{ project_name }}
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  postgres_data:
"""

    def _get_dockerignore_template(self) -> str:
        return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Environment
.env
.env.local
.env.production

# Database
*.db
*.sqlite3

# Logs
*.log

# Git
.git/
.gitignore

# Tests
.pytest_cache/
.coverage

# OS
.DS_Store
Thumbs.db
"""

    def _get_wsgi_template(self) -> str:
        return '''"""
WSGI config for {{ project_name }} project.
"""

import os
from fabiplus.core.app import create_app

os.environ.setdefault("FABIPLUS_SETTINGS_MODULE", "{{ project_name }}.settings")

application = create_app()
'''

    def _get_asgi_template(self) -> str:
        return '''"""
ASGI config for {{ project_name }} project.
"""

import os
from fabiplus.core.app import create_app

os.environ.setdefault("FABIPLUS_SETTINGS_MODULE", "{{ project_name }}.settings")

application = create_app()
'''
