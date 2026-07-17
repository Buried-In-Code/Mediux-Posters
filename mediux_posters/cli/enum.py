__all__ = ["enum_arg"]

from collections.abc import Callable
from enum import Enum


def enum_arg(enum_type: type[Enum]) -> Callable[[str], Enum]:
    def convert(value: str) -> Enum:
        value = value.lower()
        for member in enum_type:
            if member.value.lower() == value or member.name.lower() == value:
                return member
        raise ValueError(f"invalid choice: {value}")

    return convert
