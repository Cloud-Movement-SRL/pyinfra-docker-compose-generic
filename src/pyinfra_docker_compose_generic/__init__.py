from pyinfra import host
from pyinfra_docker_compose_generic.context import Context, Instance, Source
from pyinfra_docker_compose_generic.util import (
    assert_config,
    compose_project_data,
    instance_data,
)
from pyinfra.api import deploy
from pyinfra.facts.server import Home, User, Users
from typing import Callable
import os
import pprint
import pyinfra_docker_compose_generic.steps as steps


def default_build_context(compose_project_key: str, instance_context_builder: Callable):
    """Creates the runtime context based on host data.

    For the working directory, defaults to a directory named with the value of `compose_project_key` within the user's home directory.
    """
    ctx = Context()

    ctx.compose_project_key = compose_project_key

    users = host.get_fact(Users)
    home = host.get_fact(Home)
    user = host.get_fact(User)

    # Look up the user's home directory path, which is the default value used in `work_dir_base_path`.
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

    instances = []

    host_data_instances = compose_project_data(ctx, "instances")

    for instance_name in host_data_instances.keys():
        instance = instance_context_builder(ctx, instance_name)
        instances.append(instance)

    ctx.instances = instances

    return ctx


def default_build_instance_context(ctx: Context, instance_name: str):
    """Creates the runtime context for given instance based on host data."""
    users = host.get_fact(Users)
    user = host.get_fact(User)
    group = users[ctx.work_dir_user]["group"]

    instance = Instance()

    instance.instance_name = instance_name

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

    # Compute the compose override base file path if the file is coming from the compose project itself, based on the
    # (absolute) instance directory path and the (relative) compose override base file path.
    if (
        instance.compose_override_file_source is Source.COMPOSE_PROJECT
        and instance.compose_override_file_source_path is not None
    ):
        instance.compose_override_file_source_path = os.path.join(
            instance.instance_dir_path, instance.compose_override_file_source_path
        )
    elif (
        instance.compose_override_file_source is Source.LOCAL
        and instance.compose_override_file_source_path is None
    ):
        instance.compose_override_file_source_path = os.path.join(
            os.path.dirname(__file__), "templates/compose.override.yml.j2"
        )
    else:
        instance.compose_override_file_source_path = instance_data(
            ctx, instance_name, "compose_override_file_source_path"
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

    # Determine the .env base file path if the file is coming from the compose project itself, based on the (absolute)
    # instance directory path and the (relative) .env base file path.
    if (
        instance.env_base_file_source is Source.COMPOSE_PROJECT
        and instance.env_base_file_source_path is not None
    ):
        instance.env_base_file_path = os.path.join(
            instance.instance_dir_path, instance.env_base_file_source_path
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


@deploy("Deploy Docker Compose")
def deploy_docker_compose_generic(
    compose_project_key: str,
    project_key: str = "docker_compose_generic",
    context_builder=default_build_context,
    instance_context_builder=default_build_instance_context,
):
    """Deploys a Docker Compose enabled project."""

    assert_config(compose_project_key, project_key)

    ctx = context_builder(compose_project_key, instance_context_builder)

    steps.create_working_directory(ctx)
    steps.clone_git_repository(ctx)
    steps.create_instances_directory(ctx)
    steps.create_instances(ctx)
    steps.configure_instances_env(ctx)
    steps.configure_instances_compose_override(ctx)
    steps.run_instances_pull(ctx)
    steps.run_instances_up(ctx)
