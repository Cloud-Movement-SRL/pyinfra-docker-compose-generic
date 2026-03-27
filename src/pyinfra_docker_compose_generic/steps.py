from pyinfra_docker_compose_generic.context import Context, Source
from pyinfra.operations import files, git, server
import os


def _format_name(ctx: Context, message: str, instance_name: str | None = None):
    """Formats an operation's name to include the compose project key, and instance name, if given. Returns a string in
    the format of `<compose project key> | <message>` or `<compose project key> | <instance name> | <message>`.
    """
    return " | ".join(
        filter(
            lambda x: x is not None, [ctx.compose_project_key, instance_name, message]
        )
    )


def create_working_directory(ctx: Context):
    """Creates the working directory for given compose project."""

    files.directory(
        name=_format_name(ctx, "Create working directory"),
        path=ctx.work_dir_path,
        user=ctx.work_dir_user,
        group=ctx.work_dir_group,
        mode=ctx.work_dir_mode,
    )


def clone_git_repository(ctx: Context):
    """Clones the compose project's Git repository into `git_repo_dir_path`. The repo directory is created, if
    non-existent.

    Note that this does _not_ check out the configured commitish (branch, tag, ...) form `git_repo_commitish`. Checking
    out the configured commitish is part of :py:func:`create_instances`."""

    git.repo(
        name=_format_name(ctx, "Clone compose project's Git repository"),
        src=ctx.git_repo_url,
        dest=ctx.git_repo_dir_path,
        user=ctx.work_dir_user,
        group=ctx.work_dir_group,
    )


def create_instances_directory(ctx: Context):
    """Creates the instances directory."""

    files.directory(
        name=_format_name(ctx, "Create instances directory"),
        path=ctx.instances_dir_path,
        user=ctx.work_dir_user,
        group=ctx.work_dir_group,
    )


def create_instances(ctx: Context):
    """Creates the instance(s) with Git worktree. The worktree directories are created, if non-existent."""

    for instance in ctx.instances:
        # git.worktree() fails if the repository is non-existent upon execution, unless `assume_repo_exists=True` is
        # passed.
        git.worktree(
            name=_format_name(
                ctx, f"Copy Git repository files into worktree", instance.instance_name
            ),
            repo=ctx.git_repo_dir_path,
            worktree=instance.instance_dir_path,
            commitish=instance.git_repo_commitish,
            user=instance.instance_dir_user,
            group=instance.instance_dir_group,
            assume_repo_exists=True,
            pull=True,
        )

        files.directory(
            name=_format_name(
                ctx, f"Set Git worktree directory mode", instance.instance_name
            ),
            path=instance.instance_dir_path,
            user=instance.instance_dir_user,
            group=instance.instance_dir_group,
            mode=instance.instance_dir_mode,
        )

    # Fix the repository's .git/worktree ownership, which is assigned to `root:root`` because of sudo (but should be
    # `<ctx.work_dir_user>:<ctx.work_dir_group>`).
    #
    # See https://github.com/pyinfra-dev/pyinfra/issues/1626
    dotgit_dir_path = os.path.join(ctx.git_repo_dir_path, ".git", "worktrees")

    files.directory(
        name=_format_name(ctx, "Fix Git repository ownership"),
        path=dotgit_dir_path,
        user=ctx.work_dir_user,
        group=ctx.work_dir_group,
        recursive=True,
    )


def run_instances_pull(ctx: Context):
    """Prepares instances by pulling images with `docker compose pull`."""

    for instance in ctx.instances:
        server.shell(
            name=_format_name(ctx, "Pull Docker images", instance.instance_name),
            commands=[
                f"docker compose --project-directory '{instance.instance_dir_path}' pull",
            ],
        )


def run_instances_up(ctx: Context):
    """Starts instances with `docker compose up`."""

    for instance in ctx.instances:
        server.shell(
            name=_format_name(ctx, "Start instance", instance.instance_name),
            commands=[
                f"docker compose --project-directory '{instance.instance_dir_path}' up --force-recreate --detach",
            ],
        )


def configure_instances_env(ctx: Context):
    """Copies or creates the instance's `.env` files.

    An existing `.env` file is removed first. If `env_base_file_path` is configured, given file is copied into the
    instance's directory. Otherwise, an empty file is created.

    After copy or create, the `.env` file is populated with values from the instance's `env` configuration. For entries
    with `None`, the existing portion is commented out. For all other entries, the existing portion is either updated
    (if present with a different value) or added (is absent)."""

    for instance in ctx.instances:
        files.file(
            name=_format_name(
                ctx, "Remove existing dot-env file", instance.instance_name
            ),
            path=instance.env_file_path,
            present=False,
        )

        if (
            instance.env_base_file_source_path is not None
            and instance.env_base_file_source is Source.LOCAL
        ):
            files.template(
                name=_format_name(ctx, "Upload .env base file", instance.instance_name),
                src=instance.env_base_file_source_path,
                dest=instance.env_file_path,
                user=instance.env_file_user,
                group=instance.env_file_group,
                mode=instance.env_file_mode,
                instance_name=instance.instance_name,
                ctx=ctx,
            )

        # TODO: using files.copy() causes the deploy to fail on the first run, as `src` is not present yet.
        #
        # See https://github.com/pyinfra-dev/pyinfra/discussions/1629
        # files.copy(
        #     name=_format_name(
        #         ctx, "Copy dot-env base file", instance_name
        #     ),
        #     src=env_base_file_path_resolved,
        #     dest=instance_env_file_path,
        #     _if= instance.env_base_file_path is not None and instance.env_base_file_source is not Source.LOCAL.value,
        # )

        if (
            instance.env_base_file_path is not None
            and instance.env_base_file_source is not Source.LOCAL
        ):
            server.shell(
                name=_format_name(ctx, "Copy .env base file", instance.instance_name),
                commands=[
                    f"cp '{instance.env_base_file_path}' '{instance.env_file_path},'"
                ],
            )

        # Depending on whether `env_base_file_path` was set, this will either change the the previously copied file's
        # owner, or create an empty file otherwise.
        files.file(
            name=_format_name(ctx, "Touch .env file", instance.instance_name),
            path=instance.env_file_path,
            user=instance.env_file_user,
            group=instance.env_file_group,
            mode=instance.env_file_mode,
            touch=True,
        )

        for key, value in instance.env.items():
            if value is not None:
                # Handle string value (with interpolation of `instance_name`).
                if isinstance(value, str):
                    value_resolved = value.format(instance_name=instance.instance_name)
                # Handle function value (with argument `instance_name`).
                elif callable(value):
                    value_resolved = value(instance.instance_name)
                # Handle all other values (which will implicitely be converted to string).
                else:
                    value_resolved = value

                files.line(
                    name=_format_name(
                        ctx, f"Set .env parameter '{key}'", instance.instance_name
                    ),
                    path=instance.env_file_path,
                    line=f"^(?:#\s*)?{key}=.*$",
                    replace=f'{key}="{value_resolved}"',
                    ensure_newline=True,
                )
            else:
                files.line(
                    name=_format_name(
                        ctx, f"Remove .env parameter '{key}'", instance.instance_name
                    ),
                    path=instance.env_file_path,
                    line=f"^{key}=.*$",
                    present=False,
                )

        files.file(
            name=_format_name(
                ctx, "Set .env file ownership and mode", instance.instance_name
            ),
            path=instance.env_file_path,
            user=instance.env_file_user,
            group=instance.env_file_group,
            mode=instance.env_file_mode,
        )


def configure_instances_compose_override(ctx):
    """Copies or the instance's `compose.override.yml` files. Any existing compose override files are overwritten."""

    for instance in ctx.instances:
        if (
            instance.compose_override_file_source_path is not None
            and instance.compose_override_file_source is Source.LOCAL
        ):
            files.template(
                name=_format_name(
                    ctx, "Upload Docker Compose override file", instance.instance_name
                ),
                src=instance.compose_override_file_source_path,
                dest=instance.compose_override_file_path,
                user=instance.compose_override_file_user,
                group=instance.compose_override_file_group,
                mode=instance.compose_override_file_mode,
                instance_name=instance.instance_name,
                ctx=ctx,
            )

        # TODO: using files.copy() causes the deploy to fail on the first run, as `src` is not present yet.
        #
        # See https://github.com/pyinfra-dev/pyinfra/discussions/1629
        # files.copy(
        #     name=_format_name(ctx, "Copy Docker Compose override file", instance.instance_name),
        #     src=instance.compose_override_file_source_path,
        #     dest=instance.compose_override_file_path,
        #     overwrite=True,
        #     _if=instance.compose_override_file_source_path is not None and instance.compose_override_file_source is not Source.LOCAL,
        # )

        if (
            instance.compose_override_file_source_path is not None
            and instance.compose_override_file_source is not Source.LOCAL
        ):
            server.shell(
                name=_format_name(
                    ctx, "Copy Docker Compose override file", instance.instance_name
                ),
                commands=[
                    f"cp '{instance.compose_override_file_source_path}' '{instance.compose_override_file_path},'"
                ],
            )

        if (
            instance.compose_override_file_path is not None
            and instance.compose_override_file_source is not Source.LOCAL
        ):
            files.file(
                name=_format_name(
                    ctx,
                    "Set Docker Compose override file ownership and mode",
                    instance.instance_name,
                ),
                path=instance.compose_override_file_path,
                user=instance.compose_override_file_user,
                group=instance.compose_override_file_group,
                mode=instance.compose_override_file_mode,
            )
