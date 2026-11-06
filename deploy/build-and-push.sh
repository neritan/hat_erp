#!/usr/bin/env bash
# Build the HAT image and push it to Docker Hub.
#
#   docker login                       # once, as neritan
#   deploy/build-and-push.sh           # pushes neritan/hat:dev and neritan/hat:<git-sha>
#   deploy/build-and-push.sh prod      # pushes neritan/hat:prod and neritan/hat:<git-sha>
#
# Env overrides: IMAGE (default neritan/hat), ERPNEXT_VERSION, PLATFORM (e.g. linux/arm64)
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-neritan/hat}"
TAG="${1:-dev}"
ERPNEXT_VERSION="${ERPNEXT_VERSION:-v16.37.0}"
PLATFORM="${PLATFORM:-linux/amd64}"
SHA="$(git rev-parse --short HEAD)"

if [ -n "$(git status --porcelain)" ]; then
	echo "warning: uncommitted changes will be baked into the image (tag $SHA won't match them)" >&2
fi

docker buildx build \
	--platform "$PLATFORM" \
	--build-arg ERPNEXT_VERSION="$ERPNEXT_VERSION" \
	-t "$IMAGE:$TAG" \
	-t "$IMAGE:$SHA" \
	--push \
	.

echo "pushed $IMAGE:$TAG and $IMAGE:$SHA"
