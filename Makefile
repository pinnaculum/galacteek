dists: sdist wheels

sdist:
	@python setup.py sdist

bdist:
	@python setup.py bdist

wheels:
	@python setup.py bdist_wheel

FORCE:
build: FORCE
	@python setup.py build

install: build
	@python setup.py install

flake:
	@flake8 galacteek

tox:
	@tox -e py37

upload: dists
	twine upload --repository-url https://upload.pypi.org/legacy/ dist/*

themes:
	@python setup.py build_ui --tasks=themes

ui:
	@python setup.py build_ui

flatpak:
	flatpak-builder --force-clean --repo=flatpak-repo build-dir \
		packaging/linux/flatpak/org.flatpak.galacteek.Galacteek.yaml
