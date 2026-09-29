"""Canonical filesystem roots for Avatar.

Every runtime component that needs config or memory must resolve through here.
Hardcoded drive letters split the policy from the provider and break portability.

Resolution order for the home directory:
1. ``AVATAR_HOME`` if set (absolute or expandable)
2. otherwise the repository root (the parent of the ``core`` package)
"""
from __future__ import annotations

import os

_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_CORE_DIR)


def avatar_home() -> str:
    override = (os.environ.get("AVATAR_HOME") or "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return _REPO_ROOT


def config_path() -> str:
    return os.path.join(avatar_home(), "config.json")


def env_path() -> str:
    return os.path.join(avatar_home(), ".env")


def memory_dir() -> str:
    return os.path.join(avatar_home(), "memory")


def sandbox_dir() -> str:
    return os.path.join(avatar_home(), "sandbox_env")


def projects_base() -> str:
    """Parent folder that lists sibling projects (GUI project picker)."""
    override = (os.environ.get("AVATAR_PROJECTS") or "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))
    parent = os.path.dirname(avatar_home())
    return parent if parent and parent != avatar_home() else avatar_home()
