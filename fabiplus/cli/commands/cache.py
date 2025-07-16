"""
Cache management commands
High-performance caching for faster API responses
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ...core.cache import cache

console = Console()
app = typer.Typer()


@app.command("clear")
def clear_cache(
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")
):
    """Clear all cached data"""

    from ...core.cache import cache

    if not confirm:
        confirm_clear = typer.confirm("This will clear all cached data. Continue?")
        if not confirm_clear:
            console.print("[yellow]Cache clear cancelled[/yellow]")
            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Clearing cache...", total=None)

        try:
            success = cache.clear()
            if success:
                progress.update(task, description="Cache cleared successfully!")
                console.print("[green]✅ All cached data cleared[/green]")
            else:
                console.print("[red]❌ Failed to clear cache[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error clearing cache: {e}[/red]")


@app.command("stats")
def cache_stats():
    """Show cache statistics"""

    try:
        stats = cache.stats()

        if not stats:
            console.print("[yellow]No cache statistics available[/yellow]")
            return

        # Create statistics table
        table = Table(title="Cache Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        # Add basic stats
        for key, value in stats.items():
            if key == "memory_usage":
                # Format memory usage
                if value > 1024 * 1024:
                    formatted_value = f"{value / (1024 * 1024):.2f} MB"
                elif value > 1024:
                    formatted_value = f"{value / 1024:.2f} KB"
                else:
                    formatted_value = f"{value} bytes"
                table.add_row(key.replace("_", " ").title(), formatted_value)
            else:
                table.add_row(key.replace("_", " ").title(), str(value))

        console.print(table)

        # Calculate hit ratio if available
        if "hits" in stats and "misses" in stats:
            total_requests = stats["hits"] + stats["misses"]
            if total_requests > 0:
                hit_ratio = (stats["hits"] / total_requests) * 100
                console.print(f"\n[bold]Cache Hit Ratio: {hit_ratio:.2f}%[/bold]")

    except Exception as e:
        console.print(f"[red]❌ Error getting cache statistics: {e}[/red]")


@app.command("list")
def list_cached_keys(
    limit: int = typer.Option(
        50, "--limit", "-l", help="Maximum number of keys to show"
    ),
    pattern: str = typer.Option("", "--pattern", "-p", help="Filter keys by pattern"),
):
    """List all cached keys"""

    try:
        keys = cache.keys()

        if not keys:
            console.print("[yellow]No cached data found[/yellow]")
            return

        # Filter keys by pattern if provided
        if pattern:
            keys = [key for key in keys if pattern.lower() in key.lower()]

        # Limit results
        if len(keys) > limit:
            keys = keys[:limit]
            truncated = True
        else:
            truncated = False

        # Create keys table
        table = Table(title=f"Cached Keys ({len(keys)} shown)")
        table.add_column("Key", style="cyan")
        table.add_column("Type", style="green")

        for key in keys:
            # Determine key type based on prefix
            if key.startswith("model:"):
                key_type = "Model Query"
            elif key.startswith("api:"):
                key_type = "API Response"
            elif key.startswith("user:"):
                key_type = "User Data"
            else:
                key_type = "General"

            table.add_row(key, key_type)

        console.print(table)

        if truncated:
            console.print(f"[dim]... and {len(cache.keys()) - limit} more keys[/dim]")

        if pattern:
            console.print(f"[dim]Filtered by pattern: '{pattern}'[/dim]")

    except Exception as e:
        console.print(f"[red]❌ Error listing cache keys: {e}[/red]")


@app.command("get")
def get_cached_value(key: str = typer.Argument(..., help="Cache key to retrieve")):
    """Get a specific cached value"""

    try:
        value = cache.get(key)

        if value is None:
            console.print(f"[yellow]No cached value found for key: '{key}'[/yellow]")
            return

        # Display the cached value
        import json

        try:
            # Try to format as JSON if possible
            if isinstance(value, (dict, list)):
                formatted_value = json.dumps(value, indent=2, default=str)
            else:
                formatted_value = str(value)
        except Exception:
            formatted_value = str(value)

        panel_content = (
            f"[bold]Key:[/bold] {key}\n\n[bold]Value:[/bold]\n{formatted_value}"
        )
        console.print(Panel(panel_content, title="Cached Value", border_style="green"))

    except Exception as e:
        console.print(f"[red]❌ Error getting cached value: {e}[/red]")


@app.command("delete")
def delete_cached_key(
    key: str = typer.Argument(..., help="Cache key to delete"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a specific cached key"""

    if not confirm:
        confirm_delete = typer.confirm(f"Delete cached key '{key}'?")
        if not confirm_delete:
            console.print("[yellow]Cache delete cancelled[/yellow]")
            return

    try:
        success = cache.delete(key)

        if success:
            console.print(f"[green]✅ Cached key '{key}' deleted[/green]")
        else:
            console.print(f"[yellow]Key '{key}' not found in cache[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Error deleting cached key: {e}[/red]")


@app.command("info")
def cache_info():
    """Show cache configuration and backend information"""

    from ...conf.settings import settings

    info_content = f"""
[bold]Cache Configuration:[/bold]

[cyan]Backend:[/cyan] {settings.CACHE_BACKEND}
[cyan]Default TTL:[/cyan] {settings.CACHE_TTL} seconds
[cyan]Redis URL:[/cyan] {settings.REDIS_URL or 'Not configured'}

[bold]Cache Backend Details:[/bold]
[cyan]Type:[/cyan] {type(cache._backend).__name__}
[cyan]Status:[/cyan] {'✅ Active' if cache._backend else '❌ Not initialized'}
"""

    console.print(Panel(info_content, title="Cache Information", border_style="blue"))

    # Show current stats
    try:
        stats = cache.stats()
        if stats:
            console.print("\n[bold]Current Statistics:[/bold]")
            for key, value in stats.items():
                console.print(
                    f"  [cyan]{key.replace('_', ' ').title()}:[/cyan] {value}"
                )
    except Exception as e:
        console.print(f"[red]Could not retrieve statistics: {e}[/red]")


@app.command("warm")
def warm_cache():
    """Warm up the cache with frequently accessed data"""

    console.print("[blue]Warming up cache...[/blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Warming cache...", total=None)

        try:
            # This would implement cache warming logic
            # For now, just a placeholder
            import time

            time.sleep(1)  # Simulate warming

            progress.update(task, description="Cache warmed successfully!")
            console.print("[green]✅ Cache warming completed[/green]")
            console.print("[dim]Note: Cache warming logic not yet implemented[/dim]")

        except Exception as e:
            console.print(f"[red]❌ Error warming cache: {e}[/red]")


@app.command("benchmark")
def benchmark_cache():
    """Benchmark cache performance"""

    console.print("[blue]Running cache benchmark...[/blue]")

    import random
    import string
    import time

    # Test parameters
    num_operations = 1000
    key_length = 10
    value_size = 100

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Benchmarking...", total=None)

        try:
            # Generate test data
            test_keys = []
            test_values = []

            for _ in range(num_operations):
                key = "".join(random.choices(string.ascii_letters, k=key_length))
                value = "".join(random.choices(string.ascii_letters, k=value_size))
                test_keys.append(f"benchmark:{key}")
                test_values.append(value)

            # Benchmark SET operations
            start_time = time.time()
            for key, value in zip(test_keys, test_values):
                cache.set(key, value, ttl=60)
            set_time = time.time() - start_time

            # Benchmark GET operations
            start_time = time.time()
            for key in test_keys:
                cache.get(key)
            get_time = time.time() - start_time

            # Clean up
            for key in test_keys:
                cache.delete(key)

            progress.update(task, description="Benchmark completed!")

            # Display results
            results = f"""
[bold]Cache Benchmark Results:[/bold]

[cyan]Operations:[/cyan] {num_operations}
[cyan]SET Performance:[/cyan] {num_operations / set_time:.2f} ops/sec
[cyan]GET Performance:[/cyan] {num_operations / get_time:.2f} ops/sec
[cyan]Average SET Time:[/cyan] {(set_time / num_operations) * 1000:.2f} ms
[cyan]Average GET Time:[/cyan] {(get_time / num_operations) * 1000:.2f} ms
"""

            console.print(
                Panel(results, title="Benchmark Results", border_style="green")
            )

        except Exception as e:
            console.print(f"[red]❌ Error running benchmark: {e}[/red]")
