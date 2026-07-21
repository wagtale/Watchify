#!/bin/bash
set -e

# Read current version from version.properties
if [ -f version.properties ]; then
    MAJOR=$(grep "MAJOR" version.properties | cut -d'=' -f2)
    MINOR=$(grep "MINOR" version.properties | cut -d'=' -f2)
    PATCH=$(grep "PATCH" version.properties | cut -d'=' -f2)
    CODE=$(grep "CODE" version.properties | cut -d'=' -f2)
else
    MAJOR=1
    MINOR=0
    PATCH=0
    CODE=1
fi

echo "Current version is $MAJOR.$MINOR.$PATCH (Code: $CODE)"

read -p "Enter new MAJOR version [$MAJOR]: " input_major
MAJOR=${input_major:-$MAJOR}

read -p "Enter new MINOR version [$MINOR]: " input_minor
MINOR=${input_minor:-$MINOR}

# Auto-increment patch and code by default
NEXT_PATCH=$((PATCH + 1))
read -p "Enter new PATCH version [$NEXT_PATCH]: " input_patch
PATCH=${input_patch:-$NEXT_PATCH}

NEXT_CODE=$((CODE + 1))
read -p "Enter new CODE version [$NEXT_CODE]: " input_code
CODE=${input_code:-$NEXT_CODE}

read -p "Enter commit/release message [chore: automated release]: " input_msg
COMMIT_MSG=${input_msg:-"chore: automated release"}

# Update version.properties
echo "MAJOR=$MAJOR" > version.properties
echo "MINOR=$MINOR" >> version.properties
echo "PATCH=$PATCH" >> version.properties
echo "CODE=$CODE" >> version.properties

echo "Updated version.properties to $MAJOR.$MINOR.$PATCH (Code: $CODE)"

# Build the project
echo "Building APKs..."
./gradlew assembleDebug assembleRelease

# Commit any pending changes
if [ -n "$(git status --porcelain)" ]; then
    git add .
    git commit -m "$COMMIT_MSG"
    git push origin main
fi

TAG="v$MAJOR.$MINOR.$PATCH"

# Tag and push
git tag "$TAG"
git push origin "$TAG"

# Create release with both APKs
gh release create "$TAG" \
    app/build/outputs/apk/release/*.apk \
    app/build/outputs/apk/debug/app-debug.apk \
    --title "Watchify $TAG" \
    --notes "$COMMIT_MSG"
    
echo "Successfully created release: Watchify $TAG"
