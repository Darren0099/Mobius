"""Foreground app wins over the island, unless access is deliberate."""
from mobius.desktop_visibility import should_show, visibility_mode


def test_desktop_always_shows_small_island():
    for name in ('desktop', 'Progman', 'WorkerW', 'SHELLDLL_DefView'):
        assert should_show(name)
        assert visibility_mode(name) == 'compact'


def test_browser_and_editor_hide_even_if_panel_was_open():
    for name in ('Chrome_WidgetWin_1', 'CabinetWClass',
                 'MozillaWindowClass', 'ApplicationFrameWindow'):
        assert visibility_mode(name) == 'hidden'
        assert visibility_mode(name, panel_open=True) == 'hidden'
        assert not should_show(name, panel_open=True)


def test_only_explicit_interaction_can_show_over_browser():
    assert visibility_mode('Chrome_WidgetWin_1', own_foreground=True,
                           panel_open=True) == 'expanded'
    assert visibility_mode('Chrome_WidgetWin_1', temporary=True) == 'compact'
    assert visibility_mode('Chrome_WidgetWin_1', temporary=True,
                           panel_open=True) == 'expanded'
    assert visibility_mode('Chrome_WidgetWin_1', dragging_near_top=True) == 'compact'


def test_pointer_on_revealed_island_prevents_flicker():
    assert visibility_mode('Chrome_WidgetWin_1',
                           pointer_over_island=True) == 'compact'
    assert visibility_mode('Chrome_WidgetWin_1', pointer_over_island=True,
                           panel_open=True) == 'expanded'
    assert visibility_mode('Chrome_WidgetWin_1',
                           pointer_over_island=False) == 'hidden'


def test_optional_pin_and_no_tray_only_show_tiny_tip():
    assert visibility_mode('Chrome_WidgetWin_1', pinned=True) == 'tip'
    assert visibility_mode('Chrome_WidgetWin_1', recovery_available=False) == 'tip'
    assert should_show('Chrome_WidgetWin_1', pinned=True)
    assert not should_show('Chrome_WidgetWin_1', pinned=False)
