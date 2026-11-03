from mobius.desktop_visibility import should_show

def test_desktop_visible():
    for name in ('desktop', 'Progman', 'WorkerW', 'SHELLDLL_DefView'):
        assert should_show(name)

def test_browser_hides_compact():
    assert not should_show('Chrome_WidgetWin_1')
    assert not should_show('CabinetWClass')

def test_expanded_panel_stays_visible():
    assert should_show('Chrome_WidgetWin_1', panel_open=True)
    assert should_show('Chrome_WidgetWin_1', own_foreground=True)

def test_temporary_reveal_and_recovery_fallback():
    assert should_show('Chrome_WidgetWin_1', temporary=True)
    assert should_show('Chrome_WidgetWin_1', dragging_near_top=True)
    assert should_show('Chrome_WidgetWin_1', recovery_available=False)

def test_hovered_island_remains_accessible():
    # Moving the mouse onto an already visible island must prevent flicker.
    assert should_show('Chrome_WidgetWin_1', pointer_over_island=True)
    assert not should_show('Chrome_WidgetWin_1', pointer_over_island=False)

def test_pin_mode_is_opt_in():
    assert should_show('Chrome_WidgetWin_1', pinned=True)
    assert not should_show('Chrome_WidgetWin_1', pinned=False)
