import pytest

import theme


@pytest.mark.parametrize(
    ("percent", "expected"),
    [(0, "blue"), (69.9, "blue"), (70, "amber"), (89.9, "amber"), (90, "red"), (100, "red")],
)
def test_level_color_default_thresholds(percent, expected):
    assert theme.level_color(percent, "blue") == expected


def test_level_color_custom_thresholds():
    assert theme.level_color(79, "purple", warn=80, critical=92) == "purple"
    assert theme.level_color(80, "purple", warn=80, critical=92) == "amber"
    assert theme.level_color(92, "purple", warn=80, critical=92) == "red"


def test_soft_color_for_style_sheets():
    assert theme.DARK.soft("blue") == "rgba(91, 140, 255, 0.16)"
    assert theme.DARK.soft("blue", 0.5) == "rgba(91, 140, 255, 0.5)"


def test_both_themes_define_the_same_colors():
    assert theme.DARK.__dataclass_fields__.keys() == theme.LIGHT.__dataclass_fields__.keys()


@pytest.mark.parametrize("name", ["dark", "light"])
def test_apply_switches_the_current_theme(qapp, name):
    applied = theme.apply(qapp, name)
    assert theme.current is applied is theme.THEMES[name]
    assert applied.surface in qapp.styleSheet()
