#!/bin/bash

set -e

REPO_DIR="$(pwd)"
TARGET_DIR="/opt/wiki-js-app"

echo "Git Fetch Repository"

cd $REPO_DIR

git fetch origin
git reset --hard origin/main

echo "Syncing doc-embedding-api"

rsync -av --delete \
    $REPO_DIR/doc-embedding-api/ \
    $TARGET_DIR/doc-embedding-api/

echo "Rebuilding only doc-embedding-api service"

cd $TARGET_DIR

docker compose up -d --build doc-embedding-api

echo "Update complete"
