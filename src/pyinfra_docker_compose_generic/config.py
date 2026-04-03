from .types import Context, Instance, Operation, Position
from .util import (
    as_function,
    as_list,
    assert_function_in_operations,
    create_operation,
)
from pyinfra.api.exceptions import DeployError
from types import FunctionType
import logging


def process_operations_config(
    ctx: Context,
    operations: list[Operation],
    config: dict,
    instance: Instance = None,
):
    """Reads the operation removals and additions from `congig` and modifies argument `operations` by removing or adding
    those operations accordingly.

    If `instance` is given, the modifications happens for that instance only.

    The order is remove, then add, to allow for replacing operations."""

    try:
        process_operations_remove(operations, config, instance)
    except DeployError as deploy_error:
        # Include root cause message in error, as the nested error might not be shown to the user.
        logging.exception(deploy_error)

        raise DeployError(
            f"Failed to remove operation: {deploy_error}"
        ) from deploy_error

    try:
        process_operations_add(ctx, operations, config, instance)
    except Exception as deploy_error:
        # Include root cause message in error, as the nested error might not be shown to the user.
        logging.exception(deploy_error)

        raise DeployError(f"Failed to add operation: {deploy_error}") from deploy_error


def process_operations_remove(operations, config, instance):
    """Processes removal of operations according to `config`. If instance is given, the operation is removed for that
    instance only, otherwise the operation is removed for all instances."""
    for remove_operation_config in as_list(config.get("remove")):
        # Store list of operations to be removed to prevent concurrency issues.
        remove_by_function = as_function(remove_operation_config)
        remove_operations = []

        for operation in operations:
            if operation.function is remove_by_function:
                # If instance Toggle compose project vs. instance mode; for the latter, remove only if instance matches.
                if instance is None or operation.instance.name == instance.name:
                    remove_operations.append(operation)

        for remove_operation in remove_operations:
            operations.remove(remove_operation)


def process_operations_add(ctx, operations, config, instance):
    """Processes addition of operations according to `config`. If instance is given, the operation is added for that
    instance only, otherwise the operation is added for all instances."""
    for add_operation_config in as_list(config.get("add", [])):
        function = as_function(add_operation_config.get("operation"))
        name = add_operation_config.get("name", None)
        per_instance = add_operation_config.get("per_instance", False)
        position = Position(add_operation_config.get("position", Position.AFTER.value))
        relative_to = as_function(add_operation_config.get("relative_to", None))

        def insert_operations(
            ctx: Context,
            operations: Operation | list[Operation],
            function: FunctionType,
            name: str,
            per_instance: bool,
            index: int,
        ):
            _operations = create_operation(ctx, function, name, per_instance, instance)

            for _index, _operation in enumerate(as_list(_operations)):
                operations.insert(index + _index, _operation)

            # per_instance = instance is not None

        if relative_to is not None:
            assert_function_in_operations(operations, relative_to)
            # Determine the operation's index by comparing its function. For this, reduce list of operations to
            # functions; indexing remains the same.
            relative_to_index = [
                operation_function.function for operation_function in operations
            ].index(relative_to)

            if position is Position.BEFORE:
                insert_operations(
                    ctx, operations, function, name, per_instance, relative_to_index
                )
            else:
                insert_operations(
                    ctx,
                    operations,
                    function,
                    name,
                    per_instance,
                    relative_to_index + 1,
                )
        else:
            if position is Position.BEFORE:
                insert_operations(ctx, operations, function, name, per_instance, 0)
            else:
                insert_operations(
                    ctx,
                    operations,
                    function,
                    name,
                    per_instance,
                    len(operations) + 1,
                )
