#!/usr/bin/env python3
"""Autonomous agent: fetch oldest open issue, generate implementation via NVIDIA NIM, create PR."""
import json, sys, os, subprocess, httpx, re, ast, pathlib

gh_token = os.environ['GH_TOKEN']
nvidia_key = os.environ['NVIDIA_API_KEY']
repo = os.environ['REPO']
issue_input = os.environ.get('ISSUE_NUMBER_INPUT', '')

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
2. Write a minimal implementation.
3. Output the changes as JSON.

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

print('Calling NVIDIA NIM...')
nim_resp = httpx.post(
    'https://integrate.api.nvidia.com/v1/chat/completions',
    headers={'Authorization': f'Bearer {nvidia_key}', 'Content-Type': 'application/json'},
    json={
        'model': 'nvidia/llama-3.3-nemotron-super-49b-v1',
        'messages': [
            {'role': 'system', 'content': 'You are an expert software engineer. Output only valid JSON.'},
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
print('NVIDIA NIM response received')

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
    print(f'ERROR: No files in result')
    sys.exit(1)

print(f'Summary: {result.get("summary", "")}')
print(f'Files: {len(result.get("files", []))}')

# 4. Create branch (delete if exists)
branch = f'agent/issue-{issue_number}'
subprocess.run(['git', 'config', 'user.name', 'Autonomous Agency'], check=True)
subprocess.run(['git', 'config', 'user.email', 'agency@autonomous.ai'], check=True)
subprocess.run(['git', 'branch', '-D', branch], capture_output=True)
subprocess.run(['git', 'push', 'origin', '--delete', branch], capture_output=True)
subprocess.run(['git', 'checkout', '-b', branch], check=True)

# 5. Apply file changes
for file_info in result.get('files', []):
    path = file_info.get('path', '')
    file_content = file_info.get('content', '')
    if path:
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(path).write_text(file_content)
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

# 7. Commit and push
subprocess.run(['git', 'add', '-A'], check=True)
subprocess.run(['git', 'commit', '-m', f'feat: implement issue #{issue_number}\n\nGenerated by Autonomous Agency using NVIDIA NIM.'], check=True)
subprocess.run(['git', 'push', 'origin', branch], check=True)

# 8. Create PR
pr_title = result.get('summary', f'Implement issue #{issue_number}')[:60]
subprocess.run([
    'gh', 'pr', 'create',
    '--title', f'feat: implement issue #{issue_number} — {pr_title}',
    '--body', f'## Autonomous Agency PR\n\nImplements issue #{issue_number} using NVIDIA NIM.\n\n🤖 Generated by autonomous agency cycle',
    '--base', 'master',
    '--head', branch,
], check=True)

print(f'PR created for issue #{issue_number}')
