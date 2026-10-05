# CI helper targets

.PHONY: ci-test
ci-test: ## Run all CI checks (alias for 'test')
	$(MAKE) test

.PHONY: test
test: ## Run unit tests
	pytest -x -v --tb=short --timeout=120 --ignore=tests/test_hardware.py --ignore=tests/test_backend_runtime_bootstrap.py

.PHONY: lint
lint: ## Run linting checks
	flake8 . --count --show-source --statistics

.PHONY: helm-lint
helm-lint: ## Lint Helm chart
	helm lint .

.PHONY: helm-test
helm-test: ## Run Helm chart tests
	helm template . | kubectl apply --dry-run=client -f -
	helm test $(helm list -q)
