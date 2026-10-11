import React from 'react';
import { useReportSub } from '../screenContext';
import ChatScreen from './ChatScreen';
import Spinner from '../components/ui/Spinner';

// Voice is heavy (LiveKit + Web Speech wiring) and most sessions never open
// it, so it stays code-split even though the hub itself is eager.
const SamVoiceScreen = React.lazy(() => import('./SamVoiceScreen'));

/**
 * AssistantHub — one conversational surface.
 *
 * Chat and SAM voice used to be two top-level nav destinations that both
 * talked to the same agents. They are now one place: voice is a mode toggle,
 * not a second app.
 */
export default function AssistantHub({ initialMode = 'chat' }) {
  const [mode, setMode] = React.useState(initialMode === 'voice' ? 'voice' : 'chat');
  useReportSub('assistant', mode);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '10px 16px 0' }}>
        <div style={{ display: 'inline-flex', gap: 2, padding: 3, borderRadius: 999, background: 'color-mix(in oklab, var(--ink) 4%, transparent)', border: '1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
          {[['chat', 'Type'], ['voice', 'Speak']].map(([id, label]) => (
            <button
              key={id}
              onClick={() => setMode(id)}
              style={{
                padding: '5px 14px', borderRadius: 999, fontSize:13, fontWeight: 700, cursor: 'pointer',
                border: 'none', fontFamily: 'var(--font-main)', transition: 'all 0.15s',
                background: mode === id ? 'color-mix(in oklab, var(--accent) 18%, transparent)' : 'transparent',
                color: mode === id ? 'var(--text-primary)' : 'var(--text-muted)',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>
        {mode === 'chat'
          ? <ChatScreen />
          : <React.Suspense fallback={<Spinner center label="Loading voice" />}><SamVoiceScreen /></React.Suspense>}
      </div>
    </div>
  );
}
