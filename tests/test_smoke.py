import factory_app


def test_package_imports() -> None:
    assert factory_app.__name__ == "factory_app"
