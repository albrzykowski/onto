"""Helpers shared by step-definition modules."""


def quoted(group: str) -> str:
    """A Gherkin parser matching a double-quoted value into a named group."""
    return rf'"(?P<{group}>[^"]+)"'


def word(group: str) -> str:
    """A Gherkin parser matching a bare word into a named group."""
    return rf"(?P<{group}>\w+)"
