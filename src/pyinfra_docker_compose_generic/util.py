from .types import Context, Instance, Operation
from pyinfra import host
from pyinfra.api.exceptions import DeployError
from types import FunctionType
from typing import Any
import inspect
import sys


def format_name(ctx: Context, message: str, instance: Instance | None = None):
    """Formats an operation's name to include the compose project key and optionally instance name. Returns a string in
    the format of `{ctx.compose project key>} > {message}` or `{ctx.compose project} > {instance.name} > {message}`.
    """

    return " > ".join(
        filter(
            lambda item: item is not None,
            [
                ctx.compose_project_key,
                None if instance is None else instance.name,
                message,
            ],
        )
    )


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
        host.data.get(project_key).get(
            compose_project_key, {}).get("instances", {})
    )

    if len(instances) == 0:
        raise ValueError(
            f"No instances found for compose project '{compose_project_key}'."
        )


def project_data(ctx: Context, key: str, default: Any = None):
    """Resolves host data relative to `{ctx.project_key}`."""

    return host.data.get(ctx.project_key, {}).get(key, default)


def compose_project_data(ctx: Context, key: str, default: Any = None, recursive=True):
    """Resolves host data relative to `{ctx.project_key}.{ctx.compose_project_key}`."""

    data = (
        host.data.get(ctx.project_key, {})
        .get(ctx.compose_project_key, {})
        .get(key, None)
    )

    if data is None and recursive is True:
        return host.data.get(ctx.project_key, {}).get(key, default)

    if data is None:
        return default

    return data


def instance_data(
    ctx: Context, instance_name: str, key: str, default: Any = None, recursive=True
):
    """Resolves host data relative to `{ctx.project_key}.{ctx.compose_project_key}.{instance_name}`."""

    data = (
        host.data.get(ctx.project_key, {})
        .get(ctx.compose_project_key, {})
        .get("instances", {})
        .get(instance_name, {})
        .get(key, None)
    )

    if data is None and recursive is True:
        data = (
            host.data.get(ctx.project_key, {})
            .get(ctx.compose_project_key, {})
            .get(key, None)
        )

    if data is None and recursive is True:
        return host.data.get(ctx.project_key, {}).get(key, default)

    if data is None:
        return default

    return data


def as_list(item: Any | list[Any]):
    """Returns the list itself, a single item as a list or an empty list."""

    return [] if item is None else (item if isinstance(item, list) else [item])


def to_string_list(list: list[Any]):
    """Converts the list's function items to their string representations"""

    return [item.__name__ if inspect.isfunction(item) else str(item) for item in list]


def find_function(function_name: str):
    """Returns the function object for `function_name`."""

    functions: list[FunctionType] = []

    for module in sys.modules.values():
        function = getattr(module, function_name, None)

        if function is not None and inspect.isfunction(function):
            # Add function to list if not present yet.
            if not function in functions:
                functions.append(function)

    if len(functions) == 0:
        raise DeployError(f"No Function found for name '{function_name}'.")

    if len(functions) > 1:
        raise DeployError(
            f"Multiple functions found for name '{function_name}': {functions}"
        )

    return functions[0]


def as_function(obj: object):
    """Returns `obj` as is if it's a callable (i.e. a function), resolves it to the function by name otherwise."""

    return (
        None
        if obj is None
        else obj if inspect.isfunction(obj) else find_function(str(obj))
    )


def create_operation(
    ctx: Context,
    function: FunctionType,
    name: str | None = None,
    per_instance: bool = False,
    instance: Instance | None = None,
):
    """Creates operations from"""

    if instance is not None and per_instance is True:
        raise ValueError("Invalid configuration")

    if per_instance:
        operations = []

        for instance in ctx.instances:
            operation = Operation()
            operation.function = function
            operation.name = format_name(ctx, name, instance)
            operation.per_instance = True
            operation.instance = instance
            operations.append(operation)

        return operations
    else:
        operation = Operation()
        operation.function = function
        operation.name = format_name(ctx, name)
        operation.per_instance = False
        operation.instance = instance

        return operation


def assert_function_in_operations(operations: list[Operation], function: FunctionType):
    """Asserts that `operations` contains at least one operation with given `function`."""

    functions = [operation.function for operation in operations]

    if function not in functions:
        raise DeployError(
            f"Operation '{function.__name__}' not found in operations: "
            f"{[operation_function.__name__ for operation_function in functions]}."
        )
