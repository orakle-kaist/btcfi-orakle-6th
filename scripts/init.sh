#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# Get the directory of this script
# SCRIPT_DIR will be kept as requested, though not actively used in this version unless further logic is added.
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")

echo "🚀 Starting project initialization..."

echo "📦 Installing and updating dependencies..."
yarn install # 'yarn' or 'yarn install' are generally interchangeable for installing dependencies.
yarn upgrade  # Upgrade dependencies to their latest versions based on package.json

echo "⚙️ Setting up Husky..."
# Executes the "husky:prepare": "husky install" script from package.json.
# This is equivalent to running 'yarn prepare' (yarn sometimes automatically runs the prepare script).
yarn run husky:prepare

echo "📄 Sorting package.json..."
yarn format:package

# Finally, run yarn install one more time after all changes to ensure
# the node_modules state is up-to-date and the lock file is updated.
echo "🔄 Finalizing dependency state and cleaning up..."
yarn install

echo "✅ Project initialization complete!"