# Contributing to FABI+

We love your input! We want to make contributing to FABI+ as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## 🚀 Quick Start for Contributors

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/fabiplus.git
   cd fabiplus
   ```
3. **Set up development environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  
   # On Windows: venv\Scripts\activate
   pip install -e ".[dev]"
   ```
4. **Create a branch** for your feature:
   ```bash
   git checkout -b feature/amazing-feature
   ```
5. **Make your changes** and add tests
6. **Run tests** to ensure everything works:
   ```bash
   pytest
   black fabiplus/ tests/
   isort fabiplus/ tests/
   ```
7. **Commit and push** your changes:
   ```bash
   git commit -m "Add amazing feature"
   git push origin feature/amazing-feature
   ```
8. **Open a Pull Request** on GitHub

## 📋 Development Process

We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

### Pull Requests

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. If you've changed APIs, update the documentation
4. Ensure the test suite passes
5. Make sure your code lints (black, isort)
6. Issue that pull request!

### Code Review Process

- All submissions require review before merging
- We may suggest changes, improvements, or alternatives
- Once approved, maintainers will merge your PR

## 🐛 Bug Reports

We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/helevon/fabiplus/issues/new?template=bug_report.md).

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## 💡 Feature Requests

We welcome feature requests! Please [open an issue](https://github.com/helevon/fabiplus/issues/new?template=feature_request.md) with:

- **Clear description** of the feature
- **Use case** - why would this be useful?
- **Possible implementation** - if you have ideas
- **Alternatives considered** - what other solutions did you consider?

## 🧪 Testing

We use pytest for testing. Please add tests for any new features or bug fixes.

### Running Tests

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

### Writing Tests

- Place tests in the `tests/` directory
- Name test files with `test_` prefix
- Use descriptive test function names
- Include docstrings for complex tests
- Test both success and failure cases

Example test:

```python
def test_user_creation():
    """Test that users can be created with valid data."""
    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "securepass123"
    }
    user = create_user(user_data)
    assert user.username == "testuser"
    assert user.email == "test@example.com"
```

## 📝 Code Style

We use automated code formatting to maintain consistency:

### Black (Code Formatting)

```bash
# Format code
black fabiplus/ tests/

# Check formatting
black --check fabiplus/ tests/
```

### isort (Import Sorting)

```bash
# Sort imports
isort fabiplus/ tests/

# Check import sorting
isort --check-only fabiplus/ tests/
```

### Code Style Guidelines

- Follow PEP 8
- Use type hints where possible
- Write docstrings for public functions and classes
- Keep functions focused and small
- Use meaningful variable names
- Add comments for complex logic

## 📚 Documentation

Documentation is hosted at [fabiplus.helevon.org](https://fabiplus.helevon.org).

### Updating Documentation

- API documentation is auto-generated from docstrings
- Update docstrings when changing function signatures
- Add examples to docstrings when helpful
- Update README.md for major changes

### Docstring Format

We use Google-style docstrings:

```python
def create_user(user_data: dict) -> User:
    """Create a new user with the provided data.
    
    Args:
        user_data: Dictionary containing user information with keys:
            - username: Unique username string
            - email: Valid email address
            - password: Plain text password (will be hashed)
    
    Returns:
        User: The created user instance
        
    Raises:
        ValidationError: If user_data is invalid
        UserExistsError: If username or email already exists
        
    Example:
        >>> user_data = {"username": "john", "email": "john@example.com", "password": "secret"}
        >>> user = create_user(user_data)
        >>> print(user.username)
        john
    """
```

## 🔒 Security

### Reporting Security Issues

Please **DO NOT** report security vulnerabilities in public issues. Instead:

1. Email us at security@helevon.org
2. Include detailed information about the vulnerability
3. We'll respond within 48 hours
4. We'll work with you to fix the issue before public disclosure

### Security Best Practices

- Never commit secrets, passwords, or API keys
- Use environment variables for sensitive configuration
- Validate all user inputs
- Use parameterized queries to prevent SQL injection
- Follow OWASP security guidelines

## 🏷️ Versioning

We use [Semantic Versioning](http://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🤝 Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

Examples of behavior that contributes to creating a positive environment include:

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by contacting the project team at conduct@helevon.org.

## 🙋‍♀️ Questions?

Don't hesitate to ask questions! You can:

- [Open an issue](https://github.com/helevon/fabiplus/issues/new)
- [Start a discussion](https://github.com/helevon/fabiplus/discussions)
- Email us at support@helevon.org

## 🎉 Recognition

Contributors will be recognized in:

- The project README
- Release notes for their contributions
- Our [contributors page](https://fabiplus.helevon.org/contributors)

Thank you for contributing to FABI+! 🚀
