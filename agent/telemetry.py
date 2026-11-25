"""Thread-safe FPS, latency and transfer-throughput counters."""
from __future__ import annotations
import threading,time
class TelemetryTracker:
    def __init__(self)->None:
        self._lock=threading.Lock();self._frames=0;self._upload=0;self._download=0;self._ping=None
        self._last=time.monotonic();self._lf=0;self._lu=0;self._ld=0
    def frame_sent(self,n:int)->None:
        with self._lock:self._frames+=1;self._upload+=max(0,int(n))
    def transfer_received(self,n:int)->None:
        with self._lock:self._download+=max(0,int(n))
    def set_ping(self,ms:float|None)->None:
        with self._lock:self._ping=max(0.0,float(ms)) if ms is not None else None
    def snapshot(self)->dict:
        now=time.monotonic()
        with self._lock:
            elapsed=max(.001,now-self._last)
            data={"fps":round((self._frames-self._lf)/elapsed,1),"ping_ms":round(self._ping,1) if self._ping is not None else None,
            "upload_kbps":round((self._upload-self._lu)/elapsed/1024,1),"download_kbps":round((self._download-self._ld)/elapsed/1024,1)}
            self._last=now;self._lf=self._frames;self._lu=self._upload;self._ld=self._download
            return data
