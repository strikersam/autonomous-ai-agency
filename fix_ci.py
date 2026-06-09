#!/usr/bin/env python3
"""Fix docs/changelog.md: insert ### Fixed section under [Unreleased]"""
with open('docs/changelog.md', 'rb') as f:
    raw = f.read()

# The section header is "### Added- **` (dash immediately after Added, no newline)
# em-dash UTF-8 = b'\u00e2\u0080\u0094'
emdash = b'\u00e2\u0080\u0094'

# Old pattern: "### Added- **`spawn_subagent` \u2014 accept"
old = b'### Added- **` + b'spawn_subagent` ' + emdash + b' accept'

new = (
    b'### Fixed\n'
    b'- **Test `test_background_agent_retries_with_exponential_backoff` '
    + emdash + b' `AttributeError: BackgroundAgent object has no attribute '
    b"'process_task'`.** The test called the non-existent bg.process_task(task) "
    b'method. BackgroundAgent uses submit() to enqueue work picked up by a worker '
    b'thread; _handle() is the internal synchronous handler. Fixed by calling '
    b'bg._handle(task) directly in the test.\n\n'
    b'### Added\n'
    b'- **`spawn_subagent` ' + emdash + b' accept'
)

if old in raw:
    raw = raw.replace(old, new, 1)
    with open('docs/changelog.md', 'wb') as f:
        f.write(raw)
    print('SUCCESS - changelog.md updated')
else:
    idx = raw.find(b'### Added')
    print('NOT FOUND. First 120 bytes at position:', repr(raw[idx:idx+120]))