VERSION=`ls dist/*.tar.gz | sed "s/dist\/fret-\(.*\)\.tar\.gz/\1/g"`

test:
	pytest

build: test
	rm -rf dist/*
	python setup.py bdist_wheel sdist

.test:
	@pytest > /dev/null

.build:
	@rm -rf dist/*
	@python setup.py bdist_wheel sdist > /dev/null

release: test, build
	-twine upload dist/* && git tag "v$(VERSION)"
	git push --tags

version: .build
	@echo $(VERSION)

.PHONY: test, build, release, version, .test, .build
