---
name: workflow-engine
description: >
  DAG-based workflow execution engine with parallel steps, retries, and conditional branching
---

# Skill: SuperClaude Workflow Engine

## Purpose
DAG-based workflow execution engine (`agents/workflow_engine.py`) with topological ordering,
cycle detection, and dependency resolution.

## Usage
```python
from agents.workflow_engine import WorkflowEngine, Workflow, Task

engine = WorkflowEngine()
wf = Workflow(workflow_id="deploy", name="Deploy Pipeline")
wf.add_task(Task(task_id="build", name="Build", action=lambda: "built"))
wf.add_task(Task(task_id="test", name="Test", action=lambda: "tested", depends_on=["build"]))
engine.register(wf)
results = engine.execute("deploy")
```

## Key Classes
- **Task** — single DAG node with action, dependencies, status, retries
- **Workflow** — named collection of tasks, DAG validation, ready-task detection
- **WorkflowEngine** — registry, topological execution

## Testing
```bash
python -m pytest tests/test_workflow_engine.py -v
```

## Related Issues
- Issue #235: SuperClaude Workflow Engine
