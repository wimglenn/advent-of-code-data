import typing as t

def submit(
    answer: t.Optional[t.Union[int, str]],
    part: t.Optional[t.Literal["a", "b"]] = ...,
    day: t.Optional[int] = ...,
    year: t.Optional[int] = ...,
    session: t.Optional[str] = ...,
    reopen: bool = ...,
    quiet: bool = ...,
) -> None: ...
