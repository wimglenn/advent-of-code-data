import pkg_resources
import typing as t

def main() -> t.NoReturn: ...
def run_with_timeout(
    entry_point: pkg_resources.EntryPoint,
    timeout: float,
    progress: str | None,
    dt: float = ...,
    capture: bool = ...,
    **kwargs: t.Any,
) -> t.Tuple[str, str, float, str]: ...
def format_time(t: float, timeout: float = ...) -> str: ...
def run_one(
    year: int,
    day: int,
    input_data: t.Text,
    entry_point: pkg_resources.EntryPoint,
    timeout: float = ...,
    progress: str | None = ...,
    capture: bool = ...,
) -> t.Tuple[str, str, float, str]: ...
def run_for(
    plugins: t.Iterable[str],
    years: t.Iterable[int],
    days: t.Iterable[int],
    datasets: t.Dict[str, str],
    timeout: float = ...,
    autosubmit: bool = ...,
    reopen: bool = ...,
    capture: bool = ...,
) -> int: ...
