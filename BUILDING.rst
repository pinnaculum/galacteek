
Building
--------

You need to have python>=3.6,<3.8 (python 3.7 is recommended) and pip installed.

First create your virtualenv:

.. code-block:: shell

    python -m venv venvg
    source venvg/bin/activate

Install the dependencies with:

.. code-block:: shell

    pip install -r requirements-dev.txt
    pip install -r requirements.txt

To build and install the application, use:

.. code-block:: shell

    python setup.py build install

Now just run the application with:

.. code-block:: shell

    galacteek

Building the manual
-------------------

To generate the manual in HTML format:

.. code-block:: shell

    python setup.py build_docs
