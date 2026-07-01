#!/usr/bin/env bash
set -euo pipefail

required_tools=(
  tesseract
  python3
  make
  gmake
  wget
  unzip
  git
)

missing=0

echo "Checking required macOS tools..."
for tool in "${required_tools[@]}"; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf "  OK      %s (%s)\n" "$tool" "$(command -v "$tool")"
  else
    printf "  MISSING %s\n" "$tool"
    missing=1
  fi
done

if [[ "$missing" -ne 0 ]]; then
  cat <<'EOF'

Install missing tools, for example with Homebrew:

  brew install tesseract wget unzip git make

macOS already includes python3 on many systems, but if needed:

  brew install python
EOF
  exit 1
fi

echo "All required tools are available."
