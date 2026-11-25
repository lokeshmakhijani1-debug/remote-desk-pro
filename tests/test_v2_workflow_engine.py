import agent.workflow_engine as workflow_engine
from agent.workflow_engine import WorkflowRecorder,WorkflowReplayEngine

def test_recorder_stores_normalized_actions_but_not_typed_text(tmp_path):
    import json
    r=WorkflowRecorder(tmp_path);r.set_enabled(True)
    r.record_control({"event":"mouse_down","x":.25,"y":.75,"button":0})
    r.record_control({"event":"text_input","text":"do-not-store"})
    path=r.set_enabled(False)
    data=json.loads(path.read_text())
    assert data["steps"][0]["x"]==.25 and "text" not in data["steps"][0]
    assert data["privacy"]["typed_text_recorded"] is False

def test_replay_dry_run_is_non_destructive(tmp_path):
    import json
    p=tmp_path/"workflow_demo.json"
    p.write_text(json.dumps({"schema_version":1,"coordinate_space":"normalized_0_to_1","steps":[{"action":"mouse_down","x":.5,"y":.5}]}))
    result=WorkflowReplayEngine(tmp_path).replay(p,dry_run=True)
    assert result["dry_run"] and result["executed"]==0

def test_recorder_caps_workflow_size(tmp_path):
    import json
    r=WorkflowRecorder(tmp_path);r.set_enabled(True)
    for _ in range(10050):r.record_control({"event":"key_down","key":"a"})
    r.set_enabled(False)
    assert len(json.loads(r.last_saved.read_text())["steps"])<=10000


def test_recorder_emits_context_checkpoints(tmp_path, monkeypatch):
    contexts=[{"window_title":"Editor","process_name":"editor.exe","application":"editor","window_bounds":[0,0,1000,800]}, {"window_title":"Browser","process_name":"browser.exe","application":"browser","window_bounds":[0,0,1200,900]}]
    monkeypatch.setattr(workflow_engine,"_active_context",lambda:contexts.pop(0) if contexts else {"window_title":"Browser","process_name":"browser.exe","application":"browser","window_bounds":[0,0,1200,900]})
    r=WorkflowRecorder(tmp_path);r.set_enabled(True)
    r.record_control({"event":"key_down","key":"ctrl"})
    r.record_control({"event":"key_down","key":"l"})
    p=r.set_enabled(False)
    data=__import__("json").loads(p.read_text())
    assert any(step["action"]=="checkpoint" for step in data["steps"])
