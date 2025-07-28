"""
Development tools and utilities
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()
app = typer.Typer()


@app.command("shell")
def interactive_shell():
    """Start an interactive Python shell with FABI+ context"""

    # Import commonly used modules
    import fabiplus
    from fabiplus.conf.settings import settings
    from fabiplus.core.auth import auth_backend
    from fabiplus.core.models import BaseModel, ModelRegistry, User

    # Create shell context
    context = {
        "fabiplus": fabiplus,
        "BaseModel": BaseModel,
        "ModelRegistry": ModelRegistry,
        "User": User,
        "auth_backend": auth_backend,
        "settings": settings,
        "session": ModelRegistry.get_session(),
    }

    console.print("[bold blue]FABI+ Interactive Shell[/bold blue]")
    console.print("Available objects:")
    for name, obj in context.items():
        console.print(f"  [cyan]{name}[/cyan]: {type(obj).__name__}")

    try:
        # Try to use IPython if available
        from IPython import start_ipython

        start_ipython(argv=[], user_ns=context)
    except ImportError:
        # Fall back to standard Python shell
        import code

        code.interact(local=context)


@app.command("models")
def show_models():
    """Show all registered models with details"""

    from ...core.models import ModelRegistry

    models = ModelRegistry.get_all_models()

    if not models:
        console.print("[yellow]No models registered[/yellow]")
        return

    console.print("[bold]Registered Models:[/bold]")
    console.print("=" * 50)

    for model_name, model_class in models.items():
        console.print(f"\n[cyan]Model: {model_name}[/cyan]")
        console.print(f"  Class: {model_class.__name__}")
        console.print(f"  Table: {model_class.get_table_name()}")

        # Show fields
        fields = []
        for field_name, field_info in model_class.model_fields.items():
            field_type = str(field_info.type_).replace("typing.", "")
            required = "required" if field_info.required else "optional"
            fields.append(f"    {field_name}: {field_type} ({required})")

        console.print("  Fields:")
        for field in fields:
            console.print(field)


@app.command("routes")
def show_routes():
    """Show all API routes"""

    console.print("[bold]API Routes:[/bold]")
    console.print("This feature will show all registered routes")
    console.print("[yellow]Route inspection not yet implemented[/yellow]")


@app.command("config")
def show_config():
    """Show current configuration"""

    from ...conf.settings import settings

    config_panel = f"""
[bold]Application Configuration:[/bold]

[cyan]Basic Settings:[/cyan]
• App Name: {settings.APP_NAME}
• Version: {settings.APP_VERSION}
• Environment: {settings.ENVIRONMENT}
• Debug: {settings.DEBUG}

[cyan]Server Settings:[/cyan]
• Host: {settings.HOST}
• Port: {settings.PORT}
• Reload: {settings.RELOAD}

[cyan]Database:[/cyan]
• URL: {settings.DATABASE_URL}
• Echo: {settings.DATABASE_ECHO}

[cyan]API Settings:[/cyan]
• Prefix: {settings.API_PREFIX}
• Version: {settings.API_VERSION}

[cyan]Admin Settings:[/cyan]
• Enabled: {settings.ADMIN_ENABLED}
• Prefix: {settings.ADMIN_PREFIX}

[cyan]Authentication:[/cyan]
• Backend: {settings.AUTH_BACKEND}
• Global Auth Required: {settings.AUTH_REQUIRED_GLOBALLY}
• Token Expiry: {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes

[cyan]Security:[/cyan]
• CORS Origins: {settings.CORS_ORIGINS}
• Secret Key: {'***HIDDEN***'}

[cyan]Caching:[/cyan]
• Backend: {settings.CACHE_BACKEND}
• TTL: {settings.CACHE_TTL} seconds
"""

    console.print(Panel(config_panel, title="Configuration", border_style="blue"))


@app.command("test")
def run_tests(
    path: str = typer.Option(".", "--path", "-p", help="Test path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    coverage: bool = typer.Option(False, "--coverage", "-c", help="Run with coverage"),
):
    """Run tests"""

    import subprocess

    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(["--cov=fabiplus", "--cov-report=term-missing"])

    cmd.append(path)

    console.print(f"[blue]Running tests: {' '.join(cmd)}[/blue]")

    try:
        result = subprocess.run(cmd, check=True)
        console.print("[green]✅ Tests completed successfully[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Tests failed with exit code {e.returncode}[/red]")
        raise typer.Exit(e.returncode)


@app.command("lint")
def run_linting():
    """Run code linting"""

    import subprocess

    tools = [
        (["black", "--check", "."], "Black (code formatting)"),
        (["isort", "--check-only", "."], "isort (import sorting)"),
        (["flake8", "."], "Flake8 (style guide)"),
    ]

    for cmd, tool_name in tools:
        console.print(f"[blue]Running {tool_name}...[/blue]")

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            console.print(f"[green]✅ {tool_name} passed[/green]")
        except subprocess.CalledProcessError:
            console.print(f"[red]❌ {tool_name} failed[/red]")
        except FileNotFoundError:
            console.print(f"[yellow]⚠️  {tool_name} not installed[/yellow]")


@app.command("format")
def format_code():
    """Format code with Black and isort"""

    import subprocess

    tools = [
        (["black", "."], "Black (code formatting)"),
        (["isort", "."], "isort (import sorting)"),
    ]

    for cmd, tool_name in tools:
        console.print(f"[blue]Running {tool_name}...[/blue]")

        try:
            subprocess.run(cmd, check=True)
            console.print(f"[green]✅ {tool_name} completed[/green]")
        except subprocess.CalledProcessError:
            console.print(f"[red]❌ {tool_name} failed[/red]")
        except FileNotFoundError:
            console.print(f"[yellow]⚠️  {tool_name} not installed[/yellow]")


@app.command("docs")
def generate_docs():
    """Generate documentation"""

    console.print("[blue]Generating documentation...[/blue]")
    console.print("[yellow]Documentation generation not yet implemented[/yellow]")
    console.print("This will use MkDocs to generate project documentation")


@app.command("example")
def show_example():
    """Show example model and usage"""

    example_code = """
# Example FABI+ Model
from fabiplus.core.models import BaseModel, register_model
from sqlmodel import Field
from typing import Optional

@register_model
class Blog(BaseModel, table=True):
    title: str = Field(max_length=200)
    content: str
    published: bool = Field(default=False)
    author_id: Optional[str] = None
    
    def __str__(self):
        return self.title

# This automatically creates:
# - GET /api/blog/ (list with pagination)
# - GET /api/blog/{id}/ (retrieve)
# - POST /api/blog/ (create)
# - PUT /api/blog/{id}/ (update)
# - DELETE /api/blog/{id}/ (delete)
# - Admin interface at /admin/blog/
"""

    syntax = Syntax(example_code, "python", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="Example FABI+ Model", border_style="green"))
