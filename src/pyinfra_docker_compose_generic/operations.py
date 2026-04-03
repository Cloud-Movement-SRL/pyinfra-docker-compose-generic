from .types import Context, Instance, Source
from pyinfra.api import operation
from pyinfra.operations import files, git, server
import os


@operation()
def create_working_directory(ctx: Context):
    """Creates the working directory for given compose project at `ctx.work_dir_path`."""

    yield from files.directory._inner(
        path=ctx.work_dir_path,
        user=ctx.work_dir_user,
        group=ctx.work_dir_group,
        mode=ctx.work_dir_mode,
    )


@operation()
def clone_git_repository(ctx: Context):
    """Clones the compose project's Git repository into `ctx.git_repo_dir_path`. The repository directory is created if
    non-existent.

    Note that this does _not_ check out the configured commitish (branch, tag, ...) from `ctx.git_repo_commitish`.
    Checking out the configured commitish is part of :py:func:`create_instances`."""

    yield from git.repo._inner(
        src=ctx.git_repo_url,
        dest=ctx.git_repo_dir_path,
        user=ctx.work_dir_user,
        group=ctx.work_dir_group,
    )


@operation()
def create_instances_directory(ctx: Context):
    """Creates the instances directory at `ctx.instances_dir_path`."""

    yield from files.directory._inner(
        path=ctx.instances_dir_path,
        user=ctx.work_dir_user,
        group=ctx.work_dir_group,
    )


@operation()
def create_instance(ctx: Context, instance: Instance):
    """Creates the instance's with Git worktree at `instance.instance_dir_path`. The worktree directory is created if
    non-existent."""

    # git.worktree() fails if the repository is non-existent upon execution, unless `assume_repo_exists=True` is
    # passed.
    yield from git.worktree._inner(
        repo=ctx.git_repo_dir_path,
        worktree=instance.instance_dir_path,
        commitish=instance.git_repo_commitish,
        user=instance.instance_dir_user,
        group=instance.instance_dir_group,
        assume_repo_exists=True,
        pull=True,
    )

    yield from files.directory._inner(
        path=instance.instance_dir_path,
        user=instance.instance_dir_user,
        group=instance.instance_dir_group,
        mode=instance.instance_dir_mode,
    )

    # Fix the repository's .git/worktree ownership, which is assigned to `root:root` because of sudo (but should be
    # `<ctx.work_dir_user>:<ctx.work_dir_group>`).
    #
    # See https://github.com/pyinfra-dev/pyinfra/issues/1626
    dotgit_dir_path = os.path.join(ctx.git_repo_dir_path, ".git", "worktrees")

    yield from files.directory._inner(
        path=dotgit_dir_path,
        user=ctx.work_dir_user,
        group=ctx.work_dir_group,
        recursive=True,
    )


@operation()
def configure_instance_env(ctx: Context, instance: Instance):
    """Copies or creates the instance's `.env` files.

    An existing `.env` file is removed first. If `env_base_file_path` is configured, given file is copied into the
    instance's directory. Otherwise, an empty file is created.

    After copy or create, the `.env` file is populated with values from the instance's `env` configuration. For entries
    with `None`, the existing portion is commented out. For all other entries, the existing portion is either updated
    (if present with a different value) or added (is absent).

    Values can be any type, with strings being interpolated and functions being called with `instance_name`. All other
    types are converted to their string representation."""

    # Remove the current `.env` file.
    yield from files.file._inner(
        path=instance.env_file_path,
        present=False,
    )

    # Conditionally create the `.env` file from a local template.
    if (
        instance.env_base_file_source_path is not None
        and instance.env_base_file_source is Source.LOCAL
    ):
        yield from files.template._inner(
            src=instance.env_base_file_source_path,
            dest=instance.env_file_path,
            user=instance.env_file_user,
            group=instance.env_file_group,
            mode=instance.env_file_mode,
            instance_name=instance.name,
            ctx=ctx,
        )

    # TODO: using files.copy() causes the deploy to fail on the first run, as `src` is not present yet.
    #
    # See https://github.com/pyinfra-dev/pyinfra/discussions/1629
    # files.copy(
    #     src=env_base_file_path_resolved,
    #     dest=instance_env_file_path,
    #     _if= instance.env_base_file_path is not None and instance.env_base_file_source is not Source.LOCAL.value,
    # )

    # Conditionally copy the `.env` file from a remote file.
    if (
        instance.env_base_file_path is not None
        and instance.env_base_file_source is not Source.LOCAL
    ):
        yield from server.shell._inner(
            commands=[
                f"cp '{instance.env_base_file_path}' '{instance.env_file_path},'"
            ],
        )

    # Depending on whether `env_base_file_path` was set, this will either change the previously copied file's owner,
    # or create an empty file otherwise.
    yield from files.file._inner(
        path=instance.env_file_path,
        user=instance.env_file_user,
        group=instance.env_file_group,
        mode=instance.env_file_mode,
        touch=True,
    )

    # Iterate over all `env` items to modify the `.env` file.
    for key, value in instance.env.items():
        # Determine if the value should be set or removed.
        if value is not None:
            # Handle string value (with interpolation of `instance_name`).
            if isinstance(value, str):
                value_resolved = value.format(instance_name=instance.name)
            # Handle function value (with argument `instance_name`).
            elif callable(value):
                value_resolved = value(instance.name)
            # Handle all other values (which will implicitely be converted to string).
            else:
                value_resolved = value

            # Set the variable in `.env`.
            yield from files.line._inner(
                path=instance.env_file_path,
                line=f"^(?:#\s*)?{key}=.*$",
                replace=f'{key}="{value_resolved}"',
                ensure_newline=True,
            )
        else:
            # Remove the entry in `.env`.
            yield from files.line._inner(
                path=instance.env_file_path,
                line=f"^{key}=.*$",
                present=False,
            )

    # Set ownership and permissions for the `.env` file.
    yield from files.file._inner(
        path=instance.env_file_path,
        user=instance.env_file_user,
        group=instance.env_file_group,
        mode=instance.env_file_mode,
    )


@operation()
def configure_instance_compose_override(ctx: Context, instance: Instance):
    """Copies the instance's `compose.override.yml` file. An existing compose override file is overwritten."""

    # Conditionally create the `compose.override.yml` file from a local template.
    if (
        instance.compose_override_file_source_path is not None
        and instance.compose_override_file_source is Source.LOCAL
    ):
        yield from files.template._inner(
            src=instance.compose_override_file_source_path,
            dest=instance.compose_override_file_path,
            user=instance.compose_override_file_user,
            group=instance.compose_override_file_group,
            mode=instance.compose_override_file_mode,
            instance_name=instance.name,
            ctx=ctx,
        )

    # TODO: using files.copy() causes the deploy to fail on the first run, as `src` is not present yet.
    #
    # See https://github.com/pyinfra-dev/pyinfra/discussions/1629
    # files.copy(
    #     src=instance.compose_override_file_source_path,
    #     dest=instance.compose_override_file_path,
    #     overwrite=True,
    #     _if=instance.compose_override_file_source_path is not None and instance.compose_override_file_source is not Source.LOCAL,
    # )

    # Conditionally copy the `compose.override.yml` file from a remote file.
    if (
        instance.compose_override_file_source_path is not None
        and instance.compose_override_file_source is not Source.LOCAL
    ):
        yield from server.shell._inner(
            commands=[
                f"cp '{instance.compose_override_file_source_path}' '{instance.compose_override_file_path}'"
            ],
        )

    # Set ownership and permissions for the `compose.override.yml` file.
    if (
        instance.compose_override_file_path is not None
        and instance.compose_override_file_source is not Source.LOCAL
    ):
        yield from files.file._inner(
            path=instance.compose_override_file_path,
            user=instance.compose_override_file_user,
            group=instance.compose_override_file_group,
            mode=instance.compose_override_file_mode,
        )


@operation()
def run_instance_pull(ctx: Context, instance: Instance):
    """Prepares the instance by pulling images with `docker compose pull`."""

    yield from server.shell._inner(
        commands=[
            f"docker compose --project-directory '{instance.instance_dir_path}' pull",
        ],
    )


@operation()
def run_instance_up(ctx: Context, instance: Instance):
    """Starts the instance with `docker compose up`."""

    yield from server.shell._inner(
        commands=[
            f"docker compose --project-directory '{instance.instance_dir_path}' up --force-recreate --detach",
        ],
    )
