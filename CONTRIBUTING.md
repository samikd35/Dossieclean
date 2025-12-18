# Contributing to DossieClean

First off, thank you for considering contributing to DossieClean! It's people like you that make DossieClean such a great tool for the academic and research community.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Style Guidelines](#style-guidelines)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Getting Started

- Make sure you have a [GitHub account](https://github.com/signup)
- Fork the repository on GitHub
- Clone your fork locally
- Set up the development environment (see below)

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you create a bug report, include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples** (code snippets, screenshots)
- **Describe the behavior you observed and what you expected**
- **Include your environment details** (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description of the proposed enhancement**
- **Explain why this enhancement would be useful**
- **List any alternatives you've considered**

### Your First Code Contribution

Unsure where to begin? Look for issues labeled:

- `good first issue` - Simple issues for newcomers
- `help wanted` - Issues that need community help
- `documentation` - Documentation improvements

### Pull Requests

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. If you've changed APIs, update the documentation
4. Ensure the test suite passes
5. Make sure your code follows the style guidelines
6. Issue that pull request!

## Development Setup

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git

### Setting Up Your Development Environment

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/dossieclean.git
   cd dossieclean
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

5. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_connections.py
```

## Style Guidelines

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: Maximum 100 characters
- **Imports**: Grouped in order (standard library, third-party, local)
- **Docstrings**: Use Google-style docstrings
- **Type hints**: Encouraged for function signatures

### Code Formatting

We use the following tools to maintain code quality:

- **Black** for code formatting
- **flake8** for linting
- **isort** for import sorting

Run formatting before committing:

```bash
black app.py tests/
flake8 app.py tests/
isort app.py tests/
```

### Documentation Style

- Use clear, concise language
- Include code examples where helpful
- Keep README and docs up to date with changes

## Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Code style changes (formatting, semicolons, etc.)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, build, etc.)

### Examples

```
feat(upload): add batch upload progress indicator
fix(azure): handle connection timeout gracefully
docs(readme): add deployment instructions
test(api): add tests for metadata extraction endpoint
```

## Pull Request Process

1. **Update documentation** if you're changing functionality
2. **Add tests** for new features or bug fixes
3. **Update the CHANGELOG.md** with your changes
4. **Ensure CI passes** - all tests and linting must pass
5. **Request review** from at least one maintainer
6. **Address feedback** promptly and professionally

### PR Title Format

Use the same format as commit messages:

```
feat(component): brief description of change
```

### PR Description Template

Your PR description should include:

- **What** - What does this PR do?
- **Why** - Why is this change needed?
- **How** - How does it work? (if complex)
- **Testing** - How was this tested?
- **Screenshots** - If applicable

## Questions?

Feel free to open an issue with the `question` label if you have any questions about contributing.

---

Thank you for contributing to DossieClean! 🎉
