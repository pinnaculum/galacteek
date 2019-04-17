dists: requirements sdist wheels

requirements:
	pipenv run pipenv_to_requirements
	mv requirements.txt requirements.txt.autogen
	mv requirements-dev.txt requirements-dev.txt.autogen
	cat requirements.txt.autogen|grep -v '#'|sed -e '/^$$/d' > requirements.txt
	cat requirements-dev.txt.autogen|grep -v '#'|sed -e '/^$$/d' > requirements-dev.txt
	rm -f requirements.txt.autogen requirements-dev.txt.autogen

sdist: requirements
	pipenv run python setup.py sdist

bdist: requirements
	pipenv run python setup.py bdist

wheels: requirements
	pipenv run python setup.py bdist_wheel

FORCE:
build: FORCE
	python setup.py build

install: build
	python setup.py install

flake:
	@flake8 galacteek

upload: dists
	twine upload --repository-url https://upload.pypi.org/legacy/ dist/*
