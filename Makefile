.PHONY: all help setup format format-ts format-js format-go lint lint-ts lint-js lint-go lint-commit-last lint-commit-range

# ==============================================================================
# Default Target
# ==============================================================================
all: help

help:
	@echo "Available targets:"
	@echo "  make help                - Show this help message"
	@echo "  make setup               - Run initial project setup (executes scripts/init.sh)"
	@echo ""
	@echo "  Formatting:"
	@echo "  make format              - Format all supported files (using Prettier)"
	@echo "  make format-ts           - Format TypeScript files (delegates to 'make format')"
	@echo "  make format-js           - Format JavaScript files (delegates to 'make format')"
	@echo "  make format-go           - Format Go files (placeholder for gofmt)"
	@echo ""
	@echo "  Linting:"
	@echo "  make lint                - Lint all supported files (runs Prettier check, then language-specific)"
	@echo "  make lint-ts             - Lint TypeScript files (Prettier check + ESLint placeholder)"
	@echo "  make lint-js             - Lint JavaScript files (Prettier check + ESLint placeholder)"
	@echo "  make lint-go             - Lint Go files (placeholder for golint/golangci-lint)"
	@echo "  make lint-commit-last    - Lint the last commit message"
	@echo "  make lint-commit-range   - Lint commit messages from main to HEAD"

# ==============================================================================
# Project Setup
# ==============================================================================
setup:
	@echo "🚀 Running project setup..."
	@sh ./scripts/init.sh
	@echo "✅ Project setup complete!"

# ==============================================================================
# Formatting
# ==============================================================================
format:
	@echo "🎨 Formatting all supported files using Prettier..."
	@yarn format # Runs prettier --write .
	@echo "🎨 Sorting package.json..."
	@yarn format:package # Runs sort-package-json
	@echo "✅ Formatting and package.json sorting complete."

format-ts: format
	@echo "🎨 TypeScript files formatted via project-wide Prettier (invoked by 'make format')."

format-js: format
	@echo "🎨 JavaScript files formatted via project-wide Prettier (invoked by 'make format')."

format-go:
	@echo "🎨 Formatting Go files..."
	@echo "ℹ️ Placeholder: Add Go formatting command here."
	@echo "   Example: find . -name '*.go' -exec gofmt -w {} \\;"
	@# find . -name '*.go' -exec gofmt -w {} \; || true

# ==============================================================================
# Linting
# ==============================================================================
# General lint target - runs Prettier check and advises on specific linters
lint:
	@echo "🔍 Running Prettier check on all supported files..."
	@yarn lint:format
	@echo "✅ Prettier check complete."
	@echo "ℹ️ For language-specific linting, run 'make lint-ts', 'make lint-js', or 'make lint-go'."

lint-ts:
	@echo "🔍 Linting TypeScript files (Prettier check + ESLint placeholder)..."
	@yarn lint:format
	@echo "ℹ️ Placeholder: Add TypeScript linting (ESLint) command here."
	@echo "   Example: yarn eslint './**/*.{ts,tsx}'"
	@# yarn eslint './**/*.{ts,tsx}' --fix || true
	@echo "✅ TypeScript linting (Prettier check done, ESLint placeholder)."

lint-js:
	@echo "🔍 Linting JavaScript files (Prettier check + ESLint placeholder)..."
	@yarn lint:format
	@echo "ℹ️ Placeholder: Add JavaScript linting (ESLint) command here."
	@echo "   Example: yarn eslint './**/*.{js,jsx}'"
	@# yarn eslint './**/*.{js,jsx}' --fix || true
	@echo "✅ JavaScript linting (Prettier check done, ESLint placeholder)."

lint-go:
	@echo "🔍 Linting Go files..."
	@echo "ℹ️ Placeholder: Add Go linting command here."
	@echo "   Example: golint ./... or golangci-lint run"
	@# golint ./... || true
	@# golangci-lint run || true
	@echo "✅ Go linting (placeholder)."

# ==============================================================================
# Commitlint (using existing package.json scripts)
# ==============================================================================
lint-commit-last:
	@echo "🔍 Linting last commit message..."
	@yarn lint:commit:last

lint-commit-range:
	@echo "🔍 Linting commit messages (from main to HEAD)..."
	@yarn lint:commit:range 