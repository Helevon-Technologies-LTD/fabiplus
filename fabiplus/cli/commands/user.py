"""
User management commands
"""

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from sqlmodel import select

console = Console()
app = typer.Typer()


@app.command("create")
def create_user(
    username: str = typer.Option(None, "--username", "-u", help="Username"),
    email: str = typer.Option(None, "--email", "-e", help="Email address"),
    password: str = typer.Option(None, "--password", "-p", help="Password"),
    superuser: bool = typer.Option(False, "--superuser", help="Create superuser"),
    staff: bool = typer.Option(False, "--staff", help="Create staff user"),
):
    """Create a new user"""

    # Get username if not provided
    if not username:
        username = Prompt.ask("Username")

    # Get email if not provided
    if not email:
        email = Prompt.ask("Email address")

    # Get password if not provided
    if not password:
        password = Prompt.ask("Password", password=True)
        confirm_password = Prompt.ask("Confirm password", password=True)

        if password != confirm_password:
            console.print("[red]❌ Passwords do not match[/red]")
            raise typer.Exit(1)

    # Import models and auth backend
    from ...core.auth import auth_backend
    from ...core.models import ModelRegistry, User

    # Check if user already exists
    with ModelRegistry.get_session() as session:
        existing_user = session.exec(
            select(User).where(User.username == username)
        ).first()

        if existing_user:
            console.print(f"[red]❌ User '{username}' already exists[/red]")
            raise typer.Exit(1)

        existing_email = session.exec(select(User).where(User.email == email)).first()

        if existing_email:
            console.print(f"[red]❌ Email '{email}' already exists[/red]")
            raise typer.Exit(1)

    try:
        # Create user
        user = auth_backend.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=staff or superuser,
            is_superuser=superuser,
            is_active=True,
        )

        user_type = "superuser" if superuser else "staff user" if staff else "user"
        console.print(
            f"[green]✅ {user_type.title()} '{username}' created successfully![/green]"
        )
        console.print(f"User ID: {user.id}")

    except Exception as e:
        console.print(f"[red]❌ Error creating user: {e}[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_users(
    staff_only: bool = typer.Option(False, "--staff", help="Show only staff users"),
    superuser_only: bool = typer.Option(
        False, "--superuser", help="Show only superusers"
    ),
):
    """List all users"""

    from ...core.models import ModelRegistry, User

    try:
        with ModelRegistry.get_session() as session:
            query = select(User)

            if staff_only:
                query = query.where(User.is_staff.is_(True))
            elif superuser_only:
                query = query.where(User.is_superuser.is_(True))

            users = session.exec(query).all()

            if not users:
                console.print("[yellow]No users found[/yellow]")
                return

            table = Table(title="Users")
            table.add_column("ID", style="dim")
            table.add_column("Username", style="cyan")
            table.add_column("Email", style="green")
            table.add_column("Staff", style="blue")
            table.add_column("Superuser", style="red")
            table.add_column("Active", style="yellow")
            table.add_column("Created", style="dim")

            for user in users:
                table.add_row(
                    str(user.id)[:8] + "...",
                    user.username,
                    user.email,
                    "✓" if user.is_staff else "✗",
                    "✓" if user.is_superuser else "✗",
                    "✓" if user.is_active else "✗",
                    user.created_at.strftime("%Y-%m-%d") if user.created_at else "N/A",
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]❌ Error listing users: {e}[/red]")
        raise typer.Exit(1)


@app.command("delete")
def delete_user(
    username: str = typer.Argument(..., help="Username to delete"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force delete without confirmation"
    ),
):
    """Delete a user"""

    from ...core.models import ModelRegistry, User

    try:
        with ModelRegistry.get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()

            if not user:
                console.print(f"[red]❌ User '{username}' not found[/red]")
                raise typer.Exit(1)

            if not force:
                confirm = typer.confirm(f"Delete user '{username}'?")
                if not confirm:
                    console.print("[yellow]User deletion cancelled[/yellow]")
                    return

            session.delete(user)
            session.commit()

            console.print(f"[green]✅ User '{username}' deleted successfully[/green]")

    except Exception as e:
        console.print(f"[red]❌ Error deleting user: {e}[/red]")
        raise typer.Exit(1)


@app.command("changepassword")
def change_password(
    username: str = typer.Argument(..., help="Username"),
    password: str = typer.Option(None, "--password", "-p", help="New password"),
):
    """Change user password"""

    from ...core.auth import auth_backend
    from ...core.models import ModelRegistry, User

    try:
        with ModelRegistry.get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()

            if not user:
                console.print(f"[red]❌ User '{username}' not found[/red]")
                raise typer.Exit(1)

            # Get password if not provided
            if not password:
                password = Prompt.ask("New password", password=True)
                confirm_password = Prompt.ask("Confirm new password", password=True)

                if password != confirm_password:
                    console.print("[red]❌ Passwords do not match[/red]")
                    raise typer.Exit(1)

            # Update password
            user.hashed_password = auth_backend.hash_password(password)
            session.add(user)
            session.commit()

            console.print(f"[green]✅ Password changed for user '{username}'[/green]")

    except Exception as e:
        console.print(f"[red]❌ Error changing password: {e}[/red]")
        raise typer.Exit(1)


@app.command("activate")
def activate_user(username: str = typer.Argument(..., help="Username to activate")):
    """Activate a user"""

    from ...core.models import ModelRegistry, User

    try:
        with ModelRegistry.get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()

            if not user:
                console.print(f"[red]❌ User '{username}' not found[/red]")
                raise typer.Exit(1)

            user.is_active = True
            session.add(user)
            session.commit()

            console.print(f"[green]✅ User '{username}' activated[/green]")

    except Exception as e:
        console.print(f"[red]❌ Error activating user: {e}[/red]")
        raise typer.Exit(1)


@app.command("deactivate")
def deactivate_user(username: str = typer.Argument(..., help="Username to deactivate")):
    """Deactivate a user"""

    from ...core.models import ModelRegistry, User

    try:
        with ModelRegistry.get_session() as session:
            user = session.exec(select(User).where(User.username == username)).first()

            if not user:
                console.print(f"[red]❌ User '{username}' not found[/red]")
                raise typer.Exit(1)

            user.is_active = False
            session.add(user)
            session.commit()

            console.print(f"[green]✅ User '{username}' deactivated[/green]")

    except Exception as e:
        console.print(f"[red]❌ Error deactivating user: {e}[/red]")
        raise typer.Exit(1)
