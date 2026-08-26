===============
Developer guide
===============

Running the tests
++++++++++++++++++

The test suite mocks the Julia code, so it runs without a real Julia
installation::

    pip install -e .[workflows]
    pytest -v

Coding style
++++++++++++

::

    pip install -e .[pre-commit]
    pre-commit install

This runs `ruff <https://docs.astral.sh/ruff/>`_ at every commit; skip a
single commit with ``git commit -n``.

Building the documentation
++++++++++++++++++++++++++

::

    pip install -e .[docs]
    cd docs
    make

Open ``build/html/index.html`` to check the result.

Continuous integration and releases
++++++++++++++++++++++++++++++++++++

`GitHub Actions <https://github.com/features/actions>`_ runs the tests,
lints, and builds the documentation on every push and pull request. Pushing
a ``vX.Y.Z`` tag publishes the package to PyPI.
