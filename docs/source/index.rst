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

``aiida-wannierjl`` wraps `Wannier.jl`_'s manifold-splitting (``mrwf``) method. If you use
the ``split`` calculation or the ``split_wannierization`` workflow, please cite:

.. highlights:: Junfeng Qiao, Giovanni Pizzi, and Nicola Marzari, *Automated mixing of
  maximally localized Wannier functions into target manifolds*, npj Comput. Mater. 9,
  206 (2023); https://doi.org/10.1038/s41524-023-01147-9.

  Junfeng Qiao, Giovanni Pizzi, and Nicola Marzari, *Projectability disentanglement for
  accurate and automated electronic-structure Hamiltonians*, npj Comput. Mater. 9, 208
  (2023); https://doi.org/10.1038/s41524-023-01146-w.

See ``CITATION.cff`` in the repository root for how to cite ``aiida-wannierjl`` itself.

``aiida-wannierjl`` is released under the MIT license.

Please contact edwardlinscott@gmail.com for information concerning ``aiida-wannierjl`` and the `AiiDA mailing list <http://www.aiida.net/mailing-list/>`_ for questions concerning ``aiida``.


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _AiiDA: http://www.aiida.net
.. _Wannier.jl: https://github.com/qiaojunfeng/Wannier.jl
