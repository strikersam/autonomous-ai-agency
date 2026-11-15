import asyncio, pytest
from packages.runs.redaction import redact_value, redact_text
from packages.runs import side_effects as fx
def test_extra_shapes():
    for s in ["{'password': 'hunter2hunter2'}", "-----BEGIN RSA PRIVATE KEY-----\nMIIEabcdef", "xoxe-1234567890-abcdef", "xoxs-1234567890-abcdef"]:
        out = redact_text(s)
        assert "hunter2hunter2" not in out and "MIIEabcdef" not in out and "1234567890-abcdef" not in out, out
    d = redact_value({"private_key":"abcabc","cookie":"sess=zzz","pwd":"p4ss","client secret":"cs123"})
    assert set(d.values())=={"***"}, d
class WS:
    def __init__(s, fail_first): s.fail=fail_first; s.pushed=[]; s.cmds=[]
    async def push(s, branch, agent_initiated):
        if s.fail and not s.pushed and not s.cmds: raise RuntimeError("non-fast-forward")
        s.pushed.append(branch)
    async def _run(s,*a): s.cmds.append(a); return 0,"",""
def test_push_fallback():
    w=WS(True); b=asyncio.run(fx.push_branch(w,"agent/task-t1"))
    assert b.startswith("agent/task-t1-") and w.pushed==[b] and w.cmds[0][:3]==("git","checkout","-b")
    w=WS(False); assert asyncio.run(fx.push_branch(w,"agent/task-t1"))=="agent/task-t1"
    w=WS(True)
    with pytest.raises(RuntimeError): asyncio.run(fx.push_branch(w,"feature/x"))
