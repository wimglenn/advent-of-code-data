import decimal
import fractions
import platform

import numpy as np
import pytest
from freezegun import freeze_time

from aocd.exceptions import CoercionError
from aocd.exceptions import DeadTokenError
from aocd.utils import atomic_write_file
from aocd.utils import blocker
from aocd.utils import coerce
from aocd.utils import get_owner


cpython = platform.python_implementation() == "CPython"


@pytest.mark.xfail(not cpython, reason="freezegun tick is not working on pypy")
def test_blocker(capsys):
    with freeze_time("2020-11-30 23:59:59.8-05:00", tick=True):
        # 0.2 second before unlock day 1
        blocker(dt=0.2)
    out, err = capsys.readouterr()
    assert " Unlock day 1 at " in out


def test_blocker_quiet(capsys):
    with freeze_time("2020-11-30 23:59:59.8-05:00", auto_tick_seconds=1):
        blocker(dt=0.2, quiet=True)
    out, err = capsys.readouterr()
    assert not out


def test_get_owner_not_logged_in(pook):
    pook.reset()
    pook.get("https://adventofcode.com/settings", reply=302)
    with pytest.raises(DeadTokenError):
        get_owner("not_logged_in")


def test_get_owner_user_id(pook):
    pook.reset()
    pook.get(
        "https://adventofcode.com/settings",
        response_body="<span>Link to wtf</span><code>ownerproof-123-456-9c3a0172</code>",
    )
    owner = get_owner("...")
    assert owner == "unknown.unknown.123"


def test_get_owner_and_username(pook):
    pook.reset()
    pook.get(
        "https://adventofcode.com/settings",
        response_body="<span>Link to https://www.reddit.com/u/wim</span><code>ownerproof-123-456-9c3a0172</code>",
    )
    owner = get_owner("...")
    assert owner == "reddit.wim.123"


def test_get_owner_google(pook):
    pook.reset()
    pook.get(
        "https://adventofcode.com/settings",
        response_body='<span><img src="https://lh3.googleusercontent.com/...">wim</span><code>ownerproof-1-2</code>',
    )
    owner = get_owner("...")
    assert owner == "google.wim.1"


def test_atomic_write_file(aocd_data_dir):
    target = aocd_data_dir / "foo" / "bar" / "baz.txt"
    atomic_write_file(target, "123")  # no clobber
    assert target.read_text() == "123"
    atomic_write_file(target, "456")  # clobber existing
    assert target.read_text() == "456"


@pytest.mark.parametrize(
    "v_raw, v_expected, len_logs",
    [
        ("xxx", "xxx", 0),  # str -> str
        (b"123", "123", 1),  # bytes -> str
        (123, "123", 0),  # int -> str
        (123.0, "123", 1),  # float -> str
        (123.0 + 0.0j, "123", 1),  # complex -> str
        (np.int32(123), "123", 1),  # np.int -> str
        (np.uint32(123), "123", 1),  # np.uint -> str
        (np.double(123.0), "123", 1),  # np.double -> str
        (np.complex64(123.0 + 0.0j), "123", 1),  # np.complex -> str
        (np.array([123]), "123", 1),  # 1D np.array of int -> str
        (np.array([[123.0]]), "123", 1),  # 2D np.array of float -> str
        (np.array([[[[[[123.0 + 0j]]]]]]), "123", 1),  # deep np.array of complex -> str
        (fractions.Fraction(123 * 2, 2), "123", 1),  # Fraction -> int
        (decimal.Decimal("123"), "123", 1),  # Decimal -> int
    ],
)
def test_type_coercions(v_raw, v_expected, len_logs, caplog):
    v_actual = coerce(v_raw, warn=True)
    assert v_actual == v_expected, f"{type(v_raw)} {v_raw})"
    assert len(caplog.records) == len_logs


@pytest.mark.parametrize(
    "val, error_msg",
    [
        (123.5, "Failed to coerce float value 123.5 to str"),  # non-integer float
        (123.0 + 123.0j, "Failed to coerce complex value (123+123j) to str"),  # complex w/ imag
        (np.complex64(123.0 + 0.5j), "Failed to coerce complex64 value np.complex64(123+0.5j) to str"),  # np.complex w/ imag
        (np.array([1, 2]), "Failed to coerce ndarray value array([1, 2]) to str"),  # 1D np.array with size != 1
        (np.array([[1], [2]]), "Failed to coerce ndarray value array([[1],\n       [2]]) to str"),  # 2D np.array with size != 1
        (fractions.Fraction(123, 2), "Failed to coerce Fraction value Fraction(123, 2) to str"),  # Fraction
        (decimal.Decimal("123.5"), "Failed to coerce Decimal value Decimal('123.5') to str"),  # Decimal
    ]
)
def test_type_coercions_fail(val, error_msg):
    with pytest.raises(CoercionError(error_msg)):
        coerce(val)
