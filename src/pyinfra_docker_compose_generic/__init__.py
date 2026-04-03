from .builders import (
    default_operations_builder,
    default_instance_context_builder,
    default_context_builder,
)
from .types import (
    Context,
    Instance,
    Operation,
)
from .util import assert_config
from pyinfra.api import deploy


@deploy("Deploy Docker Compose")
def deploy_docker_compose_generic(
    compose_project_key: str,
    project_key: str = "docker_compose_generic",
    context_builder: Context = default_context_builder,
    instance_context_builder: Instance = default_instance_context_builder,
    operations_builder: list[Operation] = default_operations_builder,
):
    """Deploys a Docker Compose enabled project."""

    assert_config(compose_project_key, project_key)

    ctx = context_builder(project_key, compose_project_key, instance_context_builder)
    operations: list[Operation] = operations_builder(ctx)

    for operation in operations:
        if operation.per_instance:
            operation.function(
                ctx=ctx, instance=operation.instance, name=operation.name
            )
        else:
            operation.function(ctx=ctx, name=operation.name)
