# Test targets

test:
	pip install pytest
	pytest

helm-test:
	pip install pytest
	helm template . | kubectl apply --dry-run=client -f -
	helm test $(helm list -q)
