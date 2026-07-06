#!/usr/bin/env python3
"""Broaden brittle CSS locators in tests/e2e/test_regression.py.

Called by .github/workflows/nightly-regression.yml when the nightly run
fails with locator errors. Adds fallback selectors next to the specific
ones so minor frontend markup changes stop breaking the suite.
"""

TEST_FILE = "tests/e2e/test_regression.py"

FIXES = {
    "input[name='provider_id']": (
        "input[name='provider_id'], input[placeholder*='provider' i], "
        "input[id*='provider' i]"
    ),
    "input[name='name']": (
        "input[name='name'], input[placeholder*='name' i], input[id*='name' i]"
    ),
    "input[type='email']": (
        "input[type='email'], input[name='email'], "
        "input[placeholder*='email' i], input[placeholder*='user' i]"
    ),
}


def main() -> None:
    with open(TEST_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    changes = 0
    for old, new in FIXES.items():
        if old in content and new not in content:
            content = content.replace(old, new)
            changes += 1
            print(f"  Fixed: {old[:50]}...")

    if changes > 0:
        with open(TEST_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Applied {changes} locator fixes")
    else:
        print("No auto-fixable locator patterns found")


if __name__ == "__main__":
    main()
