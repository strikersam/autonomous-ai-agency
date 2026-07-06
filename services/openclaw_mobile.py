"""services/openclaw_mobile.py — Mobile web UI for iOS control of the agency.

Served at /mobile. Uses HTTP POST to /api/openclaw/command (more reliable on
Render free tier than WebSockets). Add to Home Screen from Safari for an
app-like experience.
"""
from __future__ import annotations

MOBILE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Agency">
<title>Agency Control</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; overscroll-behavior: none; }
#header { background: #1a1a1a; padding: 12px 16px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #2a2a2a; padding-top: max(12px, env(safe-area-inset-top)); }
#header h1 { font-size: 16px; font-weight: 600; }
#status-dot { width: 10px; height: 10px; border-radius: 50%; background: #666; transition: background 0.3s; }
#status-dot.connected { background: #4ade80; }
#status-dot.connecting { background: #fbbf24; }
#status-dot.error { background: #ef4444; }
#messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 8px; -webkit-overflow-scrolling: touch; }
.msg { max-width: 85%; padding: 10px 14px; border-radius: 16px; font-size: 14px; line-height: 1.4; white-space: pre-wrap; word-break: break-word; }
.msg.user { background: #2563eb; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
.msg.server { background: #1e293b; color: #e0e0e0; align-self: flex-start; border-bottom-left-radius: 4px; }
.msg.error { background: #7f1d1d; color: #fca5a5; align-self: flex-start; font-size: 13px; }
.msg.system { background: #1a2332; color: #93c5fd; align-self: center; font-size: 12px; font-style: italic; }
#input-bar { background: #1a1a1a; padding: 10px 12px; display: flex; gap: 8px; border-top: 1px solid #2a2a2a; padding-bottom: max(10px, env(safe-area-inset-bottom)); }
#msg-input { flex: 1; background: #0a0a0a; border: 1px solid #2a2a2a; border-radius: 20px; padding: 10px 16px; color: #e0e0e0; font-size: 15px; outline: none; }
#msg-input:focus { border-color: #2563eb; }
#send-btn { background: #2563eb; border: none; border-radius: 20px; padding: 10px 18px; color: white; font-size: 15px; font-weight: 600; cursor: pointer; transition: opacity 0.2s; }
#send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
#send-btn:active { opacity: 0.7; }
#connect-screen { position: fixed; inset: 0; background: #0a0a0a; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 20px; z-index: 100; }
#connect-screen.hidden { display: none; }
#connect-btn { background: #2563eb; border: none; border-radius: 12px; padding: 14px 32px; color: white; font-size: 17px; font-weight: 600; cursor: pointer; }
#connect-btn:active { opacity: 0.7; }
#connect-status { font-size: 14px; color: #888; text-align: center; padding: 0 30px; }
.quick-cmds { display: flex; flex-wrap: wrap; gap: 6px; padding: 8px 12px; background: #111; border-top: 1px solid #222; }
.quick-cmd { background: #1e293b; border: 1px solid #334155; border-radius: 14px; padding: 6px 12px; color: #93c5fd; font-size: 12px; cursor: pointer; }
.quick-cmd:active { background: #334155; }
</style>
</head>
<body>

<div id="connect-screen">
  <h2 style="font-size: 22px;">Agency Control</h2>
  <button id="connect-btn" onclick="connect()">Connect</button>
  <p id="connect-status">Tap to connect to the agency gateway.</p>
</div>

<div id="header">
  <h1>Agency Control</h1>
  <div id="status-dot" class="connecting"></div>
</div>

<div id="messages"></div>

<div class="quick-cmds">
  <div class="quick-cmd" onclick="sendQuick('status')">status</div>
  <div class="quick-cmd" onclick="sendQuick('list files')">list files</div>
  <div class="quick-cmd" onclick="sendQuick('read README.md')">read README</div>
  <div class="quick-cmd" onclick="sendQuick('ping')">ping</div>
</div>

<div id="input-bar">
  <input id="msg-input" type="text" placeholder="Send a command..." onkeydown="if(event.key==='Enter')send()">
  <button id="send-btn" onclick="send()" disabled>Send</button>
</div>

<script>
let token = null;
let connected = false;

async function connect() {
  document.getElementById('connect-status').textContent = 'Fetching pairing token...';
  try {
    const resp = await fetch('/api/openclaw/qr');
    const data = await resp.json();
    if (data.error) {
      document.getElementById('connect-status').textContent = data.error;
      return;
    }
    token = data.manual_entry.token;

    // Wake the service with a ping
    document.getElementById('connect-status').textContent = 'Waking service...';
    await fetch('/api/ping');

    // Test the command endpoint with a ping
    document.getElementById('connect-status').textContent = 'Connecting...';
    const testResp = await fetch('/api/openclaw/command', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({token: token, type: 'ping'})
    });
    const testData = await testResp.json();
    if (testData.type === 'pong') {
      connected = true;
      document.getElementById('connect-screen').classList.add('hidden');
      document.getElementById('status-dot').className = 'connected';
      document.getElementById('send-btn').disabled = false;
      addMessage('Connected to agency gateway.', 'system');
    } else {
      document.getElementById('connect-status').textContent = 'Connection test failed: ' + JSON.stringify(testData);
    }
  } catch (e) {
    document.getElementById('connect-status').textContent = 'Error: ' + e.message;
    document.getElementById('status-dot').className = 'error';
  }
}

async function send() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text || !connected) return;
  addMessage(text, 'user');
  input.value = '';
  await sendCommand({type: 'chat', message: text});
}

async function sendQuick(cmd) {
  if (!connected) return;
  addMessage(cmd, 'user');
  let body = {token: token};
  if (cmd === 'status') body.type = 'status';
  else if (cmd === 'list files') body.type = 'list_files', body.path = '.';
  else if (cmd === 'read README.md') body.type = 'read_file', body.path = 'README.md';
  else if (cmd === 'ping') body.type = 'ping';
  await sendCommand(body);
}

async function sendCommand(body) {
  try {
    const resp = await fetch('/api/openclaw/command', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const data = await resp.json();
    if (data.type === 'response') {
      addMessage(data.content, 'server');
    } else if (data.type === 'error') {
      addMessage(data.error, 'error');
    } else if (data.type === 'pong') {
      addMessage('pong', 'server');
    }
  } catch (e) {
    addMessage('Request failed: ' + e.message, 'error');
  }
}

function addMessage(text, type) {
  const div = document.createElement('div');
  div.className = 'msg ' + type;
  div.textContent = text;
  const container = document.getElementById('messages');
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}
</script>
</body>
</html>"""


def get_mobile_html() -> str:
    """Return the mobile web UI HTML."""
    return MOBILE_HTML
