The aiida-wannierjl plugin for `AiiDA`_
=====================================================

``aiida-wannierjl`` is an `AiiDA`_ plugin that wraps `Wannier.jl`_ (pinned to a fixed
revision of the ``qiaojunfeng/Wannier.jl`` fork) to manipulate Wannier functions. It
provides three CalcJobs — ``wannierjl.check_neighbors``, ``wannierjl.generate_neighbors``
and ``wannierjl.split`` — and, via the optional ``workflows`` extra, an aiida-workgraph
``split_wannierization`` graph that ties them together with a cubic ``.mmn`` regeneration
step. Each CalcJob renders a small Julia driver script and runs it against a persistent,
pinned Wannier.jl project environment.

``aiida-wannierjl`` is available at http://github.com/elinscott/aiida-wannierjl


.. toctree::
   :maxdepth: 2

   user_guide/index
   developer_guide/index
   API documentation <apidoc/aiida_wannierjl>
   AiiDA Documentation <https://aiida.readthedocs.io>

If you use AiiDA for your research, please cite the following work:

.. highlights:: Giovanni Pizzi, Andrea Cepellotti, Riccardo Sabatini, Nicola Marzari,
  and Boris Kozinsky, *AiiDA: automated interactive infrastructure and database
  for computational science*, Comp. Mat. Sci 111, 218-230 (2016);
  https://doi.org/10.1016/j.commatsci.2015.09.013; http://www.aiida.net.

``aiida-wannierjl`` is released under the MIT license.

Please contact edwardlinscott@gmail.com for information concerning ``aiida-wannierjl`` and the `AiiDA mailing list <http://www.aiida.net/mailing-list/>`_ for questions concerning ``aiida``.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _AiiDA: http://www.aiida.net
.. _Wannier.jl: https://github.com/qiaojunfeng/Wannier.jl
