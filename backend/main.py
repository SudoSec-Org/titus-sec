from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import uvicorn
from .config import LLM_API_KEY

app = FastAPI()

# All API keys and secrets loaded only from config.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "OK"}

from . import plugins
from fastapi.responses import JSONResponse
from . import agent
from fastapi import Request
from pydantic import BaseModel
from fastapi import BackgroundTasks
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import time

@app.get("/api/tools")
async def list_tools():
    # get plugin metadata for UI/agent or approval cards
    return JSONResponse(content=plugins.MCP_METADATA)

class TaskRequestModel(BaseModel):
    plugin: str
    tool_name: str
    parameters: dict = {}

@app.post("/api/task/request")
async def request_tool_run(trm: TaskRequestModel, background_tasks: BackgroundTasks):
    # Find plugin and run in approval mode
    match = None
    for meta in plugins.MCP_METADATA:
        if meta['name'] == trm.tool_name:
            match = meta
            break
    if not match:
        return JSONResponse(content={"error": "Tool not found"}, status_code=404)
    for plugin in plugins.MCP_PLUGINS:
        mcp_meta_func = getattr(plugin, 'mcp_metadata', None)
        if mcp_meta_func and mcp_meta_func().get('name') == trm.tool_name:
            info = await plugin.run_tool(**trm.parameters)
            # Prepare approval task
            task = agent.make_task(
                plugin=trm.plugin,
                tool_name=trm.tool_name,
                command=info["command"],
                message=info["approve_message"],
                parameters=trm.parameters,
                risk=info.get("risk"),
                docker=info.get("docker", False),
            )
            await agent.emit_event({"type": "task_requested", "task": task.dict()})
            return JSONResponse(content=task.dict())
    return JSONResponse(content={"error": "Plugin not found"}, status_code=404)

class ApprovalModel(BaseModel):
    id: str
    allow: bool

async def _execute_task(task_id: str, command: str):
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode(errors="ignore")
        if stderr:
            output = (output + "\n" + stderr.decode(errors="ignore")).strip() if output else stderr.decode(errors="ignore").strip()
        else:
            output = output.strip()
        task = agent.approval_tasks.get(task_id)
        if not task:
            return
        if proc.returncode == 0:
            agent.update_task_status(task_id, agent.ApprovalStatus.COMPLETED, result=output or "Completed with no output")
            await agent.emit_event({"type": "task_completed", "task": task.dict()})
        else:
            agent.update_task_status(task_id, agent.ApprovalStatus.FAILED, result=output or f"Process exited with code {proc.returncode}")
            await agent.emit_event({"type": "task_failed", "task": task.dict()})
    except Exception as e:
        task = agent.approval_tasks.get(task_id)
        if task:
            agent.update_task_status(task_id, agent.ApprovalStatus.FAILED, result=str(e))
            await agent.emit_event({"type": "task_failed", "task": task.dict()})

@app.post("/api/task/approve")
async def approve_task(approval: ApprovalModel, background_tasks: BackgroundTasks):
    task = agent.approval_tasks.get(approval.id)
    if not task:
        return JSONResponse(content={"error": "Task not found"}, status_code=404)
    if approval.allow:
        agent.update_task_status(approval.id, agent.ApprovalStatus.ALLOWED)
        await agent.emit_event({"type": "task_approved", "task": task.dict()})
        agent.update_task_status(approval.id, agent.ApprovalStatus.RUNNING)
        await agent.emit_event({"type": "task_running", "task": task.dict()})
        asyncio.create_task(_execute_task(approval.id, task.command))
    else:
        agent.update_task_status(approval.id, agent.ApprovalStatus.DENIED)
        await agent.emit_event({"type": "task_denied", "task": task.dict()})
    return JSONResponse(content=task.dict())

@app.websocket("/api/events")
async def event_stream(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            event = await agent.task_events.get()
            await ws.send_json(event)
    except WebSocketDisconnect:
        pass

@app.get("/api/task/list")
async def list_tasks():
    return JSONResponse(content=[t.dict() for t in agent.list_tasks()])

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
