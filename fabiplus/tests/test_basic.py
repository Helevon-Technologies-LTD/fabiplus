"""
Basic tests for FABI+ framework
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from fabiplus.core.app import create_app
from fabiplus.core.auth import auth_backend
from fabiplus.core.models import ModelRegistry, User


@pytest.fixture(name="session")
def session_fixture():
    """Create test database session"""
    # Import all models to ensure they're registered
    from fabiplus.core.activity import Activity
    from fabiplus.core.user_model import User

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables including User and Activity
    User.metadata.create_all(engine)
    Activity.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create test client"""

    def get_session_override():
        return session

    # Override the ModelRegistry engine before creating the app
    from fabiplus.core.models import ModelRegistry

    original_engine = ModelRegistry._engine
    ModelRegistry._engine = session.bind

    # Ensure models are properly registered before creating the app
    from fabiplus.core.activity import Activity
    from fabiplus.core.models import ModelRegistry
    from fabiplus.core.user_model import User

    # Explicitly register core models to ensure they're available
    ModelRegistry.register(User)
    ModelRegistry.register(Activity)

    # Trigger model discovery to ensure all models are loaded
    try:
        ModelRegistry.discover_models()
    except Exception:
        # Model discovery might fail in test environment, but core models are already registered
        pass

    app = create_app()

    # Override the get_session dependency
    app.dependency_overrides[ModelRegistry.get_session] = get_session_override

    # Ensure API routes are included - this handles both cases where lifespan runs and doesn't run
    try:
        from fabiplus.api.auto import get_api_router

        api_router = get_api_router()

        # Check if routes are already included by checking existing routes
        existing_paths = [route.path for route in app.routes if hasattr(route, "path")]
        user_route_exists = any("/api/user/" in path for path in existing_paths)

        if not user_route_exists:
            app.include_router(api_router)

    except Exception as e:
        # If API route generation fails, the test will fail anyway
        # but we don't want to crash the test setup
        pass

    client = TestClient(app)
    yield client

    # Clean up
    app.dependency_overrides.clear()
    ModelRegistry._engine = original_engine


def test_root_endpoint(client: TestClient):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_health_check(client: TestClient):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_create_user(session: Session):
    """Test user creation"""
    from fabiplus.core.user_model import User

    # Create user directly in the test session
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=auth_backend.hash_password("testpassword123"),
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


def test_authenticate_user(session: Session):
    """Test user authentication"""
    from fabiplus.core.user_model import User

    # Create user directly in the test session
    user = User(
        username="authtest",
        email="authtest@example.com",
        hashed_password=auth_backend.hash_password("testpassword123"),
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    # Test password verification
    assert auth_backend.verify_password("testpassword123", user.hashed_password)
    assert not auth_backend.verify_password("wrongpassword", user.hashed_password)


def test_jwt_token_creation():
    """Test JWT token creation and validation"""
    test_data = {"sub": "test-user-id", "username": "testuser"}

    # Create token
    token = auth_backend.create_access_token(test_data)
    assert isinstance(token, str)
    assert len(token) > 0

    # Decode token
    decoded_data = auth_backend.decode_access_token(token)
    assert decoded_data["sub"] == "test-user-id"
    assert decoded_data["username"] == "testuser"


def test_login_endpoint(client: TestClient, session: Session):
    """Test login endpoint"""
    # Create test user
    user = User(
        username="logintest",
        email="logintest@example.com",
        hashed_password=auth_backend.hash_password("testpassword123"),
        is_active=True,
    )
    session.add(user)
    session.commit()

    # Test JSON login
    response = client.post(
        "/auth/login", json={"username": "logintest", "password": "testpassword123"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data


def test_model_registry():
    """Test model registry functionality"""
    from fabiplus.core.models import User

    # Test model registration
    models = ModelRegistry.get_all_models()
    assert "user" in models
    assert models["user"] == User

    # Test get model
    user_model = ModelRegistry.get_model("user")
    assert user_model == User

    # Test model names
    model_names = ModelRegistry.get_model_names()
    assert "user" in model_names


def test_admin_endpoints_require_auth(client: TestClient):
    """Test that admin API endpoints require authentication"""
    # Test admin API endpoint (should return 401 for unauthenticated requests)
    response = client.get("/admin/api/")
    assert response.status_code == 401


def test_api_endpoints_exist(client: TestClient):
    """Test that API endpoints are created for models"""
    # First, verify that the API routes are actually available
    # by checking the OpenAPI schema
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi_data = response.json()

    # Check if user endpoints exist in the OpenAPI schema
    paths = openapi_data.get("paths", {})
    user_list_path = "/api/user/"
    user_detail_path = "/api/user/{item_id}"

    assert (
        user_list_path in paths
    ), f"User list endpoint not found in paths: {list(paths.keys())}"
    assert (
        user_detail_path in paths
    ), f"User detail endpoint not found in paths: {list(paths.keys())}"

    # Test user endpoints - User model is a core model and requires authentication
    response = client.get("/api/user/")
    assert (
        response.status_code == 401
    ), f"Expected 401, got {response.status_code}. Response: {response.text}"

    # Verify the error message
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Not authenticated"


if __name__ == "__main__":
    pytest.main([__file__])
