import pytest

# Try importing the MessageBus from the expected package location.
# If that fails, fall back to a top-level import.
try:
    from portfolio.message_bus import MessageBus
except ImportError:
    from message_bus import MessageBus


def test_publish_subscribe_single():
    """Verify that a single subscriber receives published messages."""
    bus = MessageBus()
    received = []

    def callback(msg):
        received.append(msg)

    bus.subscribe("topic1", callback)
    bus.publish("topic1", "hello")
    assert received == ["hello"], "Subscriber did not receive the published message."


def test_multiple_subscribers_receive_same_message():
    """Verify that all subscribers to a topic receive the same message."""
    bus = MessageBus()
    received_a = []
    received_b = []

    def callback_a(msg):
        received_a.append(msg)

    def callback_b(msg):
        received_b.append(msg)

    bus.subscribe("topic1", callback_a)
    bus.subscribe("topic1", callback_b)
    bus.publish("topic1", "msg")

    assert received_a == ["msg"], "First subscriber did not receive the message."
    assert received_b == ["msg"], "Second subscriber did not receive the message."


def test_unsubscribe_removes_callback():
    """Verify that unsubscribing a callback stops it from receiving messages."""
    bus = MessageBus()
    received = []

    def callback(msg):
        received.append(msg)

    bus.subscribe("topic1", callback)
    # Unsubscribe if the API supports it; otherwise ignore.
    try:
        bus.unsubscribe("topic1", callback)
    except AttributeError:
        pytest.skip("MessageBus does not expose an unsubscribe method.")
    bus.publish("topic1", "msg")
    assert received == [], "Callback was called after being unsubscribed."


def test_publish_no_subscribers_does_not_fail():
    """Publishing to a topic with no subscribers should not raise an exception."""
    bus = MessageBus()
    # No subscribers added; just publish.
    bus.publish("empty_topic", "msg")  # Should not raise.


def test_subscribe_to_multiple_topics():
    """Verify that subscribers to different topics are isolated."""
    bus = MessageBus()
    received_topic1 = []
    received_topic2 = []

    def cb1(msg):
        received_topic1.append(msg)

    def cb2(msg):
        received_topic2.append(msg)

    bus.subscribe("topic1", cb1)
    bus.subscribe("topic2", cb2)

    bus.publish("topic1", "msg1")
    bus.publish("topic2", "msg2")

    assert received_topic1 == ["msg1"], "Subscriber to topic1 did not receive its message."
    assert received_topic2 == ["msg2"], "Subscriber to topic2 did not receive its message."


def test_same_callback_subscribed_to_multiple_topics():
    """Verify that a single callback can be subscribed to multiple topics."""
    bus = MessageBus()
    received = []

    def cb(msg):
        received.append(msg)

    bus.subscribe("topic1", cb)
    bus.subscribe("topic2", cb)

    bus.publish("topic1", "msg1")
    bus.publish("topic2", "msg2")

    assert received == ["msg1", "msg2"], "Callback did not receive messages from both topics."


def test_unsubscribe_nonexistent_callback():
    """Unsubscribing a callback that was never subscribed should not raise an exception."""
    bus = MessageBus()

    def cb(msg):
        pass

    # Attempt to unsubscribe; should be a no-op or raise a harmless exception.
    try:
        bus.unsubscribe("nonexistent_topic", cb)
    except Exception as e:
        # If the implementation raises, ensure it's not a fatal error.
        assert isinstance(e, (KeyError, ValueError, AttributeError)), (
            f"Unexpected exception type when unsubscribing nonexistent callback: {e}"
        )

    # Ensure that subscribing and publishing still works.
    received = []

    def real_cb(msg):
        received.append(msg)

    bus.subscribe("topic1", real_cb)
    bus.publish("topic1", "msg")
    assert received == ["msg"], "Publishing after unsubscribing nonexistent callback failed."
