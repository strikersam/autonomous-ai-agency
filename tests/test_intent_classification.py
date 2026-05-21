from agent.intent import classify_direct_chat_intent


def test_classify_answer_only():
    assert classify_direct_chat_intent("Hi, how are you?") == "answer_only"


def test_classify_clarify_needed():
    assert classify_direct_chat_intent("Fix this") == "clarify_needed"


def test_classify_plan_only():
    assert classify_direct_chat_intent("Please analyze the repo and propose a plan to improve tests") == "plan_only"


def test_classify_execute_now():
    assert classify_direct_chat_intent("Fix bug in authentication and commit the change") == "execute_now"


def test_classify_execute_after_approval():
    assert classify_direct_chat_intent("Remove secrets from key_store and update admin_auth") == "execute_after_approval"
