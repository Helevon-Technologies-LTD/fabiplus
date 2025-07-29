# FABI+ Framework

<div align="center">

![FABI+ Logo](https://fabiplus.helevon.org/logo.png)

**FABI+** (FastAPI + Django-like Admin Interface) is a modern Python web framework that combines the speed and flexibility of FastAPI with the convenience of Django-style admin interfaces and ORM patterns.

[![PyPI version](https://badge.fury.io/py/fabiplus.svg)](https://badge.fury.io/py/fabiplus)
[![Python Support](https://img.shields.io/pypi/pyversions/fabiplus.svg)](https://pypi.org/project/fabiplus/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/helevon/fabiplus/workflows/Tests/badge.svg)](https://github.com/helevon/fabiplus/actions)
[![Coverage](https://codecov.io/gh/helevon/fabiplus/branch/main/graph/badge.svg)](https://codecov.io/gh/helevon/fabiplus)

[Documentation](https://fabiplus.helevon.org) • [Quick Start](#-quick-start) • [Examples](https://github.com/helevon/fabiplus-examples) • [Contributing](#-contributing)

</div>

## 🚀 Features

### 🔥 **Core Features**
- **FastAPI Backend**: High-performance async API with automatic OpenAPI documentation
- **Django-style Admin**: Familiar admin interface with CRUD operations
- **Multiple ORM Support**: SQLModel and SQLAlchemy (Tortoise ORM planned for future release)
- **Auto-generated APIs**: Automatic CRUD endpoints for your models
- **CLI Tools**: Django-like management commands (`startproject`, `startapp`, `migrate`)

### 🔐 **Authentication & Security**
- **OAuth2 + JWT**: Built-in authentication with JWT tokens
- **Role-based Permissions**: Granular permissions with custom roles
- **User Registration**: Built-in user registration and management
- **Security Headers**: CORS, CSP, and other security features
- **Rate Limiting**: Built-in API rate limiting

### 🗄️ **Database & ORM**
- **Database Migrations**: Alembic integration for schema management
- **Multiple Databases**: PostgreSQL, MySQL, SQLite support
- **Connection Pooling**: Optimized database connections
- **Query Optimization**: Built-in query optimization and caching

### 🚀 **Production Ready**
- **Docker Support**: Ready-to-use Docker configurations
- **Caching Support**: Redis and in-memory caching
- **Logging & Monitoring**: Comprehensive logging and health checks
- **Performance**: Optimized for high-performance applications
- **Scalability**: Horizontal and vertical scaling support

## 📦 Installation

### Using pip (Recommended)

```bash
pip install fabiplus
```

### From source

```bash
git clone https://github.com/helevon/fabiplus.git
cd fabiplus
pip install -e .
```

### Development installation

```bash
git clone https://github.com/helevon/fabiplus.git
cd fabiplus
pip install -e ".[dev]"
```

## 🏃‍♂️ Quick Start

### 1. Create a new project

```bash
fabiplus project startproject myblog
cd myblog
```

### 2. Create an app

```bash
fabiplus app startapp blog
```

### 3. Define your models

```python
# apps/blog/models.py
from fabiplus.core.models import BaseModel, register_model
from sqlmodel import Field
from typing import Optional
import uuid

@register_model
class Post(BaseModel, table=True):
    """Blog post model"""
    
    title: str = Field(max_length=200, description="Post title")
    content: str = Field(description="Post content")
    excerpt: Optional[str] = Field(default="", description="Post excerpt")
    is_published: bool = Field(default=False, description="Is published")
    author_id: uuid.UUID = Field(foreign_key="user.id", description="Post author")
    
    class Config:
        _verbose_name = "Blog Post"
        _verbose_name_plural = "Blog Posts"
    
    def __str__(self):
        return self.title
```

### 4. Configure your app

```python
# myblog/settings.py
INSTALLED_APPS = [
    "apps.core",
    "apps.blog",  # Add your app here
]
```

### 5. Run migrations

```bash
fabiplus db makemigrations
fabiplus db migrate
```

### 6. Create a superuser

```bash
fabiplus user create --username admin --email admin@example.com --password admin123 --superuser
```

### 7. Start the server

```bash
fabiplus server run
```

### 8. Access your application

- **API Documentation**: http://127.0.0.1:8000/docs
- **Admin Interface**: http://127.0.0.1:8000/admin
- **API Endpoints**: http://127.0.0.1:8000/api/v1/

## 🎯 Use Cases

FABI+ is perfect for:

- **Blog Systems**: Content management with authentication
- **API Backends**: RESTful APIs with automatic documentation
- **Admin Dashboards**: Data management interfaces
- **E-commerce**: Product catalogs and order management
- **CMS Applications**: Content management systems
- **SaaS Applications**: Multi-tenant applications with role-based access

## 📚 Documentation

- **📖 Full Documentation**: [fabiplus.helevon.org](https://fabiplus.helevon.org)
- **🚀 Quick Start Guide**: [Getting Started](https://fabiplus.helevon.org/getting-started)
- **📋 API Reference**: [API Documentation](https://fabiplus.helevon.org/api-reference)
- **🔐 Authentication Guide**: [Authentication](https://fabiplus.helevon.org/authentication)
- **🎨 Frontend Integration**: [Frontend Guide](https://fabiplus.helevon.org/frontend)
- **🚀 Deployment**: [Production Deployment](https://fabiplus.helevon.org/deployment)

## 🤝 Contributing

We welcome contributions from the community! FABI+ is open source and we encourage you to help make it better.

### 🌟 Ways to Contribute

- **🐛 Report Bugs**: [Create an issue](https://github.com/helevon/fabiplus/issues/new?template=bug_report.md)
- **💡 Request Features**: [Feature requests](https://github.com/helevon/fabiplus/issues/new?template=feature_request.md)
- **📝 Improve Documentation**: Help us improve our docs
- **🔧 Submit Code**: Fix bugs or add new features
- **🧪 Write Tests**: Help us improve test coverage
- **💬 Join Discussions**: [GitHub Discussions](https://github.com/helevon/fabiplus/discussions)

### 🛠️ Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/fabiplus.git
   cd fabiplus
   ```

2. **Set up development environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Run tests**
   ```bash
   pytest
   ```

4. **Format code**
   ```bash
   black fabiplus/
   isort fabiplus/
   ```

### 📋 Development Process

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes
4. **Add** tests for your changes
5. **Run** the test suite (`pytest`)
6. **Format** your code (`black . && isort .`)
7. **Commit** your changes (`git commit -m 'Add amazing feature'`)
8. **Push** to the branch (`git push origin feature/amazing-feature`)
9. **Open** a Pull Request

### 🧪 Testing

We maintain high test coverage. Please add tests for any new features:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=fabiplus

# Run specific test file
pytest tests/test_models.py

# Run with verbose output
pytest -v
```

### 📝 Code Style

We use Black and isort for code formatting:

```bash
# Format code
black fabiplus/ tests/
isort fabiplus/ tests/

# Check formatting
black --check fabiplus/ tests/
isort --check-only fabiplus/ tests/
```

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### MIT License Summary

- ✅ **Commercial use** - Use in commercial projects
- ✅ **Modification** - Modify the source code
- ✅ **Distribution** - Distribute the software
- ✅ **Private use** - Use privately
- ❌ **Liability** - No warranty or liability
- ❌ **Warranty** - No warranty provided

## 🙏 Acknowledgments

- **[FastAPI](https://fastapi.tiangolo.com/)** - For the excellent async framework
- **[Django](https://www.djangoproject.com/)** - For admin interface inspiration
- **[SQLModel](https://sqlmodel.tiangolo.com/)** - For the modern ORM approach
- **[Pydantic](https://pydantic-docs.helpmanual.io/)** - For data validation
- **[Alembic](https://alembic.sqlalchemy.org/)** - For database migrations
- **The Python Community** - For amazing tools and libraries

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=helevon/fabiplus&type=Date)](https://star-history.com/#helevon/fabiplus&Date)

## 📞 Support & Community

- **📖 Documentation**: [fabiplus.helevon.org](https://fabiplus.helevon.org)
- **🐛 Issues**: [GitHub Issues](https://github.com/helevon/fabiplus/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/helevon/fabiplus/discussions)
- **📧 Email**: support@helevon.org
- **🐦 Twitter**: [@helevon_org](https://twitter.com/helevon_org)

---

<div align="center">

**Made with ❤️ by the [Helevon](https://helevon.org) team**

[⭐ Star us on GitHub](https://github.com/helevon/fabiplus) • [🚀 Try the Demo](https://demo.fabiplus.helevon.org) • [📖 Read the Docs](https://fabiplus.helevon.org)

</div>
