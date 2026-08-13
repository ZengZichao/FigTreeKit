# Contributing to FigTreeKit

Thank you for your interest in contributing to FigTreeKit! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)
- [Feature Requests](#feature-requests)

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.11 (developed and tested on macOS Tahoe 26.5.2)
- Git
- Basic understanding of phylogenetic trees

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/figtreekit.git
   cd figtreekit
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/ZengZichao/FigTreeKit.git
   ```

## Development Setup

### Virtual Environment

Create and activate a virtual environment:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### IDE Configuration

#### VS Code

Recommended extensions:
- Python
- Pylance
- Python Test Explorer
- GitLens

Settings (`.vscode/settings.json`):
```json
{
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.testing.pytestEnabled": true,
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length=100"]
}
```

#### PyCharm

1. Open the project in PyCharm
2. Configure Python interpreter to use the virtual environment
3. Enable pytest as the test runner
4. Configure code style to follow PEP 8

## Code Style

### Python Style Guide

FigTreeKit follows [PEP 8](https://peps.python.org/pep-0008/) with some modifications:

- **Line Length**: 100 characters (instead of 79)
- **Docstrings**: Google style docstrings
- **Type Hints**: Required for all public methods

### Formatting

Use Black for code formatting:

```bash
# Format all files
black figtreekit/ test/ examples/

# Check formatting without making changes
black --check figtreekit/ test/ examples/
```

### Linting

Use Flake8 for linting:

```bash
# Run linter
flake8 figtreekit/ --max-line-length=100
```

### Type Checking

Use MyPy for type checking:

```bash
# Run type checker
mypy figtreekit/
```

## Testing

### Running Tests

```bash
# Run all tests
pytest test/ -v

# Run tests with coverage
pytest test/ -v --cov=figtreekit --cov-report=html

# Run specific test file
pytest test/test_figtreekit.py -v

# Run specific test class
pytest test/test_figtreekit.py::TestFigTreeStyler -v

# Run specific test
pytest test/test_figtreekit.py::TestFigTreeStyler::test_set_layout -v
```

### Writing Tests

1. Create test files in the `test/` directory
2. Name test files as `test_*.py`
3. Name test classes as `Test*`
4. Name test functions as `test_*`
5. Use pytest fixtures for common setup
6. Add docstrings to test functions

Example test:

```python
def test_set_layout():
    """Test setting layout type."""
    styler = FigTreeStyler()
    styler.load_content("((A:0.1,B:0.2):0.3,C:0.4);")
    styler.set_layout(LayoutType.POLAR)
    settings = styler.get_settings()
    assert settings.get("layout.layoutType") == "POLAR"
```

### Test Coverage

代码覆盖率硬门禁为 60%（见 pyproject.toml 的 `--cov-fail-under=60`）；建议新代码尽量达到 80%。查看覆盖率：

```bash
pytest test/ --cov=figtreekit --cov-report=html
open htmlcov/index.html  # View coverage report
```

## Documentation

### Docstrings

All public methods must have docstrings in Google style:

```python
def set_layout(self, layout_type: LayoutType) -> "FigTreeStyler":
    """
    Set the layout type for the tree visualization.

    Args:
        layout_type: The layout type to use (RECTILINEAR, POLAR, or RADIAL).

    Returns:
        self for method chaining.

    Raises:
        ValueError: If layout_type is not a valid LayoutType.

    Example:
        >>> styler = FigTreeStyler("tree.tre")
        >>> styler.set_layout(LayoutType.POLAR)
    """
```

### Type Hints

Add type hints to all function signatures:

```python
def highlight_clade(
    self,
    taxon_names: List[str],
    color: str = "#804548",
    width: int = 4,
    offset: float = 0.0
) -> "FigTreeStyler":
```

### README

Update README_EN.md and README_CN.md when:
- Adding new features
- Changing API
- Fixing bugs
- Updating dependencies

## Pull Request Process

### Before Submitting

1. **Update your fork**:
   ```bash
   git fetch upstream
   git merge upstream/main
   ```

2. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**:
   - Write code
   - Add tests
   - Update documentation

4. **Run tests**:
   ```bash
   pytest test/ -v
   ```

5. **Check code style**:
   ```bash
    black --check figtreekit/ test/
    flake8 figtreekit/ --max-line-length=100
   ```

6. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   ```

7. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

8. **Create a Pull Request** on GitHub

### Pull Request Template

When creating a PR, include:

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Other (please describe)

## Testing
- [ ] All tests pass
- [ ] New tests added for new functionality
- [ ] Code coverage maintained or improved

## Checklist
- [ ] Code follows PEP 8 style guidelines
- [ ] Self-review of code completed
- [ ] Docstrings added/updated
- [ ] Type hints added
- [ ] Documentation updated
```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs tests and linting
2. **Code Review**: At least one maintainer reviews the code
3. **Feedback**: Address any review comments
4. **Approval**: Maintainer approves the PR
5. **Merge**: PR is merged into main branch

## Reporting Issues

### Bug Reports

When reporting bugs, include:

1. **Description**: Clear description of the bug
2. **Steps to Reproduce**: Step-by-step instructions
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**:
   - Python version
   - Operating system
   - FigTreeKit version
   - Biopython version
6. **Code Sample**: Minimal code to reproduce the issue
7. **Error Message**: Full error traceback if applicable

### Example Bug Report

```markdown
## Bug Description
Tree export fails when using polar layout with specific Newick format.

## Steps to Reproduce
1. Create styler with Newick: "((A:0.1,B:0.2):0.3,C:0.4);"
2. Set layout to POLAR
3. Export to file

## Expected Behavior
Should export successfully.

## Actual Behavior
Raises TreeParsingError.

## Environment
- Python 3.11.0
- macOS 14.0
- FigTreeKit 1.0.0
- Biopython 1.81

## Code Sample
```python
styler = FigTreeStyler()
styler.load_content("((A:0.1,B:0.2):0.3,C:0.4);")
styler.set_layout(LayoutType.POLAR)
styler.export("output.nex")
```

## Error Message
```
TreeParsingError: Failed to parse tree
```
```

## Feature Requests

When requesting features, include:

1. **Description**: Clear description of the feature
2. **Use Case**: Why this feature is needed
3. **Proposed Solution**: How you think it should work
4. **Alternatives**: Any alternative solutions considered
5. **Additional Context**: Any other relevant information

## Questions and Discussions

For questions and discussions:
- Use GitHub Discussions for general questions
- Create an Issue for bug reports and feature requests
- Join our community chat (if available)

## Recognition

Contributors will be recognized in:
- README_EN.md / README_CN.md
- GitHub contributors page
- Release notes

## License

By contributing to FigTreeKit, you agree that your contributions will be licensed under the GNU General Public License v2.0 or later (GPL-2.0-or-later).

## Contact

For questions about contributing:
- Email: zengzichao@sjtu.edu.cn
- GitHub Issues: [https://github.com/ZengZichao/FigTreeKit/issues](https://github.com/ZengZichao/FigTreeKit/issues)

Thank you for contributing to FigTreeKit!
