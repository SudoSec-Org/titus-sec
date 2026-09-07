import os
os.environ.setdefault("LLM_API_KEY", "test-key-dummy")

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pytest
import asyncio

@pytest.fixture(autouse=True)
def isolate_approval_state():
    from backend import agent
    agent.approval_tasks.clear()
    while not agent.task_events.empty():
        try:
            agent.task_events.get_nowait()
        except asyncio.QueueEmpty:
            break
    yield
    agent.approval_tasks.clear()
    while not agent.task_events.empty():
        try:
            agent.task_events.get_nowait()
        except asyncio.QueueEmpty:
            break
