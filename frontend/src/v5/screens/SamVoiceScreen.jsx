/* SamVoiceScreen.jsx — SAM (System Autonomy Manager) voice interface
  
  Iron Man-inspired voice command and control of the autonomous AI agency.
  Uses the browser's Web Speech API for STT/TTS (completely free, no API keys).
  Backs up with server-side gTTS for higher quality voice synthesis.
  
  Architecture (push-to-talk, default):
    Mic → MediaRecorder API → audio blob → Web Speech API STT → text
    → POST /agent/sam/chat → SAM response text
    → POST /agent/sam/speak → OGG audio → <audio> playback

  Architecture (live conversation, when LiveKit is configured):
    POST /agent/sam/livekit/token → livekit-client Room (WebRTC)
    → SAM worker (voice/sam_livekit_worker.py) joins the room
    → hands-free full-duplex voice (VAD + STT + LLM tools + TTS server-side).
    livekit-client is imported dynamically so the bundle/Jest never load it
    unless the user actually goes live.
*/
import React from 'react';
import API from '../../api';

// ── Audio visualizer ──────────────────────────────────────────────────────

function AudioVisualizer({ active, analyser }) {
  const canvasRef = React.useRef(null);
  const animRef = React.useRef(null);

  React.useEffect(() => {
    if (!active || !analyser) {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      return;
    }
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      animRef.current = requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const barCount = 48;
      const barWidth = (w / barCount) * 0.7;
      const gap = (w / barCount) * 0.3;
      const step = Math.floor(bufferLength / barCount);

      for (let i = 0; i < barCount; i++) {
        const val = dataArray[i * step] / 255;
        const barH = val * h * 0.9 + 2;
        const x = i * (barWidth + gap);
        const y = h - barH;
        const grad = ctx.createLinearGradient(x, y, x, h);
        grad.addColorStop(0, `rgba(93,162,255,${0.3 + val * 0.7})`);
        grad.addColorStop(1, `rgba(93,162,255,${0.1 + val * 0.3})`);
        ctx.fillStyle = grad;
        ctx.fillRect(x, y, barWidth, barH);
      }
    };
    draw();
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [active, analyser]);

  return (
    <canvas ref={canvasRef} width={280} height={64}
      style={{ display: 'block', margin: '12px auto', borderRadius: 12,
        background: 'rgba(93,162,255,0.03)', opacity: active ? 1 : 0.3,
        transition: 'opacity 0.3s' }} />
  );
}

// ── SAM avatar ring ───────────────────────────────────────────────────────

function SamRing({ state }) {
  const colors = {
    idle: 'rgba(93,162,255,0.15)',
    listening: 'rgba(93,162,255,0.8)',
    thinking: 'rgba(255,189,102,0.8)',
    speaking: 'rgba(70,217,164,0.8)',
    error: 'rgba(255,107,125,0.8)',
  };
  const scale = state === 'listening' ? 1.08 : state === 'thinking' ? 1.04 : 1;
  const pulseAnim = state === 'listening' ? 'samPulse 1.5s ease-in-out infinite' :
                    state === 'thinking' ? 'samPulse 2.5s ease-in-out infinite' : 'none';
  return (
    <div style={{
      width: 120, height: 120, borderRadius: '50%', margin: '0 auto 16px',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: colors[state] || colors.idle,
      transform: `scale(${scale})`, transition: 'all 0.4s ease',
      animation: pulseAnim, position: 'relative',
    }}>
      <div style={{
        width: 96, height: 96, borderRadius: '50%',
        background: 'radial-gradient(circle at 30% 30%, #1a2a4a, #0a1224)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: '2px solid rgba(93,162,255,0.3)',
      }}>
        <span style={{ fontSize: 28, fontWeight: 900, color: '#5da2ff',
          fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>SAM</span>
      </div>
      {state === 'listening' && (
        <div style={{ position: 'absolute', inset: -4, borderRadius: '50%',
          border: '2px solid rgba(93,162,255,0.5)', animation: 'samRing 1.5s ease-out infinite' }} />
      )}
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────

export default function SamVoiceScreen() {
  const [state, setState] = React.useState('idle'); // idle | listening | thinking | speaking | error
  const [transcript, setTranscript] = React.useState('');
  const [response, setResponse] = React.useState('');
  const [history, setHistory] = React.useState([]);
  const [error, setError] = React.useState(null);
  const [samStatus, setSamStatus] = React.useState(null);
  const [liveAvailable, setLiveAvailable] = React.useState(false);
  const [liveState, setLiveState] = React.useState('off'); // off | connecting | live

  const mediaRecorderRef = React.useRef(null);
  const audioChunksRef = React.useRef([]);
  const analyserRef = React.useRef(null);
  const streamRef = React.useRef(null);
  const sessionIdRef = React.useRef('voice_' + Date.now().toString(36));
  const mountedRef = React.useRef(true);
  const roomRef = React.useRef(null);
  const liveAudioElsRef = React.useRef([]);

  React.useEffect(() => () => {
    mountedRef.current = false;
    // Clean up mic on unmount — prevents stuck mic if user navigates away while recording
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    // Leave the live room on unmount — prevents a stuck WebRTC session
    if (roomRef.current) {
      try { roomRef.current.disconnect(); } catch (e) { /* already gone */ }
      roomRef.current = null;
    }
    liveAudioElsRef.current.forEach(({ el }) => el.remove());
    liveAudioElsRef.current = [];
  }, []);

  // Check SAM status + LiveKit availability on mount
  React.useEffect(() => {
    API.get('/agent/sam/status').then(r => {
      if (mountedRef.current) setSamStatus(r.data);
    }).catch(() => {});
    API.get('/agent/sam/livekit/status').then(r => {
      if (mountedRef.current) setLiveAvailable(!!r.data?.configured);
    }).catch(() => {});
  }, []);

  // ── Live conversation (LiveKit full-duplex) ────────────────────────────

  const cleanupLive = React.useCallback(() => {
    liveAudioElsRef.current.forEach(({ track, el }) => {
      try { track.detach(el); } catch (e) { /* best effort */ }
      el.remove();
    });
    liveAudioElsRef.current = [];
    roomRef.current = null;
    if (mountedRef.current) {
      setLiveState('off');
      setState('idle');
    }
  }, []);

  const startLive = async () => {
    setError(null);
    setLiveState('connecting');
    try {
      const tokenRes = await API.post('/agent/sam/livekit/token', {});
      const { url, token } = tokenRes.data || {};
      if (!url || !token) throw new Error('LiveKit token unavailable');

      const lk = await import('livekit-client');
      const room = new lk.Room();
      roomRef.current = room;

      room.on(lk.RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === lk.Track.Kind.Audio) {
          const el = track.attach();
          el.style.display = 'none';
          document.body.appendChild(el);
          liveAudioElsRef.current.push({ track, el });
        }
      });

      room.on(lk.RoomEvent.ActiveSpeakersChanged, (speakers) => {
        if (!mountedRef.current || roomRef.current !== room) return;
        const agentSpeaking = speakers.some(p => p !== room.localParticipant);
        const meSpeaking = speakers.some(p => p === room.localParticipant);
        setState(agentSpeaking ? 'speaking' : meSpeaking ? 'listening' : 'idle');
      });

      room.on(lk.RoomEvent.Disconnected, () => cleanupLive());

      // Live captions: the agent publishes transcriptions as text streams
      try {
        room.registerTextStreamHandler('lk.transcription', async (reader, participantInfo) => {
          const text = await reader.readAll();
          if (!text || !mountedRef.current || roomRef.current !== room) return;
          const isMe = participantInfo?.identity === room.localParticipant?.identity;
          if (isMe) setTranscript(text); else setResponse(text);
          setHistory(h => [...h.slice(-20), { type: isMe ? 'user' : 'sam', text }]);
        });
      } catch (e) { /* captions are optional — older livekit-client */ }

      await room.connect(url, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      if (!mountedRef.current) { room.disconnect(); return; }
      setLiveState('live');
      setState('idle');
    } catch (err) {
      if (roomRef.current) {
        try { roomRef.current.disconnect(); } catch (e) { /* not connected */ }
      }
      cleanupLive();
      if (mountedRef.current) {
        setError(err?.response?.data?.detail || err?.message || 'Live voice failed');
      }
    }
  };

  const stopLive = () => {
    if (roomRef.current) {
      roomRef.current.disconnect(); // Disconnected event → cleanupLive()
    } else {
      cleanupLive();
    }
  };

  // ── Start listening ────────────────────────────────────────────────────

  const startListening = async () => {
    setError(null);
    setTranscript('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Set up audio analyser
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Start recording
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => handleRecordingStop();

      recorder.start(1000); // timeslice=1000ms → flush data every second (prevents buffer cutoff)
      setState('listening');

      // Auto-stop after 30 seconds (was 8 — too short for natural speech)
      setTimeout(() => {
        if (mediaRecorderRef.current?.state === 'recording') {
          mediaRecorderRef.current.stop();
        }
      }, 30000);

    } catch (err) {
      setError('Microphone access denied. Please allow microphone permissions.');
      setState('error');
    }
  };

  // ── Stop listening manually ────────────────────────────────────────────

  const stopListening = () => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  // ── Process recording ──────────────────────────────────────────────────

  const handleRecordingStop = async () => {
    // Clean up stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    analyserRef.current = null;

    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    if (audioBlob.size < 100) {
      setState('idle');
      return;
    }

    setState('thinking');

    try {
      // Step 1: Transcribe using Web Speech API (free, built into Chrome)
      const text = await transcribeWithWebSpeech(audioBlob);
      if (!text || !mountedRef.current) { setState('idle'); return; }

      setTranscript(text);

      // Step 2: Send to SAM backend for processing. SAM's own backend path
      // bounds itself to ~28s (context + LLM timeouts) and always resolves
      // with a fallback reply — this axios timeout is only a backstop for a
      // network/proxy-level stall, so it's set well above that.
      const chatRes = await API.post('/agent/sam/chat', {
        text,
        session_id: sessionIdRef.current,
      }, { timeout: 45000 });
      const samText = chatRes.data?.text || '';

      if (!mountedRef.current) return;

      setResponse(samText);
      setState('speaking');
      setHistory(h => [...h.slice(-20), { type: 'user', text },
                       { type: 'sam', text: samText }]);

      // Step 3: Synthesise SAM's voice. Bounded so a slow/stalled TTS call
      // falls back to browser SpeechSynthesis instead of leaving SAM silent.
      try {
        const speakRes = await API.post('/agent/sam/speak', { text: samText }, { timeout: 35000 });
        const audioB64 = speakRes.data?.audio_b64;
        if (audioB64) {
          const audio = new Audio('data:audio/ogg;base64,' + audioB64);
          audio.onended = () => { if (mountedRef.current) setState('idle'); };
          audio.play();
          return;
        }
      } catch (e) {
        // Fall back to browser SpeechSynthesis
        trySpeakBrowser(samText);
      }

      setTimeout(() => { if (mountedRef.current && state === 'speaking') setState('idle'); }, 3000);

    } catch (err) {
      if (mountedRef.current) {
        setError(err?.message || 'Voice processing failed');
        setState('error');
      }
    }
  };

  // ── Web Speech API transcription (free, browser-native) ────────────────

  const transcribeWithWebSpeech = (audioBlob) => {
    return new Promise((resolve, reject) => {
      // Try browser SpeechRecognition first (works offline in Chrome)
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        // Fallback: send audio to backend STT
        return transcribeWithBackend(audioBlob).then(resolve).catch(reject);
      }

      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.continuous = false;

      let resolved = false;
      recognition.onresult = (event) => {
        resolved = true;
        const text = event.results[0][0].transcript;
        resolve(text);
      };
      recognition.onerror = (event) => {
        if (!resolved) {
          // Fall back to backend STT on browser STT failure
          transcribeWithBackend(audioBlob).then(resolve).catch(reject);
        }
      };
      recognition.onend = () => {
        if (!resolved) resolve('');
      };

      recognition.start();
    });
  };

  // ── Backend STT fallback ───────────────────────────────────────────────

  const transcribeWithBackend = async (audioBlob) => {
    const reader = new FileReader();
    return new Promise((resolve, reject) => {
      reader.onload = async () => {
        try {
          const b64 = reader.result.split(',')[1];
          const res = await API.post('/agent/voice/transcribe', {
            audio_b64: b64,
            duration_hint_s: 5,
          });
          resolve(res.data?.text || '');
        } catch (e) {
          reject(e);
        }
      };
      reader.onerror = () => reject(new Error('Audio encoding failed'));
      reader.readAsDataURL(audioBlob);
    });
  };

  // ── Browser SpeechSynthesis fallback ───────────────────────────────────

  const trySpeakBrowser = (text) => {
    if (!window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.onend = () => { if (mountedRef.current) setState('idle'); };
    window.speechSynthesis.speak(utterance);
  };

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '20px 16px 48px', maxWidth: 600, margin: '0 auto' }}
         className="scrollbar-hide">
      <style>{`
        @keyframes samPulse {
          0%,100% { box-shadow: 0 0 0 0 rgba(93,162,255,0.3); }
          50% { box-shadow: 0 0 0 16px rgba(93,162,255,0); }
        }
        @keyframes samRing {
          0% { transform: scale(1); opacity: 0.8; }
          100% { transform: scale(1.3); opacity: 0; }
        }
      `}</style>

      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)',
        letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 6 }}>
        Voice Command
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 10, marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#fff',
            letterSpacing: '-0.04em', lineHeight: 1.1, marginBottom: 4 }}>SAM</h1>
          <p style={{ fontSize: 14, color: 'var(--text-tertiary)', lineHeight: 1.5, maxWidth: 400 }}>
            System Autonomy Manager — voice command and control of your agency.
            {samStatus && <span style={{ color: 'var(--text-muted)', marginLeft: 8 }}>
              · {samStatus.active_sessions || 0} sessions
            </span>}
          </p>
        </div>
      </div>

      {/* SAM avatar + mic button */}
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <SamRing state={state} />

        <AudioVisualizer active={state === 'listening'} analyser={analyserRef.current} />

        <button
          onClick={state === 'listening' ? stopListening : startListening}
          disabled={state === 'thinking' || liveState !== 'off'}
          style={{
            width: 64, height: 64, borderRadius: '50%', border: 'none', cursor: 'pointer',
            background: state === 'listening'
              ? 'linear-gradient(135deg, #ff6b7d, #e05567)'
              : state === 'thinking'
              ? 'linear-gradient(135deg, #ffbd66, #e0a050)'
              : 'linear-gradient(135deg, #5da2ff, #4a8ae0)',
            boxShadow: state === 'listening'
              ? '0 0 24px rgba(255,107,125,0.5)'
              : '0 4px 20px rgba(93,162,255,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.3s ease', margin: '0 auto',
          }}>
          {state === 'listening' ? (
            <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.5}
              strokeLinecap="round"><rect x={6} y={6} width={12} height={12} rx={1} /></svg>
          ) : state === 'thinking' ? (
            <div style={{ width: 20, height: 20, border: '2px solid rgba(255,255,255,0.3)',
              borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
          ) : (
            <svg width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.5}
              strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1={12} y1={19} x2={12} y2={23} />
              <line x1={8} y1={23} x2={16} y2={23} />
            </svg>
          )}
        </button>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
          {liveState === 'live' && (state === 'speaking' ? 'SAM is speaking...' :
            state === 'listening' ? 'Listening...' : 'Live — just talk')}
          {liveState === 'connecting' && 'Connecting live session...'}
          {liveState === 'off' && <>
            {state === 'idle' && 'Tap to speak'}
            {state === 'listening' && 'Listening... tap to stop'}
            {state === 'thinking' && 'Processing...'}
            {state === 'speaking' && 'SAM is speaking...'}
            {state === 'error' && 'Error — tap to retry'}
          </>}
        </div>

        {/* Live conversation (LiveKit) — only offered when the backend is configured */}
        {liveAvailable && (
          <button
            onClick={liveState === 'live' ? stopLive : startLive}
            disabled={liveState === 'connecting' || state === 'listening'}
            style={{
              marginTop: 14, padding: '10px 18px', borderRadius: 999, cursor: 'pointer',
              border: liveState === 'live'
                ? '1px solid rgba(255,107,125,0.4)' : '1px solid rgba(70,217,164,0.35)',
              background: liveState === 'live'
                ? 'rgba(255,107,125,0.12)' : 'rgba(70,217,164,0.08)',
              color: liveState === 'live' ? '#ff6b7d' : '#46d9a4',
              fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-mono)',
              letterSpacing: '0.06em', transition: 'all 0.3s ease',
              opacity: liveState === 'connecting' ? 0.6 : 1,
            }}>
            {liveState === 'off' && '● Start live conversation'}
            {liveState === 'connecting' && '● Connecting...'}
            {liveState === 'live' && '■ End live conversation'}
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div style={{ padding: '10px 14px', borderRadius: 10, marginBottom: 14,
          background: 'rgba(255,107,125,0.08)', border: '1px solid rgba(255,107,125,0.25)',
          color: '#ff6b7d', fontSize: 12 }}>{error}</div>
      )}

      {/* Current transcript */}
      {transcript && (
        <div style={{ padding: '10px 14px', borderRadius: 10, marginBottom: 8,
          background: 'rgba(93,162,255,0.05)', border: '1px solid rgba(93,162,255,0.15)' }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
            textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>You said</div>
          <div style={{ fontSize: 14, color: 'var(--text-primary)' }}>{transcript}</div>
        </div>
      )}

      {/* SAM response */}
      {response && (
        <div style={{ padding: '10px 14px', borderRadius: 10, marginBottom: 14,
          background: 'rgba(70,217,164,0.05)', border: '1px solid rgba(70,217,164,0.15)' }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
            textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>SAM</div>
          <div style={{ fontSize: 14, color: '#46d9a4' }}>{response}</div>
        </div>
      )}

      {/* Conversation history */}
      {history.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
            textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
            Recent conversation
          </div>
          {history.slice(-6).map((item, i) => (
            <div key={i} style={{ padding: '6px 10px', marginBottom: 4, borderRadius: 8, fontSize: 12,
              background: item.type === 'user' ? 'rgba(93,162,255,0.03)' : 'rgba(70,217,164,0.03)',
              borderLeft: `3px solid ${item.type === 'user' ? '#5da2ff' : '#46d9a4'}` }}>
              <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
                fontSize: 9, marginRight: 6 }}>
                {item.type === 'user' ? 'YOU' : 'SAM'}
              </span>
              <span style={{ color: item.type === 'user' ? 'var(--text-secondary)' : '#46d9a4' }}>
                {item.text}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
