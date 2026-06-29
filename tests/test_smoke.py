"""Smoke test: the package and its top-level exports import cleanly."""


def test_package_imports():
    import roscoe

    assert roscoe.__version__


def test_top_level_exports():
    from roscoe import AgentResult, AgentRunner

    assert AgentRunner is not None
    assert AgentResult is not None
