from decimal import Decimal
from fractions import Fraction
from typing import Literal
from typing import Optional
from typing import TYPE_CHECKING
from typing import Union

if TYPE_CHECKING:
    import numpy as np

__all__ = [
    "_Answer",
    "_Part",
    "_LoosePart",
]

_Answer = Optional[Union[str, bytes, int, float, complex, Fraction, Decimal, "np.number[np.typing.NBitBase]"]]
_Part = Literal["a", "b"]
_LoosePart = Union[_Part, Literal[1, "1", 2, "2"]]
