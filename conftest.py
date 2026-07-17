"""pytest fixtures for simplified testing."""

import os
import pathlib
import socket
import stat

import pytest

# The modern AiiDA (>=2.x) pytest fixture plugin. Provides ``aiida_profile``,
# ``aiida_profile_clean``, ``aiida_localhost`` and the ``aiida_code_installed``
# code factory used below. (Replaces the removed ``aiida.manage.tests.*`` module,
# which shipped the old ``clear_database``/``aiida_local_code_factory`` fixtures.)
pytest_plugins = ["aiida.tools.pytest_fixtures"]

#: Directory holding the tiny Wannier90-like fixture files used by the mock code.
FIXTURES_DIR = pathlib.Path(__file__).parent / "tests" / "fixtures"


def _rabbitmq_available(host="127.0.0.1", port=5672, timeout=0.5):
    """Return whether a RabbitMQ broker looks reachable.

    The CalcJob/driver tests run blocking in-process and need no broker, but the
    workflow tests submit through the WorkGraph engine, which does. We probe once
    per session so that developers without RabbitMQ transparently fall back to a
    broker-less profile (those tests then self-skip), while CI — which ships a
    RabbitMQ service — gets a broker-backed profile and actually runs them.

    ``AIIDA_WANNIERJL_RABBITMQ`` overrides the probe entirely: ``1`` forces the
    broker on, any other value (e.g. ``0``) forces it off -- useful when the probe
    would false-positive on an unrelated service holding port 5672.
    """
    override = os.environ.get("AIIDA_WANNIERJL_RABBITMQ")
    if override is not None:
        return override == "1"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session", autouse=True)
def aiida_profile(aiida_config, aiida_profile_factory):
    """Session-wide AiiDA profile, broker-backed only when RabbitMQ is reachable.

    Overrides the plugin's default (broker-less) profile following aiida-workgraph's
    conftest pattern, but conditionally: with ``broker_backend='core.rabbitmq'`` when
    a broker is reachable, otherwise the plain broker-less profile.
    """
    kwargs = {}
    if _rabbitmq_available():
        kwargs["broker_backend"] = "core.rabbitmq"
    with aiida_profile_factory(aiida_config, **kwargs) as profile:
        yield profile


@pytest.fixture(scope="function", autouse=True)
def clean_profile(aiida_profile_clean):  # pylint: disable=unused-argument
    """Reset the AiiDA profile storage before every test."""


# ---------------------------------------------------------------------------- #
# Mock "julia" codes
#
# The real CalcJobs run ``julia ... driver.jl``. In CI there is no Julia, so we
# register a bash script as the code. It inspects the rendered ``driver.jl``
# (always the last command-line argument), branches on which Wannier.jl call it
# contains, and fakes the outputs a real run would leave behind (``results.json``
# plus, for generate/split, the extra files). ``seedname`` and ``outdirs`` are
# read straight out of the driver so the mock honours option overrides.
# ---------------------------------------------------------------------------- #

# The working mock. ``__FIXTURES__`` is substituted with the absolute fixtures dir.
_MOCK_SCRIPT = r"""#!/usr/bin/env bash
set -e

# The driver script is always the last argument on the command line.
for driver in "$@"; do :; done

fixtures="__FIXTURES__"
seedname=$(grep '^seedname = ' "$driver" | head -1 | grep -oE '"[^"]*"' | tr -d '"')

if grep -q 'write_nnkp_cubic' "$driver"; then
    cp "$fixtures/cubic.nnkp" cubic.nnkp
    echo '{"success": true}' > results.json
elif grep -q 'has_cubic_neighbors' "$driver"; then
    echo '{"has_cubic_neighbors": true}' > results.json
elif grep -q 'mrwf' "$driver"; then
    outdirs=$(grep '^outdirs = ' "$driver" | head -1 | grep -oE '"[^"]*"' | tr -d '"')
    json_items=""
    for d in $outdirs; do
        mkdir -p "$d"
        cp "$fixtures/aiida.amn" "$d/${seedname}.amn"
        cp "$fixtures/aiida.eig" "$d/${seedname}.eig"
        cp "$fixtures/aiida.mmn" "$d/${seedname}.mmn"
        cp "$fixtures/aiida.win" "$d/${seedname}.win"
        cp "$fixtures/aiida_split.amn" "$d/${seedname}_split.amn"
        if [ -z "$json_items" ]; then
            json_items="\"$d\""
        else
            json_items="$json_items, \"$d\""
        fi
    done
    echo "{\"outdirs\": [$json_items]}" > results.json
else
    echo "ERROR: mock julia code did not recognise the driver script" >&2
    exit 1
fi
"""

# Emits a Julia-style error and writes no results file -> exit code 310.
_MOCK_SCRIPT_BROKEN = r"""#!/usr/bin/env bash
echo "ERROR: LoadError: mock julia failure" >&2
exit 1
"""

# Exits cleanly but writes no results file -> exit code 301.
_MOCK_SCRIPT_NO_RESULTS = r"""#!/usr/bin/env bash
exit 0
"""


def _register_mock_code(aiida_code_installed, tmp_path_factory, body, name, label):
    """Write ``body`` to an executable script and register it as an InstalledCode."""
    script = tmp_path_factory.mktemp("mock_julia") / name
    script.write_text(body.replace("__FIXTURES__", str(FIXTURES_DIR)))
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return aiida_code_installed(
        label=label,
        default_calc_job_plugin="wannierjl.check_neighbors",
        filepath_executable=str(script),
    )


@pytest.fixture
def mock_julia_code(aiida_code_installed, tmp_path_factory):
    """A bash stand-in for ``julia`` that fakes each driver's outputs."""
    return _register_mock_code(aiida_code_installed, tmp_path_factory, _MOCK_SCRIPT, "julia.sh", "mock.julia")


@pytest.fixture
def mock_julia_code_broken(aiida_code_installed, tmp_path_factory):
    """A mock ``julia`` that fails with a Julia-style error (drives exit code 310)."""
    return _register_mock_code(
        aiida_code_installed, tmp_path_factory, _MOCK_SCRIPT_BROKEN, "julia_broken.sh", "mock.julia.broken"
    )


@pytest.fixture
def mock_julia_code_no_results(aiida_code_installed, tmp_path_factory):
    """A mock ``julia`` that exits cleanly without results.json (drives exit code 301)."""
    return _register_mock_code(
        aiida_code_installed,
        tmp_path_factory,
        _MOCK_SCRIPT_NO_RESULTS,
        "julia_no_results.sh",
        "mock.julia.no_results",
    )
