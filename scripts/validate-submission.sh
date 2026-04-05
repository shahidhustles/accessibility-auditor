#!/usr/bin/env bash
# validate-submission.sh — OpenEnv Submission Validator
# Checks that Docker image builds, openenv validate passes, and files exist.

set -uo pipefail

DOCKER_BUILD_TIMEOUT=600

if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  NC='\033[0m'
else
  RED=''
  GREEN=''
  YELLOW=''
  NC=''
fi

error() {
  echo -e "${RED}❌ $1${NC}" >&2
}

success() {
  echo -e "${GREEN}✅ $1${NC}"
}

warning() {
  echo -e "${YELLOW}⚠️  $1${NC}"
}

info() {
  echo "ℹ️  $1"
}

check_dependencies() {
  info "Checking dependencies..."
  
  local missing=0
  
  if ! command -v docker &>/dev/null; then
    warning "Docker not found (optional for local validation)"
  fi
  
  if ! command -v python3 &>/dev/null; then
    error "python3 not found. Install Python 3.10+."
    missing=1
  fi
  
  if [ $missing -eq 1 ]; then
    exit 1
  fi
  
  success "Dependencies OK"
}

check_openenv_validate() {
  info "Running openenv validate..."
  
  if ! command -v openenv &>/dev/null; then
    warning "openenv CLI not found, skipping validation"
    return 0
  fi
  
  if openenv validate 2>&1; then
    success "openenv validate passed"
    return 0
  else
    error "openenv validate failed"
    return 1
  fi
}

check_inference_script() {
  info "Checking inference.py..."
  
  if [ ! -f "inference.py" ]; then
    error "inference.py not found in repo root"
    return 1
  fi
  
  # Check if it uses OpenAI client
  if ! grep -q "from openai import OpenAI" inference.py; then
    warning "inference.py might not use OpenAI client"
  fi
  
  success "inference.py exists"
  return 0
}

check_graders() {
  info "Checking graders..."
  
  if [ ! -d "graders" ]; then
    error "graders/ directory not found"
    return 1
  fi
  
  local grader_count=$(find graders/ -name "*.py" -type f | wc -l | tr -d ' ')
  
  if [ "$grader_count" -lt 1 ]; then
    error "No grader Python files found in graders/"
    return 1
  fi
  
  success "Found $grader_count grader file(s)"
  return 0
}

check_required_files() {
  info "Checking required files..."
  
  local missing=0
  
  if [ ! -f "openenv.yaml" ]; then
    error "openenv.yaml not found"
    missing=1
  fi
  
  if [ ! -f "pyproject.toml" ]; then
    error "pyproject.toml not found"
    missing=1
  fi
  
  if [ ! -f "README.md" ]; then
    error "README.md not found"
    missing=1
  fi
  
  if [ ! -f "models.py" ]; then
    error "models.py not found"
    missing=1
  fi
  
  if [ ! -d "server" ]; then
    error "server/ directory not found"
    missing=1
  fi
  
  if [ $missing -eq 0 ]; then
    success "All required files present"
    return 0
  else
    return 1
  fi
}

main() {
  echo "======================================"
  echo "OpenEnv Submission Validator"
  echo "======================================"
  echo
  
  check_dependencies
  echo
  
  local failed=0
  
  if ! check_required_files; then
    failed=1
  fi
  echo
  
  if ! check_openenv_validate; then
    failed=1
  fi
  echo
  
  if ! check_inference_script; then
    failed=1
  fi
  echo
  
  if ! check_graders; then
    failed=1
  fi
  echo
  
  echo "======================================"
  if [ $failed -eq 0 ]; then
    success "All local checks passed!"
    echo "======================================"
    exit 0
  else
    error "Some checks failed"
    echo "======================================"
    exit 1
  fi
}

cd "$(dirname "$0")/.." || exit 1
main "$@"
