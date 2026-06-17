.DEFAULT_GOAL := help
PYTHON        := uv run python
UV            := uv

# ── Sources ────────────────────────────────────────────────────────────────
SRC  := src/life_simulator
TEST := tests

.PHONY: help install run test test-fast lint fmt fmt-check ci clean

# ── Help ───────────────────────────────────────────────────────────────────
help:
	@echo "Available targets:"
	@echo ""
	@echo "  install     install / sync all dependencies (including dev)"
	@echo "  run         launch the simulator"
	@echo "  test        run the test suite with full output"
	@echo "  test-fast   run the test suite quietly (short tracebacks)"
	@echo "  lint        check code with ruff (no changes)"
	@echo "  fmt         format & auto-fix code with ruff"
	@echo "  fmt-check   check formatting without modifying files (CI-safe)"
	@echo "  ci          fmt-check + test in one shot"
	@echo "  clean       remove __pycache__, .pytest_cache, build artefacts"
	@echo ""

# ── Environment ────────────────────────────────────────────────────────────
install:
	$(UV) sync --all-groups

# ── Application ────────────────────────────────────────────────────────────
run:
	$(UV) run life-sim

# ── Testing ────────────────────────────────────────────────────────────────
test:
	$(UV) run pytest -v

test-fast:
	$(UV) run pytest -q --tb=short

# ── Linting & formatting ───────────────────────────────────────────────────
lint:
	$(UV) run ruff check $(SRC) $(TEST)

fmt:
	$(UV) run ruff check --fix $(SRC) $(TEST)
	$(UV) run ruff format $(SRC) $(TEST)

fmt-check:
	$(UV) run ruff check $(SRC) $(TEST)
	$(UV) run ruff format --check $(SRC) $(TEST)

# ── CI convenience (lint + tests in one shot) ──────────────────────────────
ci: fmt-check test

# ── Cleanup ────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean."
