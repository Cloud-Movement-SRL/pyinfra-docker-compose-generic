from dataclasses import dataclass
from enum import Enum
from types import FunctionType
from typing import Any


class Source(Enum):
    """Denotes the source of a file."""

    LOCAL = "local"
    REMOTE = "remote"
    COMPOSE_PROJECT = "compose-project"


@dataclass
class Instance:
    """Holds the runtime context for an instance of a compose project deploy."""

    compose_override_file_group: str = None
    compose_override_file_mode: str = None
    compose_override_file_path: str = None
    compose_override_file_source_path: str = None
    compose_override_file_source: Source = None
    compose_override_file_user: str = None
    env_base_file_path: str = None
    env_base_file_source_path: str = None
    env_base_file_source: Source = None
    env_file_group: str = None
    env_file_mode: str = None
    env_file_path: str = None
    env_file_user: str = None
    env: dict[str, Any] = None
    git_repo_commitish: str = None
    instance_dir_group: str = None
    instance_dir_mode: str = None
    instance_dir_path: str = None
    instance_dir_user: str = None
    name: str = None


@dataclass
class Context:
    """Holds the runtime context for a compose project deploy."""

    project_key: str = None
    compose_project_key: str = None
    git_repo_commitish: str = None
    git_repo_dir_path: str = None
    git_repo_url: str = None
    instances_dir_path: str = None
    instances: list[Instance] = None
    work_dir_group: str = None
    work_dir_mode: str | int = None
    work_dir_path: str = None
    work_dir_user: str = None


@dataclass
class Operation:
    """Encapsulates the normalized configuration of an operation."""

    function: FunctionType = None
    name: str = None
    per_instance: bool = None
    instance: Instance | None = None


class Position(Enum):
    """Denotes the order for inserted operation."""

    AFTER = "after"
    BEFORE = "before"
