import datetime

import typing as t

AOC_TZ: datetime.tzinfo

def blocker(
    quiet: bool = False,
    dt: float = 0.1,
    datefmt: t.Text | None = None,
    until: tuple[int, int] | None = None,
) -> None: ...
def get_owner(token: t.Text) -> t.Text: ...
