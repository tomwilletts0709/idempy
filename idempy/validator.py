from typing import Any, Callable, Generic, TypeVar

Validator = Callable[[str, Any], None]
T = TypeVar("T")


def non_empty(field: str, value: Any) -> None:
    """Raise ``ValueError`` if *value* is not a non-whitespace string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field} cannot be empty')

def min_value(n: int) -> Validator:
    """Return a validator that raises ``ValueError`` if a numeric field is below *n*."""
    def _v(field: str, value: Any) -> None:
        if value < n:
            raise ValueError(f'{field} must be greater than {n}')
    return _v

class ValidatedField(Generic[T]):
    """Descriptor that casts and validates a field on assignment.

    Combine with built-in validators (``non_empty``, ``min_value``) or any
    callable matching ``(field_name: str, value: Any) -> None``.

    Example::

        class Config:
            retries = ValidatedField(int, (min_value(0),))
            name    = ValidatedField(str, (non_empty,))
    """

    def __init__(
        self,
        cast: Callable[[Any], T],
        validators: tuple[Validator, ...] = (),
    ) -> None:
        self.cast = cast
        self.validators = validators
        self.name: str = ""
        self.storage_name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
        self.storage_name = f"_{name}"

    def __get__(self, instance: object | None, owner: type) -> Any:
        if instance is None:
            return self
        return getattr(instance, self.storage_name)

    def __set__(self, instance: object, value: Any) -> None:
        """Cast *value* and run all validators before storing."""
        casted = self.cast(value)
        for v in self.validators:
            v(self.name, casted)
        setattr(instance, self.storage_name, casted)
    

    