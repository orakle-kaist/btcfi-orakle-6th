# btcfi-orakle-6th

<!-- Add a cool project logo or banner here if you have one! -->

> A brief description of your project goes here. What does it do? Who is it for?

[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![Prettier Code Style](https://img.shields.io/badge/code_style-prettier-brightgreen.svg)](https://prettier.io)

<!-- Add other badges like build status, coverage, etc. as your project grows -->
<!-- e.g., [![Build Status](https://travis-ci.org/your-org/your-repo.svg?branch=main)](https://travis-ci.org/your-org/your-repo) -->

This project is set up with a modern development environment to ensure code quality, consistency, and a streamlined workflow.

## ✨ Features

- **Automated Code Formatting**: [Prettier](https://prettier.io/) is configured to automatically format code on commit using `lint-staged`.
- **Commit Message Linting**: [Commitlint](https://commitlint.js.org/) enforces [Conventional Commits](https://www.conventionalcommits.org/) standards for clear and maintainable commit history.
- **Git Hooks**: [Husky](https://typicode.github.io/husky/) manages Git hooks for:
  - `pre-commit`: Runs `lint-staged` for formatting.
  - `commit-msg`: Validates commit messages with `commitlint`.
  - `pre-push`: Verifies entire project formatting before pushing.
- **Development Workflow**: A `Makefile` provides convenient shortcuts for common tasks like setup, formatting, and linting.
- **Consistent Editor Settings**: `.editorconfig` helps maintain consistent coding styles across different editors and IDEs.
- **Organized `package.json`**: Scripts are optimized, and `sort-package-json` keeps the file tidy.

## Prerequisites

- [Node.js](https://nodejs.org/) (LTS version recommended)
- [Yarn Classic (v1.x)](https://classic.yarnpkg.com/en/docs/install)

## 🚀 Getting Started

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/orakle-kaist/btcfi-orakle-6th.git
    cd btcfi-orakle-6th
    ```

2.  **Install dependencies:**

    ```bash
    yarn install
    ```

    This will also set up Husky Git hooks.

3.  **Run the initial setup script (optional but recommended):**
    This script ensures all dependencies are up-to-date and Husky is properly configured.
    ```bash
    sh ./scripts/init.sh
    # Or using make:
    # make setup
    ```

## 🛠️ Available Scripts

This project uses both Yarn scripts (defined in `package.json`) and `make` targets (defined in `Makefile`).

### Yarn Scripts (from `package.json`)

- `yarn format`: Formats all supported files in the project using Prettier.
- `yarn format:package`: Sorts the `package.json` file.
- `yarn lint:format`: Checks for formatting issues using Prettier.
- `yarn lint:commit:last`: Lints the last commit message.
- `yarn lint:commit:range`: Lints commit messages from `main` to `HEAD`.
- `yarn husky:prepare`: Installs Husky (usually run automatically post-install).

### Makefile Targets

Run `make` or `make help` to see all available targets. Key targets include:

- `make setup`: Runs the initial project setup script.
- `make format`: Formats all code and sorts `package.json`.
- `make lint`: Checks for formatting issues across the project.
  - `make lint-ts` (Placeholder for TypeScript linting)
  - `make lint-js` (Placeholder for JavaScript linting)
  - `make lint-go` (Placeholder for Go linting)
- `make lint-commit-last`: Lints the last commit message.
- `make lint-commit-range`: Lints commit messages from `main` to `HEAD`.

## 🎨 Code Style & Linting

- **Formatting**: [Prettier](https://prettier.io/) is used for code formatting. It's configured via `.prettierrc` and runs automatically on commit for staged files.
  - To format all files manually: `yarn format` or `make format`.
- **Commit Messages**: [Commitlint](https://commitlint.js.org/) ensures commit messages adhere to the Conventional Commits specification. This is checked automatically on commit.

## 🪝 Git Hooks (Husky)

- **`pre-commit`**: Before committing, `lint-staged` runs Prettier on staged files to automatically format them.
- **`commit-msg`**: When a commit message is written, `commitlint` checks if it follows the Conventional Commits standard.
- **`pre-push`**: Before pushing to the remote repository, the entire project's formatting is verified using `yarn lint:format`.

## 🤝 Contributing

Contributions are welcome! Please ensure your code adheres to the project's linting and formatting standards. (Further details on the contribution process can be added here).

## 📜 License

This project is licensed under the [MIT License](./LICENSE). (Assuming MIT, as per `package.json`. If you don't have a LICENSE file, you should add one.)
