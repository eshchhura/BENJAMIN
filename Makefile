.PHONY: test lint run-api run-worker

test:
	python scripts/test.py

lint:
	@echo "No lint target configured yet."

run-api:
	benjamin-api

run-worker:
	benjamin-worker
