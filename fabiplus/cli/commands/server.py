"""
Server management commands
"""

import typer
import uvicorn
from rich.console import Console

console = Console()
app = typer.Typer()


@app.command("run")
def run_server(
    host: str = typer.Option(None, "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(None, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(
        None, "--reload/--no-reload", help="Enable auto-reload"
    ),
    workers: int = typer.Option(
        1, "--workers", "-w", help="Number of worker processes"
    ),
    log_level: str = typer.Option(None, "--log-level", help="Log level"),
):
    """Run the development server"""

    from ...conf.settings import settings

    # Use settings defaults if not provided
    if host is None:
        host = settings.HOST
    if port is None:
        port = settings.PORT
    if reload is None:
        reload = settings.RELOAD
    if log_level is None:
        log_level = settings.LOG_LEVEL.lower()

    console.print(f"[green]Starting FABI+ server on {host}:{port}[/green]")
    console.print(f"Environment: {settings.ENVIRONMENT}")
    console.print(f"Debug mode: {settings.DEBUG}")

    if workers > 1 and reload:
        console.print(
            "[yellow]Warning: Auto-reload is disabled when using multiple workers[/yellow]"
        )
        reload = False

    try:
        uvicorn.run(
            "fabiplus.core.app:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers,
            log_level=log_level,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]")


@app.command("check")
def check_server():
    """Check server configuration"""

    from ...conf.settings import settings

    console.print("[bold]Server Configuration:[/bold]")
    console.print(f"Host: {settings.HOST}")
    console.print(f"Port: {settings.PORT}")
    console.print(f"Debug: {settings.DEBUG}")
    console.print(f"Environment: {settings.ENVIRONMENT}")
    console.print(f"Database: {settings.DATABASE_URL}")
    console.print(f"API Prefix: {settings.API_PREFIX}")
    console.print(f"Admin Enabled: {settings.ADMIN_ENABLED}")

    console.print("\n[green]✅ Configuration check completed[/green]")
