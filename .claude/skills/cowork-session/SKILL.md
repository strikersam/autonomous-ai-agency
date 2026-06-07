---
name: cowork-session
description: >
  Claude Cowork shared AI pairing sessions with real-time sync,
  turn-taking, and collaboration context propagation.
triggers:
  - "cowork session"
  - "shared coding"
  - "collaborative AI"
  - "pair programming"
  - any change to agents/cowork_session.py
references:
  - agents/cowork_session.py
  - tests/test_cowork_session.py
  - Quick-Note Issue #261
---

# Skill: cowork-session (Claude Cowork)

## Purpose

Enables multiple developers to share an AI pair-programming session with
context propagation, turn-taking, and collaborative state management.

## When to Use

- Pair programming with an AI assistant as mediator
- Code review sessions with real-time context sharing
- Onboarding new team members (observe mode)
- Collaborative debugging sessions

## Components

| Class | Role |
|---|---|
| `ContributorState` | Per-user state (role, cursor, activity) |
| `CollaborationContext` | Shared workspace context blob |
| `CoworkSession` | Turn-taking, role assignment, phase management |
| `SyncAgent` | Background sync with idle-editor eviction |

## Session Roles

| Role | Permissions |
|---|---|
| HOST | Always can take editing control |
| PARTICIPANT | Can request edit; blocked if another editor is active |
| OBSERVER | Read-only; can only edit during IDLE/BRAINSTORMING |

## Quick Start

```python
from agents.cowork_session import CoworkSession, SessionRole

session = CoworkSession(session_id="s1", host_user_id="alice")
session.add_contributor("bob")
session.add_contributor("carol", role=SessionRole.OBSERVER)
session.request_edit("bob")  # bob gets editing control
session.sync_context("bob", {"message": "Let's refactor this"})
```

## Testing

```bash
pytest tests/test_cowork_session.py -v
```

12 tests covering CollaborationContext, CoworkSession, SyncAgent.

## Branch

`fix/quick-note-261-cowork`
