import numbers
from typing import TYPE_CHECKING, Literal, Optional, Union

if TYPE_CHECKING:
    import numpy as np

__all__ = [
    "_Answer",
    "_AnswerTuple",
    "_Part",
]

_Answer = Optional[Union[str, numbers.Number, "np.number"]]
_AnswerTuple = tuple[_Answer, _Answer]
_Part = Literal["a", "b"]
