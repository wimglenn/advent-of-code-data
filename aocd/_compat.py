from importlib.metadata import entry_points
import sys

if sys.version_info >= (3, 11):
    from typing import Self as Self # import using same name to tell the type checker we intend to export this (so other modules can import it)
else:
    from typing_extensions import Self as Self # import using same name to tell the type checker we intend to export this (so other modules can import it)

if sys.version_info >= (3, 10):
    from importlib.metadata import EntryPoints
    from typing import ParamSpec as ParamSpec # import using same name to tell the type checker we intend to export this (so other modules can import it)

    # Python 3.10+ - group/name selectable entry points
    def get_entry_points(group: str, name: str) -> EntryPoints:
        return entry_points().select(group=group, name=name)

    def get_plugins(group: str = "adventofcode.user") -> EntryPoints:
        """
        Currently installed plugins for user solves.
        """
        return entry_points(group=group)
else:
    from importlib.metadata import EntryPoint

    from typing_extensions import ParamSpec as ParamSpec # import using same name to tell the type checker we intend to export this (so other modules can import it)

    # Python 3.9 - dict interface
    def get_entry_points(group: str, name: str) -> list[EntryPoint]:
        return [ep for ep in entry_points()[group] if ep.name == name]

    def get_plugins(group: str = "adventofcode.user") -> list[EntryPoint]:
        """
        Currently installed plugins for user solves.
        """
        return entry_points().get(group, [])
