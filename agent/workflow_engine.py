"""Consent-gated semantic workflows. Typed text and clipboard contents are never stored."""
from __future__ import annotations
import json, os, re, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
try:
    from adaptive_replay import resolve_target, wait_for_anchor, dismiss_known_popups, clear_input_and_verify
except ModuleNotFoundError:
    from agent.adaptive_replay import resolve_target, wait_for_anchor, dismiss_known_popups, clear_input_and_verify

_EMAIL=re.compile(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}")
MAX_STEPS=10_000

def workflow_directory()->Path:
    override=os.getenv("RDP_WORKFLOW_DIR")
    if override: return Path(override).expanduser()
    base=Path(os.getenv("APPDATA",str(Path.home())))/"RemoteDeskPro"
    return base/"workflows"

def _active_context()->dict[str,Any]:
    context={"window_title":"","process_name":"","application":"","window_bounds":None}
    if os.name!="nt": return context
    try:
        import win32gui,win32process,psutil
        hwnd=win32gui.GetForegroundWindow(); title=win32gui.GetWindowText(hwnd) or ""
        _,pid=win32process.GetWindowThreadProcessId(hwnd); name=psutil.Process(pid).name()
        bounds=win32gui.GetWindowRect(hwnd)
        context.update({"window_title":_EMAIL.sub("[redacted-email]",title[:180]),"process_name":name[:100],"application":Path(name).stem[:80],"window_bounds":[int(v) for v in bounds]})
    except Exception: pass
    return context


def _semantic_anchor_at(x: int, y: int) -> dict[str, Any]:
    """Capture nearby UIA label/role and optional OCR; never read input field values."""
    result: dict[str, Any] = {}
    if os.name == "nt":
        try:
            from pywinauto import Desktop
            candidates = []
            for window in Desktop(backend="uia").windows():
                for control in window.descendants():
                    try:
                        rect = control.rectangle()
                        if rect.left <= x <= rect.right and rect.top <= y <= rect.bottom:
                            name = str(control.window_text() or "").strip()
                            role = str(control.element_info.control_type or "").strip()
                            if name or role:
                                candidates.append((max(1,(rect.right-rect.left)*(rect.bottom-rect.top)),name,role,rect))
                    except Exception:
                        continue
            if candidates:
                _, name, role, rect = min(candidates,key=lambda item:item[0])
                if name and role.casefold() != "edit":
                    result["name"] = _EMAIL.sub("[redacted-email]",name[:100])
                if role:
                    result["role"] = role[:40]
                result["bounds"] = [int(rect.left),int(rect.top),int(rect.right),int(rect.bottom)]
        except Exception:
            pass
    # Restrict OCR to a click-adjacent crop and skip edit controls to avoid field values.
    if result.get("role","").casefold() != "edit":
        try:
            import pyautogui
            import pytesseract
            from pytesseract import Output
            left,top=max(0,x-260),max(0,y-100)
            image=pyautogui.screenshot(region=(left,top,520,200))
            data=pytesseract.image_to_data(image,output_type=Output.DICT)
            words=[]
            for i,token in enumerate(data.get("text",[])):
                token=str(token).strip()
                try: confidence=float(data["conf"][i])
                except (ValueError,TypeError): confidence=0
                if token and confidence>=55: words.append(token)
            text=_EMAIL.sub("[redacted-email]"," ".join(words))[:100]
            if text: result["text"]=text
        except Exception:
            pass
    return result


def _focused_input_state() -> dict[str, Any]:
    """Record focus/editability booleans only; never capture typed values."""
    if os.name != "nt":
        return {"focused":False,"editable":False}
    try:
        from pywinauto import Desktop
        control=Desktop(backend="uia").get_focus()
        role=str(control.element_info.control_type or "")
        return {"focused":True,"editable":role.casefold() in {"edit","document","combobox"},"role":role[:40]}
    except Exception:
        return {"focused":False,"editable":False}


class WorkflowRecorder:
    def __init__(self,root:Path|None=None)->None:
        self.root=Path(root) if root else workflow_directory(); self._lock=threading.RLock()
        self._enabled=False; self._steps:list[dict[str,Any]]=[]; self._last=0.0
        self._screen={"width":0,"height":0}; self.last_saved:Path|None=None; self._pressed_keys:set[str]=set()
    @property
    def enabled(self)->bool:
        with self._lock: return self._enabled
    def set_enabled(self,enabled:bool)->Path|None:
        with self._lock:
            if enabled and not self._enabled:
                self._steps=[]; self._pressed_keys.clear(); self._last=time.monotonic()
                try:
                    import pyautogui
                    size=pyautogui.size(); self._screen={"width":int(size.width),"height":int(size.height)}
                except Exception: self._screen={"width":0,"height":0}
                self._enabled=True; return None
            if not enabled and self._enabled:
                self._enabled=False; return self._save_locked()
            return None
    def record_control(self,message:dict[str,Any])->None:
        event=message.get("event")
        if event not in {"mouse_down","key_down","key_up","mouse_scroll"}: return
        with self._lock:
            if not self._enabled or len(self._steps)>=MAX_STEPS: return
            now=time.monotonic()
            context=_active_context()
            if self._steps and self._steps[-1].get("context")!=context and len(self._steps)<MAX_STEPS:
                self._steps.append({"action":"checkpoint","delay_ms":0,"context":context})
            step={"action":event,"delay_ms":min(30000,max(0,round((now-self._last)*1000))),"context":context}
            self._last=now
            if event=="mouse_down":
                x,y=message.get("x"),message.get("y")
                if not isinstance(x,(int,float)) or not isinstance(y,(int,float)) or not(0<=float(x)<=1 and 0<=float(y)<=1): return
                mode="screen"
                bounds=context.get("window_bounds")
                if isinstance(bounds,list) and len(bounds)==4 and self._screen["width"]>0 and self._screen["height"]>0:
                    left,top,right,bottom=bounds
                    px=float(x)*self._screen["width"]; py=float(y)*self._screen["height"]
                    if right>left and bottom>top and left<=px<=right and top<=py<=bottom:
                        x=(px-left)/(right-left); y=(py-top)/(bottom-top); mode="window"
                step.update({"x":round(float(x),6),"y":round(float(y),6),"coordinate_mode":mode,"button":{0:"left",1:"middle",2:"right"}.get(message.get("button"),"left")})
                if self._screen["width"] and self._screen["height"]:
                    anchor=_semantic_anchor_at(round(float(message.get("x",0))*self._screen["width"]),
                                               round(float(message.get("y",0))*self._screen["height"]))
                    if anchor:
                        step["anchor"]=anchor
            elif event in {"key_down","key_up"}:
                key=str(message.get("key",""))[:32]
                if not key:return
                normalized=key.casefold()
                if event=="key_down":
                    if normalized in {"ctrl","control","alt","shift","win"}:
                        self._pressed_keys.add("ctrl" if normalized=="control" else normalized)
                    elif normalized=="a" and "ctrl" in self._pressed_keys:
                        step["action"]="clear_input"
                else:
                    if normalized in {"ctrl","control","alt","shift","win"}:
                        self._pressed_keys.discard("ctrl" if normalized=="control" else normalized)
                # Printable keys are deliberately not persisted; Ctrl+A becomes a safe clear action.
                if len(key)>1 or normalized in {"ctrl","control","alt","shift","win"}:
                    step["key"]=key
                step["input_state"]=_focused_input_state()
            else:
                dx,dy=message.get("deltaX",0),message.get("deltaY",0)
                if not isinstance(dx,(int,float)) or not isinstance(dy,(int,float)):return
                step.update({"delta_x":max(-2400,min(2400,float(dx))),"delta_y":max(-2400,min(2400,float(dy)))})
                if isinstance(message.get("x"),(int,float)) and isinstance(message.get("y"),(int,float)):
                    step.update({"x":max(0.0,min(1.0,float(message["x"]))),"y":max(0.0,min(1.0,float(message["y"])))})
            self._steps.append(step)
    def _save_locked(self)->Path|None:
        if not self._steps:return None
        self.root.mkdir(parents=True,exist_ok=True); stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target=self.root/f"workflow_{stamp}.json"
        payload={"schema_version":1,"created_at":datetime.now(timezone.utc).isoformat(),"coordinate_space":"normalized_0_to_1","recorded_screen":self._screen,"step_count":len(self._steps),"steps":self._steps,"name":"Untitled workflow","tags":[],"notes":"","is_public":False,"privacy":{"typed_text_recorded":False,"clipboard_recorded":False,"local_only":True}}
        temporary=target.with_suffix(".json.tmp"); temporary.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
        os.replace(temporary,target); self.last_saved=target; self._steps=[]; return target

class WorkflowReplayEngine:
    def __init__(self,root:Path|None=None)->None:self.root=Path(root) if root else workflow_directory()
    def latest(self)->Path|None:
        files=sorted(self.root.glob("workflow_*.json"),key=lambda p:p.stat().st_mtime,reverse=True)
        return files[0] if files else None
    @staticmethod
    def _focus_process(name:str):
        if os.name!="nt" or not name:return None
        try:
            import psutil,win32gui,win32process,win32con
            matches=[]
            def visit(hwnd:int,_:Any)->bool:
                if not win32gui.IsWindowVisible(hwnd):return True
                _,pid=win32process.GetWindowThreadProcessId(hwnd)
                try:
                    if psutil.Process(pid).name().casefold()==name.casefold():matches.append(hwnd)
                except Exception:pass
                return True
            win32gui.EnumWindows(visit,None)
            if matches:
                win32gui.ShowWindow(matches[0],win32con.SW_RESTORE);win32gui.SetForegroundWindow(matches[0]);return tuple(win32gui.GetWindowRect(matches[0]))
        except Exception:pass
        return None
    def replay(self,path:Path|None=None,*,dry_run:bool=False,
               popup_handler=None,readiness_waiter=None,uia_resolver=None,ocr_resolver=None)->dict[str,Any]:
        target=Path(path) if path else self.latest()
        if target is None or not target.is_file():
            raise FileNotFoundError("No saved workflow was found.")
        data=json.loads(target.read_text(encoding="utf-8"))
        if data.get("schema_version")!=1 or data.get("coordinate_space")!="normalized_0_to_1":
            raise ValueError("Unsupported workflow schema.")
        steps=data.get("steps")
        if not isinstance(steps,list) or len(steps)>MAX_STEPS:
            raise ValueError("Workflow step count is invalid.")
        if dry_run:
            return {"steps":len(steps),"executed":0,"dry_run":True,"warnings":[],"adaptations":[]}
        import pyautogui
        pyautogui.FAILSAFE=True
        width,height=pyautogui.size()
        executed=0
        warnings=[]
        adaptations=[]
        popup_events=0
        for index,step in enumerate(steps):
            if not isinstance(step,dict):
                continue
            if step.get("wait_for"):
                waiter=readiness_waiter or wait_for_anchor
                if not waiter(step["wait_for"],float(step.get("wait_timeout_seconds",15))):
                    warnings.append(f"Readiness condition timed out at step {index+1}")
                    continue
            else:
                time.sleep(max(0,min(30000,int(step.get("delay_ms",0))))/1000)
            if dismiss_known_popups(popup_handler):
                popup_events+=1
            context=step.get("context") if isinstance(step.get("context"),dict) else {}
            process=str(context.get("process_name",""))[:100]
            bounds=self._focus_process(process) if process else None
            if process and bounds is None:
                warning=f"Target application not found: {process}"
                if warning not in warnings:
                    warnings.append(warning)
            action=step.get("action")
            if action=="checkpoint":
                executed+=1
                continue
            if action=="mouse_down":
                resolved=resolve_target(step,(width,height),bounds,uia_resolver=uia_resolver,ocr_resolver=ocr_resolver)
                pyautogui.click(resolved["x"],resolved["y"],button=step.get("button","left"))
                adaptations.append({"step":index+1,"strategy":resolved["strategy"],"attempts":resolved["attempts"]})
            elif action=="clear_input":
                resolved=resolve_target(step,(width,height),bounds,uia_resolver=uia_resolver,ocr_resolver=ocr_resolver)
                pyautogui.click(resolved["x"],resolved["y"])
                focused=clear_input_and_verify(None,lambda: pyautogui.hotkey("ctrl","a"))
                if not focused:
                    warnings.append(f"Input focus could not be verified at step {index+1}")
                adaptations.append({"step":index+1,"strategy":resolved["strategy"],"input_focus_verified":focused})
            elif action in {"key_down","key_up"}:
                key=str(step.get("key",""))[:32]
                allowed=set(getattr(pyautogui,"KEYBOARD_KEYS",()))
                if key and (len(key)==1 or key in allowed):
                    (pyautogui.keyDown if action=="key_down" else pyautogui.keyUp)(key)
            elif action=="mouse_scroll":
                if "x" in step and "y" in step:
                    resolved=resolve_target(step,(width,height),bounds,uia_resolver=uia_resolver,ocr_resolver=ocr_resolver)
                    pyautogui.moveTo(resolved["x"],resolved["y"])
                    adaptations.append({"step":index+1,"strategy":resolved["strategy"],"attempts":resolved["attempts"]})
                dx=float(step.get("delta_x",0))
                dy=float(step.get("delta_y",0))
                if dy:
                    pyautogui.scroll(int(dy/120))
                if dx and os.name=="nt":
                    import ctypes
                    ctypes.windll.user32.mouse_event(0x01000,0,0,ctypes.c_ulong(int(dx)).value,0)
            executed+=1
        return {"steps":len(steps),"executed":executed,"dry_run":False,"warnings":warnings,
                "adaptations":adaptations,"popup_events_handled":popup_events}


def annotate_workflow(path: Path, name: str, tags: list[str] | None = None, notes: str = "") -> Path:
    """Name and annotate a locally saved workflow without publishing or uploading it."""
    root = workflow_directory().resolve()
    target = Path(path).expanduser().resolve()
    if target.parent != root or target.suffix.lower() != ".json" or not target.is_file():
        raise ValueError("Workflow must be an existing file in the local workflow directory.")
    clean_name = " ".join(str(name).split())[:80]
    if not clean_name:
        raise ValueError("Workflow name is required.")
    clean_tags = []
    for tag in tags or []:
        value = " ".join(str(tag).split())[:32]
        if value and value.casefold() not in {item.casefold() for item in clean_tags}:
            clean_tags.append(value)
        if len(clean_tags) == 12:
            break
    clean_notes = str(notes or "").strip()[:1200]
    data = json.loads(target.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("steps"), list):
        raise ValueError("Unsupported workflow document.")
    data.update({"name": clean_name, "tags": clean_tags, "notes": clean_notes,
                 "is_public": False, "updated_at": datetime.now(timezone.utc).isoformat()})
    safe_stem = re.sub(r"[^0-9A-Za-z_-]+", "-", clean_name).strip("-_").lower()[:48] or "workflow"
    destination = root / f"{safe_stem}_{target.stem.rsplit('_', 1)[-1]}.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, destination)
    if target != destination:
        target.unlink(missing_ok=True)
    return destination


def list_workflows(root: Path | None = None) -> list[Path]:
    """Return local workflow history, newest first; community workflows are not included."""
    directory = Path(root) if root else workflow_directory()
    if not directory.exists():
        return []
    return sorted((p for p in directory.glob("*.json") if p.is_file()),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def convert_session_recording_to_workflow(filename: str, recordings_folder: Path | None = None,
                                          workflow_root: Path | None = None,
                                          name: str | None = None) -> Path:
    """Convert an MP4 plus its consented replay-safe control-event sidecar into workflow JSON.

    MP4 pixels alone cannot establish reliable mouse/keyboard semantics; a matching sidecar is required.
    """
    import hashlib
    import re
    try:
        from session_recorder import RECORDING_DIR, _recording_target, list_recordings
    except ModuleNotFoundError:
        from agent.session_recorder import RECORDING_DIR, _recording_target, list_recordings
    root = Path(recordings_folder or RECORDING_DIR).expanduser().resolve()
    if not re.fullmatch(r"session_[A-Za-z0-9_.-]+\.mp4", str(filename or "")):
        raise ValueError("Invalid recording filename")
    _, video = _recording_target(filename, root)
    if not video.is_file() or video.is_symlink():
        raise FileNotFoundError("Completed MP4 recording was not found")
    if filename not in {row["filename"] for row in list_recordings(root)}:
        raise ValueError("Recording has not been finalized")
    sidecar = video.with_suffix(".events.jsonl")
    if sidecar.is_symlink() or not sidecar.is_file():
        raise ValueError("Video-only recording has no control-event sidecar and cannot be converted reliably")
    if sidecar.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Recording event sidecar exceeds the conversion limit")
    steps = []
    previous_ms = 0
    last_pointer = None
    allowed = {"mouse_down", "key_down", "key_up", "mouse_scroll", "clear_input"}
    for line in sidecar.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if len(steps) >= MAX_STEPS:
            raise ValueError("Recording contains too many workflow events")
        event = json.loads(line)
        if not isinstance(event, dict) or event.get("event") not in allowed:
            continue
        elapsed = event.get("elapsed_ms")
        if type(elapsed) is not int or elapsed < previous_ms:
            raise ValueError("Recording event timeline is invalid")
        action = event["event"]
        step = {"action": action, "delay_ms": min(30000, elapsed - previous_ms)}
        previous_ms = elapsed
        if action == "mouse_down":
            x, y = event.get("x"), event.get("y")
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)) or not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError("Recording contains invalid pointer coordinates")
            last_pointer = (round(float(x), 6), round(float(y), 6))
            step.update({"x": last_pointer[0], "y": last_pointer[1],
                         "coordinate_mode": "screen", "button": event.get("button", "left")})
        elif action in {"key_down", "key_up"}:
            key = event.get("key")
            if key not in {"ctrl", "alt", "shift", "win", "enter", "tab", "esc", "backspace",
                           "delete", "up", "down", "left", "right", "home", "end",
                           "pageup", "pagedown", "space"}:
                raise ValueError("Recording contains a non-replayable key")
            step["key"] = key
        elif action == "mouse_scroll":
            dx, dy = event.get("delta_x", 0), event.get("delta_y", 0)
            if not isinstance(dx, (int, float)) or not isinstance(dy, (int, float)):
                raise ValueError("Recording contains invalid scroll values")
            step.update({"delta_x": max(-2400, min(2400, float(dx))),
                         "delta_y": max(-2400, min(2400, float(dy)))})
            if "x" in event and "y" in event:
                last_pointer = (float(event["x"]), float(event["y"]))
                step.update({"x": last_pointer[0], "y": last_pointer[1]})
            elif last_pointer:
                step.update({"x": last_pointer[0], "y": last_pointer[1]})
        elif action == "clear_input":
            if "x" in event and "y" in event:
                last_pointer = (float(event["x"]), float(event["y"]))
            if not last_pointer:
                raise ValueError("clear_input event is missing focus coordinates")
            step.update({"x": last_pointer[0], "y": last_pointer[1], "coordinate_mode": "screen"})
        steps.append(step)
    if not steps:
        raise ValueError("No replayable control events were captured for this recording")
    digest = hashlib.sha256()
    with video.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    root_out = Path(workflow_root) if workflow_root else workflow_directory()
    root_out.mkdir(parents=True, exist_ok=True)
    safe_name = " ".join(str(name or f"Recording {video.stem}").split())[:80] or "Recorded workflow"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = root_out / f"workflow_{stamp}.json"
    payload = {
        "schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "name": safe_name, "tags": ["recording-conversion"], "notes": "",
        "coordinate_space": "normalized_0_to_1", "recorded_screen": {"width": 0, "height": 0},
        "step_count": len(steps), "steps": steps, "is_public": False,
        "privacy": {"typed_text_recorded": False, "clipboard_recorded": False, "local_only": True},
        "source_recording": {"filename": filename, "sha256": digest.hexdigest()}
    }
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, target)
    return target
