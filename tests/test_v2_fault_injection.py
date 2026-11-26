import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"agent"))
from host_agent import calculate_backoff

def test_reconnect_backoff_grows_exponentially_and_caps():
    assert [calculate_backoff(i) for i in (1,2,3)]==[2,4,8]
    assert calculate_backoff(99)==30


def test_host_outgoing_file_queue_and_digest(tmp_path):
    import hashlib
    from host_agent import enqueue_file_send, _FILE_SEND_QUEUE, _sha256_file
    source=tmp_path/"share.txt";source.write_bytes(b"remote-desk-pro-v2")
    enqueue_file_send(str(source))
    assert _FILE_SEND_QUEUE.get_nowait()==str(source.resolve())
    assert _sha256_file(source)==hashlib.sha256(b"remote-desk-pro-v2").hexdigest()
