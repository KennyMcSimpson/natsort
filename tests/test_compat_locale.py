"""Test the locale compatibility layer."""

from __future__ import annotations

import importlib.util
import locale
import sys
import types
from typing import TYPE_CHECKING

import pytest

import natsort.compat.locale

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def icu_locale_module() -> Iterator[types.ModuleType]:
    """Load natsort/compat/locale.py with a stub "icu" module in place."""
    saved = sys.modules.get("icu")
    sys.modules["icu"] = types.ModuleType("icu")
    spec = importlib.util.spec_from_file_location(
        "_icu_locale", natsort.compat.locale.__file__
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        if saved is None:
            del sys.modules["icu"]
        else:
            sys.modules["icu"] = saved


def test_icu_null_string_locale_max_sorts_after_any_bytes(
    icu_locale_module: types.ModuleType,
) -> None:
    # Prepended to numbers under ns.NUMAFTER | ns.LOCALE, so it must sort
    # after every sort key PyICU can return.
    assert icu_locale_module.null_string_locale_max > b"\xff" * 49
    assert icu_locale_module.null_string_locale_max > b"\xfe" * 100


@pytest.fixture
def stdlib_locale_module(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Load the standard-library backend even when PyICU is installed."""
    monkeypatch.setitem(sys.modules, "icu", None)
    spec = importlib.util.spec_from_file_location(
        "_stdlib_locale", natsort.compat.locale.__file__
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("grouping", "expected"),
    [
        ([], (3, 3)),
        ([0], (3, 3)),
        ([locale.CHAR_MAX], (3, 3)),
        ([3], (3, 3)),
        ([3, 0], (3, 3)),
        ([3, locale.CHAR_MAX], (3, 3)),
        ([3, 3, 0], (3, 3)),
        ([3, 2, 0], (3, 2)),
    ],
)
def test_get_grouping_stdlib(
    grouping: list[int],
    expected: tuple[int, int],
    stdlib_locale_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(locale, "localeconv", lambda: {"grouping": grouping})
    assert stdlib_locale_module.get_grouping() == expected


@pytest.mark.parametrize(
    ("primary", "secondary", "expected"),
    [(3, 2, (3, 2)), (3, 0, (3, 3)), (3, 3, (3, 3)), (0, 0, (3, 3))],
)
def test_get_grouping_icu(
    primary: int,
    secondary: int,
    expected: tuple[int, int],
    icu_locale_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    formatter = types.SimpleNamespace(
        getGroupingSize=lambda: primary,
        getSecondaryGroupingSize=lambda: secondary,
    )
    icu_locale_module.icu.DecimalFormat = types.SimpleNamespace
    icu_locale_module.icu.NumberFormat = types.SimpleNamespace(
        createInstance=lambda _: formatter
    )
    monkeypatch.setattr(icu_locale_module, "get_icu_locale", lambda: "en_IN")
    assert icu_locale_module.get_grouping() == expected


def test_get_grouping_icu_falls_back_for_non_decimal_format(
    icu_locale_module: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    icu_locale_module.icu.DecimalFormat = types.SimpleNamespace
    icu_locale_module.icu.NumberFormat = types.SimpleNamespace(
        createInstance=lambda _: object()
    )
    monkeypatch.setattr(icu_locale_module, "get_icu_locale", lambda: "en_IN")
    assert icu_locale_module.get_grouping() == (3, 3)
