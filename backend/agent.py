from enum import Enum
from typing import Optional, Dict, Any
from uuid import uuid4
from pydantic import BaseModel
import asyncio
import time

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    ALLOWED = "allowed"
    DENIED = "denied"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ApprovalTask(BaseModel):
    id: str
    plugin: str
    tool_name: str
    parameters: dict
    command: str
    message: str
    status: ApprovalStatus
    result: Optional[Any] = None
    created_at: float
    updated_at: float
    risk: Optional[str] = None
    docker: Optional[bool] = None

approval_tasks: Dict[str, ApprovalTask] = {}
task_events = asyncio.Queue(maxsize=100)

def _now():
    try:
        loop = asyncio.get_running_loop()
        return loop.time()
    except RuntimeError:
        return time.time()

def make_task(plugin, tool_name, command, message, parameters, risk=None, docker=None):
    tid = str(uuid4())
    now = _now()
    task = ApprovalTask(
        id=tid,
        plugin=plugin,
        tool_name=tool_name,
        command=command,
        message=message,
        parameters=parameters or {},
        status=ApprovalStatus.PENDING,
        result=None,
        created_at=now,
        updated_at=now,
        risk=risk,
        docker=docker,
    )
    approval_tasks[tid] = task
    return task

def update_task_status(tid: str, status: ApprovalStatus, result=None):
    task = approval_tasks.get(tid)
    if not task:
        raise ValueError(f"No such task: {tid}")
    task.status = status
    task.updated_at = _now()
    if result is not None:
        task.result = result
    approval_tasks[tid] = task
    return task

async def emit_event(event: dict):
    await task_events.put(event)

def list_tasks():
    return list(approval_tasks.values())
