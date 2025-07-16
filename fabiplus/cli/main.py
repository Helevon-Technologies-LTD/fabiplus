"""
FABI+ Framework CLI
Enhanced command-line interface with Django-style project scaffolding
"""

import sys
from pathlib import Path

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
except ImportError:
    print("Error: Required dependencies not installed.")
    print("Please install with: pip install typer rich")
    sys.exit(1)

try:
    from .commands import app, cache, database, dev, project, server, user
except ImportError:
    # Fallback for development
    from fabiplus.cli.commands import app, cache, database, dev, project, server, user

# Initialize Rich console
console = Console()

# Main CLI app
cli = typer.Typer(
    name="fabiplus",
    help="FABI+ Framework - Production-ready API-only Python framework",
    add_completion=False,
    rich_markup_mode="rich",
)

# Add command groups
cli.add_typer(server.app, name="server", help="Server management commands")
cli.add_typer(project.app, name="project", help="Project scaffolding commands")
cli.add_typer(app.app, name="app", help="Application management commands")
cli.add_typer(database.app, name="db", help="Database management commands")
cli.add_typer(user.app, name="user", help="User management commands")
cli.add_typer(cache.app, name="cache", help="Cache management commands")
cli.add_typer(dev.app, name="dev", help="Development tools")


@cli.command()
def version():
    """Show FABI+ version information"""
    try:
        import fabiplus

        version_text = Text(
            f"FABI+ Framework v{fabiplus.__version__}", style="bold green"
        )
        console.print(Panel(version_text, title="Version Info", border_style="green"))
    except ImportError:
        console.print("[red]Error: FABI+ not properly installed[/red]")


@cli.command()
def info():
    """Show system and framework information"""
    import platform
    import sys

    info_text = f"""
[bold]System Information:[/bold]
• Python: {sys.version.split()[0]}
• Platform: {platform.system()} {platform.release()}
• Architecture: {platform.machine()}

[bold]FABI+ Framework:[/bold]
• Version: {getattr(__import__('fabiplus'), '__version__', 'Unknown')}
• Location: {Path(__file__).parent.parent}

[bold]Available Commands:[/bold]
• [cyan]fabiplus project startproject[/cyan] - Create new project
• [cyan]fabiplus app startapp[/cyan] - Create new app
• [cyan]fabiplus server run[/cyan] - Run development server
• [cyan]fabiplus db migrate[/cyan] - Run database migrations
• [cyan]fabiplus user create[/cyan] - Create superuser
"""

    console.print(Panel(info_text, title="FABI+ Information", border_style="blue"))


@cli.command()
def quickstart():
    """Quick start guide for FABI+"""
    guide_text = """
[bold green]🚀 FABI+ Quick Start Guide[/bold green]

[bold]1. Create a new project:[/bold]
   [cyan]fabiplus project startproject myproject[/cyan]

[bold]2. Navigate to project:[/bold]
   [cyan]cd myproject[/cyan]

[bold]3. Create your first app:[/bold]
   [cyan]fabiplus app startapp blog[/cyan]

[bold]4. Install dependencies:[/bold]
   [cyan]poetry install[/cyan]

[bold]5. Setup database:[/bold]
   [cyan]fabiplus db migrate[/cyan]

[bold]6. Create superuser:[/bold]
   [cyan]fabiplus user create[/cyan]

[bold]7. Run development server:[/bold]
   [cyan]fabiplus server run[/cyan]

[bold]8. Visit your API:[/bold]
   • API Docs: [link]http://localhost:8000/docs[/link]
   • Admin: [link]http://localhost:8000/admin[/link]
"""

    console.print(Panel(guide_text, title="Quick Start", border_style="green"))


def main():
    """Main CLI entry point"""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
