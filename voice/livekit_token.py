"""voice/livekit_token.py — LiveKit access-token minting.

LiveKit access tokens are standard HS256 JWTs signed with the LiveKit API
secret (https://docs.livekit.io/home/get-started/authentication/). We mint
them with PyJWT (already a backend dependency) so the backend does not need
the ``livekit-api`` SDK installed.

Used by the ``POST /agent/sam/livekit/token`` endpoint to let the dashboard
join the SAM voice room, and by the worker CLI for debugging.
"""
from __future__ import annotations

import time

import jwt

DEFAULT_TTL_S = 3600  # 1 hour — a voice session token, not a long-lived credential
MAX_TTL_S = 24 * 3600


def mint_access_token(
    *,
    api_key: str,
    api_secret: str,
    identity: str,
    room: str,
    name: str = "",
    ttl_s: int = DEFAULT_TTL_S,
    can_publish: bool = True,
    can_subscribe: bool = True,
    metadata: str = "",
) -> str:
    """Mint a LiveKit room-join access token (HS256 JWT).

    Args:
        api_key: LiveKit API key (becomes the JWT ``iss``).
        api_secret: LiveKit API secret (HS256 signing key).
        identity: Unique participant identity (JWT ``sub``).
        room: Room the token grants access to.
        name: Human-readable participant name shown in the room.
        ttl_s: Token lifetime in seconds (clamped to [60, 24h]).
        can_publish: Allow publishing audio (the Commander's microphone).
        can_subscribe: Allow subscribing to tracks (SAM's voice).
        metadata: Optional participant metadata string.

    Returns:
        The signed JWT string.

    Raises:
        ValueError: If any required argument is empty.
    """
    if not api_key or not api_secret:
        raise ValueError("LiveKit api_key and api_secret are required")
    if not identity:
        raise ValueError("identity is required")
    if not room:
        raise ValueError("room is required")

    ttl_s = max(60, min(int(ttl_s), MAX_TTL_S))
    now = int(time.time())

    claims: dict[str, object] = {
        "iss": api_key,
        "sub": identity,
        "nbf": now - 10,  # small clock-skew allowance
        "exp": now + ttl_s,
        "video": {
            "room": room,
            "roomJoin": True,
            "roomCreate": True,
            "canPublish": can_publish,
            "canSubscribe": can_subscribe,
            "canPublishData": True,
        },
    }
    if name:
        claims["name"] = name
    if metadata:
        claims["metadata"] = metadata

    return jwt.encode(claims, api_secret, algorithm="HS256")
