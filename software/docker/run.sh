#!/bin/bash
# run.sh — Launch Quartus 11.1 Docker container with GUI support
# Detects Linux, Mac Intel, or Mac Apple Silicon and configures accordingly
IMAGE="warm-tdm"
PROJECT_DIR="${1:-$(pwd)}"
REPO_ROOT=$(git -C "$(dirname "$(realpath "$0")")" rev-parse --show-toplevel)
# ---------------------------------------------------------------------------- #
#  Detect platform
# ---------------------------------------------------------------------------- #
OS=$(uname -s)
ARCH=$(uname -m)
if [ "$OS" = "Linux" ]; then
    PLATFORM="linux"
elif [ "$OS" = "Darwin" ] && [ "$ARCH" = "x86_64" ]; then
    PLATFORM="mac_intel"
elif [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
    PLATFORM="mac_silicon"
else
    echo "Unsupported platform: $OS $ARCH"
    exit 1
fi
echo "Detected platform: $PLATFORM"
echo "Using project directory: $PROJECT_DIR"
echo ""
# ---------------------------------------------------------------------------- #
#  Platform-specific X11 / display setup
# ---------------------------------------------------------------------------- #
if [ "$PLATFORM" = "linux" ]; then
    xhost +local:docker 2>/dev/null || true
    docker run --rm -it \
        -u $(id -u):$(id -g) \
        -e DISPLAY="$DISPLAY" \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v "$PROJECT_DIR":/build \
	-v ${REPO_ROOT}:/usr/local/src/warm-tdm \
        "$IMAGE" bash
elif [ "$PLATFORM" = "mac_intel" ]; then
    if ! pgrep -x Xquartz > /dev/null; then
        echo "Starting XQuartz..."
        open -a XQuartz
        sleep 2
    fi
    xhost +localhost 2>/dev/null || true
    docker run --rm -it \
        -u $(id -u):$(id -g) \
        -e DISPLAY=host.docker.internal:0 \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v "$PROJECT_DIR":/build \
	-v ${REPO_ROOT}:/usr/local/src/warm-tdm \
        "$IMAGE" bash
elif [ "$PLATFORM" = "mac_silicon" ]; then
    if ! pgrep -x Xquartz > /dev/null; then
        echo "Starting XQuartz..."
        open -a XQuartz
        sleep 2
    fi
    xhost +localhost 2>/dev/null || true
    docker run --rm -it \
        -u $(id -u):$(id -g) \
        --platform linux/amd64 \
        -e DISPLAY=host.docker.internal:0 \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        -v "$PROJECT_DIR":/build \
	-v ${REPO_ROOT}:/usr/local/src/warm-tdm \
        "$IMAGE" bash
fi
