from agent.state import AgentSessionStore


def test_session_repo_context_is_sticky(tmp_path):
    store = AgentSessionStore(db_path=str(tmp_path / "sessions.db"))
    session_id = "s1"
    store.create_with_id(session_id=session_id, title="t", owner_id="u")
    store.update_repo_context(session_id, "https://github.com/owner/repo", "main")
    s = store.get(session_id)
    assert s.repo_url == "https://github.com/owner/repo"
    assert s.repo_ref == "main"
