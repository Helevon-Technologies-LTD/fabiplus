"""
FABI+ Framework Application Factory
Creates and configures the FastAPI application
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles

from ..conf.settings import settings
from ..middleware.logging import LoggingMiddleware
from ..middleware.security import SecurityMiddleware
from .apps import apps
from .auth import AuthenticationError, PermissionError, auth_backend
from .docs import setup_docs_customization

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL), format=settings.LOG_FORMAT
)

# Silence bcrypt warnings
logging.getLogger("passlib.handlers.bcrypt").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting FABI+ application...")

    # Reload settings to pick up any project-specific configuration
    from ..conf.settings import reload_settings

    settings = reload_settings()

    # Load installed apps
    try:
        apps.populate(settings.INSTALLED_APPS)
        logger.info(f"Loaded {len(settings.INSTALLED_APPS)} apps")
    except Exception as e:
        logger.error(f"Error loading apps: {e}")

    # Discover models from all loaded apps
    try:
        from ..core.models import ModelRegistry

        ModelRegistry.discover_models()
        models = ModelRegistry.get_all_models()
        logger.info(f"Discovered {len(models)} models: {list(models.keys())}")
    except Exception as e:
        logger.error(f"Error discovering models: {e}")

    # Generate and include API routes after models are loaded
    try:
        from ..api.auto import get_api_router

        api_router = get_api_router()
        app.include_router(api_router)
        logger.info("API routes generated and included")
    except Exception as e:
        logger.error(f"Error generating API routes: {e}")

    # Discover and include custom app routers
    try:
        custom_routers = _discover_app_routers()
        for app_name, router in custom_routers.items():
            app.include_router(router)
            logger.info(f"Custom router from '{app_name}' included")
        if custom_routers:
            logger.info(f"Included {len(custom_routers)} custom app routers")
    except Exception as e:
        logger.error(f"Error discovering custom routers: {e}")

    # Note: Database tables are created via migrations, not on startup

    yield

    # Shutdown
    logger.info("Shutting down FABI+ application...")


def _setup_middleware(app: FastAPI) -> None:
    """Setup middleware for the FastAPI application"""
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_CREDENTIALS,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )

    # Add custom middleware
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(LoggingMiddleware)

    # Add activity logging middleware
    try:
        from ..middleware.activity import ActivityLoggingMiddleware

        app.add_middleware(
            ActivityLoggingMiddleware,
            log_all_requests=settings.DEBUG,  # Log all requests in debug mode
            exclude_paths=[
                "/docs",
                "/redoc",
                "/openapi.json",
                "/favicon.ico",
                "/static/",
                "/admin/static/",
                "/health",
                "/metrics",
                "/admin/logs/live",  # Exclude WebSocket endpoint
            ],
        )
        logger.info("Activity logging middleware enabled")
    except ImportError as e:
        logger.warning(f"Activity logging middleware not available: {e}")


def _setup_auth_endpoints(app: FastAPI) -> None:
    """Setup authentication endpoints"""
    from passlib.context import CryptContext
    from pydantic import BaseModel, EmailStr

    from .auth import get_current_active_user
    from .models import ModelRegistry, User

    # Define dependency for this function scope
    ActiveUserDep = Depends(get_current_active_user)

    # Password hashing
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    class UserRegistration(BaseModel):
        username: str
        email: EmailStr
        password: str
        first_name: str = ""
        last_name: str = ""

    class UserResponse(BaseModel):
        id: str
        username: str
        email: str
        first_name: str
        last_name: str
        is_staff: bool
        is_superuser: bool

    # Authentication endpoints
    @app.post("/auth/token", tags=["Authentication"])
    async def login(request: Request):
        """
        Login endpoint that accepts both form data and JSON
        """
        try:
            content_type = request.headers.get("content-type", "")

            if "application/json" in content_type:
                # Handle JSON login
                data = await request.json()
                username = data.get("username")
                password = data.get("password")
            else:
                # Handle form data login
                form = await request.form()
                username = form.get("username")
                password = form.get("password")

            if not username or not password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username and password are required",
                )

            # Authenticate user
            user = auth_backend.authenticate_user(username, password)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                )

            logger.info(f"Authentication successful for user: {username}")
            access_token = auth_backend.create_access_token(
                data={"sub": str(user.id), "username": user.username}
            )

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                },
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error",
            )

    @app.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
    async def get_current_user(current_user: User = ActiveUserDep):
        """Get current authenticated user"""
        return UserResponse(
            id=str(current_user.id),
            username=current_user.username,
            email=current_user.email,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            is_staff=current_user.is_staff,
            is_superuser=current_user.is_superuser,
        )

    @app.post("/auth/register", response_model=UserResponse, tags=["Authentication"])
    async def register_user(user_data: UserRegistration):
        """Register a new user"""
        session = ModelRegistry.get_session()

        # Check if user already exists
        existing_user = (
            session.query(User)
            .filter(
                (User.username == user_data.username) | (User.email == user_data.email)
            )
            .first()
        )

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already registered",
            )

        # Create new user
        hashed_password = pwd_context.hash(user_data.password)
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )

        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        logger.info(f"New user registered: {user_data.username}")

        return UserResponse(
            id=str(new_user.id),
            username=new_user.username,
            email=new_user.email,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            is_staff=new_user.is_staff,
            is_superuser=new_user.is_superuser,
        )


def _setup_exception_handlers(app: FastAPI) -> None:
    """Setup exception handlers for the FastAPI application"""
    from pydantic import ValidationError

    @app.exception_handler(AuthenticationError)
    async def auth_exception_handler(_request, exc: AuthenticationError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(PermissionError)
    async def permission_exception_handler(_request, exc: PermissionError):
        return JSONResponse(
            status_code=403,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(_request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        if settings.DEBUG:
            return JSONResponse(
                status_code=500,
                content={
                    "detail": f"Internal server error: {str(exc)}",
                    "type": type(exc).__name__,
                },
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    """

    # Create FastAPI app
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=f"{settings.APP_NAME} - Built with FABI+ Framework",
        debug=settings.DEBUG,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Setup middleware, exception handlers, and auth endpoints
    _setup_middleware(app)
    _setup_exception_handlers(app)
    _setup_auth_endpoints(app)

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information"""
        return {
            "message": f"Welcome to {settings.APP_NAME}",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "api_docs": "/docs",
            "admin_panel": settings.ADMIN_PREFIX if settings.ADMIN_ENABLED else None,
            "api_prefix": settings.API_PREFIX,
        }

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        }

    # Authentication endpoints
    @app.post("/auth/token", tags=["Authentication"])
    async def login(request: Request):
        """
        OAuth2 compatible token login endpoint
        Accepts form data (application/x-www-form-urlencoded)
        """
        try:
            logger.info("OAuth2 token endpoint reached")

            # Get form data manually with timeout and error handling
            logger.info("About to parse OAuth2 form data...")

            # Check content type first
            content_type = request.headers.get("content-type", "")
            logger.info(f"OAuth2 request content-type: {content_type}")

            if not content_type.startswith("application/x-www-form-urlencoded"):
                logger.error(
                    f"Invalid content-type for OAuth2 form data: {content_type}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid content-type. Expected application/x-www-form-urlencoded",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Parse form data manually from raw body
            try:
                body = await request.body()
                logger.info(f"OAuth2 raw body received, length: {len(body)}")

                # Parse URL-encoded form data manually
                from urllib.parse import parse_qs

                body_str = body.decode("utf-8")
                logger.info(
                    f"OAuth2 body string: {body_str[:100]}..."
                )  # Log first 100 chars

                parsed_data = parse_qs(body_str)
                logger.info(f"OAuth2 parsed form data keys: {list(parsed_data.keys())}")

                # Extract username and password (parse_qs returns lists)
                username = parsed_data.get("username", [None])[0]
                password = parsed_data.get("password", [None])[0]

                logger.info(
                    f"OAuth2 extracted username: {username}, password present: {bool(password)}"
                )

            except Exception as e:
                logger.error(f"OAuth2 manual form parsing failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to parse form data",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            logger.info(f"OAuth2 token authentication attempt for user: {username}")
            logger.info(
                f"Form data received - username: {username}, password length: {len(password) if password else 0}"
            )

            if not username or not password:
                logger.error("Missing username or password in OAuth2 form data")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username and password are required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user = auth_backend.authenticate_user(username, password)
            if not user:
                logger.warning(f"OAuth2 authentication failed for user: {username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            logger.info(f"OAuth2 authentication successful for user: {username}")
            access_token = auth_backend.create_access_token(
                data={"sub": str(user.id), "username": user.username}
            )

            logger.info(f"Returning OAuth2 token for user: {username}")
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                },
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"OAuth2 authentication error for {username}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error",
            )

    from pydantic import BaseModel

    class LoginRequest(BaseModel):
        username: str
        password: str

    @app.post("/auth/login", tags=["Authentication"])
    async def login_json(credentials: LoginRequest):
        """
        JSON login endpoint for better API integration
        """
        try:
            logger.info(f"JSON authentication attempt for user: {credentials.username}")
            user = auth_backend.authenticate_user(
                credentials.username, credentials.password
            )
            if not user:
                logger.warning(
                    f"JSON authentication failed for user: {credentials.username}"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                )

            logger.info(
                f"JSON authentication successful for user: {credentials.username}"
            )
            access_token = auth_backend.create_access_token(
                data={"sub": str(user.id), "username": user.username}
            )

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                },
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"JSON authentication error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error",
            )

    # Current user endpoint
    from passlib.context import CryptContext
    from pydantic import BaseModel, EmailStr

    from .auth import get_current_active_user
    from .models import ModelRegistry, User

    # Password hashing
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    class UserRegistration(BaseModel):
        username: str
        email: EmailStr
        password: str
        first_name: str = ""
        last_name: str = ""

    class UserResponse(BaseModel):
        id: str
        username: str
        email: str
        first_name: str
        last_name: str
        full_name: str
        is_active: bool
        is_staff: bool
        is_superuser: bool
        created_at: str

    @app.post("/auth/register", tags=["Authentication"], response_model=UserResponse)
    async def register_user(user_data: UserRegistration):
        """
        Register a new user
        """
        session = ModelRegistry.get_session()

        try:
            # Check if username already exists
            existing_user = (
                session.query(User).filter(User.username == user_data.username).first()
            )
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered",
                )

            # Check if email already exists
            existing_email = (
                session.query(User).filter(User.email == user_data.email).first()
            )
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )

            # Hash password
            hashed_password = pwd_context.hash(user_data.password)

            # Create new user
            new_user = User(
                username=user_data.username,
                email=user_data.email,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                hashed_password=hashed_password,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )

            session.add(new_user)
            session.commit()
            session.refresh(new_user)

            return UserResponse(
                id=str(new_user.id),
                username=new_user.username,
                email=new_user.email,
                first_name=new_user.first_name,
                last_name=new_user.last_name,
                full_name=new_user.full_name,
                is_active=new_user.is_active,
                is_staff=new_user.is_staff,
                is_superuser=new_user.is_superuser,
                created_at=(
                    new_user.created_at.isoformat() if new_user.created_at else ""
                ),
            )

        except HTTPException:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Registration error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed",
            )
        finally:
            session.close()

    @app.get("/auth/me", tags=["Authentication"], response_model=UserResponse)
    async def get_current_user_info(current_user=Depends(get_current_active_user)):
        """
        Get current authenticated user information
        """
        return UserResponse(
            id=str(current_user.id),
            username=current_user.username,
            email=current_user.email,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            full_name=current_user.full_name,
            is_active=current_user.is_active,
            is_staff=current_user.is_staff,
            is_superuser=current_user.is_superuser,
            created_at=(
                current_user.created_at.isoformat() if current_user.created_at else ""
            ),
        )

    # API router is now included in lifespan startup after models are loaded

    # Include admin router if enabled
    if settings.ADMIN_ENABLED:
        from ..admin.routes import main_admin_router

        app.include_router(main_admin_router)

        # Mount admin static files if UI is enabled
        if settings.ADMIN_UI_ENABLED:
            admin_static_path = Path(__file__).parent.parent / "admin" / "static"
            if admin_static_path.exists():
                app.mount(
                    f"{settings.ADMIN_PREFIX}/static",
                    StaticFiles(directory=str(admin_static_path)),
                    name="admin-static",
                )

    # Setup custom documentation
    try:
        setup_docs_customization(app, settings)
    except Exception as e:
        logger.warning(f"Could not setup custom documentation: {e}")

    # Load and register plugins
    _load_plugins(app)

    logger.info("FABI+ application created successfully")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API prefix: {settings.API_PREFIX}")
    logger.info(f"Admin enabled: {settings.ADMIN_ENABLED}")

    return app


def _discover_app_routers():
    """Discover and load custom routers from installed apps"""
    import importlib
    from typing import Dict

    from fastapi import APIRouter

    custom_routers: Dict[str, APIRouter] = {}

    for app_name in settings.INSTALLED_APPS:
        try:
            # Try to import the app's views module
            views_module_path = f"{app_name}.views"
            views_module = importlib.import_module(views_module_path)

            # Look for a router in the views module
            if hasattr(views_module, "router") and isinstance(
                views_module.router, APIRouter
            ):
                custom_routers[app_name] = views_module.router
                logger.info(f"Found custom router in {app_name}.views")
                continue

        except ImportError:
            # No views module, try urls module
            pass

        try:
            # Try to import the app's urls module
            urls_module_path = f"{app_name}.urls"
            urls_module = importlib.import_module(urls_module_path)

            # Look for a router in the urls module
            if hasattr(urls_module, "router") and isinstance(
                urls_module.router, APIRouter
            ):
                custom_routers[app_name] = urls_module.router
                logger.info(f"Found custom router in {app_name}.urls")

        except ImportError:
            # No urls module either, skip this app
            logger.debug(f"No custom router found for app '{app_name}'")
            continue
        except Exception as e:
            logger.warning(f"Error loading router from app '{app_name}': {e}")
            continue

    return custom_routers


def _load_plugins(app: FastAPI):
    """Load and register plugins"""
    for plugin_path in settings.INSTALLED_PLUGINS:
        try:
            import importlib

            plugin_module = importlib.import_module(plugin_path)

            # Look for plugin registration function
            if hasattr(plugin_module, "register_plugin"):
                plugin_module.register_plugin(app)
                logger.info(f"Plugin '{plugin_path}' loaded successfully")
            else:
                logger.warning(
                    f"Plugin '{plugin_path}' has no register_plugin function"
                )

        except ImportError as e:
            logger.error(f"Failed to load plugin '{plugin_path}': {e}")
        except Exception as e:
            logger.error(f"Error registering plugin '{plugin_path}': {e}")


# Create default app instance
app = create_app()
