import pytest

from .fixtures.builders import FIXTURE_NAMES, build_bundle


@pytest.fixture(params=FIXTURE_NAMES)
def bundle(request):
    return build_bundle(request.param)
