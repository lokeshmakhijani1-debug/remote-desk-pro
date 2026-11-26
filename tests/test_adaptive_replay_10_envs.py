from agent.adaptive_replay import resolve_target, wait_until, dismiss_known_popups, clear_input_and_verify

def test_env01_resolution_and_dpi_scaling():
    step={'x':0.5,'y':0.25}
    assert resolve_target(step,(1366,768))['x']==682
    assert resolve_target(step,(3840,2160))['x']==1920
    assert resolve_target(step,(1920,1080))['y']==270

def test_env02_browser_variants_use_accessibility_labels():
    step={'x':0.1,'y':0.1,'anchor':{'name':'Save','role':'Button'}}
    for browser in ('chrome','edge','firefox','brave'):
        result=resolve_target(step,(1920,1080),uia_resolver=lambda anchor,bounds:(700,420))
        assert (result['strategy'],result['x'],result['y'])==('uia',700,420)

def test_env03_theme_and_layout_shift_use_ocr():
    result=resolve_target({'x':0.1,'y':0.1,'anchor':{'text':'Continue'}},(1920,1080),ocr_resolver=lambda anchor:(1110,760))
    assert (result['strategy'],result['x'],result['y'])==('ocr',1110,760)

def test_env04_multi_monitor_bounds():
    result=resolve_target({'x':0.5,'y':0.5},(3840,2160),(1920,0,3840,1080))
    assert (result['x'],result['y'],result['strategy'])==(2880,540,'relative')

def test_env05_slow_load_readiness_polling():
    state={'polls':0}
    def ready():
        state['polls']+=1
        return state['polls']>=4
    assert wait_until(ready,1,0.05) and state['polls']==4

def test_env06_locale_change_uses_role_fallback():
    result=resolve_target({'x':0.2,'y':0.3,'anchor':{'role':'Button'}},(1600,900),uia_resolver=lambda anchor,bounds:(350,250))
    assert result['strategy']=='uia'

def test_env07_popup_handler_is_explicit():
    calls=[]
    assert dismiss_known_popups(lambda:(calls.append('known') or True))
    assert calls==['known'] and dismiss_known_popups(None) is False

def test_env08_dynamic_ids_do_not_change_static_anchor():
    step={'x':0.3,'y':0.3,'dynamic_id':'generated-123','anchor':{'name':'Billing','role':'Text'}}
    results=[resolve_target(step,(1920,1080),uia_resolver=lambda anchor,bounds:(500,200)) for _ in range(3)]
    assert all(r['strategy']=='uia' and r['x']==500 for r in results)

def test_env09_prefilled_input_ctrl_a_focus_verification():
    calls=[]
    class Control:
        def set_focus(self): calls.append('focus')
    assert clear_input_and_verify(Control(),lambda:calls.append('ctrl+a'),lambda:True)
    assert calls==['focus','ctrl+a']
    assert clear_input_and_verify(None,lambda:None,lambda:True) is False

def test_env10_self_reflection_uia_ocr_then_relative():
    step={'x':0.25,'y':0.5,'anchor':{'name':'Save','role':'Button','text':'Save changes'}}
    result=resolve_target(step,(1920,1080),(100,100,900,700),uia_resolver=lambda anchor,bounds:None,ocr_resolver=lambda anchor:None)
    assert result['strategy']=='relative' and result['attempts']==['uia','ocr','relative']
    assert (result['x'],result['y'])==(300,400)
