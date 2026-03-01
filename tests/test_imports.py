def test_package_imports() -> None:
    import benjamin
    import benjamin.apps.api.main
    import benjamin.core.orchestration.orchestrator

    assert benjamin is not None
