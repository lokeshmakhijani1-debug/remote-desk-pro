import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"agent"))
from host_agent import calculate_backoff

def test_reconnect_backoff_grows_exponentially_and_caps():
    assert [calculate_backoff(i) for i in (1,2,3)]==[2,4,8]
    assert calculate_backoff(99)==30
