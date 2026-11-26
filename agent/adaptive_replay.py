"""Three-tier adaptive replay: Windows UIA, OCR text anchors, then relative coordinates."""
from __future__ import annotations
import difflib
import time
from typing import Any, Callable

def _uia_anchor(anchor: dict[str, Any], window_bounds=None):
    if not anchor.get("name") and not anchor.get("role"):
        return None
    try:
        from pywinauto import Desktop
        expected = " ".join(str(anchor.get("name", "")).casefold().split())
        role = str(anchor.get("role", "")).casefold()
        best = None
        for window in Desktop(backend="uia").windows():
            for control in window.descendants():
                try:
                    name = " ".join(str(control.window_text() or "").casefold().split())
                    actual_role = str(control.element_info.control_type or "").casefold()
                    score = difflib.SequenceMatcher(None, expected, name).ratio() if expected and name else 0
                    if (not expected or score >= 0.78) and (not role or role == actual_role):
                        rect = control.rectangle()
                        point = ((rect.left+rect.right)//2, (rect.top+rect.bottom)//2)
                        if not window_bounds or (window_bounds[0] <= point[0] <= window_bounds[2] and window_bounds[1] <= point[1] <= window_bounds[3]):
                            if best is None or score > best[0]:
                                best = (score, point)
                except Exception:
                    continue
        return best[1] if best else None
    except Exception:
        return None

def _ocr_anchor(anchor: dict[str, Any]):
    expected = " ".join(str(anchor.get("text", "")).casefold().split())
    if not expected:
        return None
    try:
        import pyautogui
        import pytesseract
        from pytesseract import Output
        data = pytesseract.image_to_data(pyautogui.screenshot(), output_type=Output.DICT)
        groups: dict[tuple[int,int,int], list[int]] = {}
        for i, token in enumerate(data.get("text", [])):
            if str(token).strip():
                groups.setdefault((int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i])), []).append(i)
        best = None
        for indices in groups.values():
            text = " ".join(str(data["text"][i]).strip() for i in indices)
            score = difflib.SequenceMatcher(None, expected, " ".join(text.casefold().split())).ratio()
            if best is None or score > best[0]:
                left=min(int(data["left"][i]) for i in indices)
                top=min(int(data["top"][i]) for i in indices)
                right=max(int(data["left"][i])+int(data["width"][i]) for i in indices)
                bottom=max(int(data["top"][i])+int(data["height"][i]) for i in indices)
                best=(score,((left+right)//2,(top+bottom)//2))
        return best[1] if best and best[0] >= 0.72 else None
    except Exception:
        return None

def resolve_target(step: dict[str, Any], screen_size: tuple[int,int],
                   window_bounds: tuple[int,int,int,int] | None = None, *,
                   uia_resolver: Callable[[dict[str,Any],Any],Any] | None = None,
                   ocr_resolver: Callable[[dict[str,Any]],Any] | None = None) -> dict[str,Any]:
    anchor = step.get("anchor") if isinstance(step.get("anchor"),dict) else {}
    attempts=[]
    if anchor.get("name") or anchor.get("role"):
        try:
            point=(uia_resolver or _uia_anchor)(anchor,window_bounds)
            if point and len(point)==2:
                return {"x":int(point[0]),"y":int(point[1]),"strategy":"uia","attempts":["uia"]}
        except Exception:
            pass
        attempts.append("uia")
    if anchor.get("text"):
        try:
            point=(ocr_resolver or _ocr_anchor)(anchor)
            if point and len(point)==2:
                return {"x":int(point[0]),"y":int(point[1]),"strategy":"ocr","attempts":attempts+["ocr"]}
        except Exception:
            pass
        attempts.append("ocr")
    sw,sh=max(1,int(screen_size[0])),max(1,int(screen_size[1]))
    x=max(0.0,min(1.0,float(step.get("x",0))))
    y=max(0.0,min(1.0,float(step.get("y",0))))
    if window_bounds:
        left,top,right,bottom=window_bounds
        if right>left and bottom>top:
            return {"x":round(left+x*(right-left)),"y":round(top+y*(bottom-top)),"strategy":"relative","attempts":attempts+["relative"]}
    return {"x":round(x*(sw-1)),"y":round(y*(sh-1)),"strategy":"normalized","attempts":attempts+["normalized"]}

def wait_until(predicate: Callable[[],bool], timeout_seconds: float, interval_seconds: float=0.2) -> bool:
    deadline=time.monotonic()+max(0.0,min(float(timeout_seconds),120.0))
    while True:
        try:
            if predicate():
                return True
        except Exception:
            pass
        remaining=deadline-time.monotonic()
        if remaining<=0:
            return False
        time.sleep(min(max(0.05,float(interval_seconds)),remaining))

def wait_for_anchor(anchor: dict[str,Any], timeout_seconds: float=15.0, *, uia_resolver=None, ocr_resolver=None) -> bool:
    def ready():
        if anchor.get("name") or anchor.get("role"):
            if (uia_resolver or _uia_anchor)(anchor,None):
                return True
        if anchor.get("text"):
            return bool((ocr_resolver or _ocr_anchor)(anchor))
        return False
    return wait_until(ready,timeout_seconds)

def dismiss_known_popups(handler: Callable[[],bool] | None) -> bool:
    """Invoke only an explicitly supplied, application-specific safe popup handler."""
    if handler is None:
        return False
    try:
        return bool(handler())
    except Exception:
        return False

def clear_input_and_verify(control, key_sender: Callable[[],None], focus_verifier: Callable[[],bool]) -> bool:
    """Focus an accessibility Edit control, send Ctrl+A, and verify focus remains on it."""
    if control is None:
        return False
    try:
        control.set_focus()
        key_sender()
        return bool(focus_verifier())
    except Exception:
        return False


def clear_input_and_verify(control, key_sender: Callable[[],None], focus_verifier: Callable[[],bool] | None = None) -> bool:
    """Focus current UIA control, send Ctrl+A, then verify focus remains."""
    if control is None:
        try:
            from pywinauto import Desktop
            control = Desktop(backend="uia").get_focus()
        except Exception:
            return False
    try:
        control.set_focus()
        key_sender()
        if focus_verifier is not None:
            return bool(focus_verifier())
        try:
            return bool(control.has_keyboard_focus())
        except Exception:
            try:
                return bool(control.element_info.has_keyboard_focus)
            except Exception:
                return False
    except Exception:
        return False
