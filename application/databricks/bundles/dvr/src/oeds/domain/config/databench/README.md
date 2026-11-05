# DataBench Configuration

Place DataBench configuration files and subdirectories here. During dev
pre-deploy, `deploy_databench_config` copies everything in this directory,
including this README, to `${var.databench_root}/config` in the target Volume.
Relative paths are preserved without an extra `databench` directory.

Matching destination files are overwritten; destination-only files are retained.
The destination Volume must already exist, and the deployment identity needs
write access. If the source directory is absent, the script logs a skip message
and succeeds. It does not check the destination before copying. Any copy failure
retains the CLI diagnostics, emits an Azure DevOps warning, and allows deployment
to continue. A failed copy may leave partially updated files; there is no retry
or rollback. Staging and production do not run this script by default.

This directory holds deployment assets for DataBench. Other project-owned
configuration remains under `conf/oeds/config/`.
