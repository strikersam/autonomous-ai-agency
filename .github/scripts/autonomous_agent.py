#!/usr/bin/env python3
"""Autonomous agent: fetch oldest open issue, generate implementation, create PR.

Uses the recommended free-cloud brain (Cerebras -> Groq -> NVIDIA NIM, by which
key is present) and a slop-gate (slop_gate.py) that refuses destructive /
low-quality output before opening a PR — so an empty or garbled model response
can never overwrite working code (the PR #833 failure mode).
"""
import json, sys, os, subprocess, httpx, re, ast, pathlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slop_gate import is_destructive_overwrite, python_parses, diff_is_sloppy

gh_token = os.environ['GH_TOKEN']
repo = os.environ['REPO']
issue_input = os.environ.get('ISSUE_NUMBER_INPUT', '')


def _select_brain():
    """Pick the auto-PR model from the recommended free-cloud chain by key.

    Mirrors the in-app brain (services/brain_config_store.RECOMMENDED_PROVIDER_
    PRIORITY): Cerebras -> Groq -> NVIDIA NIM. The auto-PR scripts used to be
    hardcoded to the weak NIM 49B regardless of which superior key was set — so
    upgrading the in-app brain did nothing for them. This closes that gap.
    """
    if os.environ.get('CEREBRAS_API_KEY'):
        return ('cerebras', 'https://api.cerebras.ai/v1/chat/completions',
                os.environ['CEREBRAS_API_KEY'], 'qwen-3-coder-480b')
    if os.environ.get('GROQ_API_KEY'):
        return ('groq', 'https://api.groq.com/openai/v1/chat/completions',
                os.environ['GROQ_API_KEY'], 'llama-3.3-70b-versatile')
    return ('nvidia', 'https://integrate.api.nvidia.com/v1/chat/completions',
            os.environ.get('NVIDIA_API_KEY', ''), 'nvidia/llama-3.3-nemotron-super-49b-v1')

# 1. Find the oldest open issue
if issue_input:
    resp = httpx.get(
        f'https://api.github.com/repos/{repo}/issues/{issue_input}',
        headers={'Authorization': f'Bearer {gh_token}', 'Accept': 'application/vnd.github+json'},
        timeout=30.0,
    )
    issue = resp.json()
else:
    resp = httpx.get(
        f'https://api.github.com/repos/{repo}/issues',
        params={'state': 'open', 'per_page': '50', 'sort': 'created', 'direction': 'asc'},
        headers={'Authorization': f'Bearer {gh_token}', 'Accept': 'application/vnd.github+json'},
        timeout=30.0,
    )
    all_issues = [i for i in resp.json() if 'pull_request' not in i]
    actionable = [i for i in all_issues if 'quick-note:exhausted' not in [l.get('name','') for l in i.get('labels',[])]]
    if not actionable:
        print('No open issues to process — agency is idle')
        sys.exit(0)
    issue = actionable[0]

issue_number = issue['number']
issue_title = issue['title']
issue_body = (issue.get('body') or '')[:2000]
print(f'Processing issue #{issue_number}: {issue_title[:60]}')

# 2. Call NVIDIA NIM
prompt = f"""You are an autonomous AI agent implementing a GitHub issue.

Issue #{issue_number}: {issue_title}

Issue body:
{issue_body}

Instructions:
1. Read the issue carefully.
2. Write a MINIMAL, ADDITIVE implementation.
3. Output the changes as JSON.

HARD RULES (a violation makes your output useless and it will be rejected):
- NEVER replace an existing file's whole content unless you reproduce ALL of it
  plus your additions. Prefer creating new files or appending.
- NEVER output empty, placeholder, or stub content (no "{{}}", "", "TODO", "...").
- For `action: "create"`, `content` must be the COMPLETE, valid file.
- If you cannot implement the issue safely and completely, output {{"summary":
  "cannot safely implement", "files": [], "changelog": ""}} — an empty PR is far
  better than a destructive one.

Format your response as JSON:
{{
  "summary": "Brief description",
  "files": [
    {{
      "path": "path/to/file.py",
      "action": "create",
      "content": "full file content"
    }}
  ],
  "changelog": "One-line changelog entry"
}}

Output only the JSON."""

brain_provider, brain_url, brain_key, brain_model = _select_brain()
if not brain_key:
    print('ERROR: no brain API key configured (set CEREBRAS_API_KEY / GROQ_API_KEY / NVIDIA_API_KEY)')
    sys.exit(1)
print(f'Calling brain: {brain_provider} / {brain_model} ...')
nim_resp = httpx.post(
    brain_url,
    headers={'Authorization': f'Bearer {brain_key}', 'Content-Type': 'application/json'},
    json={
        'model': brain_model,
        'messages': [
            {'role': 'system', 'content': 'You are an expert software engineer. Output only valid JSON. Make minimal, additive changes; never delete or empty existing code.'},
            {'role': 'user', 'content': prompt},
        ],
        'max_tokens': 4096,
        'temperature': 0.3,
        'stream': False,
    },
    timeout=120.0,
)
nim_resp.raise_for_status()
content = nim_resp.json()['choices'][0]['message']['content']
print(f'{brain_provider} response received')

# 3. Parse JSON (with repair fallback)
start = content.find('{')
end = content.rfind('}') + 1
if start < 0 or end <= start:
    print(f'ERROR: No JSON in response: {content[:300]}')
    sys.exit(1)

json_str = content[start:end]
result = None

try:
    result = json.loads(json_str)
except json.JSONDecodeError:
    print('Strict JSON failed — trying repair...')
    fixed = re.sub(r',\s*([}\]])', r'\1', json_str)
    try:
        result = json.loads(fixed)
    except json.JSONDecodeError:
        try:
            py_str = fixed.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            result = ast.literal_eval(py_str)
        except Exception:
            print('JSON repair failed — regex extraction')
            paths = re.findall(r'"path":\s*"([^"]+)"', json_str)
            contents = re.findall(r'"content":\s*"((?:[^"\\]|\\.)*)"', json_str)
            files = []
            for i, p in enumerate(paths):
                c = contents[i] if i < len(contents) else ''
                c = c.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                files.append({'path': p, 'action': 'create', 'content': c})
            sm = re.search(r'"summary":\s*"([^"]+)"', json_str)
            result = {'summary': sm.group(1) if sm else 'Regex extracted', 'files': files, 'changelog': 'Agent impl'}

if not result or not result.get('files'):
    # An empty file list is now a VALID "I decline to implement this safely"
    # response (see the prompt's HARD RULES). Exit cleanly without a PR — far
    # better than forcing a destructive change.
    print(f'Model declined / produced no files (summary: {(result or {}).get("summary","")!r}). No PR.')
    sys.exit(0)

print(f'Summary: {result.get("summary", "")}')
print(f'Files: {len(result.get("files", []))}')

# 4. Create branch (delete if exists)
branch = f'agent/issue-{issue_number}'
subprocess.run(['git', 'config', 'user.name', 'Autonomous Agency'], check=True)
subprocess.run(['git', 'config', 'user.email', 'agency@autonomous.ai'], check=True)
subprocess.run(['git', 'branch', '-D', branch], capture_output=True)
subprocess.run(['git', 'push', 'origin', '--delete', branch], capture_output=True)
subprocess.run(['git', 'checkout', '-b', branch], check=True)

# 5. Apply file changes — SLOP-GATE each write before touching disk.
def _abort(reason):
    print(f'SLOP-GATE: {reason}')
    print('Refusing to open a PR for this change. Exiting without a PR.')
    sys.exit(0)  # exit 0 — a declined slop PR is a success, not a CI failure

for file_info in result.get('files', []):
    path = file_info.get('path', '')
    file_content = file_info.get('content', '')
    # NIM sometimes returns content as a list of lines — convert to string
    if isinstance(file_content, list):
        file_content = '\n'.join(str(line) for line in file_content)
    elif not isinstance(file_content, str):
        file_content = str(file_content)
    if not path:
        continue
    p = pathlib.Path(path)
    # Gate 1: never empty/truncate an existing file (the #833 failure mode).
    if p.exists():
        try:
            old = p.read_text()
        except Exception:
            old = ''
        destructive, why = is_destructive_overwrite(old, file_content)
        if destructive:
            _abort(f'{path} — {why}')
    # Gate 2: generated Python must at least parse.
    if path.endswith('.py') and not python_parses(file_content):
        _abort(f'{path} — generated Python does not parse (syntax error)')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(file_content)
    print(f'  {file_info.get("action","create")}: {path}')

# 6. Add changelog
changelog = result.get('changelog', f'Implement issue #{issue_number}')
for cpath in ['CHANGELOG.md', 'docs/changelog.md']:
    try:
        text = pathlib.Path(cpath).read_text()
        marker = '## [Unreleased]\n\n### Added\n\n'
        if marker not in text:
            marker = '## [Unreleased]\n\n### Fixed\n\n'
        if marker in text:
            text = text.replace(marker, marker + f'- {changelog} (issue #{issue_number})\n\n', 1)
            pathlib.Path(cpath).write_text(text)
    except Exception:
        pass

# 7. Stage, then SLOP-GATE the aggregate diff before committing.
subprocess.run(['git', 'add', '-A'], check=True)
_numstat = subprocess.run(['git', 'diff', '--cached', '--numstat'], capture_output=True, text=True).stdout  # nosec
_add = _del = 0
for _line in _numstat.splitlines():
    _parts = _line.split('\t')
    if len(_parts) == 3 and _parts[0].isdigit() and _parts[1].isdigit():
        _add += int(_parts[0]); _del += int(_parts[1])
sloppy, why = diff_is_sloppy(_add, _del)
if sloppy:
    _abort(f'aggregate diff — {why}')

subprocess.run(['git', 'commit', '-m', f'feat: implement issue #{issue_number}\n\nGenerated by the Autonomous Agency ({brain_provider}).'], check=True)
subprocess.run(['git', 'push', 'origin', branch], check=True)

# 8. Create PR
pr_title = result.get('summary', f'Implement issue #{issue_number}')[:60]
subprocess.run([
    'gh', 'pr', 'create',
    '--title', f'feat: implement issue #{issue_number} — {pr_title}',
    '--body', f'## Autonomous Agency PR\n\nImplements issue #{issue_number} via the {brain_provider} brain ({brain_model}).\n\nPassed the slop-gate (no destructive overwrites, Python parses, not a net mass-deletion). Review before merge.\n\n🤖 Generated by autonomous agency cycle',
    '--base', 'master',
    '--head', branch,
], check=True)

print(f'PR created for issue #{issue_number}')
