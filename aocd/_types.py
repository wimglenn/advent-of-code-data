import numbers
from typing import TYPE_CHECKING, Literal, Optional, Union

if TYPE_CHECKING:
    import numpy as np

__all__ = [
    "_Answer",
    "_Part",
    "_LoosePart",
]

_Answer = Optional[Union[str, numbers.Number, "np.number"]]
_Part = Literal["a", "b"]
_LoosePart = Union[_Part, Literal[1, "1", 2, "2"]]
