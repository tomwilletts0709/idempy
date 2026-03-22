from pytest import fixture, pytest
from idempy.validator import ValidatedField, non_empty, min_value

@fixture
def validated_field(): 
    return VaidatedField(str, 'test', (non_empty,))

