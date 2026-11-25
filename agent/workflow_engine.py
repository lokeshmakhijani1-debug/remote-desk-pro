"""Consent-gated semantic workflows. Typed text and clipboard contents are never stored."""
from __future__ import annotations
import json, os, re, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_EMAIL=re.compile(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}")
MAX_STEPS=10_000

def workflow_directory()->Path:
    override=os.getenv("RDP_WORKFLOW_DIR")
    if override: return Path(override).expanduser()
    base=(Path(os.getenv("APPDATA",str(Path.home())))/"RemoteDeskPro") if getattr(sys,"frozen",False) else Path(__file__).resolve().parents[1]
    return base/"project_memory"/"workflows"

def _active_context()->dict[str,str]:
    context={"window_title":"","process_name":"","application":""}
    if os.name!="nt": return context
    try:
        import win32gui,win32process,psutil
        hwnd=win32gui.GetForegroundWindow(); title=win32gui.GetWindowText(hwnd) or ""
        _,pid=win32process.GetWindowThreadProcessId(hwnd); name=psutil.Process(pid).name()
        context.update({"window_title":_EMAIL.sub("[redacted-email]",title[:180]),"process_name":name[:100],"application":Path(name).stem[:80]})
    except Exception: pass
    return context

class WorkflowRecorder:
    def __init__(self,root:Path|None=None)->None:
        self.root=Path(root) if root else workflow_directory(); self._lock=threading.RLock()
        self._enabled=False; self._steps:list[dict[str,Any]]=[]; self._last=0.0
        self._screen={"width":0,"height":0}; self.last_saved:Path|None=None
    @property
    def enabled(self)->bool:
        with self._lock: return self._enabled
    def set_enabled(self,enabled:bool)->Path|None:
        with self._lock:
            if enabled and not self._enabled:
                self._steps=[]; self._last=time.monotonic()
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
            step={"action":event,"delay_ms":min(30000,max(0,round((now-self._last)*1000))),"context":_active_context()}
            self._last=now
            if event=="mouse_down":
                x,y=message.get("x"),message.get("y")
                if not isinstance(x,(int,float)) or not isinstance(y,(int,float)) or not(0<=float(x)<=1 and 0<=float(y)<=1): return
                step.update({"x":round(float(x),6),"y":round(float(y),6),"button":{0:"left",1:"middle",2:"right"}.get(message.get("button"),"left")})
            elif event in {"key_down","key_up"}:
                key=str(message.get("key",""))[:32]
                if not key:return
                step["key"]=key
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
        payload={"schema_version":1,"created_at":datetime.now(timezone.utc).isoformat(),"coordinate_space":"normalized_0_to_1","recorded_screen":self._screen,"step_count":len(self._steps),"steps":self._steps,"privacy":{"typed_text_recorded":False,"clipboard_recorded":False}}
        temporary=target.with_suffix(".json.tmp"); temporary.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding="utf-8")
        os.replace(temporary,target); self.last_saved=target; self._steps=[]; return target

class WorkflowReplayEngine:
    def __init__(self,root:Path|None=None)->None:self.root=Path(root) if root else workflow_directory()
    def latest(self)->Path|None:
        files=sorted(self.root.glob("workflow_*.json"),key=lambda p:p.stat().st_mtime,reverse=True)
        return files[0] if files else None
    @staticmethod
    def _focus_process(name:str)->bool:
        if os.name!="nt" or not name:return True
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
                win32gui.ShowWindow(matches[0],win32con.SW_RESTORE);win32gui.SetForegroundWindow(matches[0]);return True
        except Exception:pass
        return False
    def replay(self,path:Path|None=None,*,dry_run:bool=False)->dict[str,Any]:
        target=Path(path) if path else self.latest()
        if target is None or not target.is_file():raise FileNotFoundError("No saved workflow was found.")
        data=json.loads(target.read_text(encoding="utf-8"))
        if data.get("schema_version")!=1 or data.get("coordinate_space")!="normalized_0_to_1":raise ValueError("Unsupported workflow schema.")
        steps=data.get("steps")
        if not isinstance(steps,list) or len(steps)>MAX_STEPS:raise ValueError("Workflow step count is invalid.")
        if dry_run:return {"steps":len(steps),"executed":0,"dry_run":True,"warnings":[]}
        import pyautogui
        pyautogui.FAILSAFE=True; width,height=pyautogui.size(); executed=0; warnings=[]
        for step in steps:
            if not isinstance(step,dict):continue
            time.sleep(max(0,min(30000,int(step.get("delay_ms",0))))/1000)
            context=step.get("context") if isinstance(step.get("context"),dict) else {}
            process=str(context.get("process_name",""))[:100]
            if process and not self._focus_process(process):
                warning=f"Target application not found: {process}"
                if warning not in warnings:warnings.append(warning)
            action=step.get("action")
            if action=="mouse_down":
                x=max(0.0,min(1.0,float(step.get("x",0))));y=max(0.0,min(1.0,float(step.get("y",0))))
                pyautogui.click(round(x*max(0,width-1)),round(y*max(0,height-1)),button=step.get("button","left"))
            elif action in {"key_down","key_up"}:
                key=str(step.get("key",""))[:32];allowed=set(getattr(pyautogui,"KEYBOARD_KEYS",()))
                if key and (len(key)==1 or key in allowed):(pyautogui.keyDown if action=="key_down" else pyautogui.keyUp)(key)
            elif action=="mouse_scroll":
                dx=float(step.get("delta_x",0));dy=float(step.get("delta_y",0))
                if "x" in step and "y" in step:pyautogui.moveTo(round(float(step["x"])*(width-1)),round(float(step["y"])*(height-1)))
                if dy:pyautogui.scroll(int(dy/120))
                if dx and os.name=="nt":
                    import ctypes
                    ctypes.windll.user32.mouse_event(0x01000,0,0,ctypes.c_ulong(int(dx)).value,0)
            executed+=1
        return {"steps":len(steps),"executed":executed,"dry_run":False,"warnings":warnings}
