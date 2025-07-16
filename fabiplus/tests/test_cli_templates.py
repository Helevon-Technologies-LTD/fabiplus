"""
Tests for CLI template commands
Tests the CLI interface for project and app creation
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from fabiplus.cli.commands.app import app as app_app
from fabiplus.cli.commands.project import app as project_app


class TestProjectCLI:
    """Test project CLI commands"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.runner = CliRunner()

    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_startproject_command_basic(self):
        """Test basic startproject command"""
        project_name = "testproject"

        with patch("fabiplus.cli.commands.project.ProjectTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance

            result = self.runner.invoke(
                project_app, ["startproject", project_name, "--dir", str(self.temp_dir)]
            )

            assert result.exit_code == 0
            mock_template.assert_called_once_with(
                project_name, "default", include_docker=False
            )
            mock_instance.create_project.assert_called_once()

    def test_startproject_command_with_template(self):
        """Test startproject command with template option"""
        project_name = "testproject"
        template_type = "minimal"

        with patch("fabiplus.cli.commands.project.ProjectTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance

            result = self.runner.invoke(
                project_app,
                [
                    "startproject",
                    project_name,
                    "--template",
                    template_type,
                    "--dir",
                    str(self.temp_dir),
                ],
            )

            assert result.exit_code == 0
            mock_template.assert_called_once_with(
                project_name, template_type, include_docker=False
            )

    def test_startproject_command_with_docker(self):
        """Test startproject command with Docker option"""
        project_name = "testproject"

        with patch("fabiplus.cli.commands.project.ProjectTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance

            result = self.runner.invoke(
                project_app,
                ["startproject", project_name, "--docker", "--dir", str(self.temp_dir)],
            )

            assert result.exit_code == 0
            mock_template.assert_called_once_with(
                project_name, "default", include_docker=True
            )

    def test_startproject_command_with_force(self):
        """Test startproject command with force option"""
        project_name = "testproject"

        with patch("fabiplus.cli.commands.project.ProjectTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance

            result = self.runner.invoke(
                project_app,
                ["startproject", project_name, "--force", "--dir", str(self.temp_dir)],
            )

            assert result.exit_code == 0
            mock_instance.create_project.assert_called_with(
                self.temp_dir / project_name, force=True
            )

    def test_list_templates_command(self):
        """Test list-templates command"""
        result = self.runner.invoke(project_app, ["list-templates"])

        assert result.exit_code == 0
        assert "Available Project Templates:" in result.stdout
        assert "default" in result.stdout
        assert "minimal" in result.stdout
        assert "full" in result.stdout
        assert "microservice" in result.stdout
        assert "monolith" in result.stdout

    def test_init_command(self):
        """Test init command"""
        with patch("fabiplus.cli.commands.project.ProjectTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance

            # Change to temp directory
            with patch("pathlib.Path.cwd", return_value=self.temp_dir):
                result = self.runner.invoke(project_app, ["init", "--force"])

            assert result.exit_code == 0
            mock_instance.init_existing_project.assert_called_once()

    def test_startproject_error_handling(self):
        """Test error handling in startproject command"""
        project_name = "testproject"

        with patch("fabiplus.cli.commands.project.ProjectTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance
            mock_instance.create_project.side_effect = Exception("Test error")

            result = self.runner.invoke(
                project_app, ["startproject", project_name, "--dir", str(self.temp_dir)]
            )

            assert result.exit_code == 1
            assert "Error creating project" in result.stdout


class TestAppCLI:
    """Test app CLI commands"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.runner = CliRunner()

    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_startapp_command_basic(self):
        """Test basic startapp command"""
        app_name = "testapp"

        with patch("fabiplus.cli.commands.app.AppTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance

            # Mock Path.cwd() to return our temp directory
            with patch("pathlib.Path.cwd", return_value=self.temp_dir):
                # Mock the _is_fabiplus_project function to return True
                with patch(
                    "fabiplus.cli.commands.app._is_fabiplus_project", return_value=True
                ):
                    result = self.runner.invoke(app_app, ["startapp", app_name])

            assert result.exit_code == 0
            mock_template.assert_called_once_with(app_name, "default")
            mock_instance.create_app.assert_called_once()

    def test_startapp_command_with_template(self):
        """Test startapp command with template option"""
        app_name = "testapp"
        template_type = "api"

        with patch("fabiplus.cli.commands.app.AppTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance

            with patch("pathlib.Path.cwd", return_value=self.temp_dir):
                with patch(
                    "fabiplus.cli.commands.app._is_fabiplus_project", return_value=True
                ):
                    result = self.runner.invoke(
                        app_app, ["startapp", app_name, "--template", template_type]
                    )

            assert result.exit_code == 0
            mock_template.assert_called_once_with(app_name, template_type)

    def test_startapp_command_with_directory(self):
        """Test startapp command with custom directory"""
        app_name = "testapp"
        custom_dir = self.temp_dir / "custom"

        with patch("fabiplus.cli.commands.app.AppTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance

            result = self.runner.invoke(
                app_app, ["startapp", app_name, "--dir", str(custom_dir)]
            )

            assert result.exit_code == 0
            mock_instance.create_app.assert_called_with(
                custom_dir / app_name, force=False
            )

    def test_startapp_command_with_force(self):
        """Test startapp command with force option"""
        app_name = "testapp"

        with patch("fabiplus.cli.commands.app.AppTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance

            with patch("pathlib.Path.cwd", return_value=self.temp_dir):
                with patch(
                    "fabiplus.cli.commands.app._is_fabiplus_project", return_value=True
                ):
                    result = self.runner.invoke(
                        app_app, ["startapp", app_name, "--force"]
                    )

            assert result.exit_code == 0
            mock_instance.create_app.assert_called_with(
                self.temp_dir / "apps" / app_name, force=True
            )

    def test_list_app_templates_command(self):
        """Test list-templates command for apps"""
        result = self.runner.invoke(app_app, ["list-templates"])

        assert result.exit_code == 0
        assert "Available App Templates:" in result.stdout
        assert "default" in result.stdout
        assert "minimal" in result.stdout
        assert "api" in result.stdout
        assert "crud" in result.stdout
        assert "readonly" in result.stdout
        assert "auth" in result.stdout
        assert "blog" in result.stdout
        assert "ecommerce" in result.stdout

    def test_addmodel_command(self):
        """Test addmodel command"""
        app_name = "testapp"
        model_name = "TestModel"
        fields = "name:str,age:int,is_active:bool"

        with patch("pathlib.Path.cwd", return_value=self.temp_dir):
            # Create apps directory structure
            apps_dir = self.temp_dir / "apps" / app_name
            apps_dir.mkdir(parents=True)
            (apps_dir / "models.py").write_text("# Initial models file")

            result = self.runner.invoke(
                app_app, ["addmodel", app_name, model_name, "--fields", fields]
            )

            assert result.exit_code == 0
            # Check that the model was added to the file
            models_content = (apps_dir / "models.py").read_text()
            assert f"class {model_name}" in models_content

    def test_remove_app_command(self):
        """Test remove app command"""
        app_name = "testapp"

        # Create app directory
        app_dir = self.temp_dir / "apps" / app_name
        app_dir.mkdir(parents=True)
        (app_dir / "models.py").write_text("# test content")

        with patch("pathlib.Path.cwd", return_value=self.temp_dir):
            # Mock user confirmation
            with patch("typer.confirm", return_value=True):
                result = self.runner.invoke(app_app, ["remove", app_name])

        assert result.exit_code == 0
        assert not app_dir.exists()

    def test_list_apps_command(self):
        """Test list apps command"""
        # Create some app directories with required files
        app1_dir = self.temp_dir / "app1"
        app2_dir = self.temp_dir / "app2"
        app1_dir.mkdir(parents=True)
        app2_dir.mkdir(parents=True)
        (app1_dir / "__init__.py").touch()
        (app1_dir / "models.py").touch()
        (app2_dir / "__init__.py").touch()
        (app2_dir / "models.py").touch()

        with patch("pathlib.Path.cwd", return_value=self.temp_dir):
            with patch(
                "fabiplus.cli.commands.app._is_fabiplus_project", return_value=True
            ):
                result = self.runner.invoke(app_app, ["list"])

        assert result.exit_code == 0
        assert "app1" in result.stdout
        assert "app2" in result.stdout

    def test_startapp_error_handling(self):
        """Test error handling in startapp command"""
        app_name = "testapp"

        with patch("fabiplus.cli.commands.app.AppTemplate") as mock_template:
            mock_instance = MagicMock()
            mock_template.return_value = mock_instance
            mock_instance.create_app.side_effect = Exception("Test error")

            with patch("pathlib.Path.cwd", return_value=self.temp_dir):
                with patch(
                    "fabiplus.cli.commands.app._is_fabiplus_project", return_value=True
                ):
                    result = self.runner.invoke(app_app, ["startapp", app_name])

            assert result.exit_code == 1
            assert "Error creating app" in result.stdout


class TestTemplateIntegration:
    """Integration tests for template system"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.runner = CliRunner()

    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_full_project_creation_workflow(self):
        """Test complete project creation workflow"""
        project_name = "integrationtest"

        # Create project
        with patch("fabiplus.cli.templates.app.AppTemplate.create_app"):
            result = self.runner.invoke(
                project_app, ["startproject", project_name, "--dir", str(self.temp_dir)]
            )

        assert result.exit_code == 0

        project_dir = self.temp_dir / project_name
        assert project_dir.exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "manage.py").exists()
        assert (project_dir / project_name / "settings.py").exists()

    def test_template_content_validation(self):
        """Test that generated template content is valid"""
        project_name = "validationtest"

        # Create project
        with patch("fabiplus.cli.templates.app.AppTemplate.create_app"):
            result = self.runner.invoke(
                project_app, ["startproject", project_name, "--dir", str(self.temp_dir)]
            )

        assert result.exit_code == 0

        project_dir = self.temp_dir / project_name

        # Validate pyproject.toml content
        pyproject_content = (project_dir / "pyproject.toml").read_text()
        assert f'name = "{project_name}"' in pyproject_content
        # Check for FastAPI and other dependencies instead of fabiplus
        assert "fastapi" in pyproject_content

        # Validate settings.py content
        settings_content = (project_dir / project_name / "settings.py").read_text()
        assert "from fabiplus.conf.settings import *" in settings_content
        assert f'APP_NAME = "{project_name.title()} API"' in settings_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
