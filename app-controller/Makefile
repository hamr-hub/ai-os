.PHONY: install run test lint clean logs restart

# Variables
PYTHON ?= python3
PIP ?= pip3
VENV ?= .venv
HOST ?= 0.0.0.0
PORT ?= 5000

# Install dependencies
install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/$(PIP) install -r requirements.txt
	@echo "Dependencies installed successfully"

# Install dependencies (production mode)
install-prod:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/$(PIP) install --no-cache-dir -r requirements.txt
	@echo "Production dependencies installed successfully"

# Run the service
run:
	$(PYTHON) main.py

# Run with uvicorn (development)
dev:
	$(VENV)/bin/uvicorn main:app --host $(HOST) --port $(PORT) --reload --log-level debug

# Run with uvicorn (production)
prod:
	$(VENV)/bin/uvicorn main:app --host $(HOST) --port $(PORT) --workers 1 --log-level info

# Run tests
test:
	$(VENV)/bin/pytest tests/ -v

# Run single test file
test-file:
	$(VENV)/bin/pytest $(file) -v

# Run tests with coverage
test-cov:
	$(VENV)/bin/pytest tests/ --cov=. --cov-report=html

# Lint code
lint:
	$(VENV)/bin/flake8 . --exclude=$(VENV) --max-line-length=120

# Format code
format:
	$(VENV)/bin/black . --exclude=$(VENV)

# Clean up
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .coverage -delete
	find . -type d -name htmlcov -exec rm -rf {} +
	@echo "Cleaned up Python cache files"

# View logs
logs:
	tail -f logs/ai_controller.log

# Check service status
status:
	@curl -s http://localhost:$(PORT)/health | python3 -m json.tool

# Check GPU status
gpu:
	@curl -s http://localhost:$(PORT)/manage/gpu | python3 -m json.tool

# Check model status
models:
	@curl -s http://localhost:$(PORT)/manage/models | python3 -m json.tool

# Get system metrics
metrics:
	@curl -s http://localhost:$(PORT)/manage/metrics | python3 -m json.tool

# Health check
health:
	@curl -s http://localhost:$(PORT)/health | python3 -m json.tool

# Preload all models
preload-all:
	@curl -X POST http://localhost:$(PORT)/manage/preload/all

# Restart service (systemd)
restart:
	sudo systemctl restart aiclient-python

# Stop service (systemd)
stop:
	sudo systemctl stop aiclient-python

# Start service (systemd)
start:
	sudo systemctl start aiclient-python

# View systemd service logs
syslogs:
	journalctl -u aiclient-python -f

# Generate requirements lock file
freeze:
	$(VENV)/bin/pip freeze > requirements.txt
