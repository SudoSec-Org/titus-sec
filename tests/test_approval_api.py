import asyncio
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    from backend.main import app
    with TestClient(app) as c:
        yield c

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "OK"}

def test_list_tools(client):
    r = client.get("/api/tools")
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert "nmap" in names
    assert "gobuster" in names

def test_request_tool_nmap_creates_pending_task(client):
    r = client.post("/api/task/request", json={"plugin": "network", "tool_name": "nmap", "parameters": {"target": "127.0.0.1", "options": "-F"}})
    assert r.status_code == 200
    data = r.json()
    assert data["tool_name"] == "nmap"
    assert data["status"] == "pending"
    assert "nmap" in data["command"]
    assert "127.0.0.1" in data["command"]
    assert data["id"]

def test_request_tool_gobuster(client):
    r = client.post("/api/task/request", json={"plugin": "web", "tool_name": "gobuster", "parameters": {"target": "http://example.com"}})
    assert r.status_code == 200
    data = r.json()
    assert data["tool_name"] == "gobuster"
    assert data["status"] == "pending"
    assert "gobuster" in data["command"]

def test_request_tool_not_found(client):
    r = client.post("/api/task/request", json={"plugin": "x", "tool_name": "nonexistent", "parameters": {}})
    assert r.status_code == 404
    assert "error" in r.json()

def test_list_tasks_after_request(client):
    r1 = client.post("/api/task/request", json={"plugin": "network", "tool_name": "nmap", "parameters": {"target": "127.0.0.1"}})
    tid = r1.json()["id"]
    r2 = client.get("/api/task/list")
    assert r2.status_code == 200
    ids = {t["id"] for t in r2.json()}
    assert tid in ids

def test_approve_not_found(client):
    r = client.post("/api/task/approve", json={"id": "does-not-exist", "allow": True})
    assert r.status_code == 404

def test_approve_deny_transitions_to_denied(client):
    from backend import agent
    task = agent.make_task(plugin="test", tool_name="test", command="echo should_not_run", message="m", parameters={})
    r = client.post("/api/task/approve", json={"id": task.id, "allow": False})
    assert r.status_code == 200
    assert r.json()["status"] == "denied"
    assert agent.approval_tasks[task.id].status == agent.ApprovalStatus.DENIED

def test_approve_allow_triggers_real_execution_success(client):
    from backend import agent
    task = agent.make_task(plugin="test", tool_name="test", command="echo approved_ok", message="m", parameters={})
    r = client.post("/api/task/approve", json={"id": task.id, "allow": True})
    assert r.status_code == 200
    assert r.json()["status"] == "running"
    for _ in range(20):
        t = agent.approval_tasks[task.id]
        if t.status in (agent.ApprovalStatus.COMPLETED, agent.ApprovalStatus.FAILED):
            break
        asyncio.run(asyncio.sleep(0.1))
    t = agent.approval_tasks[task.id]
    assert t.status == agent.ApprovalStatus.COMPLETED
    assert "approved_ok" in t.result

def test_approve_allow_real_execution_failure(client):
    from backend import agent
    task = agent.make_task(plugin="test", tool_name="test", command="false", message="m", parameters={})
    r = client.post("/api/task/approve", json={"id": task.id, "allow": True})
    assert r.status_code == 200
    for _ in range(20):
        t = agent.approval_tasks[task.id]
        if t.status == agent.ApprovalStatus.FAILED:
            break
        asyncio.run(asyncio.sleep(0.1))
    assert agent.approval_tasks[task.id].status == agent.ApprovalStatus.FAILED

def test_approve_allow_captures_output(client):
    from backend import agent
    task = agent.make_task(plugin="test", tool_name="test", command="echo hello && echo world >&2", message="m", parameters={})
    client.post("/api/task/approve", json={"id": task.id, "allow": True})
    for _ in range(20):
        if agent.approval_tasks[task.id].status == agent.ApprovalStatus.COMPLETED:
            break
        asyncio.run(asyncio.sleep(0.1))
    t = agent.approval_tasks[task.id]
    assert "hello" in t.result

def test_full_flow_request_then_approve_with_nmap_task(client):
    from backend import agent
    r = client.post("/api/task/request", json={"plugin": "network", "tool_name": "nmap", "parameters": {"target": "127.0.0.1", "options": "-F"}})
    tid = r.json()["id"]
    assert agent.approval_tasks[tid].status == agent.ApprovalStatus.PENDING
    agent.approval_tasks[tid].command = "echo full_flow_ok"
    r2 = client.post("/api/task/approve", json={"id": tid, "allow": True})
    assert r2.json()["status"] == "running"
    for _ in range(20):
        if agent.approval_tasks[tid].status == agent.ApprovalStatus.COMPLETED:
            break
        asyncio.run(asyncio.sleep(0.1))
    assert agent.approval_tasks[tid].status == agent.ApprovalStatus.COMPLETED
    assert "full_flow_ok" in agent.approval_tasks[tid].result

@pytest.mark.asyncio
async def test_approval_emits_events_via_queue():
    from backend import agent
    from backend.main import app
    from fastapi.testclient import TestClient
    agent.approval_tasks.clear()
    while not agent.task_events.empty():
        agent.task_events.get_nowait()
    task = agent.make_task(plugin="test", tool_name="test", command="echo evt_test", message="m", parameters={})
    with TestClient(app) as c:
        c.post("/api/task/approve", json={"id": task.id, "allow": True})
        ev1 = await asyncio.wait_for(agent.task_events.get(), timeout=2)
        assert ev1["type"] == "task_approved"
        ev2 = await asyncio.wait_for(agent.task_events.get(), timeout=2)
        assert ev2["type"] == "task_running"
        ev3 = await asyncio.wait_for(agent.task_events.get(), timeout=2)
        assert ev3["type"] in ("task_completed", "task_failed")
