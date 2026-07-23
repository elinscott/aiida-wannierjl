# Create / update the persistent Wannier.jl project environment used by every
# aiida-wannierjl CalcJob. Run this ONCE per machine (not per calculation):
#
#     julia --startup-file=no --project=<env_dir> install_wannierjl.jl
#
# where <env_dir> is a directory that will hold the Project.toml / Manifest.toml
# for the pinned Wannier.jl + JSON stack. The same <env_dir> must later be
# exported as JULIA_PROJECT for the AiiDA Code (see helpers.get_wannierjl_code).
#
# Requires julia >= 1.11.

using Pkg

# The `url` form is used deliberately: pinning a git `rev` while resolving the
# package name through the registry is unreliable, so we point Pkg straight at
# the repository and let it check out the exact revision.
Pkg.add(url="https://github.com/qiaojunfeng/Wannier.jl.git", rev="65245c59")

# JSON.jl is a lightweight pure-Julia dependency used by the driver scripts to
# emit machine-readable results.json files.
Pkg.add("JSON")

Pkg.instantiate()
Pkg.precompile()
