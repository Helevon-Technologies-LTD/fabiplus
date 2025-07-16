"""
App scaffolding commands
Django-style app creation with models, views, and admin
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..templates import AppTemplate

console = Console()
app = typer.Typer()


@app.command("startapp")
def start_app(
    name: str = typer.Argument(..., help="App name"),
    directory: Optional[str] = typer.Option(
        None, "--dir", "-d", help="Directory to create app in"
    ),
    template: Optional[str] = typer.Option(
        "default", "--template", "-t", help="App template to use"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing app"),
):
    """
    Create a new FABI+ app with models, views, and admin

    This creates a new app directory with:
    - models.py - Database models
    - views.py - API views
    - admin.py - Admin configuration
    - serializers.py - Pydantic schemas
    - urls.py - URL routing
    - tests.py - Test cases
    """

    # Validate app name
    if not name.isidentifier():
        console.print(f"[red]Error: '{name}' is not a valid Python identifier[/red]")
        raise typer.Exit(1)

    # Determine app directory - apps should be created in apps/ folder
    if directory:
        app_dir = Path(directory) / name
    else:
        # Create in apps/ directory for proper Django-style structure
        apps_dir = Path.cwd() / "apps"
        if not apps_dir.exists():
            apps_dir.mkdir(parents=True, exist_ok=True)
            (apps_dir / "__init__.py").touch()
        app_dir = apps_dir / name

    # Check if directory exists
    if app_dir.exists() and not force:
        console.print(f"[red]Error: App '{name}' already exists[/red]")
        console.print("Use --force to overwrite existing app")
        raise typer.Exit(1)

    # Check if we're in a FABI+ project
    if not _is_fabiplus_project():
        console.print("[yellow]Warning: Not in a FABI+ project directory[/yellow]")
        if not typer.confirm("Create app anyway?"):
            raise typer.Exit(0)

    # Create app
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating app...", total=None)

        try:
            # Detect project ORM backend
            orm_backend = _detect_project_orm_backend()

            # Create app structure
            template_engine = AppTemplate(name, template, orm_backend=orm_backend)
            template_engine.create_app(app_dir, force=force)

            progress.update(task, description="App created successfully!")

        except Exception as e:
            console.print(f"[red]Error creating app: {e}[/red]")
            raise typer.Exit(1)

    # Success message
    success_text = f"""
[bold green]✅ App '{name}' created successfully![/bold green]

[bold]App structure:[/bold]
• [blue]{name}/models.py[/blue] - Database models
• [blue]{name}/views.py[/blue] - API views
• [blue]{name}/admin.py[/blue] - Admin configuration
• [blue]{name}/serializers.py[/blue] - Pydantic schemas
• [blue]{name}/urls.py[/blue] - URL routing
• [blue]{name}/tests.py[/blue] - Test cases

[bold]Next steps:[/bold]
1. Add your models to [cyan]{name}/models.py[/cyan]
2. Configure admin in [cyan]{name}/admin.py[/cyan]
3. Add app to [cyan]INSTALLED_APPS[/cyan] in settings
4. Run [cyan]fabiplus db makemigrations[/cyan]
5. Run [cyan]fabiplus db migrate[/cyan]
"""

    console.print(Panel(success_text, title="App Created", border_style="green"))

    # Ask if user wants to add app to INSTALLED_APPS
    if typer.confirm(f"Add '{name}' to INSTALLED_APPS in settings?"):
        _add_app_to_settings(name)


@app.command("list")
def list_apps():
    """List all apps in the current project"""

    if not _is_fabiplus_project():
        console.print("[red]Error: Not in a FABI+ project directory[/red]")
        raise typer.Exit(1)

    current_dir = Path.cwd()
    apps = []

    # Find app directories
    for item in current_dir.iterdir():
        if (
            item.is_dir()
            and (item / "models.py").exists()
            and (item / "__init__.py").exists()
        ):
            apps.append(item.name)

    if not apps:
        console.print("[yellow]No apps found in current project[/yellow]")
        return

    apps_text = "[bold]Apps in current project:[/bold]\n\n"

    for app_name in sorted(apps):
        app_path = current_dir / app_name

        # Check for models
        models_count = 0
        try:
            with open(app_path / "models.py") as f:
                content = f.read()
                models_count = content.count("class ") - content.count("class Meta")
        except Exception:
            pass

        apps_text += f"• [cyan]{app_name}[/cyan] ({models_count} models)\n"

    console.print(Panel(apps_text, title="Project Apps", border_style="blue"))


@app.command("list-templates")
def list_app_templates():
    """List available app templates"""

    templates = {
        "default": "Standard app with models, views, admin, and tests",
        "minimal": "Minimal app structure with basic files",
        "api": "API-focused app with serializers and viewsets",
        "crud": "Full CRUD app with all operations",
        "readonly": "Read-only app for data display",
        "auth": "Authentication app with user management",
        "blog": "Blog app example with posts and comments",
        "ecommerce": "E-commerce app with products and orders",
    }

    template_text = "[bold]Available App Templates:[/bold]\n\n"

    for template_name, description in templates.items():
        template_text += f"• [cyan]{template_name}[/cyan]: {description}\n"

    template_text += (
        "\n[dim]Use: fabiplus app startapp myapp --template <template_name>[/dim]"
    )

    console.print(Panel(template_text, title="App Templates", border_style="blue"))


@app.command("remove")
def remove_app(
    name: str = typer.Argument(..., help="App name to remove"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force removal without confirmation"
    ),
):
    """
    Remove an existing FABI+ app

    This will:
    - Remove the app directory and all files
    - Remove from INSTALLED_APPS in settings
    - Check for model dependencies
    """

    # Look for app in apps/ directory first, then root
    app_dir = Path.cwd() / "apps" / name
    if not app_dir.exists():
        app_dir = Path.cwd() / name

    if not app_dir.exists():
        console.print(f"[red]❌ App '{name}' not found[/red]")
        raise typer.Exit(1)

    # Check for model dependencies
    try:
        from ...core.models import ModelRegistry

        ModelRegistry.discover_models()
        models = ModelRegistry.get_all_models()

        app_models = [
            model_name
            for model_name, model_class in models.items()
            if hasattr(model_class, "__module__") and name in model_class.__module__
        ]

        if app_models and not force:
            console.print(
                f"[yellow]⚠️  App '{name}' has registered models: {', '.join(app_models)}[/yellow]"
            )
            console.print(
                "[yellow]This may affect other apps that depend on these models.[/yellow]"
            )
    except Exception as e:
        console.print(
            f"[yellow]Warning: Could not check model dependencies: {e}[/yellow]"
        )

    if not force:
        confirm = typer.confirm(
            f"Are you sure you want to remove app '{name}' and all its files?"
        )
        if not confirm:
            console.print("[yellow]App removal cancelled[/yellow]")
            return

    try:
        # Remove app directory
        import shutil

        shutil.rmtree(app_dir)

        # Remove from INSTALLED_APPS
        settings_file = Path.cwd() / f"{Path.cwd().name}" / "settings.py"
        if settings_file.exists():
            content = settings_file.read_text()
            lines = content.split("\n")
            new_lines = []
            in_installed_apps = False

            for line in lines:
                if "INSTALLED_APPS" in line and "=" in line:
                    in_installed_apps = True
                    new_lines.append(line)
                elif in_installed_apps and line.strip() == "]":
                    in_installed_apps = False
                    new_lines.append(line)
                elif in_installed_apps and f'"{name}"' in line:
                    continue  # Skip this app
                else:
                    new_lines.append(line)

            settings_file.write_text("\n".join(new_lines))

        console.print(f"[green]✅ App '{name}' removed successfully[/green]")
        console.print(
            "[yellow]Note: You may need to create and run migrations to remove database tables[/yellow]"
        )

    except Exception as e:
        console.print(f"[red]❌ Error removing app: {e}[/red]")
        raise typer.Exit(1)


@app.command("addmodel")
def add_model(
    app_name: str = typer.Argument(..., help="App name"),
    model_name: str = typer.Argument(..., help="Model name"),
    fields: str = typer.Option(
        "", "--fields", "-f", help="Model fields (name:str,email:str,age:int)"
    ),
):
    """
    Add a new model to an existing app

    Example:
    fabiplus app addmodel blog Post --fields "title:str,content:str,published:bool"
    """

    # Look for app in apps/ directory first, then root
    app_dir = Path.cwd() / "apps" / app_name
    if not app_dir.exists():
        app_dir = Path.cwd() / app_name

    if not app_dir.exists():
        console.print(f"[red]❌ App '{app_name}' not found[/red]")
        raise typer.Exit(1)

    models_file = app_dir / "models.py"
    if not models_file.exists():
        console.print(f"[red]❌ models.py not found in app '{app_name}'[/red]")
        raise typer.Exit(1)

    # Parse fields
    model_fields = []
    if fields:
        for field_def in fields.split(","):
            if ":" in field_def:
                field_name, field_type = field_def.strip().split(":", 1)
                model_fields.append((field_name.strip(), field_type.strip()))

    # Generate model code
    model_code = f"""

@register_model
class {model_name}(BaseModel, table=True):
    \"\"\"Generated model for {model_name}\"\"\"

"""

    for field_name, field_type in model_fields:
        if field_type.lower() in ["str", "string"]:
            model_code += f'    {field_name}: str = Field(max_length=200, description="{field_name.title()}")\n'
        elif field_type.lower() in ["int", "integer"]:
            model_code += (
                f'    {field_name}: int = Field(description="{field_name.title()}")\n'
            )
        elif field_type.lower() in ["bool", "boolean"]:
            model_code += f'    {field_name}: bool = Field(default=False, description="{field_name.title()}")\n'
        elif field_type.lower() in ["float", "decimal"]:
            model_code += (
                f'    {field_name}: float = Field(description="{field_name.title()}")\n'
            )
        else:
            model_code += (
                f'    {field_name}: str = Field(description="{field_name.title()}")\n'
            )

    if not model_fields:
        model_code += (
            f'    name: str = Field(max_length=100, description="{model_name} name")\n'
        )
        model_code += f'    description: Optional[str] = Field(default="", description="{model_name} description")\n'

    model_code += f"""
    class Config:
        _verbose_name = "{model_name}"
        _verbose_name_plural = "{model_name}s"

    def __str__(self):
        return self.{model_fields[0][0] if model_fields else 'name'}
"""

    # Append to models.py
    try:
        current_content = models_file.read_text()
        models_file.write_text(current_content + model_code)

        console.print(
            f"[green]✅ Model '{model_name}' added to app '{app_name}'[/green]"
        )
        console.print(
            "[yellow]Don't forget to run 'fabiplus db makemigrations' and 'fabiplus db migrate'[/yellow]"
        )

    except Exception as e:
        console.print(f"[red]❌ Error adding model: {e}[/red]")
        raise typer.Exit(1)


@app.command("generate")
def generate_code(
    app_name: str = typer.Argument(..., help="App name"),
    model_name: str = typer.Argument(..., help="Model name"),
    fields: str = typer.Option(
        "", "--fields", "-f", help="Model fields (name:type,email:str)"
    ),
    admin: bool = typer.Option(
        True, "--admin/--no-admin", help="Generate admin configuration"
    ),
    views: bool = typer.Option(True, "--views/--no-views", help="Generate API views"),
    tests: bool = typer.Option(True, "--tests/--no-tests", help="Generate test cases"),
):
    """
    Generate model, views, admin, and tests for an app

    Example:
    fabiplus app generate blog Post --fields "title:str,content:text,published:bool"
    """

    app_dir = Path.cwd() / app_name

    if not app_dir.exists():
        console.print(f"[red]Error: App '{app_name}' does not exist[/red]")
        raise typer.Exit(1)

    # Parse fields
    field_list = []
    if fields:
        for field_def in fields.split(","):
            if ":" in field_def:
                field_name, field_type = field_def.split(":", 1)
                field_list.append((field_name.strip(), field_type.strip()))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating code...", total=None)

        try:
            template_engine = AppTemplate(app_name, "default")
            template_engine.generate_model_code(
                app_dir,
                model_name,
                field_list,
                generate_admin=admin,
                generate_views=views,
                generate_tests=tests,
            )

            progress.update(task, description="Code generated successfully!")

        except Exception as e:
            console.print(f"[red]Error generating code: {e}[/red]")
            raise typer.Exit(1)

    success_text = f"""
[bold green]✅ Code generated for {model_name} in {app_name}![/bold green]

[bold]Generated files:[/bold]
• Updated [cyan]{app_name}/models.py[/cyan]
"""

    if admin:
        success_text += f"• Updated [cyan]{app_name}/admin.py[/cyan]\n"
    if views:
        success_text += f"• Updated [cyan]{app_name}/views.py[/cyan]\n"
    if tests:
        success_text += f"• Updated [cyan]{app_name}/tests.py[/cyan]\n"

    success_text += f"""
[bold]Next steps:[/bold]
1. Run [cyan]fabiplus db makemigrations[/cyan]
2. Run [cyan]fabiplus db migrate[/cyan]
3. Test your new model: [cyan]fabiplus server run[/cyan]
"""

    console.print(Panel(success_text, title="Code Generated", border_style="green"))


@app.command("delete")
def delete_app(
    app_name: str = typer.Argument(..., help="App name to delete"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force delete without confirmation"
    ),
    keep_data: bool = typer.Option(
        False, "--keep-data", help="Keep database data (only delete files)"
    ),
):
    """
    Delete an app and all its data (DANGEROUS!)

    This will:
    1. Drop all database tables for the app's models
    2. Delete all data in those tables
    3. Remove the app directory and files
    4. Remove app from INSTALLED_APPS
    """

    app_dir = Path.cwd() / app_name

    if not app_dir.exists():
        console.print(f"[red]❌ App '{app_name}' does not exist[/red]")
        raise typer.Exit(1)

    # Check if it's a valid FABI+ app
    if not (app_dir / "models.py").exists():
        console.print(
            f"[red]❌ '{app_name}' is not a valid FABI+ app (no models.py)[/red]"
        )
        raise typer.Exit(1)

    # Show warning
    warning_text = f"""
[bold red]⚠️  DANGER: This will permanently delete:[/bold red]

• App directory: [cyan]{app_name}/[/cyan]
• All app files (models, views, admin, tests)
• All database tables for this app's models
• All data in those tables
• App entry from INSTALLED_APPS

[bold red]This action cannot be undone![/bold red]
"""

    console.print(Panel(warning_text, title="Deletion Warning", border_style="red"))

    if not force:
        # Double confirmation
        confirm1 = typer.confirm(
            f"Are you sure you want to delete app '{app_name}' and ALL its data?"
        )
        if not confirm1:
            console.print("[yellow]App deletion cancelled[/yellow]")
            return

        confirm2 = typer.confirm(
            "This will permanently delete all data. Type 'yes' to confirm",
            default=False,
        )
        if not confirm2:
            console.print("[yellow]App deletion cancelled[/yellow]")
            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        try:
            # Step 1: Get app models and drop tables
            if not keep_data:
                task = progress.add_task("Analyzing app models...", total=None)
                models_to_drop = _get_app_models(app_name, app_dir)

                if models_to_drop:
                    progress.update(
                        task,
                        description=f"Dropping {len(models_to_drop)} database tables...",
                    )
                    _drop_app_tables(models_to_drop)
                    progress.update(task, description="Database tables dropped")
                else:
                    progress.update(task, description="No database tables found")

            # Step 2: Remove from INSTALLED_APPS
            task2 = progress.add_task("Removing from INSTALLED_APPS...", total=None)
            _remove_app_from_settings(app_name)
            progress.update(task2, description="Removed from INSTALLED_APPS")

            # Step 3: Delete app directory
            task3 = progress.add_task("Deleting app files...", total=None)
            import shutil

            shutil.rmtree(app_dir)
            progress.update(task3, description="App files deleted")

            console.print(f"[green]✅ App '{app_name}' deleted successfully![/green]")

            if keep_data:
                console.print(
                    "[yellow]Note: Database data was preserved (--keep-data flag)[/yellow]"
                )

        except Exception as e:
            console.print(f"[red]❌ Error deleting app: {e}[/red]")
            raise typer.Exit(1)


def _get_app_models(app_name: str, app_dir: Path) -> list:
    """Get list of models defined in the app"""
    models = []
    models_file = app_dir / "models.py"

    if not models_file.exists():
        return models

    try:
        with open(models_file, "r") as f:
            content = f.read()

        # Simple regex to find model classes
        import re

        # Look for classes that inherit from BaseModel and have table=True
        pattern = r"class\s+(\w+)\s*\([^)]*BaseModel[^)]*\).*?table\s*=\s*True"
        matches = re.findall(pattern, content, re.DOTALL)

        for match in matches:
            models.append(
                {
                    "name": match,
                    "table_name": _camel_to_snake(match),
                    "app_name": app_name,
                }
            )

    except Exception as e:
        console.print(f"[yellow]Warning: Could not parse models.py: {e}[/yellow]")

    return models


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case"""
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _drop_app_tables(models: list):
    """Drop database tables for app models"""
    try:
        # Import here to avoid circular imports
        from ...core.models import ModelRegistry

        engine = ModelRegistry.create_engine()

        with engine.connect() as conn:
            for model in models:
                table_name = model["table_name"]
                try:
                    # Drop table if exists using text() for raw SQL
                    from sqlalchemy import text

                    conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                    console.print(f"  [dim]Dropped table: {table_name}[/dim]")
                except Exception as e:
                    console.print(
                        f"  [yellow]Warning: Could not drop table {table_name}: {e}[/yellow]"
                    )

            conn.commit()

    except Exception as e:
        console.print(f"[red]Error dropping tables: {e}[/red]")
        raise


def _remove_app_from_settings(app_name: str):
    """Remove app from INSTALLED_APPS in settings"""
    current_dir = Path.cwd()

    # Look for settings.py in common locations
    settings_files = [
        current_dir / "settings.py",
        current_dir / current_dir.name / "settings.py",
    ]

    settings_file = None
    for file_path in settings_files:
        if file_path.exists():
            settings_file = file_path
            break

    if not settings_file:
        console.print("[yellow]Could not find settings.py file[/yellow]")
        return

    try:
        # Read current settings
        with open(settings_file, "r") as f:
            content = f.read()

        # Remove app from INSTALLED_APPS
        app_entries = [
            f'"apps.{app_name}",',
            f"'apps.{app_name}',",
            f'"apps.{app_name}"',
            f"'apps.{app_name}'",
        ]

        modified = False
        for entry in app_entries:
            if entry in content:
                # Remove the entry and any surrounding whitespace
                import re

                pattern = r"\s*" + re.escape(entry) + r"\s*"
                content = re.sub(pattern, "", content)
                modified = True
                break

        # Clean up empty lines and trailing commas
        import re

        content = re.sub(
            r",\s*\n\s*\]", "\n]", content
        )  # Remove trailing comma before ]
        content = re.sub(
            r"\n\s*\n\s*\n", "\n\n", content
        )  # Remove multiple empty lines

        if modified:
            # Write back to file
            with open(settings_file, "w") as f:
                f.write(content)

            console.print(f"[green]✅ Removed '{app_name}' from INSTALLED_APPS[/green]")
        else:
            console.print(
                f"[yellow]App '{app_name}' not found in INSTALLED_APPS[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]❌ Error updating settings: {e}[/red]")


def _add_app_to_settings(app_name: str):
    """Add app to INSTALLED_APPS in settings"""
    current_dir = Path.cwd()

    # Look for settings.py in common locations
    settings_files = [
        current_dir / "settings.py",
        current_dir / current_dir.name / "settings.py",
    ]

    settings_file = None
    for file_path in settings_files:
        if file_path.exists():
            settings_file = file_path
            break

    if not settings_file:
        console.print("[yellow]Could not find settings.py file[/yellow]")
        return

    try:
        # Read current settings
        with open(settings_file, "r") as f:
            content = f.read()

        # Check if app already in INSTALLED_APPS (and not commented out)
        app_entry = f'"apps.{app_name}"'
        import re

        # Look for the app entry that's not commented out
        pattern = rf"^\s*{re.escape(app_entry)}\s*,?\s*$"
        if re.search(pattern, content, re.MULTILINE):
            console.print(
                f"[yellow]App '{app_name}' already in INSTALLED_APPS[/yellow]"
            )
            return

        # Find INSTALLED_APPS and add the app
        pattern = r"(INSTALLED_APPS\s*=\s*\[)(.*?)(\])"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            before, apps_content, after = match.groups()

            # Add the new app
            if apps_content.strip():
                new_content = content.replace(
                    match.group(0),
                    f"{before}{apps_content.rstrip()}\n    {app_entry},\n{after}",
                )
            else:
                new_content = content.replace(
                    match.group(0), f"{before}\n    {app_entry},\n{after}"
                )

            # Write back to file
            with open(settings_file, "w") as f:
                f.write(new_content)

            console.print(f"[green]✅ Added '{app_name}' to INSTALLED_APPS[/green]")
        else:
            console.print(
                "[yellow]Could not find INSTALLED_APPS in settings.py[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]❌ Error updating settings: {e}[/red]")


def _is_fabiplus_project() -> bool:
    """Check if current directory is a FABI+ project"""
    current_dir = Path.cwd()

    # Check for pyproject.toml with fabiplus
    pyproject_file = current_dir / "pyproject.toml"
    if pyproject_file.exists():
        try:
            with open(pyproject_file) as f:
                if "fabiplus" in f.read():
                    return True
        except Exception:
            pass

    # Check for manage.py
    if (current_dir / "manage.py").exists():
        return True

    # Check for settings.py
    if (current_dir / "settings.py").exists():
        return True

    return False


def _detect_project_orm_backend() -> str:
    """Detect the ORM backend used in the current project"""
    try:
        current_dir = Path.cwd()

        # Look for settings.py in current directory structure
        for settings_file in current_dir.rglob("settings.py"):
            if settings_file.parent.name != "migrations":  # Skip migration settings
                try:
                    # Read the settings file
                    content = settings_file.read_text()

                    # Look for ORM_BACKEND setting
                    for line in content.split("\n"):
                        if "ORM_BACKEND" in line and "=" in line:
                            # Extract the value
                            value = line.split("=")[1].strip().strip("\"'")
                            if value in ["sqlmodel", "sqlalchemy", "tortoise"]:
                                return value

                    # Check for Tortoise ORM configuration
                    if "TORTOISE_ORM" in content:
                        return "tortoise"

                    # Check for SQLModel imports
                    if (
                        "from sqlmodel import" in content
                        or "import sqlmodel" in content
                    ):
                        return "sqlmodel"

                    # Check for SQLAlchemy imports
                    if (
                        "from sqlalchemy import" in content
                        or "import sqlalchemy" in content
                    ):
                        return "sqlalchemy"

                except Exception:
                    continue

        # Default to sqlmodel
        return "sqlmodel"

    except Exception:
        return "sqlmodel"
