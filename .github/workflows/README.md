# GitHub Actions Workflows

This directory contains the GitHub Actions workflows for the FABI+ framework.

## Active Workflow

**📋 `ci.yml`** - Main CI/CD Pipeline ✅ **ACTIVE**

This is the comprehensive CI/CD pipeline that runs on every push and pull request. It includes:

- **Multi-version testing** (Python 3.10, 3.11, 3.12)
- **Code quality checks** (Black, isort, flake8, mypy)
- **Security scanning** (Bandit, Safety)
- **Test coverage** with reporting
- **Package building** and validation
- **Integration testing** with real database
- **Dependency review** (for private repos with GitHub Advanced Security)
- **Automated notifications** of results

## Workflow Triggers

The CI pipeline runs on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches  
- Daily scheduled runs at 2 AM UTC
- Manual workflow dispatch

## Local Testing

To run the same checks locally before pushing:

```bash
# Make the script executable (first time only)
chmod +x scripts/test-ci-locally.sh

# Run local CI checks
./scripts/test-ci-locally.sh
```

## Configuration

The workflow is configured to:
- Use Python 3.10+ (3.9 removed due to compatibility issues)
- Use Poetry for dependency management
- Generate security and coverage reports
- Upload artifacts for debugging
- Continue on non-critical errors (security scans)

## Troubleshooting

### Common Issues

1. **Python 3.9 not supported**: The project requires Python 3.10+
2. **Author string format**: Must be in format "Name <email@domain.com>"
3. **Deprecated actions**: All actions updated to latest versions (v4)
4. **Dependency review**: Only works with GitHub Advanced Security on private repos

### Status Checks

The workflow includes these status checks:
- ✅ Tests (all Python versions)
- ✅ Code quality (linting, formatting)
- ✅ Security scans (with warnings)
- ✅ Package build
- ✅ Integration tests

### Artifacts

The following artifacts are generated:
- `security-reports` - Bandit and Safety scan results
- `dist` - Built Python packages
- Coverage reports (in job logs)

## Maintenance

To update the workflow:
1. Edit `.github/workflows/ci.yml`
2. Test locally with `./scripts/test-ci-locally.sh`
3. Commit and push to trigger the workflow
4. Monitor the Actions tab for results

## Security

The workflow includes:
- Dependency vulnerability scanning
- Security linting with Bandit
- SARIF upload for GitHub Security tab
- Secrets scanning (GitHub native)

For security issues, see [SECURITY.md](../../SECURITY.md).
