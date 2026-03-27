# pyinfra-docker-compose-generic

Provides a generic [pyinfra](https://github.com/pyinfra-dev/pyinfra) deploy for Docker Compose projects.

## Synopsis

pyinfra-docker-compose-generic allows for deployments of Docker Compose projects, i.e., projects that come with a
`compose.yml` file in their Git repository. We'll refer to them as _compose projects_ henceforth.

Upon execution, pyinfra-docker-compose-generic

- clones the compose project's Git repository onto the target host,
- copies the specified commit into a separate instance directory,
- configures the instance with `.env` and `compose.override.yml` files,
- and finally starts the instance with `docker compose up`.

Supports multiple compose projects per host, of which each may have multiple instances.

## Quick Start

For an example, see the pyinfra inventory and deploy files shown below to deploy
[Uptime Kuma](https://github.com/louislam/uptime-kuma) on host `localhost`, along with basic project setup:

```shell
# Shell: project setup

uv init pyinfra-uptime-kuma --python ">=3.10"
cd pyinfra-uptime-kuma
uv add pyinfra git+https://github.com/Cloud-Movement-SRL/pyinfra-docker-compose-generic
```

```python
# File: inventory.py

hosts = [
    (
        "@local",                           # Target host with Docker Compose
        {                                   # Host data dict
            "docker_compose_generic": {     # pyinfra-docker-compose-generic configuration
                "uptime-kuma": {            # Compose project key (arbitrary value chosen by user)
                    "git_repo_url":         # The compose project's Git URL
                    "https://github.com/louislam/uptime-kuma.git",
                    "instances": {          # Instances dict
                        "production": {},   # Instance name
                    },
                },
            },
        },
    )
]
```

```python
# File: deploy.py

from pyinfra.api import deploy
from pyinfra_docker_compose_generic import deploy_docker_compose_generic

@deploy("Deploy Uptime Kuma")
def deploy_uptime_kuma():
    # Argument matches host data's compose project key from inventory.py
    deploy_docker_compose_generic("uptime-kuma")

deploy_uptime_kuma()
```

Now deploy Uptime Kuma:

```shell
# Shell: run project

uv run pyinfra inventory.py deploy.py
```

Open [http://localhost:3001/](http://localhost:3001/) – that's it!

## Usage

To use pyinfra-docker-compose-generic in your project, add pyinfra and this GitHub repository as dependencies. We
assume [uv](https://docs.astral.sh/uv/) is used, as per pyinfra's
[recommendation](https://docs.pyinfra.com/en/3.x/install.html#using-uv-recommended):

```shell
uv add pyinfra git+https://github.com/Cloud-Movement-SRL/pyinfra-docker-compose-generic
```

Once added, `deploy_docker_compose_generic()` may be called with the compose project key which is defined in pyinfra's
host data (see [Configuration](#configuration)).

## Configuration

pyinfra-docker-compose-generic is configured through pyinfra's host data with a nested structure:

```python
hosts = [
    (
        "<hostname>",
        {
            "docker_compose_generic": {                         # Mandatory: pyinfra-docker-compose-generic configuration block
                "<compose project key>": {                      # Mandatory: compose project key
                    "git_repo_url": "...",                      # Mandatory: Git repo URL
                    "env_base_file_path": "...",                # Optional: custom .env base file path
                    "compose_override_file_path": "...",        # Optional: custom compose.override.yml file path
                    "<instance name>": {                        # Mandatory: at least one instance
                        "compose_override_file_path": "...",    # Optional: custom instance compose.override.yml file path
                        "env": {                                # Optional: dict from which the instance's .env file is populated
                            "<key>": "<value>",
                            ...
                        },
                        "env_base_file_path": "...",            # Optional: custom instance .env base file path
                        ...
                    },
                    "<instance name>": {                        # Optional: additional instances
                        ...
                    },
                },
                "<compose project key>": {                      # Optional: further compose projects
                    ...
                },
            },
        },
    )
]
```

At the host data's top level, a dict under `docker_compose_generic` holds all configuration.

Below, a config entry (`<compose project key>`) per compose project is expected. Because this module is a generic
deploy that doesn't know the compose project's name, the config key name may be set arbitrarily. However, the name
must be a valid directory name on the target host.

The name given in host data has to be passed to the deploy function as an argument, i.e. as
`deploy_docker_compose_generic("<compose project key>")`.

Each compose project config entry is expected to have a dict of instances, which allow to deploy the same compose
project with stages or to achieve a multi-tenant setup. As with compose project keys, they may be named arbitrarily,
as long as those names are valid directory names on the target host and do not clash with an existing branch name, such
as `main` or `master`.

Based on given keys, pyinfra-docker-compose-generic creates a worktree copy of the configured Git repository per
instance. By default, it resides under `/home/<ssh_user>/<compose project key>/instances/<instance name>` on the target
host.

> 🛈 Notice
>
> Directory permissions for the instance directory are set to `0750` by default. To change, supply a custom value for
> `instance_dir_mode` on compose project or instance level.

> ⚠ Warning
>
> Note that once the Docker Compose stack is started for any given instance, its services may use the instance directory
> as a working directory.
>
> The instance directory thus might also contain persistent data from binds, such as database files.
>
> **An instance directory should not be deleted without prior review.**

Every instance is configured by an individual `.env` file, which is either copied from the optional value of
`env_base_file_source_path` (by default a relative file path to the Git repository root), or created as an empty file if
no base file was specified.

Regardless of its origin, the `.env` file is populated from the optional `env` entry for given instance, which is a dict
of key-value-pairs that are converted into key-value-pairs within the `.env` file.

Entries in `env` with a value of `None` cause the entry within the `.env` file to be commented out – although this has
an effect only if `env_base_file_path` is used. If the value is a string, the string will be interpolated, with the only
variable available being `{instance_name}`. If the value is a function, the function is called with `instance_name` as
its only argument. Other types are converted to string.

When none of the above env-configurations are supplied, the `.env` file is still created but remains empty.

> 🛈 Notice
>
> File permissions for `.env` are set to `0640` by default. To change, supply a custom value for `env_file_mode` on
> compose project or instance level.

If `compose_override_file_source_path` is given (by default an absolute file path on the _control_ host), this file will
be used in place of the default `compose.override.yml` for given instance (on the _target_ host).

Any additional keys may be added to the instance for configuration of custom deploys – these are ignored by
`deploy_docker_compose_generic()`.

Assuming a compose project named `foo`, the configuration compose project key might also be set to `foo`. If using
multiple compose projects per host, more entries with arbitrary names may be added as needed, such as `bar` in the
following example:

```python
hosts = [
    (
        "example.com",
        {
            "docker_compose_generic": {
                "foo": {                                        # First compose project
                    "git_repo_url": "...",
                    "production": {                             # First instance `production` for `foo`
                        "env": {
                            "BASE_PATH": "/foo",
                            "PORT": "8080",
                        },
                    },
                    "test": {                                   # Second instance `test` for `foo`
                        "env": {
                            "BASE_PATH": "/foo-test",
                            "PORT": "8081",
                        },
                        "compose_override_file_path": "...",    # Custom compose.override.yml file for second instance of `foo`
                    },
                },
                "bar": {                                        # Second compose project
                    "git_repo_url": "...",
                    "default": {                                # First and only instance `default` for `bar`
                        "env": {
                            "DATABASE_URL": "...",
                        },
                        "env_base_file_path": ".env.example"    # Custom `.env` base file (from the compose project's repository) for `bar`
                    },
                },
            },
        },
    )
]
```

### Directory Layout

pyinfra-docker-compose-generic creates a directory layout as follows:

```plain
<work_dir_base_path>            # Defaults to the SSH user's home directory
├ <compose project key 1>
│ ├ compose-project
│ └ instances
│   ├ <instance 1>
│   │ ├ .env
│   │ └ compose.override.yml
│   ├ <instance 2>
│   │ ├ .env
│   │ └ compose.override.yml
│   ├ <instance n>
│   ...
├ <compose project key 2>
│ ├ compose-project
│ └ instances
│   ├ <instance 1>
│   │ ├ .env
│   │ └ compose.override.yml
│   ├ <instance 2>
│   │ ├ .env
│   │ └ compose.override.yml
│   ├ <instance n>
│   ...
├ <compose project key n>
...
```

With defaults, the above yields `/home/<ssh_user>/<compose project key>/compose-project` and
`/home/<ssh_user>/<compose project key>/instances/<instance name>`.

## Known Issues and Limitations

### Changing Configuration after Deployments

Deploys do not support changes of configuration that yield different instance directories, e.g. changing
`work_dir_base_path` or `<instance name>`.

Docker Compose assumes that a deployed stack's name and its directory remain the same throughout its lifetime.

Changing `<instance name>` yields a new name for the Docker Compose stack from the default `compose.override.yml`,
which would make Docker Compose see it as another deployment, creating new volumes as well.

### Instance Naming Restrictions

Due to the way pyinfra's `git.worktree()` operation is utilized, it's currently _not_ possible to give the instance a
name that exists as a branch (such as `main` or `master`).

## About

pyinfra-docker-compose-generic is written and maintained by Cloud Movement SRL. This project does not contain any
AI generated code. Licensed under MIT.
