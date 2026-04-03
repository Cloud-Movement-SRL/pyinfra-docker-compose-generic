from .config import process_operations_config
from .types import Context, Instance, Source
from .util import (
    compose_project_data,
    create_operation,
    instance_data,
)
from pyinfra import host
from pyinfra.facts.server import Home, User, Users
from types import FunctionType
import os
import pyinfra_docker_compose_generic.operations as operations


def default_context_builder(
    project_key: str, compose_project_key: str, instance_context_builder: FunctionType
):
    """Creates the runtime context based on host data."""

    ctx = Context()

    ctx.project_key = project_key
    ctx.compose_project_key = compose_project_key

    # Read user related host data for determining defaults.
    users = host.get_fact(Users)
    home = host.get_fact(Home)
    user = host.get_fact(User)

    # Determine the home directory path for `work_dir_user`.
    home_dir_path = (
        home
        if compose_project_data(ctx, "work_dir_user") is None
        else users[compose_project_data(ctx, "work_dir_user")]["home"]
    )

    # Look up the compose project's `work_dir_base_path`.
    work_dir_base_path = compose_project_data(ctx, "work_dir_base_path")

    # Determine the compose project's work dir path.
    work_dir_path_default = (
        os.path.join(home_dir_path, compose_project_key)
        if work_dir_base_path is None
        else os.path.join(work_dir_base_path, compose_project_key)
    )

    ctx.work_dir_path = compose_project_data(
        ctx, "work_dir_path", work_dir_path_default
    )

    ctx.work_dir_user = compose_project_data(ctx, "work_dir_user", user)

    # Determine the user's primary group for `work_dir_user`.
    group = users[ctx.work_dir_user]["group"]

    ctx.work_dir_group = compose_project_data(ctx, "work_dir_group", group)

    ctx.work_dir_mode = compose_project_data(ctx, "work_dir_mode")

    ctx.git_repo_dir_path = compose_project_data(
        ctx, "git_repo_dir_path", os.path.join(ctx.work_dir_path, "compose-project")
    )

    ctx.git_repo_url = compose_project_data(ctx, "git_repo_url")

    ctx.git_repo_commitish = compose_project_data(ctx, "git_repo_commitish")

    ctx.instances_dir_path = compose_project_data(
        ctx, "instances_dir_path", os.path.join(ctx.work_dir_path, "instances")
    )

    # Build instance contexts.
    instances = []

    host_data_instances = compose_project_data(ctx, "instances")

    for instance_name in host_data_instances.keys():
        instance = instance_context_builder(ctx, instance_name)
        instances.append(instance)

    ctx.instances = instances

    return ctx


def default_instance_context_builder(ctx: Context, instance_name: str):
    """Creates the runtime context for the instance identified by `instance_name`, based on host data."""

    # Read user related host data for determining defaults.
    users = host.get_fact(Users)
    user = host.get_fact(User)
    group = users[ctx.work_dir_user]["group"]

    instance = Instance()

    instance.name = instance_name

    instance.instance_dir_path = instance_data(
        ctx,
        instance_name,
        "instance_dir_path",
        os.path.join(ctx.instances_dir_path, ctx.compose_project_key),
        False,
    )

    instance.compose_override_file_source = Source(
        instance_data(
            ctx, instance_name, "compose_override_file_source", Source.LOCAL.value
        )
    )

    instance.compose_override_file_path = os.path.join(
        instance.instance_dir_path, "compose.override.yml"
    )

    instance.compose_override_file_group = instance_data(
        ctx, instance_name, "compose_override_file_group", group
    )

    instance.compose_override_file_mode = instance_data(
        ctx, instance_name, "compose_override_file_mode"
    )

    instance.compose_override_file_source_path = instance_data(
        ctx, instance_name, "compose_override_file_source_path"
    )

    # Determine the source and path for the compose override file.
    if instance.compose_override_file_source_path is not None:
        if instance.compose_override_file_source is Source.COMPOSE_PROJECT:
            # From the compose project (on the target host).
            instance.compose_override_file_source_path = os.path.join(
                instance.instance_dir_path, instance.compose_override_file_source_path
            )
        elif instance.compose_override_file_source in [Source.LOCAL, Source.REMOTE]:
            # From a path (on the control or target host, use as is).
            pass
        else:
            raise ValueError(
                f"Unknown value for compose_override_file_source: '{instance.compose_override_file_source}'."
            )
    else:
        # Use default from this module (on the control host).
        instance.compose_override_file_source_path = os.path.join(
            os.path.dirname(__file__), "templates/compose.override.yml.j2"
        )

    instance.compose_override_file_user = instance_data(
        ctx, instance_name, "compose_override_file_user", user
    )

    instance.env_base_file_source = Source(
        instance_data(
            ctx, instance_name, "env_base_file_source", Source.COMPOSE_PROJECT.value
        )
    )

    instance.env_base_file_source_path = instance_data(
        ctx, instance_name, "env_base_file_source_path"
    )

    # Determine the source and path for the .env file.
    if instance.env_base_file_source_path is not None:
        if instance.env_base_file_source is Source.COMPOSE_PROJECT:
            instance.env_base_file_path = os.path.join(
                instance.instance_dir_path, instance.env_base_file_source_path
            )
        elif instance.env_base_file_source in [Source.LOCAL, Source.REMOTE]:
            # From a path (on the control or target host, use as is).
            pass
        else:
            raise ValueError(
                f"Unknown value for env_base_file_source: '{instance.env_base_file_source}'."
            )

    instance.env_file_group = instance_data(ctx, instance_name, "env_file_group", group)

    instance.env_file_mode = instance_data(ctx, instance_name, "env_file_mode", "0640")

    instance.env_file_path = os.path.join(instance.instance_dir_path, ".env")

    instance.env_file_user = instance_data(ctx, instance_name, "env_file_user", user)

    instance.env = instance_data(ctx, instance_name, "env", {})

    instance.git_repo_commitish = instance_data(
        ctx, instance_name, "git_repo_commitish"
    )

    instance.instance_dir_group = instance_data(
        ctx, instance_name, "instance_dir_group", group
    )

    instance.instance_dir_mode = instance_data(
        ctx, instance_name, "instance_dir_mode", "0750"
    )

    instance.instance_dir_user = instance_data(
        ctx, instance_name, "instance_dir_user", user
    )

    return instance


def default_operations_builder(ctx: Context):
    """Creates a list of operations based on `ctx`."""

    operations_list = []
    operations_list.append(
        create_operation(
            ctx, operations.create_working_directory, "Create working directory"
        )
    )
    operations_list.append(
        create_operation(ctx, operations.clone_git_repository, "Clone Git repository")
    )
    operations_list.append(
        create_operation(
            ctx, operations.create_instances_directory, "Create instances directory"
        )
    )
    operations_list.extend(
        create_operation(ctx, operations.create_instance, "Create instance", True)
    )
    operations_list.extend(
        create_operation(ctx, operations.configure_instance_env, "Configure .env", True)
    )
    operations_list.extend(
        create_operation(
            ctx,
            operations.configure_instance_compose_override,
            "Configure compose.override.yml",
            True,
        )
    )
    operations_list.extend(
        create_operation(ctx, operations.run_instance_pull, "Pull images", True)
    )
    operations_list.extend(
        create_operation(ctx, operations.run_instance_up, "Start instance", True)
    )

    # process_operations_config(ctx, operations_list, project_data(ctx, "operations", {}))
    process_operations_config(
        ctx, operations_list, compose_project_data(ctx, "operations", {})
    )

    for instance in ctx.instances:
        process_operations_config(
            ctx,
            operations_list,
            instance_data(ctx, instance.name, "operations", {}, False),
            instance,
        )

    return operations_list
