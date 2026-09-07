import asyncio
import pytest
from backend import agent

def test_make_task_defaults():
    task = agent.make_task(plugin="network", tool_name="nmap", command="nmap -F 127.0.0.1", message="approve?", parameters={"target": "127.0.0.1"})
    assert task.plugin == "network"
    assert task.tool_name == "nmap"
    assert task.command == "nmap -F 127.0.0.1"
    assert task.status == agent.ApprovalStatus.PENDING
    assert task.result is None
    assert task.id in agent.approval_tasks

def test_make_task_with_risk_and_docker():
    task = agent.make_task(plugin="web", tool_name="gobuster", command="gobuster dir -u http://x", message="msg", parameters={}, risk="medium", docker=True)
    assert task.risk == "medium"
    assert task.docker is True

def test_update_task_status_transitions():
    task = agent.make_task(plugin="p", tool_name="t", command="echo hi", message="m", parameters={})
    agent.update_task_status(task.id, agent.ApprovalStatus.ALLOWED)
    assert agent.approval_tasks[task.id].status == agent.ApprovalStatus.ALLOWED
    agent.update_task_status(task.id, agent.ApprovalStatus.RUNNING)
    assert agent.approval_tasks[task.id].status == agent.ApprovalStatus.RUNNING
    agent.update_task_status(task.id, agent.ApprovalStatus.COMPLETED, result="ok")
    t = agent.approval_tasks[task.id]
    assert t.status == agent.ApprovalStatus.COMPLETED
    assert t.result == "ok"

def test_update_task_status_failed():
    task = agent.make_task(plugin="p", tool_name="t", command="false", message="m", parameters={})
    agent.update_task_status(task.id, agent.ApprovalStatus.FAILED, result="boom")
    assert agent.approval_tasks[task.id].status == agent.ApprovalStatus.FAILED
    assert agent.approval_tasks[task.id].result == "boom"

def test_update_task_status_denied_and_cancelled():
    task = agent.make_task(plugin="p", tool_name="t", command="cmd", message="m", parameters={})
    agent.update_task_status(task.id, agent.ApprovalStatus.DENIED)
    assert agent.approval_tasks[task.id].status == agent.ApprovalStatus.DENIED
    agent.update_task_status(task.id, agent.ApprovalStatus.CANCELLED)
    assert agent.approval_tasks[task.id].status == agent.ApprovalStatus.CANCELLED

def test_update_task_status_invalid_id_raises():
    with pytest.raises(ValueError, match="No such task"):
        agent.update_task_status("non-existent", agent.ApprovalStatus.COMPLETED)

def test_list_tasks_returns_all():
    t1 = agent.make_task(plugin="a", tool_name="t1", command="c1", message="m", parameters={})
    t2 = agent.make_task(plugin="a", tool_name="t2", command="c2", message="m", parameters={})
    ids = {t.id for t in agent.list_tasks()}
    assert t1.id in ids and t2.id in ids

@pytest.mark.asyncio
async def test_emit_event_queue():
    await agent.emit_event({"type": "task_requested", "task": {"id": "x"}})
    ev = await asyncio.wait_for(agent.task_events.get(), timeout=1)
    assert ev["type"] == "task_requested"

@pytest.mark.asyncio
async def test_execute_task_success_emits_completed():
    from backend.main import _execute_task
    task = agent.make_task(plugin="test", tool_name="test", command="echo hello_real", message="m", parameters={})
    await _execute_task(task.id, task.command)
    t = agent.approval_tasks[task.id]
    assert t.status == agent.ApprovalStatus.COMPLETED
    assert "hello_real" in t.result
    ev = await asyncio.wait_for(agent.task_events.get(), timeout=1)
    assert ev["type"] == "task_completed"
    assert ev["task"]["id"] == task.id

@pytest.mark.asyncio
async def test_execute_task_failure_emits_failed():
    from backend.main import _execute_task
    task = agent.make_task(plugin="test", tool_name="test", command="false", message="m", parameters={})
    await _execute_task(task.id, task.command)
    t = agent.approval_tasks[task.id]
    assert t.status == agent.ApprovalStatus.FAILED
    ev = await asyncio.wait_for(agent.task_events.get(), timeout=1)
    assert ev["type"] == "task_failed"

@pytest.mark.asyncio
async def test_execute_task_captures_stderr():
    from backend.main import _execute_task
    task = agent.make_task(plugin="test", tool_name="test", command="echo out; echo err >&2", message="m", parameters={})
    await _execute_task(task.id, task.command)
    t = agent.approval_tasks[task.id]
    assert t.status == agent.ApprovalStatus.COMPLETED
    assert "out" in t.result
    assert "err" in t.result

@pytest.mark.asyncio
async def test_execute_task_nonexistent_command_fails():
    from backend.main import _execute_task
    task = agent.make_task(plugin="test", tool_name="test", command="nonexistent_cmd_12345", message="m", parameters={})
    await _execute_task(task.id, task.command)
    t = agent.approval_tasks[task.id]
    assert t.status == agent.ApprovalStatus.FAILED

@pytest.mark.asyncio
async def test_execute_task_missing_task_no_crash():
    from backend.main import _execute_task
    await _execute_task("does-not-exist", "echo hi")
