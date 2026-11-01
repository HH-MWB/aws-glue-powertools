# Contributing

Thank you for your interest in contributing to Powertools for AWS Glue. This guide covers local environment setup, development workflow, and pull request expectations.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (environment and dependency management)
- [just](https://github.com/casey/just) (command runner)
- [Docker](https://www.docker.com/) (required for running tests inside the official AWS Glue container)

## Setup

From the repository root:

```bash
just init
```

`just init` installs the project Python version, syncs development dependencies into `.venv`, and installs the git pre-commit hooks.

If you do not use `just`, run:

```bash
uv python install
uv sync --group dev
uv run pre-commit install
```

## Making Changes

1. Create a feature branch: `git checkout -b feat/my-new-feature`
2. Add your implementation under `src/aws_glue_powertools/`.
3. Add BDD scenarios and step definitions under `features/`.
4. Run lint and formatting checks across all files:

   ```bash
   just lint
   ```

5. Run the test suite inside the AWS Glue container and verify 100% test coverage:

   ```bash
   just coverage
   ```

## Code Style

This project enforces strict code quality standards configured in `pyproject.toml`:
- **Line length:** 79 characters (PEP 8).
- **Docstrings:** Required on all modules, functions, classes, and step definitions (`pydocstyle` Google convention).
- **Typing:** Fully type-annotated (`mypy` and `pyright` strict modes).
- **Coverage:** 100% branch and line coverage enforced.

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) for commit subjects, for example:

```text
feat(job): add streaming job lifecycle manager
fix(job): handle unhandled exceptions during commit
docs: update usage examples in README
test: add scenario for parameter resolution
```

## Pull Requests

- Keep pull requests focused on a single concern.
- Ensure `just lint` and `just coverage` pass before requesting review.
- Use a Conventional Commits title for your pull request.

## Code of Conduct

Follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Report security vulnerabilities through [SECURITY.md](SECURITY.md).
