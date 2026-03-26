from collections.abc import Callable
from pyinfra import host
from pyinfra_docker_compose_generic.context import Context
from typing import Any


def compose_project_data(ctx: Context, key: str, default: Any = None, recursive=True):
    """Resolves host data relative to `docker_compose_generic.{compose_project_key}`."""
    data = (
        host.data.get("docker_compose_generic", {})
        .get(ctx.compose_project_key, {})
        .get(key, None)
    )

    if data is None and recursive is True:
        return host.data.get("docker_compose_generic", {}).get(key, default)

    if data is None:
        return default

    return data


def assert_config(compose_project_key: str, project_key: str):
    """Asserts that the configuration is present and valid."""
    _assert_config_exists(compose_project_key, project_key)
    _assert_config_valid(compose_project_key, project_key)


def _assert_config_exists(compose_project_key: str, project_key: str):
    """Asserts that given compose project key exists in host data. Raises an error if no configuration is present."""
    if host.data.get(project_key) is None:
        raise ValueError(f"No host data for project key '{project_key}'")

    if host.data.get(project_key).get(compose_project_key) is None:
        raise ValueError(
            f"No host data for compose project key '{compose_project_key}'"
        )


def _assert_config_valid(compose_project_key: str, project_key: str):
    """Asserts that the configuration contains required variables."""

    compose_project = host.data.get(project_key).get(compose_project_key)

    if compose_project.get("git_repo_url") is None:
        raise ValueError(
            f"Host variable `{project_key}.{compose_project_key}.git_repo_url` not found."
        )

    instances = (
        host.data.get(project_key).get(compose_project_key, {}).get("instances", {})
    )

    if len(instances) == 0:
        raise ValueError(
            f"No instances found for compose project '{compose_project_key}'."
        )


def docker_compose_generic_data(key: str, default: Any = None):
    """Resolves host data relative to `docker_compose_generic`."""

    return host.data.get("docker_compose_generic", {}).get(key, default)


def instance_data(
    ctx: Context, instance_name: str, key: str, default: Any = None, recursive=True
):
    """Resolves host data relative to `docker_compose_generic.{compose_project_key}.{instance_name}`."""

    data = (
        host.data.get("docker_compose_generic", {})
        .get(ctx.compose_project_key, {})
        .get("instances", {})
        .get(instance_name, {})
        .get(key, None)
    )

    if data is None and recursive is True:
        data = (
            host.data.get("docker_compose_generic", {})
            .get(ctx.compose_project_key, {})
            .get(key, None)
        )

    if data is None and recursive is True:
        return host.data.get("docker_compose_generic", {}).get(key, default)

    if data is None:
        return default

    return data
