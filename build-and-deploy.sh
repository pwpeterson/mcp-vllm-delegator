#!/bin/bash

# vLLM Delegator MCP - Build and Deploy Script
# This script rebuilds the container image with the latest code changes

set -e  # Exit on any error

CONTAINER_NAME="vllm-delegator-mcp"
IMAGE_NAME="localhost/vllm-delegator-mcp:latest"
DOCKERFILE="Dockerfile-vllm-delegator"

echo "🚀 vLLM Delegator MCP - Build and Deploy"
echo "=========================================="

# Function to check if container exists
container_exists() {
    podman container exists "$CONTAINER_NAME" 2>/dev/null
}

# Function to check if container is running
container_running() {
    [ "$(podman container inspect "$CONTAINER_NAME" --format '{{.State.Running}}' 2>/dev/null)" = "true" ]
}

# Stop and remove existing container if it exists
if container_exists; then
    echo "📦 Stopping existing container: $CONTAINER_NAME"
    if container_running; then
        podman stop "$CONTAINER_NAME"
    fi
    echo "🗑️  Removing existing container: $CONTAINER_NAME"
    podman rm "$CONTAINER_NAME"
fi

# Remove old image to force rebuild
echo "🧹 Cleaning up old image"
podman rmi "$IMAGE_NAME" 2>/dev/null || true

# Build new image
echo "🔨 Building new image: $IMAGE_NAME"
podman build -f "$DOCKERFILE" -t "$IMAGE_NAME" .

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

echo "✅ Build completed successfully"

# Create and start new container
echo "🚀 Starting new container: $CONTAINER_NAME"
podman run -d \
    --name "$CONTAINER_NAME" \
    --network host \
    --env VLLM_API_URL="http://localhost:8002/v1/chat/completions" \
    --env VLLM_MODEL="Qwen/Qwen2.5-Coder-32B-Instruct-AWQ" \
    --env LOGGING_ON="true" \
    --env LOG_LEVEL="INFO" \
    --env LOG_FILE="/app/logs/vllm_mcp_delegator.log" \
    --volume "$(pwd)/logs:/app/logs:Z" \
    --volume "$(pwd)/context_portal:/app/context_portal:Z" \
    --volume "$(pwd)/config.yaml:/app/config.yaml:Z" \
    --restart unless-stopped \
    --memory 2g \
    --cpus 2.0 \
    "$IMAGE_NAME"

if [ $? -ne 0 ]; then
    echo "❌ Container start failed!"
    exit 1
fi

echo "✅ Container started successfully"

# Wait a moment for container to initialize
echo "⏳ Waiting for container to initialize..."
sleep 3

# Check container status
echo "📊 Container Status:"
podman ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Show recent logs
echo "📋 Recent logs:"
podman logs --tail 20 "$CONTAINER_NAME"

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📝 Useful commands:"
echo "  View logs:     podman logs -f $CONTAINER_NAME"
echo "  Stop:          podman stop $CONTAINER_NAME"
echo "  Restart:       podman restart $CONTAINER_NAME"
echo "  Shell access:  podman exec -it $CONTAINER_NAME /bin/bash"
echo "  Status:        podman ps --filter name=$CONTAINER_NAME"
echo ""
