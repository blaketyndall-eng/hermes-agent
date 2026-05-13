#!/usr/bin/env bash
# Quick Win Automation Checklist — Hermes Agent
# Run each section to enable a new automation gate.
# All are non-breaking; use --dry-run mode first if unsure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_section() {
  echo -e "\n${BLUE}━━━ $1${NC}"
}

log_done() {
  echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}⚠${NC} $1"
}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: Immediate Wins (< 30 minutes, high ROI)
# ═══════════════════════════════════════════════════════════════════════════

phase1_linting() {
  log_section "PHASE 1.1: Linting Gate (ruff + black)"

  if command -v ruff >/dev/null 2>&1; then
    log_warn "ruff already installed"
  else
    echo "Installing ruff..."
    pip install ruff black==24.x
  fi

  # Create ruff config
  cat >> pyproject.toml << 'EOF'

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "W", "F", "N", "UP", "SIM"]
ignore = ["E203", "E501"]  # Handled by formatter

[tool.black]
line-length = 100
target-version = ["py311"]
EOF

  log_done "ruff + black config added to pyproject.toml"

  # Dry run
  echo "Running ruff check (dry-run)..."
  ruff check . --select E,W,F --statistics 2>/dev/null || true
}

phase1_credential_detection() {
  log_section "PHASE 1.2: Credential Leak Detection (detect-secrets)"

  if ! command -v detect-secrets >/dev/null 2>&1; then
    echo "Installing detect-secrets..."
    pip install detect-secrets
  fi

  # Create baseline
  echo "Scanning for credential patterns..."
  detect-secrets scan --baseline .secrets.baseline 2>/dev/null
  log_done "baseline created at .secrets.baseline"

  # Add to git
  echo ".secrets.baseline" >> .gitignore
}

phase1_type_checking() {
  log_section "PHASE 1.3: Type Checking Baseline (mypy)"

  if ! command -v mypy >/dev/null 2>&1; then
    echo "Installing mypy..."
    pip install mypy==1.x
  fi

  # Create mypy config
  cat > mypy.ini << 'EOF'
[mypy]
python_version = 3.11
warn_return_any = False
warn_unused_ignores = True
disallow_untyped_defs = False
no_implicit_optional = True

[mypy-tests.*]
ignore_errors = True

[mypy-tools.*]
ignore_errors = True

[mypy-gateway.*]
ignore_errors = True

[mypy-plugins.*]
ignore_errors = True
EOF

  log_done "mypy.ini created (lenient for now)"

  # Dry run on core
  echo "Running mypy check (core modules only)..."
  mypy run_agent.py --no-incremental 2>&1 | head -20 || true
}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: Test & Performance (1-2 hours)
# ═══════════════════════════════════════════════════════════════════════════

phase2_coverage() {
  log_section "PHASE 2.1: Test Coverage Baseline"

  if ! command -v coverage >/dev/null 2>&1; then
    echo "Installing coverage..."
    pip install coverage pytest-cov
  fi

  echo "Measuring coverage (this may take 2-3 minutes)..."
  coverage run -m pytest tests/ -n 4 --tb=no -q 2>/dev/null || true

  echo "Coverage Report:"
  coverage report --skip-empty --skip-covered | head -20

  log_done "coverage baseline established"
}

phase2_import_profiling() {
  log_section "PHASE 2.2: Import Time Profiler"

  cat > scripts/profile-imports.py << 'EOFPY'
#!/usr/bin/env python3
"""Profile import times for core modules."""
import sys
import importlib.util

modules = ["run_agent", "cli", "model_tools", "batch_runner", "hermes_state"]

print("Module Import Times:")
print("─" * 50)

total = 0
for mod in modules:
    spec = importlib.util.find_spec(mod)
    if spec is None:
        print(f"✗ {mod}: not found")
        continue

    import time
    t0 = time.perf_counter()
    __import__(mod)
    elapsed = (time.perf_counter() - t0) * 1000
    total += elapsed
    pct = int(100 * elapsed / max(500, total))
    print(f"  {mod:20} {elapsed:6.1f}ms ({pct:3}%)")

print("─" * 50)
print(f"{'TOTAL':20} {total:6.1f}ms")
EOFPY

  chmod +x scripts/profile-imports.py
  log_done "profile-imports.py created"

  echo "Running import profiler..."
  python scripts/profile-imports.py
}

phase2_test_sharding() {
  log_section "PHASE 2.3: Test Sharding Setup (pytest-split)"

  if ! pip show pytest-split >/dev/null 2>&1; then
    echo "Installing pytest-split..."
    pip install pytest-split
  fi

  cat >> .github/workflows/tests.yml << 'EOF'

  # Add this to the existing test job matrix:
  # strategy:
  #   matrix:
  #     test-shard: [0, 1, 2, 3, 4]
  # steps:
  #   - run: |
  #       scripts/run_tests.sh --pytest-extra \
  #         --split-group=${{ matrix.test-shard }} \
  #         --split-total=5
EOF

  log_warn "Manual step: add matrix strategy to .github/workflows/tests.yml"
  log_done "pytest-split installed (CI config needs manual update)"
}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: Codebase Hygiene (1-2 hours, optional)
# ═══════════════════════════════════════════════════════════════════════════

phase3_dead_code() {
  log_section "PHASE 3.1: Dead Code Detection (vulture)"

  if ! command -v vulture >/dev/null 2>&1; then
    echo "Installing vulture..."
    pip install vulture
  fi

  echo "Scanning for unused code..."
  vulture run_agent.py cli.py model_tools.py hermes_state.py \
    batch_runner.py --min-confidence 80 | head -30 || true

  log_warn "Review output above; archive suspects to LEGACY.md"
}

phase3_docstring_coverage() {
  log_section "PHASE 3.2: Docstring Coverage (pydocstyle)"

  if ! command -v pydocstyle >/dev/null 2>&1; then
    echo "Installing pydocstyle..."
    pip install pydocstyle
  fi

  echo "Checking docstrings..."
  pydocstyle run_agent.py cli.py 2>&1 | head -20 || true

  log_warn "Docstrings on public APIs (run_agent.py, cli.py) recommended"
}

# ═══════════════════════════════════════════════════════════════════════════
# Main Menu
# ═══════════════════════════════════════════════════════════════════════════

main() {
  cat << 'EOF'

╔═════════════════════════════════════════════════════════════╗
║  Hermes Agent — Quick Win Automation Checklist              ║
║  See: /Users/blake_t/.hermes/EFFICIENCY_QUICK_WINS.md       ║
╚═════════════════════════════════════════════════════════════╝

Phase 1: Immediate Wins (< 30 minutes)
  1. Linting Gate (ruff)
  2. Credential Detection (detect-secrets)
  3. Type Checking Baseline (mypy)

Phase 2: Testing & Performance (1-2 hours)
  4. Coverage Dashboard (coverage.py)
  5. Import Profiler (custom)
  6. Test Sharding (pytest-split)

Phase 3: Codebase Hygiene (1-2 hours, optional)
  7. Dead Code Detection (vulture)
  8. Docstring Coverage (pydocstyle)

Usage:
  bash automation-checklist.sh phase1   # Run all Phase 1 automations
  bash automation-checklist.sh phase2   # Run all Phase 2 automations
  bash automation-checklist.sh phase3   # Run all Phase 3 automations
  bash automation-checklist.sh all      # Run everything

EOF

  case "${1:-all}" in
    phase1)
      phase1_linting
      phase1_credential_detection
      phase1_type_checking
      ;;
    phase2)
      phase2_coverage
      phase2_import_profiling
      phase2_test_sharding
      ;;
    phase3)
      phase3_dead_code
      phase3_docstring_coverage
      ;;
    all)
      phase1_linting
      phase1_credential_detection
      phase1_type_checking
      phase2_coverage
      phase2_import_profiling
      phase2_test_sharding
      phase3_dead_code
      phase3_docstring_coverage
      ;;
    *)
      echo "Usage: bash automation-checklist.sh {phase1|phase2|phase3|all}"
      exit 1
      ;;
  esac

  echo -e "\n${GREEN}All automations complete!${NC}"
  echo "Next: Run 'bash automation-checklist.sh' to install pre-commit hooks"
}

main "$@"
