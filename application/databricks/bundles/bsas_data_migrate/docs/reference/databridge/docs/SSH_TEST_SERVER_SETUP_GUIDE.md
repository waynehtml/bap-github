# SSH Test Server Setup Guide

This guide explains how to set up and test the local SSH/SFTP test server used by DataBridge development tooling.

The test server is intended for local Databricks cluster validation only. It is not a production SFTP service and should not be used for partner integrations.

## Tooling

The setup and smoke-test notebooks are in:

```text
application/databricks/bundles/databridge/tools/ssh/
```

Files:

- `setup.py`: creates or updates the local SSH/SFTP test server on the attached cluster.
- `test_access.py`: connects to the local SFTP server and lists the fixture directory.
- `test_download.py`: connects to the local SFTP server and downloads one fixture file.

## Fixture Volume

Fixture files are read from a Unity Catalog Volume, not from the deployed workspace bundle.

For `dev`, the fixture root is:

```text
/Volumes/dev_application_cat/oedisint_db/vol-oedisint-land/oedis/data/ssh
```

For other environments, the notebooks derive the same shape from the `env` parameter:

```text
/Volumes/<env>_application_cat/oedisint_db/vol-oedisint-land/oedis/data/ssh
```

Expected layout under the fixture root:

```text
key/id_rsa
key/id_rsa.pub
sftp/sample.txt
sftp/archive/clear/
sftp/archive/pass/
sftp/gpg/
```


## Prerequisites

Run these notebooks on a normal Databricks cluster that allows:

- `%sh` notebook cells
- Linux user creation
- writing `/etc/ssh/sshd_config`
- restarting `ssh.socket` and `ssh.service`
- reading fixture files from the configured Unity Catalog Volume path

Before running setup, manually copy the fixture `key/` and `sftp/` folders into the fixture root. This avoids Databricks workspace bundle handling for encrypted ZIP fixture files.

## Running Through OEDS-DATABRIDGE

The DataBridge job can run these notebooks by setting the `config` job parameter to a workspace notebook path.

Run setup first:

```text
config: /Workspace/oedataservices/.bundle/oedis/files/tools/ssh/setup
```

Then run the access smoke test:

```text
config: /Workspace/oedataservices/.bundle/oedis/files/tools/ssh/test_access
```

Then run the download smoke test:

```text
config: /Workspace/oedataservices/.bundle/oedis/files/tools/ssh/test_download
```

The same notebooks can also be opened and run directly in Databricks after the bundle files are deployed.

## What Setup Does

`setup.py` performs these actions on the attached cluster:

1. Creates or reuses the Linux user `test`.
2. Installs an authorized SSH public key for that user.
3. Copies the SFTP fixture files from `<fixture-root>/sftp` into the user's SFTP payload folder.
4. Generates SSH host keys if needed.
5. Replaces `/etc/ssh/sshd_config` with the test-server configuration.
6. Restarts the system SSH services.
7. Verifies that port `22` is listening.

If `<fixture-root>/key/id_rsa.pub` exists, setup installs it as the authorized key. If it does not exist, setup generates an ephemeral keypair under:

```text
/tmp/oedis-sftp-test/key
```

The volume fixture private key is for this test server only. Do not reuse it outside local test setup.

## SFTP Paths

The SSH login user is:

```text
test
```

The user's Linux home directory is:

```text
/home/test
```

The setup notebook copies SFTP fixture payloads into:

```text
/home/test/sftp
```

From an SFTP session, the test payload directory is:

```text
sftp
```

The smoke tests intentionally target this `sftp` directory instead of the login home directory. This avoids downloading home-directory files such as `.bashrc`.

## Expected Test Behavior

`test_access.py` connects to:

```text
localhost:22
```

as user `test`, then lists:

```text
sftp
```

`test_download.py` connects to the same local SFTP server, lists regular files in:

```text
sftp
```

and downloads the first regular file it finds into:

```text
/tmp/sftp_downloads
```

With the current fixtures, the default smoke download should be:

```text
sftp/sample.txt
```

saved locally as:

```text
/tmp/sftp_downloads/sample.txt
```

## Re-running

The setup is cluster-local. Re-run `setup.py` after:

- cluster restart
- cluster recreation
- changing fixture files in the volume
- changing SSH configuration in the setup notebook

The setup notebook refreshes the `test` user's `sftp` folder from the configured volume fixture root each time it runs.

## Troubleshooting

If `test_download.py` downloads a file such as `.bashrc`, the deployed test notebook is not using the current version that targets the `sftp` fixture directory. Redeploy or refresh the bundle files, then run `setup.py` and `test_download.py` again.

If the tests cannot authenticate, confirm that `setup.py` ran successfully on the same cluster before running the tests.

If the setup cannot find fixtures, confirm that the fixture folders were copied to the configured Unity Catalog Volume path and that the cluster has permission to read it.
