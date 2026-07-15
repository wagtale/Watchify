#!/bin/bash
set -e

# Pass an optional commit message as an argument, e.g. ./release.sh "feat: add new feature"
COMMIT_MSG=${1:-"chore: automated release"}

# Build the project
./gradlew assembleDebug assembleRelease

# Commit any pending changes
if [ -n "$(git status --porcelain)" ]; then
    git add .
    git commit -m "$COMMIT_MSG"
    git push
fi

# Generate version tag based on commit count
COMMIT_COUNT=$(git rev-list --count HEAD)
TAG="v1.0.${COMMIT_COUNT}"

# Tag and push
git tag "$TAG"
git push origin "$TAG"

# Create release with both APKs. GitHub automatically includes the source code zip/tarball in releases.
gh release create "$TAG" \
    app/build/outputs/apk/release/app-release.apk \
    app/build/outputs/apk/debug/app-debug.apk \
    --title "Watchify $TAG" \
    --notes "$COMMIT_MSG"
    
echo "Successfully created release: Watchify $TAG"
