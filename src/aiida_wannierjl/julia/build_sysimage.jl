# Build a PackageCompiler sysimage that bakes in Wannier + JSON so that each
# CalcJob's `julia driver.jl` pays ~0.1 s instead of the 2-10 s cost of
# `using Wannier` from scratch. AiiDA runs a fresh julia process per calculation,
# so this saving matters on every run.
#
# Run this AFTER install_wannierjl.jl, against the SAME project environment:
#
#     julia --startup-file=no --project=<env_dir> build_sysimage.jl [sysimage_path]
#
# sysimage_path defaults to <env_dir>/wannierjl.so. PackageCompiler must be
# available in the active project (helpers.setup_julia_environment adds it
# before invoking this script).
#
# CAVEAT: the sysimage bakes in the exact package versions present when it was
# built. After upgrading Wannier.jl (rerun install_wannierjl.jl) you MUST
# rebuild the sysimage, otherwise CalcJobs keep loading the stale baked-in code.

using PackageCompiler

# Default the output next to the project's Manifest.toml so the sysimage travels
# with the environment it was built against.
project_dir = dirname(Base.active_project())
sysimage_path = length(ARGS) >= 1 ? ARGS[1] : joinpath(project_dir, "wannierjl.so")

create_sysimage([:Wannier, :JSON]; sysimage_path=sysimage_path)

@info "Wrote sysimage" sysimage_path
