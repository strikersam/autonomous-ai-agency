Direct chat intent-driven behavior

LLM Relay's Direct Chat endpoint now classifies user messages and automatically chooses an execution path:

- answer_only: Assistant answers directly.
- clarify_needed: Assistant asks for more details.
- plan_only: Assistant returns a plan (no execution).
- execute_now: Assistant will run the plan (auto-escalate) when safe.
- execute_after_approval: Assistant will ask for approval before making sensitive changes.

The system performs a fast "doctor" preflight for repo tasks, selects a conservative default runtime (local/internal), and humanizes progress messages for a smooth assistant experience.
