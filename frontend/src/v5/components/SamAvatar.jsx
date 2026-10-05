import React from 'react';
import * as api from '../../api';
import { getScreenPath } from '../screenContext';

// SamAvatar.jsx — SAM as a floating, slightly unhinged little creature.
//
// It is the same SAM as the Assistant → Voice screen: it talks to
// /agent/sam/chat, so alerts, delegation ("create a task to …") and CEO
// triage all run through agent/sam.py. Visibility is server-decided
// (GET /agent/sam/avatar ← SAM_AVATAR_ENABLED / SAM_AVATAR_SCOPE controls).

const SESSION_ID = 'sam-avatar';
const CONFIG_RECHECK_MS = 60000;
const ADMIN_CHIPS = ['Brief me', 'Pick up portfolio work', 'Triage the queue', 'Fix the alerts'];
const USER_CHIPS = ['What alerts do I have?'];

function useEyeTracking(ref) {
  const [look, setLook] = React.useState({ x: 0, y: 0 });
  React.useEffect(() => {
    const onMove = (e) => {
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const dx = e.clientX - (r.left + r.width / 2);
      const dy = e.clientY - (r.top + r.height / 2);
      const d = Math.max(1, Math.hypot(dx, dy));
      setLook({ x: (dx / d) * Math.min(4, d / 30), y: (dy / d) * Math.min(4, d / 30) });
    };
    window.addEventListener('pointermove', onMove);
    return () => window.removeEventListener('pointermove', onMove);
  }, [ref]);
  return look;
}

// The creature. `mood` is idle | thinking | talking.
export function SamFace({ mood = 'idle', look = { x: 0, y: 0 }, size = 64 }) {
  const thinking = mood === 'thinking';
  const talking = mood === 'talking';
  const lx = thinking ? 0 : look.x;
  const ly = thinking ? -2 : look.y;
  return (
    <svg width={size} height={size} viewBox="-4 -8 108 108" aria-hidden="true" className={`sam-face sam-${mood}`}>
      <defs>
        <radialGradient id="samBody" cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#ffe36e" />
          <stop offset="45%" stopColor="#ff6fd8" />
          <stop offset="100%" stopColor="#7b5cff" />
        </radialGradient>
      </defs>
      {/* wild antenna with a bouncing spark */}
      <path d="M50 18 Q44 6 54 2" stroke="#7b5cff" strokeWidth="3" fill="none" strokeLinecap="round" />
      <circle className="sam-spark" cx="54" cy="3" r="4.5" fill="#3df2c6" />
      {/* hair tufts */}
      <path d="M30 22 L26 10 L36 19 Z M68 20 L76 9 L72 23 Z" fill="#ff6fd8" />
      {/* body */}
      <path className="sam-body" fill="url(#samBody)"
        d="M50 16 C76 14 92 34 90 58 C88 82 70 94 50 93 C28 94 10 82 10 58 C9 34 25 17 50 16 Z" />
      {/* cheeks */}
      <ellipse cx="25" cy="66" rx="7" ry="4" fill="#ff3d7f" opacity="0.45" />
      <ellipse cx="76" cy="66" rx="7" ry="4" fill="#ff3d7f" opacity="0.45" />
      {/* mismatched googly eyes */}
      <g className="sam-eyes">
        <circle cx="35" cy="46" r="13" fill="#fff" stroke="#2a1655" strokeWidth="2" />
        <circle cx="67" cy="44" r="9.5" fill="#fff" stroke="#2a1655" strokeWidth="2" />
        <g className={thinking ? 'sam-swirl-l' : ''}>
          <circle cx={35 + lx * 1.4} cy={46 + ly * 1.4} r="6" fill="#1b0f3a" />
          <circle cx={33 + lx * 1.4} cy={44 + ly * 1.4} r="2" fill="#fff" />
        </g>
        <g className={thinking ? 'sam-swirl-r' : ''}>
          <circle cx={67 + lx} cy={44 + ly} r="4.5" fill="#1b0f3a" />
          <circle cx={65.5 + lx} cy={42.5 + ly} r="1.5" fill="#fff" />
        </g>
        <rect className="sam-lid" x="20" y="30" width="62" height="0" fill="#ff8fe0" />
      </g>
      {/* mouth: grin with one tooth, opens when talking */}
      {talking ? (
        <ellipse className="sam-mouth-talk" cx="52" cy="74" rx="9" ry="7" fill="#2a1655" />
      ) : (
        <g>
          <path d="M37 70 Q52 84 67 70" stroke="#2a1655" strokeWidth="3" fill="#2a1655" strokeLinecap="round" />
          <rect x="49" y="71" width="5" height="5" rx="1" fill="#fff" />
          <path d="M55 77 Q58 83 61 77" fill="#ff5c8a" />
        </g>
      )}
    </svg>
  );
}

function speak(text) {
  try {
    if (!window.speechSynthesis || !text) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.pitch = 1.6;
    u.rate = 1.08;
    window.speechSynthesis.speak(u);
  } catch { /* voice is a bonus, never an error */ }
}

function useSpeechInput(onFinal) {
  const recRef = React.useRef(null);
  const [listening, setListening] = React.useState(false);
  const Rec = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
  const start = React.useCallback(() => {
    if (!Rec || listening) return;
    const rec = new Rec();
    rec.lang = 'en-US';
    rec.interimResults = false;
    rec.onresult = (e) => onFinal(e.results?.[0]?.[0]?.transcript || '');
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  }, [Rec, listening, onFinal]);
  React.useEffect(() => () => { try { recRef.current?.abort(); } catch { /* noop */ } }, []);
  return { supported: !!Rec, listening, start };
}

function SamPanel({ canOrchestrate, onClose, onNavigate, setMood }) {
  const [history, setHistory] = React.useState([
    { who: 'sam', text: canOrchestrate
      ? "Hey Commander! I run the agency with you. Tell me what to do — or say 'create a task to …'."
      : "Hi! I'm SAM. Ask me about the agency or your alerts." },
  ]);
  const [input, setInput] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [voiceOn, setVoiceOn] = React.useState(false);
  const scrollRef = React.useRef(null);
  const mountedRef = React.useRef(true);
  React.useEffect(() => () => { mountedRef.current = false; }, []);
  React.useEffect(() => { scrollRef.current?.scrollTo?.(0, 1e6); }, [history]);

  const send = React.useCallback(async (raw) => {
    const text = (raw || '').trim();
    if (!text || busy) return;
    setInput('');
    setHistory(h => [...h.slice(-30), { who: 'me', text }]);
    setBusy(true);
    setMood('thinking');
    let reply;
    let confirm = false;
    try {
      const { data } = await api.samChat(text, SESSION_ID, getScreenPath());
      reply = data?.text || '…';
      confirm = !!data?.needs_confirmation;
    } catch {
      reply = "Ack, I lost the connection. Try me again in a sec.";
    }
    if (!mountedRef.current) return;
    setHistory(h => [...h.slice(-30).map(m => ({ ...m, confirm: false })), { who: 'sam', text: reply, confirm }]);
    setBusy(false);
    setMood('talking');
    if (voiceOn) speak(reply);
    setTimeout(() => mountedRef.current && setMood('idle'), Math.min(6000, 900 + reply.length * 35));
  }, [busy, setMood, voiceOn]);

  const mic = useSpeechInput(send);
  const chips = canOrchestrate ? ADMIN_CHIPS : USER_CHIPS;

  return (
    <div className="sam-panel" role="dialog" aria-label="Chat with SAM">
      <div className="sam-panel-head">
        <strong>SAM</strong>
        <span className="sam-sub">{canOrchestrate ? 'running the agency' : 'agency assistant'}</span>
        <button type="button" className="sam-icon" onClick={() => setVoiceOn(v => !v)}
          aria-label={voiceOn ? 'Mute SAM' : 'Let SAM speak'} title={voiceOn ? 'Mute' : 'Speak replies'}>
          {voiceOn ? '🔊' : '🔈'}
        </button>
        <button type="button" className="sam-icon" onClick={() => { onClose(); onNavigate?.('sam'); }}
          aria-label="Open full voice mode" title="Full voice mode">🎙️</button>
        <button type="button" className="sam-icon" onClick={onClose} aria-label="Close SAM">✕</button>
      </div>
      <div className="sam-log" ref={scrollRef}>
        {history.map((m, i) => (
          <div key={i} className={`sam-msg sam-msg-${m.who}`}>
            {m.text}
            {m.confirm && (
              <div className="sam-confirm">
                <button type="button" className="sam-confirm-yes" disabled={busy} onClick={() => send('confirm')}>Confirm</button>
                <button type="button" className="sam-confirm-no" disabled={busy} onClick={() => send('cancel')}>Cancel</button>
              </div>
            )}
          </div>
        ))}
        {busy && <div className="sam-msg sam-msg-sam sam-dots"><span/><span/><span/></div>}
      </div>
      <div className="sam-chips">
        {chips.map(c => (
          <button type="button" key={c} disabled={busy} onClick={() => send(c)}>{c}</button>
        ))}
      </div>
      <form className="sam-input" onSubmit={e => { e.preventDefault(); send(input); }}>
        <input value={input} onChange={e => setInput(e.target.value)} maxLength={2000}
          placeholder={canOrchestrate ? 'Create a task to…' : 'Ask SAM…'} aria-label="Message SAM" />
        {mic.supported && (
          <button type="button" className={`sam-icon ${mic.listening ? 'sam-hot' : ''}`} onClick={mic.start}
            aria-label="Speak to SAM" disabled={busy}>🎤</button>
        )}
        <button type="submit" className="sam-send" disabled={busy || !input.trim()}>Go</button>
      </form>
    </div>
  );
}

export default function SamAvatar({ onNavigate }) {
  const [config, setConfig] = React.useState(null);
  const [open, setOpen] = React.useState(false);
  const [mood, setMood] = React.useState('idle');
  const btnRef = React.useRef(null);
  const look = useEyeTracking(btnRef);

  // Re-checked on focus and every minute, so flipping the Platform Control
  // shows or hides SAM without a page reload. A failed check keeps the last
  // known state rather than making SAM flicker away on a network blip.
  React.useEffect(() => {
    let alive = true;
    const load = () => Promise.resolve()
      .then(() => api.samAvatarConfig())
      .then(r => { if (alive) setConfig(r?.data || null); })
      .catch(() => {});
    const onVisible = () => { if (document.visibilityState === 'visible') load(); };
    load();
    window.addEventListener('focus', load);
    document.addEventListener('visibilitychange', onVisible);
    const timer = setInterval(load, CONFIG_RECHECK_MS);
    return () => {
      alive = false;
      window.removeEventListener('focus', load);
      document.removeEventListener('visibilitychange', onVisible);
      clearInterval(timer);
    };
  }, []);

  if (!config?.enabled) return null;

  return (
    <div className="sam-avatar-root">
      <style>{SAM_CSS}</style>
      {open && (
        <SamPanel canOrchestrate={!!config.can_orchestrate} onClose={() => setOpen(false)}
          onNavigate={onNavigate} setMood={setMood} />
      )}
      <button ref={btnRef} type="button" className={`sam-fab ${open ? 'sam-open' : ''}`}
        onClick={() => setOpen(o => !o)} aria-label={open ? 'Close SAM' : 'Open SAM'} aria-expanded={open}>
        <SamFace mood={mood} look={look} />
      </button>
    </div>
  );
}

const SAM_CSS = `
.sam-fab { position:fixed; z-index:120; left:12px; bottom:calc(env(safe-area-inset-bottom,0px) + 84px);
  width:68px; height:68px; padding:0; border:none; background:transparent; cursor:pointer;
  filter:drop-shadow(0 6px 14px rgba(123,92,255,0.55)); animation:samBob 3.2s ease-in-out infinite;
  -webkit-tap-highlight-color:transparent; }
.sam-fab:hover { animation:samWiggle .6s ease-in-out infinite; }
.sam-fab:focus-visible { outline:2px solid #3df2c6; outline-offset:3px; border-radius:50%; }
.sam-fab.sam-open { transform:scale(1.08); }
.sam-panel { position:fixed; z-index:121; left:12px; bottom:calc(env(safe-area-inset-bottom,0px) + 160px);
  width:min(360px, calc(100vw - 24px)); max-height:min(520px, calc(100dvh - 240px)); display:flex; flex-direction:column;
  background:rgba(14,10,28,0.97); border:1px solid rgba(255,111,216,0.35); border-radius:18px;
  box-shadow:0 18px 50px rgba(0,0,0,0.55), 0 0 0 4px rgba(123,92,255,0.12); color:#f4ecff;
  font-size:13px; animation:samPop .22s cubic-bezier(.3,1.6,.5,1); overflow:hidden; }
@media (min-width:1024px) {
  .sam-fab { left:268px; bottom:20px; }
  .sam-panel { left:268px; bottom:96px; max-height:min(560px, calc(100dvh - 140px)); }
}
.sam-panel-head { display:flex; align-items:center; gap:6px; padding:10px 12px;
  background:linear-gradient(90deg, rgba(255,111,216,0.18), rgba(61,242,198,0.12)); }
.sam-panel-head strong { font-size:15px; letter-spacing:.06em; }
.sam-sub { flex:1; font-size:10px; opacity:.7; text-transform:uppercase; letter-spacing:.1em; }
.sam-icon { background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); color:inherit;
  border-radius:10px; min-width:32px; height:32px; cursor:pointer; font-size:14px; }
.sam-icon.sam-hot { background:rgba(255,61,127,0.35); animation:samPulse 1s infinite; }
.sam-log { flex:1; overflow-y:auto; padding:10px 12px; display:flex; flex-direction:column; gap:8px; min-height:120px; }
.sam-msg { max-width:85%; padding:8px 11px; border-radius:14px; line-height:1.4; white-space:pre-wrap; word-break:break-word; }
.sam-msg-sam { align-self:flex-start; background:rgba(123,92,255,0.22); border-bottom-left-radius:4px; }
.sam-msg-me { align-self:flex-end; background:rgba(61,242,198,0.18); border-bottom-right-radius:4px; }
.sam-confirm { display:flex; gap:8px; margin-top:8px; }
.sam-confirm button { border-radius:8px; padding:5px 12px; font-size:12px; font-weight:700; cursor:pointer; }
.sam-confirm-yes { background:#ffbd66; color:#1a1004; border:none; }
.sam-confirm-no { background:transparent; color:#f4ecff; border:1px solid rgba(255,255,255,0.3); }
.sam-dots { display:flex; gap:4px; }
.sam-dots span { width:6px; height:6px; border-radius:50%; background:#ff6fd8; animation:samPulse 1s infinite; }
.sam-dots span:nth-child(2) { animation-delay:.15s } .sam-dots span:nth-child(3) { animation-delay:.3s }
.sam-chips { display:flex; gap:6px; padding:0 12px 8px; overflow-x:auto; }
.sam-chips button { flex-shrink:0; background:rgba(255,111,216,0.12); border:1px solid rgba(255,111,216,0.35);
  color:#ffd6f4; border-radius:999px; padding:5px 10px; font-size:11px; cursor:pointer; }
.sam-input { display:flex; gap:6px; padding:10px 12px; border-top:1px solid rgba(255,255,255,0.08); }
.sam-input input { flex:1; min-width:0; background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.14);
  color:inherit; border-radius:10px; padding:8px 10px; font-size:16px; }
.sam-send { background:linear-gradient(135deg,#ff6fd8,#7b5cff); color:#fff; border:none; border-radius:10px;
  padding:0 14px; font-weight:700; cursor:pointer; }
.sam-send:disabled, .sam-chips button:disabled { opacity:.45; cursor:default; }
.sam-face .sam-spark { animation:samSpark 1.4s ease-in-out infinite; transform-box:fill-box; transform-origin:center; }
.sam-face .sam-body { animation:samSquish 2.4s ease-in-out infinite; transform-box:fill-box; transform-origin:50% 100%; }
.sam-face .sam-lid { animation:samBlink 5s infinite; }
.sam-thinking .sam-spark { animation:samSpark .35s linear infinite; fill:#ffe36e; }
.sam-thinking .sam-swirl-l { animation:samSpin .9s linear infinite; transform-box:fill-box; transform-origin:center; }
.sam-thinking .sam-swirl-r { animation:samSpin .7s linear infinite reverse; transform-box:fill-box; transform-origin:center; }
.sam-talking .sam-mouth-talk { animation:samTalk .18s ease-in-out infinite alternate; transform-box:fill-box; transform-origin:center; }
@keyframes samBob { 0%,100%{transform:translateY(0) rotate(-3deg)} 50%{transform:translateY(-6px) rotate(3deg)} }
@keyframes samWiggle { 0%,100%{transform:rotate(-8deg) scale(1.05)} 50%{transform:rotate(8deg) scale(1.1)} }
@keyframes samSquish { 0%,100%{transform:scale(1,1)} 50%{transform:scale(1.04,.96)} }
@keyframes samSpark { 0%,100%{transform:translateY(0) scale(1)} 50%{transform:translateY(-3px) scale(1.25)} }
@keyframes samBlink { 0%,94%,100%{height:0} 96%{height:30px} }
@keyframes samSpin { to { transform:rotate(360deg) } }
@keyframes samTalk { from{transform:scaleY(.35)} to{transform:scaleY(1)} }
@keyframes samPop { from{opacity:0; transform:translateY(12px) scale(.92)} to{opacity:1; transform:none} }
@keyframes samPulse { 0%,100%{opacity:1} 50%{opacity:.35} }
@media (prefers-reduced-motion: reduce) {
  .sam-fab, .sam-fab:hover, .sam-face *, .sam-panel { animation:none !important; }
}
`;
