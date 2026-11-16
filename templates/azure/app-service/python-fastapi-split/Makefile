PY ?= python3

.PHONY: install run test check

install:
	$(PY) -m pip install -r app/requirements.txt -r tests/requirements.txt

run:
	$(PY) -m uvicorn main:app --app-dir app --reload

test:
	$(PY) -m pytest tests -q

# Definition of done: architecture rules, tests, no weakened test, protected paths, change budget.
check:
	$(PY) tools/guardrail.py check
