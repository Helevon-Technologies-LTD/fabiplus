"""
FABI+ Framework Database Migrations
Django-style migrations supporting multiple ORMs
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from ..conf.settings import settings
from .models import ModelRegistry


class MigrationManager:
    """Django-style migration manager supporting multiple ORMs"""

    def __init__(self):
        # Try to get ORM backend from settings
        # First, try to load project settings
        self.orm_backend = self._detect_orm_backend()

        # Debug: Print the detected ORM backend
        print(f"Detected ORM backend: {self.orm_backend}")

        self._setup_migration_system()

    def _detect_orm_backend(self) -> str:
        """Detect ORM backend from project settings"""
        try:
            # Try to get from current settings
            if hasattr(settings, "ORM_BACKEND"):
                return settings.ORM_BACKEND

            # Try to load from project settings file
            import sys
            from pathlib import Path

            # Look for settings.py in current directory structure
            current_dir = Path.cwd()

            # Check for project_name/settings.py pattern
            for settings_file in current_dir.rglob("settings.py"):
                if settings_file.parent.name != "migrations":  # Skip migration settings
                    try:
                        # Add the parent directory to sys.path temporarily
                        parent_dir = str(settings_file.parent.parent)
                        if parent_dir not in sys.path:
                            sys.path.insert(0, parent_dir)

                        # Import the settings module
                        module_name = f"{settings_file.parent.name}.settings"
                        import importlib

                        settings_module = importlib.import_module(module_name)

                        if hasattr(settings_module, "ORM_BACKEND"):
                            return settings_module.ORM_BACKEND

                    except Exception as e:
                        print(
                            f"Warning: Could not load settings from {settings_file}: {e}"
                        )
                        continue

            # Default to sqlmodel
            return "sqlmodel"

        except Exception as e:
            print(f"Warning: Could not detect ORM backend: {e}")
            return "sqlmodel"

    def _setup_migration_system(self):
        """Setup migration system based on ORM backend"""
        if self.orm_backend == "tortoise":
            self._setup_aerich()
        else:
            # SQLModel and SQLAlchemy use Alembic
            self._setup_alembic()

    def _setup_alembic(self):
        """Setup Alembic configuration for SQLModel/SQLAlchemy"""
        from alembic import command
        from alembic.config import Config

        # Create migrations directory if it doesn't exist
        migrations_dir = Path.cwd() / "migrations"
        migrations_dir.mkdir(exist_ok=True)

        # Create versions directory
        versions_dir = migrations_dir / "versions"
        versions_dir.mkdir(exist_ok=True)

        # Create alembic.ini if it doesn't exist
        alembic_ini = Path.cwd() / "alembic.ini"
        if not alembic_ini.exists():
            self._create_alembic_ini(alembic_ini, migrations_dir)

        # Setup Alembic config
        self.alembic_cfg = Config(str(alembic_ini))
        self.alembic_cfg.set_main_option("script_location", str(migrations_dir))
        self.alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

        # Initialize Alembic if needed
        if not (migrations_dir / "env.py").exists():
            self._init_alembic(migrations_dir)

    def _setup_aerich(self):
        """Setup Aerich configuration for Tortoise ORM"""
        # Create migrations directory if it doesn't exist
        migrations_dir = Path.cwd() / "migrations"
        migrations_dir.mkdir(exist_ok=True)

        # Check if aerich is initialized
        if not (migrations_dir / "models").exists():
            self._init_aerich()

    def _init_aerich(self):
        """Initialize Aerich for Tortoise ORM"""
        try:
            # Run aerich init-db command
            result = subprocess.run(
                ["aerich", "init-db"], capture_output=True, text=True, cwd=Path.cwd()
            )

            if result.returncode != 0:
                print(f"Warning: Aerich init failed: {result.stderr}")
                return False

            return True
        except Exception as e:
            print(f"Warning: Could not initialize Aerich: {e}")
            return False

    def _create_alembic_ini(self, alembic_ini: Path, migrations_dir: Path):
        """Create alembic.ini configuration file"""
        content = f"""# FABI+ Alembic Configuration

[alembic]
# path to migration scripts
script_location = {migrations_dir}

# template used to generate migration files
# file_template = %%(rev)s_%%(slug)s

# sys.path path, will be prepended to sys.path if present.
# defaults to the current working directory.
prepend_sys_path = .

# timezone to use when rendering the date within the migration file
# as well as the filename.
# If specified, requires the python-dateutil library that can be
# installed by adding `alembic[tz]` to the pip requirements
# string value is passed to dateutil.tz.gettz()
# leave blank for localtime
# timezone =

# max length of characters to apply to the
# "slug" field
# truncate_slug_length = 40

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
# revision_environment = false

# set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
# sourceless = false

# version number format
version_num_format = %%04d

# version path separator; As mentioned above, this is the character used to split
# version_locations. The default within new alembic.ini files is "os", which uses
# os.pathsep. If this key is omitted entirely, it falls back to the legacy
# behavior of splitting on spaces and/or commas.
# Valid values for version_path_separator are:
#
# version_path_separator = :
# version_path_separator = ;
# version_path_separator = space
version_path_separator = os

# the output encoding used when revision files
# are written from script.py.mako
# output_encoding = utf-8

sqlalchemy.url = {settings.DATABASE_URL}


[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.  See the documentation for further
# detail and examples

# format using "black" - use the console_scripts runner, against the "black" entrypoint
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""

        with open(alembic_ini, "w") as f:
            f.write(content)

    def _init_alembic(self, migrations_dir: Path):
        """Initialize Alembic in the migrations directory"""
        try:
            from alembic import command

            # Ensure versions directory exists
            versions_dir = migrations_dir / "versions"
            versions_dir.mkdir(exist_ok=True)

            # Create the Alembic environment
            command.init(self.alembic_cfg, str(migrations_dir))

            # Ensure versions directory exists after init (in case it was removed)
            versions_dir.mkdir(exist_ok=True)

            # Update env.py to work with FABI+
            env_py = migrations_dir / "env.py"
            if env_py.exists():
                self._update_env_py(env_py)

            # Update script.py.mako template
            script_mako = migrations_dir / "script.py.mako"
            if script_mako.exists():
                self._update_script_template(script_mako)

        except Exception as e:
            print(f"Warning: Could not initialize Alembic: {e}")

    def _update_env_py(self, env_py: Path):
        """Update env.py to work with FABI+ models"""
        content = '''"""FABI+ Alembic Environment"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import FABI+ components
from fabiplus.core.models import ModelRegistry
from fabiplus.core.user_model import User  # Ensure User model is imported
from fabiplus.conf.settings import settings

# Ensure User model is registered
ModelRegistry.register(User)

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Discover all models to ensure they're loaded
ModelRegistry.discover_models()

# Get all registered models metadata
target_metadata = ModelRegistry.get_metadata()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={{"paramstyle": "named"}},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''

        with open(env_py, "w") as f:
            f.write(content)

    def _update_script_template(self, script_mako: Path):
        """Update script.py.mako template to include required imports based on ORM backend"""

        # Generate backend-specific imports
        # Note: Even SQLAlchemy backend needs sqlmodel import because core models use SQLModel
        if self.orm_backend == "sqlmodel":
            orm_imports = "import sqlmodel"
        elif self.orm_backend == "sqlalchemy":
            orm_imports = (
                "import sqlmodel  # Required for core models that use SQLModel types"
            )
        else:  # tortoise
            orm_imports = "# Tortoise ORM backend - no additional ORM imports needed"

        content = f'''"""${{message}}

Revision ID: ${{up_revision}}
Revises: ${{down_revision | comma,n}}
Create Date: ${{create_date}}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
{orm_imports}
import fabiplus.core.user_model
${{imports if imports else ""}}

# revision identifiers, used by Alembic.
revision: str = ${{repr(up_revision)}}
down_revision: Union[str, None] = ${{repr(down_revision)}}
branch_labels: Union[str, Sequence[str], None] = ${{repr(branch_labels)}}
depends_on: Union[str, Sequence[str], None] = ${{repr(depends_on)}}


def upgrade() -> None:
    """Upgrade schema."""
    ${{upgrades if upgrades else "pass"}}


def downgrade() -> None:
    """Downgrade schema."""
    ${{downgrades if downgrades else "pass"}}
'''

        with open(script_mako, "w") as f:
            f.write(content)

    def _configure_black_hook(self):
        """Configure black post-write hook if black is available"""
        try:
            import importlib.util
            import os
            import subprocess
            import sys

            # Check if black is available in the current Python environment
            black_available = False

            # First, try to import black directly (most reliable for current environment)
            try:
                import black

                black_available = True
            except ImportError:
                black_available = False

            # If import failed, try to check if black executable is available in current environment
            if not black_available:
                try:
                    # Use sys.executable to ensure we're checking the current Python environment
                    result = subprocess.run(
                        [sys.executable, "-m", "black", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    black_available = result.returncode == 0
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    black_available = False

            # Read current alembic.ini
            alembic_ini = Path.cwd() / "alembic.ini"
            if not alembic_ini.exists():
                return

            with open(alembic_ini, "r") as f:
                content = f.read()

            # Configure black hook based on availability
            if black_available:
                # Enable black hook
                content = content.replace(
                    "# hooks = black\n# black.type = console_scripts\n# black.entrypoint = black\n# black.options = -l 79 REVISION_SCRIPT_FILENAME",
                    "hooks = black\nblack.type = console_scripts\nblack.entrypoint = black\nblack.options = -l 79 REVISION_SCRIPT_FILENAME",
                )
            else:
                # Ensure black hook is disabled (already commented out by default)
                content = content.replace(
                    "hooks = black\nblack.type = console_scripts\nblack.entrypoint = black\nblack.options = -l 79 REVISION_SCRIPT_FILENAME",
                    "# hooks = black\n# black.type = console_scripts\n# black.entrypoint = black\n# black.options = -l 79 REVISION_SCRIPT_FILENAME",
                )

            # Write back the modified content
            with open(alembic_ini, "w") as f:
                f.write(content)

        except Exception as e:
            # If anything goes wrong, just continue without black formatting
            print(f"Warning: Could not configure black hook: {e}")

    def makemigrations(self, message: Optional[str] = None) -> bool:
        """Create a new migration (like Django's makemigrations)"""
        try:
            if self.orm_backend == "tortoise":
                return self._makemigrations_aerich(message)
            else:
                return self._makemigrations_alembic(message)
        except Exception as e:
            print(f"Error creating migration: {e}")
            return False

    def _makemigrations_alembic(self, message: Optional[str] = None) -> bool:
        """Create migration using Alembic"""
        from alembic import command

        # Ensure all models are loaded
        ModelRegistry.discover_models()

        # Check if black is available and enable post-write hook if it is
        self._configure_black_hook()

        # Generate migration
        message = message or "Auto-generated migration"
        command.revision(self.alembic_cfg, autogenerate=True, message=message)
        return True

    def _makemigrations_aerich(self, message: Optional[str] = None) -> bool:
        """Create migration using Aerich"""
        try:
            # First, check if aerich is initialized
            migrations_dir = Path.cwd() / "migrations"
            if not (migrations_dir / "models").exists():
                print("Initializing Aerich database...")
                # Run aerich init-db first
                init_result = subprocess.run(
                    ["aerich", "init-db"],
                    capture_output=True,
                    text=True,
                    cwd=Path.cwd(),
                )

                if init_result.returncode != 0:
                    print(f"Error initializing database: {init_result.stderr}")
                    return False

                print("Database initialized successfully!")
                print(init_result.stdout)

            # Now run aerich migrate command
            cmd = ["aerich", "migrate"]
            if message:
                cmd.extend(["--name", message])

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())

            if result.returncode != 0:
                print(f"Error creating migration: {result.stderr}")
                return False

            print(result.stdout)
            return True
        except Exception as e:
            print(f"Error creating migration: {e}")
            return False

    def migrate(self, revision: str = "head") -> bool:
        """Apply migrations (like Django's migrate)"""
        try:
            if self.orm_backend == "tortoise":
                return self._migrate_aerich()
            else:
                return self._migrate_alembic(revision)
        except Exception as e:
            print(f"Error applying migrations: {e}")
            return False

    def _migrate_alembic(self, revision: str = "head") -> bool:
        """Apply migrations using Alembic"""
        from alembic import command

        command.upgrade(self.alembic_cfg, revision)
        return True

    def _migrate_aerich(self) -> bool:
        """Apply migrations using Aerich"""
        try:
            # Run aerich upgrade command
            result = subprocess.run(
                ["aerich", "upgrade"], capture_output=True, text=True, cwd=Path.cwd()
            )

            if result.returncode != 0:
                print(f"Error applying migrations: {result.stderr}")
                return False

            print(result.stdout)
            return True
        except Exception as e:
            print(f"Error applying migrations: {e}")
            return False

    def rollback(self, revision: str = "-1") -> bool:
        """Rollback migrations"""
        try:
            if self.orm_backend == "tortoise":
                return self._rollback_aerich(revision)
            else:
                return self._rollback_alembic(revision)
        except Exception as e:
            print(f"Error rolling back migrations: {e}")
            return False

    def _rollback_alembic(self, revision: str = "-1") -> bool:
        """Rollback migrations using Alembic"""
        from alembic import command

        command.downgrade(self.alembic_cfg, revision)
        return True

    def _rollback_aerich(self, revision: str = "-1") -> bool:
        """Rollback migrations using Aerich"""
        try:
            # Run aerich downgrade command
            cmd = ["aerich", "downgrade"]
            if revision != "-1":
                cmd.extend(["--version", revision])

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())

            if result.returncode != 0:
                print(f"Error rolling back migrations: {result.stderr}")
                return False

            print(result.stdout)
            return True
        except Exception as e:
            print(f"Error rolling back migrations: {e}")
            return False

    def show_migrations(self) -> List[str]:
        """Show migration history"""
        try:
            if self.orm_backend == "tortoise":
                return self._show_migrations_aerich()
            else:
                return self._show_migrations_alembic()
        except Exception as e:
            print(f"Error getting migration history: {e}")
            return []

    def _show_migrations_alembic(self) -> List[str]:
        """Show migration history using Alembic"""
        from alembic.script import ScriptDirectory

        # Get migration history
        script = ScriptDirectory.from_config(self.alembic_cfg)
        revisions = []

        for revision in script.walk_revisions():
            revisions.append(f"{revision.revision}: {revision.doc}")

        return revisions

    def _show_migrations_aerich(self) -> List[str]:
        """Show migration history using Aerich"""
        try:
            # Run aerich history command
            result = subprocess.run(
                ["aerich", "history"], capture_output=True, text=True, cwd=Path.cwd()
            )

            if result.returncode != 0:
                return []

            return result.stdout.strip().split("\n") if result.stdout.strip() else []
        except Exception:
            return []

    def current_revision(self) -> Optional[str]:
        """Get current database revision"""
        try:
            if self.orm_backend == "tortoise":
                return self._current_revision_aerich()
            else:
                return self._current_revision_alembic()
        except Exception as e:
            print(f"Error getting current revision: {e}")
            return None

    def _current_revision_alembic(self) -> Optional[str]:
        """Get current revision using Alembic"""
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine

        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            return context.get_current_revision()

    def _current_revision_aerich(self) -> Optional[str]:
        """Get current revision using Aerich"""
        try:
            # Run aerich heads command
            result = subprocess.run(
                ["aerich", "heads"], capture_output=True, text=True, cwd=Path.cwd()
            )

            if result.returncode != 0:
                return None

            return result.stdout.strip() if result.stdout.strip() else None
        except Exception:
            return None

    def check_migrations(self) -> bool:
        """Check if there are pending migrations"""
        try:
            if self.orm_backend == "tortoise":
                return self._check_migrations_aerich()
            else:
                return self._check_migrations_alembic()
        except Exception as e:
            print(f"Error checking migrations: {e}")
            return False

    def _check_migrations_alembic(self) -> bool:
        """Check pending migrations using Alembic"""
        from alembic.script import ScriptDirectory

        script = ScriptDirectory.from_config(self.alembic_cfg)
        current = self.current_revision()
        head = script.get_current_head()

        return current != head

    def _check_migrations_aerich(self) -> bool:
        """Check pending migrations using Aerich"""
        try:
            # Run aerich status command
            result = subprocess.run(
                ["aerich", "status"], capture_output=True, text=True, cwd=Path.cwd()
            )

            # If there are pending migrations, aerich status will show them
            return "pending" in result.stdout.lower() if result.stdout else False
        except Exception:
            return False


# Global migration manager instance
migration_manager = MigrationManager()
