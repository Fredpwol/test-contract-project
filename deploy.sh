#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  --component <backend|frontend|both>   Which component(s) to build and push (default: both)
  --region <aws-region>                  AWS region (default: env AWS_REGION or aws config)
  --account-id <id>                      AWS account ID (default: from sts get-caller-identity)
  --backend-repo <name>                  ECR repo name for backend (default: test-contract-backend)
  --frontend-repo <name>                 ECR repo name for frontend (default: test-contract-frontend)
  --backend-tag <tag>                    Image tag for backend (default: v1)
  --frontend-tag <tag>                   Image tag for frontend (default: v1)
  --backend-dockerfile <path>            Backend Dockerfile (default: backend/deploy.Dockerfile)
  --platform <platform>                  Build platform (default: linux/amd64)
  -h, --help                             Show this help

Examples:
  $(basename "$0") --component backend --backend-tag v2
  $(basename "$0") --region us-east-1 --account-id 123456789012
USAGE
}

# Defaults
COMPONENT="both"
AWS_REGION="${AWS_REGION:-}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-}"
BACKEND_REPO="test-contract-backend"
FRONTEND_REPO="test-contract-frontend"
BACKEND_TAG="v1"
FRONTEND_TAG="v1"
PLATFORM="linux/amd64"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
BACKEND_CONTEXT="$SCRIPT_DIR/backend"
FRONTEND_CONTEXT="$SCRIPT_DIR/frontend"
BACKEND_DOCKERFILE="$BACKEND_CONTEXT/deploy.Dockerfile"

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --component) COMPONENT="$2"; shift 2 ;;
    --region) AWS_REGION="$2"; shift 2 ;;
    --account-id) AWS_ACCOUNT_ID="$2"; shift 2 ;;
    --backend-repo) BACKEND_REPO="$2"; shift 2 ;;
    --frontend-repo) FRONTEND_REPO="$2"; shift 2 ;;
    --backend-tag) BACKEND_TAG="$2"; shift 2 ;;
    --frontend-tag) FRONTEND_TAG="$2"; shift 2 ;;
    --backend-dockerfile) BACKEND_DOCKERFILE="$2"; shift 2 ;;
    --platform) PLATFORM="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

# Resolve region if not provided
if [[ -z "$AWS_REGION" ]]; then
  AWS_REGION=$(aws configure get region || true)
fi
if [[ -z "$AWS_REGION" ]]; then
  echo "ERROR: AWS region not set. Use --region or export AWS_REGION." >&2
  exit 1
fi

# Resolve account ID if not provided
if [[ -z "$AWS_ACCOUNT_ID" ]]; then
  AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
fi

echo "Region: $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"
echo "Component: $COMPONENT"

# Ensure buildx
docker buildx create --use >/dev/null 2>&1 || true

# Login to ECR
aws ecr get-login-password --region "$AWS_REGION" \
| docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

ensure_repo() {
  local repo="$1"
  aws ecr describe-repositories --repository-names "$repo" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$repo" --image-scanning-configuration scanOnPush=true >/dev/null
}

build_and_push_backend() {
  ensure_repo "$BACKEND_REPO"
  local ecr="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$BACKEND_REPO:$BACKEND_TAG"
  echo "Building backend → $ecr"
  docker buildx build --platform "$PLATFORM" -t "$ecr" -f "$BACKEND_DOCKERFILE" "$BACKEND_CONTEXT" --push
  echo "Pushed backend: $ecr"
}

build_and_push_frontend() {
  ensure_repo "$FRONTEND_REPO"
  local ecr="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$FRONTEND_REPO:$FRONTEND_TAG"
  echo "Building frontend → $ecr"
  docker buildx build --platform "$PLATFORM" -t "$ecr" -f "$FRONTEND_CONTEXT/Dockerfile" "$FRONTEND_CONTEXT" --push
  echo "Pushed frontend: $ecr"
}

case "$COMPONENT" in
  backend) build_and_push_backend ;;
  frontend) build_and_push_frontend ;;
  both) build_and_push_backend; build_and_push_frontend ;;
  *) echo "Invalid --component: $COMPONENT (expected backend|frontend|both)" >&2; exit 1 ;;
esac

echo "Done."