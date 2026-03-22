from pytest import fixture
from idempy.validator import VaidatedField, non_empty, min_value

@fixture
def validated_field(): 
    return VaidatedField(str, 'test', (non_empty,))

def test_validated_field(validated_field):
    assert validated_field.validate() is True

def test_validated_field_error(validated_field):
    with pytest.raises(ValueError):
        validated_field.validate()
    assert validated_field.errors == ['test cannot be empty']

def test_validated_field_min_value(validated_field):
    with pytest.raises(ValueError):
        validated_field.validate()
    assert validated_field.errors == ['test must be greater than 10']

    