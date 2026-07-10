---
name: stop-slop-quality
description: "Remove AI writing tells and cliches — enforce natural, human-quality output"
---

# Stop-Slop Quality Skill

**Inspired by:** [stop-slop](https://github.com/hardikpandya/stop-slop) — removing AI tells from prose

**Purpose:** Train AI agents to catch and remove common AI writing patterns (generic phrases, structural clichés, weak prose).

## What's Unique About stop-slop

stop-slop identifies AI "tells"—predictable patterns that reveal AI authorship:
- **Banned phrases** — "harness-native operator", "it's important to note", "ultimately"
- **Structural clichés** — binary contrasts, dramatic fragmentation, false agency
- **Weak prose** — passive voice, vague declaratives, Wh-sentence starters

## AI Tells Detected

### Throat-Clearing Phrases
- "It's important to note that..."
- "As you may know..."
- "It's worth mentioning..."

### Emphasis Crutches (Banned Adverbs)
- truly, really, very, literally, certainly, definitely

### Business Jargon
- leverage, synergy, paradigm shift, ecosystem

### Meta-Commentary
- "The following code demonstrates"
- "As mentioned above"

## Implementation

Create `agents/quality_checker.py` to check/clean text:

```python
class StopSlopChecker:
    def check_text(self, text: str) -> list[dict]:
        """Find AI tells in text"""
    
    def clean_text(self, text: str) -> str:
        """Remove AI tells"""
```

## Integration Points

- Pre-commit hook to check commit messages
- Pre-PR hook to check descriptions
- Real-time filtering during agent output

## References

- stop-slop: https://github.com/hardikpandya/stop-slop
- Quick-Note Issue: #229
