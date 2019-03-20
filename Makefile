VERSION=`ls dist/*.tar.gz | sed "s/dist\/fret-\(.*\)\.tar\.gz/\1/g"`

test:
	pytest

build: test
	rm -rf dist/*
	python setup.py bdist_wheel sdist

release: test, build
	-twine upload dist/* && git tag "v$(VERSION)"
	git push && git push --tags

 .PHONY: test, build, release
