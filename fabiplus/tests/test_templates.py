"""
Comprehensive tests for FABI+ template system
Tests project and app template generation functionality
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabiplus.cli.templates.app import AppTemplate
from fabiplus.cli.templates.project import ProjectTemplate


class TestProjectTemplate:
    """Test ProjectTemplate class functionality"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_name = "testproject"

    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_project_template_init(self):
        """Test ProjectTemplate initialization"""
        template = ProjectTemplate(
            project_name=self.project_name,
            template_type="default",
            include_docker=False,
        )

        assert template.project_name == self.project_name
        assert template.template_type == "default"
        assert template.include_docker is False
        assert template.jinja_env is not None

    def test_project_template_init_with_docker(self):
        """Test ProjectTemplate initialization with Docker"""
        template = ProjectTemplate(
            project_name=self.project_name, template_type="full", include_docker=True
        )

        assert template.include_docker is True
        assert template.template_type == "full"

    def test_get_template_context(self):
        """Test template context generation"""
        template = ProjectTemplate(self.project_name)
        context = template._get_template_context()

        assert context["project_name"] == self.project_name
        assert context["project_name_title"] == self.project_name.title()
        assert context["project_name_upper"] == self.project_name.upper()
        assert context["template_type"] == "default"
        assert "created_date" in context
        assert "created_year" in context

    def test_create_project_structure(self):
        """Test project directory structure creation"""
        template = ProjectTemplate(self.project_name)
        project_dir = self.temp_dir / self.project_name

        # Create the parent directory first
        project_dir.mkdir(parents=True, exist_ok=True)

        template._create_project_structure(project_dir)

        # Check directories exist
        assert project_dir.exists()
        assert (project_dir / self.project_name).exists()
        assert (project_dir / "apps").exists()
        assert (project_dir / "tests").exists()

        # Check __init__.py files
        assert (project_dir / self.project_name / "__init__.py").exists()
        assert (project_dir / "apps" / "__init__.py").exists()
        assert (project_dir / "tests" / "__init__.py").exists()

    def test_create_project_files_basic(self):
        """Test basic project file creation"""
        template = ProjectTemplate(self.project_name)
        project_dir = self.temp_dir / self.project_name
        project_dir.mkdir(parents=True)

        template._create_project_files(project_dir)

        # Check essential files exist
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "manage.py").exists()
        assert (project_dir / ".env.example").exists()
        assert (project_dir / ".gitignore").exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / self.project_name / "settings.py").exists()
        assert (project_dir / self.project_name / "urls.py").exists()
        assert (project_dir / self.project_name / "wsgi.py").exists()
        assert (project_dir / self.project_name / "asgi.py").exists()

    def test_create_project_files_with_docker(self):
        """Test project file creation with Docker files"""
        template = ProjectTemplate(self.project_name, include_docker=True)
        project_dir = self.temp_dir / self.project_name
        project_dir.mkdir(parents=True)

        template._create_project_files(project_dir)

        # Check Docker files exist
        assert (project_dir / "Dockerfile").exists()
        assert (project_dir / "docker-compose.yml").exists()
        assert (project_dir / ".dockerignore").exists()

    def test_create_project_files_without_docker(self):
        """Test project file creation without Docker files"""
        template = ProjectTemplate(self.project_name, include_docker=False)
        project_dir = self.temp_dir / self.project_name
        project_dir.mkdir(parents=True)

        template._create_project_files(project_dir)

        # Check Docker files don't exist
        assert not (project_dir / "Dockerfile").exists()
        assert not (project_dir / "docker-compose.yml").exists()
        assert not (project_dir / ".dockerignore").exists()

    def test_template_content_rendering(self):
        """Test that template content is properly rendered"""
        template = ProjectTemplate(self.project_name)
        project_dir = self.temp_dir / self.project_name
        project_dir.mkdir(parents=True)

        template._create_project_files(project_dir)

        # Check settings.py content
        settings_content = (project_dir / self.project_name / "settings.py").read_text()
        assert f'APP_NAME = "{self.project_name.title()} API"' in settings_content

        # Check README.md content
        readme_content = (project_dir / "README.md").read_text()
        assert f"# {self.project_name.title()}" in readme_content

        # Check .env.example content
        env_content = (project_dir / ".env.example").read_text()
        assert f"DATABASE_URL=sqlite:///./{self.project_name}.db" in env_content

    @patch("fabiplus.cli.templates.app.AppTemplate")
    def test_create_main_app(self, mock_app_template):
        """Test main app creation"""
        template = ProjectTemplate(self.project_name)
        project_dir = self.temp_dir / self.project_name
        project_dir.mkdir(parents=True)

        # Mock AppTemplate
        mock_instance = MagicMock()
        mock_app_template.return_value = mock_instance

        template._create_main_app(project_dir)

        # Verify AppTemplate was called correctly
        mock_app_template.assert_called_once_with("core", "minimal")
        mock_instance.create_app.assert_called_once()

    def test_create_project_full_workflow(self):
        """Test complete project creation workflow"""
        template = ProjectTemplate(self.project_name, include_docker=True)
        project_dir = self.temp_dir / self.project_name

        # Mock the main app creation to avoid dependency issues
        with patch.object(template, "_create_main_app"):
            template.create_project(project_dir)

        # Verify project structure
        assert project_dir.exists()
        assert (project_dir / self.project_name).exists()
        assert (project_dir / "apps").exists()
        assert (project_dir / "tests").exists()

        # Verify files
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "manage.py").exists()
        assert (project_dir / "Dockerfile").exists()  # Docker enabled

    def test_create_project_with_force(self):
        """Test project creation with force flag"""
        template = ProjectTemplate(self.project_name)
        project_dir = self.temp_dir / self.project_name

        # Create existing directory with file
        project_dir.mkdir(parents=True)
        (project_dir / "existing_file.txt").write_text("existing content")

        # Create project with force=True
        with patch.object(template, "_create_main_app"):
            template.create_project(project_dir, force=True)

        # Verify old content is removed and new project created
        assert not (project_dir / "existing_file.txt").exists()
        assert (project_dir / "pyproject.toml").exists()

    def test_init_existing_project(self):
        """Test initializing FABI+ in existing directory"""
        template = ProjectTemplate(self.project_name)
        project_dir = self.temp_dir / self.project_name
        project_dir.mkdir(parents=True)

        # Create some existing files
        (project_dir / "existing.txt").write_text("existing")

        template.init_existing_project(project_dir)

        # Verify existing files are preserved
        assert (project_dir / "existing.txt").exists()

        # Verify FABI+ files are added
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "manage.py").exists()


class TestAppTemplate:
    """Test AppTemplate class functionality"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.app_name = "testapp"

    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_app_template_init(self):
        """Test AppTemplate initialization"""
        template = AppTemplate(self.app_name, "default")

        assert template.app_name == self.app_name
        assert template.template_type == "default"
        assert template.jinja_env is not None

    def test_get_template_context(self):
        """Test app template context generation"""
        template = AppTemplate(self.app_name)
        context = template._get_template_context()

        assert context["app_name"] == self.app_name
        assert context["app_name_title"] == self.app_name.title()
        assert context["app_name_upper"] == self.app_name.upper()
        assert context["template_type"] == "default"
        assert "created_date" in context
        assert "created_year" in context

    def test_create_app_files(self):
        """Test app file creation"""
        template = AppTemplate(self.app_name)
        app_dir = self.temp_dir / self.app_name

        template.create_app(app_dir)

        # Check all app files exist
        assert (app_dir / "__init__.py").exists()
        assert (app_dir / "models.py").exists()
        assert (app_dir / "views.py").exists()
        assert (app_dir / "admin.py").exists()
        assert (app_dir / "serializers.py").exists()
        assert (app_dir / "urls.py").exists()
        assert (app_dir / "tests.py").exists()
        assert (app_dir / "apps.py").exists()

    def test_app_template_content_rendering(self):
        """Test that app template content is properly rendered"""
        template = AppTemplate(self.app_name)
        app_dir = self.temp_dir / self.app_name

        template.create_app(app_dir)

        # Check models.py content
        models_content = (app_dir / "models.py").read_text()
        assert f"{self.app_name.title()} Models" in models_content
        assert (
            "from fabiplus.core.models import BaseModel, register_model"
            in models_content
        )

        # Check views.py content
        views_content = (app_dir / "views.py").read_text()
        assert f"{self.app_name.title()} Views" in views_content
        assert (
            f'router = APIRouter(prefix="/{self.app_name}", tags=["{self.app_name.title()}"])'
            in views_content
        )

        # Check apps.py content
        apps_content = (app_dir / "apps.py").read_text()
        assert f'name = "{self.app_name}"' in apps_content
        assert f'verbose_name = "{self.app_name.title()}"' in apps_content

    def test_create_app_with_force(self):
        """Test app creation with force flag"""
        template = AppTemplate(self.app_name)
        app_dir = self.temp_dir / self.app_name

        # Create existing directory with file
        app_dir.mkdir(parents=True)
        (app_dir / "existing_file.txt").write_text("existing content")

        # Create app with force=True
        template.create_app(app_dir, force=True)

        # Verify old content is removed and new app created
        assert not (app_dir / "existing_file.txt").exists()
        assert (app_dir / "models.py").exists()

    def test_generate_model_code(self):
        """Test model code generation"""
        template = AppTemplate(self.app_name)
        app_dir = self.temp_dir / self.app_name

        # Create app first
        template.create_app(app_dir)

        # Generate model code
        fields = [("name", "str"), ("age", "int"), ("is_active", "bool")]
        template.generate_model_code(
            app_dir,
            "TestModel",
            fields,
            generate_admin=True,
            generate_views=True,
            generate_tests=True,
        )

        # Check that model code was appended to models.py
        models_content = (app_dir / "models.py").read_text()
        assert "class TestModel(BaseModel, table=True):" in models_content
        assert "@register_model" in models_content

        # Check that admin code was appended
        admin_content = (app_dir / "admin.py").read_text()
        assert "class TestModelAdmin(AdminView):" in admin_content
        assert "model = TestModel" in admin_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
