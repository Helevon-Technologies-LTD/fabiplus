"""
Project scaffolding commands
Django-style project creation with proper structure
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..templates import ProjectTemplate

console = Console()
app = typer.Typer()


@app.command("startproject")
def start_project(
    name: str = typer.Argument(..., help="Project name"),
    directory: Optional[str] = typer.Option(
        None, "--dir", "-d", help="Directory to create project in"
    ),
    template: Optional[str] = typer.Option(
        "default", "--template", "-t", help="Project template to use"
    ),
    orm: Optional[str] = typer.Option(
        "sqlmodel", "--orm", "-o", help="ORM backend (sqlmodel, sqlalchemy)"
    ),
    auth: Optional[str] = typer.Option(
        "oauth2", "--auth", "-a", help="Authentication backend (oauth2, jwt)"
    ),
    show_admin_routes: bool = typer.Option(
        False, "--show-admin-routes", help="Show admin routes in API docs"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing directory"
    ),
    docker: bool = typer.Option(False, "--docker", help="Include Docker files"),
):
    """
    Create a new FABI+ project with proper structure

    This creates a new project directory with:
    - Project configuration files
    - Basic app structure
    - Docker configuration
    - Poetry setup
    - Example models and views
    """

    # Validate project name
    if not name.isidentifier():
        console.print(f"[red]Error: '{name}' is not a valid Python identifier[/red]")
        raise typer.Exit(1)

    # Validate ORM backend
    from fabiplus.core.orm import ORMRegistry

    available_orms = ORMRegistry.list_backends()
    if orm not in available_orms:
        console.print(f"[red]Error: Unknown ORM backend '{orm}'[/red]")
        console.print(f"Available backends: {', '.join(available_orms)}")
        raise typer.Exit(1)

    # Validate authentication backend
    available_auth = ["oauth2", "jwt"]
    if auth not in available_auth:
        console.print(f"[red]Error: Unknown authentication backend '{auth}'[/red]")
        console.print(f"Available backends: {', '.join(available_auth)}")
        raise typer.Exit(1)

    # Determine project directory
    if directory:
        project_dir = Path(directory) / name
    else:
        project_dir = Path.cwd() / name

    # Check if directory exists
    if project_dir.exists() and not force:
        console.print(f"[red]Error: Directory '{project_dir}' already exists[/red]")
        console.print("Use --force to overwrite existing directory")
        raise typer.Exit(1)

    # Create project
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating project...", total=None)

        try:
            # Create project structure
            template_engine = ProjectTemplate(
                name,
                template,
                include_docker=docker,
                orm_backend=orm,
                auth_backend=auth,
                show_admin_routes=show_admin_routes,
            )
            template_engine.create_project(project_dir, force=force)

            progress.update(task, description="Project created successfully!")

        except Exception as e:
            console.print(f"[red]Error creating project: {e}[/red]")
            raise typer.Exit(1)

    # Success message
    success_text = f"""
[bold green]✅ Project '{name}' created successfully![/bold green]

[bold]Next steps:[/bold]
1. [cyan]cd {name}[/cyan]
2. [cyan]poetry install[/cyan]
3. [cyan]fabiplus app startapp myapp[/cyan]
4. [cyan]fabiplus server run[/cyan]"""

    if docker:
        success_text += """
5. [cyan]docker-compose up[/cyan] (for Docker deployment)"""

    success_text += f"""

[bold]Project structure:[/bold]
• [blue]{name}/[/blue] - Main project directory
• [blue]{name}/settings.py[/blue] - Project settings
• [blue]{name}/urls.py[/blue] - URL configuration
• [blue]manage.py[/blue] - Management script
• [blue]pyproject.toml[/blue] - Poetry configuration"""

    if docker:
        success_text += """

[bold]Docker files:[/bold]
• [blue]Dockerfile[/blue] - Container definition
• [blue]docker-compose.yml[/blue] - Multi-service setup
• [blue].dockerignore[/blue] - Docker ignore rules
• [blue]requirements.txt[/blue] - Python dependencies"""

    console.print(Panel(success_text, title="Project Created", border_style="green"))


@app.command("list-templates")
def list_templates():
    """List available project templates"""

    templates = {
        "default": "Basic FABI+ project with essential features",
        "minimal": "Minimal project structure for simple APIs",
        "full": "Full-featured project with all plugins and examples",
        "microservice": "Microservice-oriented project structure",
        "monolith": "Monolithic application structure",
    }

    template_text = "[bold]Available Project Templates:[/bold]\n\n"

    for template_name, description in templates.items():
        template_text += f"• [cyan]{template_name}[/cyan]: {description}\n"

    template_text += "\n[dim]Use: fabiplus project startproject myproject --template <template_name>[/dim]"

    console.print(Panel(template_text, title="Project Templates", border_style="blue"))


@app.command("list-orms")
def list_orms():
    """List available ORM backends"""

    from fabiplus.core.orm import ORMRegistry

    orm_text = "[bold]Available ORM Backends:[/bold]\n\n"

    for orm_name in ORMRegistry.list_backends():
        try:
            info = ORMRegistry.get_backend_info(orm_name)
            orm_text += f"• [cyan]{orm_name}[/cyan]: "

            if info["supports_async"]:
                orm_text += "[green]Async[/green] "
            else:
                orm_text += "[yellow]Sync[/yellow] "

            orm_text += f"({len(info['dependencies'])} dependencies)\n"
            orm_text += f"  [dim]Field types: {', '.join(info['field_types'][:5])}{'...' if len(info['field_types']) > 5 else ''}[/dim]\n\n"

        except Exception as e:
            orm_text += (
                f"• [cyan]{orm_name}[/cyan]: [red]Error loading info: {e}[/red]\n\n"
            )

    orm_text += (
        "[dim]Use: fabiplus project startproject myproject --orm <orm_name>[/dim]"
    )

    console.print(Panel(orm_text, title="ORM Backends", border_style="blue"))


@app.command("init")
def init_project(
    force: bool = typer.Option(
        False, "--force", "-f", help="Initialize in non-empty directory"
    )
):
    """
    Initialize FABI+ in existing directory

    This adds FABI+ configuration to an existing project directory
    """

    current_dir = Path.cwd()

    # Check if directory has files
    if list(current_dir.iterdir()) and not force:
        console.print("[red]Error: Directory is not empty[/red]")
        console.print("Use --force to initialize in non-empty directory")
        raise typer.Exit(1)

    # Check if already a FABI+ project
    if (current_dir / "pyproject.toml").exists():
        with open(current_dir / "pyproject.toml") as f:
            if "fabiplus" in f.read():
                console.print(
                    "[yellow]Warning: This appears to be a FABI+ project already[/yellow]"
                )
                if not typer.confirm("Continue anyway?"):
                    raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing project...", total=None)

        try:
            # Create basic FABI+ structure
            project_name = current_dir.name
            template_engine = ProjectTemplate(project_name, "minimal")
            template_engine.init_existing_project(current_dir)

            progress.update(task, description="Project initialized successfully!")

        except Exception as e:
            console.print(f"[red]Error initializing project: {e}[/red]")
            raise typer.Exit(1)

    success_text = """
[bold green]✅ FABI+ initialized in current directory![/bold green]

[bold]Next steps:[/bold]
1. [cyan]poetry install[/cyan]
2. [cyan]fabiplus app startapp myapp[/cyan]
3. [cyan]fabiplus server run[/cyan]

[bold]Files created:[/bold]
• [blue]pyproject.toml[/blue] - Poetry configuration
• [blue]manage.py[/blue] - Management script
• [blue].env.example[/blue] - Environment template
• [blue]settings.py[/blue] - Project settings
"""

    console.print(
        Panel(success_text, title="Project Initialized", border_style="green")
    )


def _create_project_docker_files(project_dir: Path, project_name: str):
    """Create Docker files for the project"""

    # Dockerfile
    dockerfile_content = """# FABI+ Project Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \\
    && apt-get install -y --no-install-recommends \\
        gcc \\
        postgresql-client \\
        curl \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser \\
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["fabiplus", "server", "run", "--host", "0.0.0.0", "--port", "8000"]
"""

    # docker-compose.yml
    docker_compose_content = f"""version: '3.8'

services:
  {project_name}:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/{project_name}_db
      - REDIS_URL=redis://redis:6379/0
      - DEBUG=false
    depends_on:
      - db
      - redis
    volumes:
      - .:/app
    command: fabiplus server run --host 0.0.0.0 --port 8000

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB={project_name}_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
"""

    # .dockerignore
    dockerignore_content = """# FABI+ Docker ignore
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
MANIFEST

# PyInstaller
*.manifest
*.spec

# Unit test / coverage reports
htmlcov/
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
.hypothesis/
.pytest_cache/

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# FABI+ specific
*.db
*.sqlite3
migrations/versions/
logs/
.fabiplus/
"""

    # requirements.txt
    requirements_content = """# FABI+ Project Requirements
fabiplus>=0.1.0
uvicorn[standard]>=0.24.0
gunicorn>=21.2.0
psycopg2-binary>=2.9.7
redis>=5.0.0
python-multipart>=0.0.6
"""

    try:
        # Write Docker files
        (project_dir / "Dockerfile").write_text(dockerfile_content)
        (project_dir / "docker-compose.yml").write_text(docker_compose_content)
        (project_dir / ".dockerignore").write_text(dockerignore_content)
        (project_dir / "requirements.txt").write_text(requirements_content)

        console.print(f"  [dim]Created Docker files for {project_name}[/dim]")

    except Exception as e:
        console.print(f"[yellow]Warning: Could not create Docker files: {e}[/yellow]")
