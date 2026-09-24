def test_package_imports():
    import chorus
    assert isinstance(chorus.__version__, str)
