wheels:
	python -m build --wheel

release:
	twine upload dist/*

test:
	python -m unittest discover -s tests