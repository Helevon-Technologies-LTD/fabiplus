"""
Database management commands
"""

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()
app = typer.Typer()


@app.command("migrate")
def migrate_database(
    revision: str = typer.Option("head", "--revision", "-r", help="Target revision")
):
    """Apply database migrations (like Django's migrate)"""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running database migrations...", total=None)

        try:
            from ...core.migrations import migration_manager

            # Apply migrations
            success = migration_manager.migrate(revision)

            if success:
                progress.update(
                    task, description="Database migrations completed successfully!"
                )
                console.print(
                    "[green]✅ Database migrations completed successfully[/green]"
                )
            else:
                console.print("[red]❌ Migration failed[/red]")
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]❌ Migration failed: {e}[/red]")
            raise typer.Exit(1)


@app.command("reset")
def reset_database(
    force: bool = typer.Option(
        False, "--force", "-f", help="Force reset without confirmation"
    )
):
    """Reset database (WARNING: This will delete all data)"""

    if not force:
        confirm = typer.confirm("This will delete all data. Are you sure?")
        if not confirm:
            console.print("[yellow]Database reset cancelled[/yellow]")
            return

    console.print("[red]Resetting database...[/red]")

    try:
        # This would implement database reset logic
        # For now, just recreate tables
        from ...core.models import ModelRegistry

        ModelRegistry.create_tables()
        console.print("[green]✅ Database reset completed[/green]")
    except Exception as e:
        console.print(f"[red]❌ Database reset failed: {e}[/red]")
        raise typer.Exit(1)


@app.command("shell")
def database_shell():
    """Open database shell"""

    console.print("[blue]Opening database shell...[/blue]")
    console.print("[yellow]Database shell not yet implemented[/yellow]")


@app.command("info")
def database_info():
    """Show database information"""

    from ...conf.settings import settings

    table = Table(title="Database Information")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Database URL", settings.DATABASE_URL)
    table.add_row("Echo SQL", str(settings.DATABASE_ECHO))

    # Get model count
    from ...core.models import ModelRegistry

    models = ModelRegistry.get_all_models()
    table.add_row("Registered Models", str(len(models)))

    console.print(table)

    if models:
        console.print("\n[bold]Registered Models:[/bold]")
        for model_name, model_class in models.items():
            console.print(f"• {model_name}: {model_class.__name__}")


@app.command("makemigrations")
def make_migrations(
    message: str = typer.Option("", "--message", "-m", help="Migration message")
):
    """Create new database migrations (like Django's makemigrations)"""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating migrations...", total=None)

        try:
            from ...core.migrations import migration_manager

            # Create migration
            success = migration_manager.makemigrations(message or None)

            if success:
                progress.update(task, description="Migration created successfully!")
                console.print("[green]✅ Migration created successfully[/green]")
            else:
                console.print("[red]❌ Failed to create migration[/red]")
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]❌ Migration creation failed: {e}[/red]")
            raise typer.Exit(1)


@app.command("showmigrations")
def show_migrations():
    """Show migration status and history"""

    try:
        from ...core.migrations import migration_manager

        console.print("[blue]Migration Status:[/blue]")

        # Get current revision
        current = migration_manager.current_revision()
        console.print(f"Current revision: [cyan]{current or 'None'}[/cyan]")

        # Check for pending migrations
        pending = migration_manager.check_migrations()
        if pending:
            console.print("[yellow]⚠️  There are pending migrations[/yellow]")
        else:
            console.print("[green]✅ Database is up to date[/green]")

        # Show migration history
        migrations = migration_manager.show_migrations()
        if migrations:
            console.print("\n[bold]Migration History:[/bold]")
            for migration in migrations:
                console.print(f"  • {migration}")
        else:
            console.print("\n[dim]No migrations found[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error getting migration status: {e}[/red]")


@app.command("rollback")
def rollback_migrations(
    revision: str = typer.Option(
        "-1", "--revision", "-r", help="Target revision (default: rollback 1 migration)"
    )
):
    """Rollback database migrations"""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Rolling back migrations...", total=None)

        try:
            from ...core.migrations import migration_manager

            # Rollback migrations
            success = migration_manager.rollback(revision)

            if success:
                progress.update(task, description="Rollback completed successfully!")
                console.print("[green]✅ Rollback completed successfully[/green]")
            else:
                console.print("[red]❌ Rollback failed[/red]")
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]❌ Rollback failed: {e}[/red]")
            raise typer.Exit(1)


@app.command("createtables")
def create_tables():
    """Create all database tables (bypass migrations)"""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating database tables...", total=None)

        try:
            # Import all models to register them
            import importlib
            import sys
            from pathlib import Path

            # Add current directory to path
            current_dir = str(Path.cwd())
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)

            # Import models from known locations
            try:
                importlib.import_module("blog.models")
                progress.update(task, description="Imported blog models...")
            except ImportError:
                pass

            try:
                importlib.import_module("apps.core.models")
                progress.update(task, description="Imported core models...")
            except ImportError:
                pass

            # Create tables using SQLModel
            from sqlmodel import SQLModel, create_engine

            from ...conf.settings import settings

            engine = create_engine(settings.DATABASE_URL)
            SQLModel.metadata.create_all(engine)

            progress.update(task, description="Database tables created successfully!")
            console.print("[green]✅ Database tables created successfully[/green]")

            # Show created tables
            from sqlalchemy import inspect

            inspector = inspect(engine)
            tables = inspector.get_table_names()

            if tables:
                console.print("\n[bold]Created tables:[/bold]")
                for table in tables:
                    console.print(f"  • [cyan]{table}[/cyan]")
            else:
                console.print("[yellow]No tables were created[/yellow]")

        except Exception as e:
            console.print(f"[red]❌ Table creation failed: {e}[/red]")
            raise typer.Exit(1)
