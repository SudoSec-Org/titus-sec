PYTHON=python3
PIP=pip3

install:
	$(PIP) install -r backend/requirements.txt
	cd frontend && npm install

backend:
	$(PYTHON) -m backend.main

frontend:
	cd frontend && npm run tauri dev

run:
	concurrently "make backend" "make frontend"

test:
	$(PYTHON) -m pytest tests backend/tests

dev: install run

