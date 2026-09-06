const { v4: uuidv4 } = require('uuid');

const Status = {
  PENDING: 'pending',
  ALLOWED: 'allowed',
  DENIED: 'denied',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed',
  CANCELLED: 'cancelled'
};

const tasks = {};
const listeners = new Set();

function emitEvent(event) {
  for (const listener of listeners) listener(event);
}

function registerListener(fn) {
  listeners.add(fn);
}
function unregisterListener(fn) {
  listeners.delete(fn);
}

function createTask({ plugin, tool_name, command, message, parameters, risk, docker }) {
  const id = uuidv4();
  const now = Date.now();
  const task = {
    id, plugin, tool_name, command, message, parameters,
    status: Status.PENDING, result: null,
    created_at: now, updated_at: now, risk, docker
  };
  tasks[id] = task;
  emitEvent({ type: 'task_requested', task });
  return task;
}

function updateTaskStatus(id, status, result) {
  const task = tasks[id];
  if (!task) throw new Error('no-such-task');
  task.status = status;
  task.updated_at = Date.now();
  if (result !== undefined) task.result = result;
  tasks[id] = task;
  let eventType = '';
  switch(status) {
    case Status.ALLOWED: eventType = 'task_approved'; break;
    case Status.DENIED: eventType = 'task_denied'; break;
    case Status.RUNNING: eventType = 'task_running'; break;
    case Status.COMPLETED: eventType = 'task_completed'; break;
    case Status.FAILED: eventType = 'task_failed'; break;
  }
  if(eventType)
    emitEvent({ type: eventType, task });
  return task;
}

module.exports = {
  Status,
  tasks,
  listeners,
  emitEvent,
  registerListener,
  unregisterListener,
  createTask,
  updateTaskStatus
};
