# Running checks on your own Linux server

A check can run on this computer or on a Linux server you control, such as an Azure virtual machine. The server only needs SSH, Python 3.9 or newer and about 1 GB of free disk. Nothing here creates a server or spends money for you.

## What you set up once

1. A Linux server you can reach with an SSH key. Allow inbound SSH from your own address only.
2. A key pair for this tool. Keep the private key outside every repository.
3. Add the server to a known hosts file you name yourself, so the tool never trusts a host blindly:
   `ssh-keyscan -p 22 your-vm.example.com >> /Users/you/.ssh/upgradeguard_known_hosts`
   Check the fingerprint against the one your cloud portal shows before relying on it.
4. Copy `config/remote.example.json` somewhere private, edit it, and point the tool at it:
   `export UPGRADEGUARD_REMOTE_PROFILES=/Users/you/upgradeguard-servers.json`
   All paths in a profile must be absolute.

Servers are defined only in this file on the machine that runs the site. The web page can list them and pick one, but it can never add one or type in a host.

## Install the worker on the server (explicit, once)

```
./.venv/bin/python -m upgradeguard remote-bootstrap --server azure-demo
./.venv/bin/python -m upgradeguard remote-check --server azure-demo
```

`remote-bootstrap` copies the tool to the server and builds a Python environment there. It is never run as part of a check.

## Run a check on the server

```
./.venv/bin/python -m upgradeguard run --repo examples/demo_repo --package requests --from 2.28.2 --to 2.32.5 --runner remote --server azure-demo
```

Or choose "Server: azure-demo" in the web form.

## What happens

1. The tool checks the server (Python version, free disk).
2. It sends the project as one archive, leaving out `.git`, environments, caches and anything that looks like a secret (`.env`, keys, credentials).
3. The server builds two clean environments, runs the project's tests in both, and writes the evidence.
4. The tool downloads the evidence, refuses anything that is not a plain file, and checks it against the contract and its recorded hashes before showing it.
5. The job folder on the server is removed.

The evidence folder also holds `remote.json`: the server name, Python version and platform, as proof of where the run happened.

## What it does not do

- A separate folder and virtual environment is not a sandbox. Checks on a server run the project's own code under the server account, so use it for projects you trust, on a server that holds nothing else.
- A connection or server problem is reported as a server problem, never as an upgrade failure.
- Cancelling stops the remote process group. If the server cannot confirm it stopped, the page says so.
- Only servers that have actually been tested count as supported. See `docs` and the status notes for what has been run for real.
