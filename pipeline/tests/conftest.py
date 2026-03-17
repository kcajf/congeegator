import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Update golden files with current output instead of asserting",
    )


@pytest.fixture
def update_golden(request):
    return request.config.getoption("--update-golden")
