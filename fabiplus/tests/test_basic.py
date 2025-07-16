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
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create test client"""

    def get_session_override():
        return session

    app = create_app()

    # Override the get_session dependency
    from fabiplus.core.models import ModelRegistry

    app.dependency_overrides[ModelRegistry.get_session] = get_session_override

    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


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


def test_create_user():
    """Test user creation"""
    user = auth_backend.create_user(
        username="testuser", email="test@example.com", password="testpassword123"
    )

    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


def test_authenticate_user():
    """Test user authentication"""
    # Create user
    user = auth_backend.create_user(
        username="authtest", email="authtest@example.com", password="testpassword123"
    )

    # Test successful authentication
    authenticated_user = auth_backend.authenticate_user("authtest", "testpassword123")
    assert authenticated_user is not None
    assert authenticated_user.username == "authtest"

    # Test failed authentication
    failed_auth = auth_backend.authenticate_user("authtest", "wrongpassword")
    assert failed_auth is None


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
    """Test that admin endpoints require authentication"""
    response = client.get("/admin/")
    assert response.status_code == 401


def test_api_endpoints_exist(client: TestClient):
    """Test that API endpoints are created for models"""
    # Test user endpoints
    response = client.get("/api/user/")
    # Should return 200 with empty results (no auth required for listing)
    assert response.status_code == 200

    data = response.json()
    assert "count" in data
    assert "results" in data


if __name__ == "__main__":
    pytest.main([__file__])
