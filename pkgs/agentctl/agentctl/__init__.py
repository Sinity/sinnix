"""agentctl: native project jobs and preserved work history."""

__all__ = ["ProjectAdapter", "ProjectCatalog", "ProjectOperation"]


def __getattr__(name: str):
    if name in __all__:
        from . import projects

        return getattr(projects, name)
    raise AttributeError(name)
