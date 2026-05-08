import json
import os
import time
from typing import Optional

# Simple file-based memory store
# In production, replace with Redis or PostgreSQL
MEMORY_DIR = "/tmp/practus_memory"
os.makedirs(MEMORY_DIR, exist_ok=True)

MAX_HISTORY = 20  # max messages per thread before trimming


def _thread_key(agent: str, context_id: str) -> str:
    """
    context_id = channel name for channel messages
                 user_id for DMs
    """
    safe = context_id.replace("/", "_").replace(" ", "_")
    return f"{agent}_{safe}"

def _thread_path(key: str) -> str:
    return os.path.join(MEMORY_DIR, f"{key}.json")


def load_thread(agent: str, context_id: str) -> list:
    """Load conversation history for an agent in a given context."""
    key  = _thread_key(agent, context_id)
    path = _thread_path(key)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data.get("messages", [])
    except Exception:
        return []


def save_thread(agent: str, context_id: str, messages: list) -> None:
    """Save conversation history, trimming to MAX_HISTORY."""
    # Keep only the last MAX_HISTORY messages
    if len(messages) > MAX_HISTORY:
        messages = messages[-MAX_HISTORY:]
    key  = _thread_key(agent, context_id)
    path = _thread_path(key)
    try:
        with open(path, "w") as f:
            json.dump({
                "agent":      agent,
                "context_id": context_id,
                "updated_at": time.time(),
                "messages":   messages
            }, f, indent=2)
    except Exception as e:
        print(f"[memory] save error: {e}")


def append_and_save(agent: str, context_id: str, role: str, content: str) -> list:
    """Append one message to thread and save. Returns full updated thread."""
    messages = load_thread(agent, context_id)
    messages.append({"role": role, "content": content})
    save_thread(agent, context_id, messages)
    return messages


def clear_thread(agent: str, context_id: str) -> None:
    """Clear conversation history for a specific thread."""
    key  = _thread_key(agent, context_id)
    path = _thread_path(key)
    if os.path.exists(path):
        os.remove(path)


def list_active_threads() -> list:
    """List all active thread files."""
    files = []
    for f in os.listdir(MEMORY_DIR):
        if f.endswith(".json"):
            files.append(f.replace(".json", ""))
    return files


# ─── Task state tracking ─────────────────────────────────────────────────────── 
TASK_DIR = "/tmp/practus_tasks"
os.makedirs(TASK_DIR, exist_ok=True)


def save_task(task_id: str, task_data: dict) -> None:
    """Persist a task and its state."""
    path = os.path.join(TASK_DIR, f"{task_id}.json")
    task_data["updated_at"] = time.time()
    with open(path, "w") as f:
        json.dump(task_data, f, indent=2)


def load_task(task_id: str) -> Optional[dict]:
    """Load a task by ID."""
    path = os.path.join(TASK_DIR, f"{task_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def update_task_status(task_id: str, status: str, notes: str = "") -> None:
    """Update task status."""
    task = load_task(task_id)
    if task:
        task["status"] = status
        if notes:
            task.setdefault("notes", []).append({
                "time": time.time(),
                "note": notes
            })
        save_task(task_id, task)


def create_task(task_id: str, owner: str, description: str,
                assigned_agents: list, channel: str) -> dict:
    """Create and persist a new task."""
    task = {
        "task_id":         task_id,
        "owner":           owner,
        "description":     description,
        "assigned_agents": assigned_agents,
        "channel":         channel,
        "status":          "in_progress",
        "hops":            0,
        "created_at":      time.time(),
        "subtasks":        [],
        "notes":           [],
    }
    save_task(task_id, task)
    return task
