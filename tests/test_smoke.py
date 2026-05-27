def test_python_multipart_available() -> None:
    import multipart

    assert multipart.__version__
