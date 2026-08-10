/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import { useSafeData } from '../hooks/useSafeData';
import * as api from '../../api';
import McpCard from '../components/McpCard';
import BrainCard from '../components/BrainCard';
import LocalBrainToggleCard from '../components/LocalBrainToggleCard';
import ProviderHealthToggleCard from '../components/ProviderHealthToggleCard';
import ProviderConsole from '../components/ProviderConsole';


// providers.jsx — V5.0: All providers + Ollama model management + MCP servers tab

// Reference catalogue of popular integrations. These are typically configured via
// environment variables on the server; the live, editable providers come from the
// backend (GET /api/providers). The catalogue doubles as quick-fill templates.
const ALL_PROVIDERS = [
  { id:'nvidia-nim',   name:'NVIDIA NIM',      tier:'free',       icon:'⬡', color:'#76b900', defaultPriority:0, defaultModel:'nvidia/nemotron-3-super-120b-a12b', models:['nvidia/nemotron-3-super-120b-a12b','nvidia/llama-3.1-nemotron-70b-instruct','nvidia/mistral-nemo-12b-instruct'], keyEnv:'NVIDIA_API_KEY', keyHint:'nvapi-…', free:true, desc:'Free hosted inference. No GPU needed. Priority 0 — tried first.', capabilities:['chat','code','reasoning'] },
  { id:'ollama',       name:'Local Ollama',     tier:'local',      icon:'◎', color:'#5da2ff', defaultPriority:1, defaultModel:'qwen3-coder:30b', models:['qwen3-coder:7b','qwen3-coder:30b','qwen3-coder:235b','qwen3.6:35b','deepseek-r1:32b','deepseek-r1:671b','deepseek-v3:685b','gemma4:9b','gemma4:27b','llama4-scout:17b','llama4-maverick:17b'], keyEnv:null, free:true, desc:'Fully local, private, on-device. Manage models from the Ollama tab.', capabilities:['chat','code','reasoning','vision'] },
  { id:'colibri',      name:'Local Colibri',    tier:'local',      icon:'⌘', color:'#10b981', defaultPriority:2, defaultModel:'glm-5.2', models:['glm-5.2'], keyEnv:null, free:true, desc:'Local GLM-5.2 744B MoE served via JustVugg/colibri. Starts on port 8081.', capabilities:['chat','code','reasoning'] },
  { id:'groq',         name:'Groq',             tier:'free-cloud', icon:'⚡', color:'#f97316', defaultPriority:3, defaultModel:'llama-3.3-70b-versatile', models:['llama-3.3-70b-versatile','llama-3.1-8b-instant','mixtral-8x7b-32768','gemma2-9b-it'], keyEnv:'GROQ_API_KEY', keyHint:'gsk_…', free:true, desc:'Ultra-fast inference. Free tier available.', capabilities:['chat','code'] },
  { id:'deepseek',     name:'DeepSeek API',     tier:'free-cloud', icon:'◈', color:'#6366f1', defaultPriority:3, defaultModel:'deepseek-chat', models:['deepseek-chat','deepseek-reasoner','deepseek-coder'], keyEnv:'DEEPSEEK_API_KEY', keyHint:'sk-…', free:true, desc:'Excellent coder + reasoner. Very competitive pricing.', capabilities:['chat','code','reasoning'] },
  { id:'gemini',       name:'Google Gemini',    tier:'free-cloud', icon:'✦', color:'#4285f4', defaultPriority:3, defaultModel:'gemini-2.0-flash', models:['gemini-2.0-flash','gemini-1.5-pro','gemini-1.5-flash','gemini-2.0-flash-thinking-exp'], keyEnv:'GOOGLE_API_KEY', keyHint:'AIza…', free:true, desc:'Generous free tier with vision support.', capabilities:['chat','code','vision','reasoning'] },
  { id:'cerebras',     name:'Cerebras',         tier:'free-cloud', icon:'◉', color:'#ef4444', defaultPriority:3, defaultModel:'llama-3.3-70b', models:['llama-3.3-70b','llama-3.1-8b','llama-3.1-70b'], keyEnv:'CEREBRAS_API_KEY', keyHint:'csk-…', free:true, desc:'Fastest inference. Purpose-built wafer-scale chip.', capabilities:['chat','code'] },
  { id:'sambanova',    name:'SambaNova',        tier:'free-cloud', icon:'◇', color:'#8b5cf6', defaultPriority:3, defaultModel:'Meta-Llama-3.3-70B-Instruct', models:['Meta-Llama-3.3-70B-Instruct','Meta-Llama-3.1-405B-Instruct'], keyEnv:'SAMBANOVA_API_KEY', keyHint:'snova-…', free:true, desc:'Large context streaming-focused inference.', capabilities:['chat','code'] },
  { id:'together',     name:'Together AI',      tier:'free-cloud', icon:'⊕', color:'#06b6d4', defaultPriority:3, defaultModel:'Llama-3.3-70B-Instruct-Turbo-Free', models:['Llama-3.3-70B-Instruct-Turbo-Free','Mixtral-8x7B-Instruct-v0.1-Free'], keyEnv:'TOGETHER_API_KEY', keyHint:'together-…', free:true, desc:'Wide model catalogue, many free options.', capabilities:['chat','code','reasoning'] },
  { id:'mistral',      name:'Mistral',          tier:'free-cloud', icon:'≋', color:'#f59e0b', defaultPriority:3, defaultModel:'mistral-small-latest', models:['mistral-small-latest','mistral-large-latest','codestral-latest','mistral-nemo'], keyEnv:'MISTRAL_API_KEY', keyHint:'mis-…', free:false, desc:'Strong multilingual and code. European provider.', capabilities:['chat','code'] },
  { id:'huggingface',  name:'Hugging Face',     tier:'free-cloud', icon:'🤗', color:'#fbbf24', defaultPriority:3, defaultModel:'serverless', models:['serverless'], keyEnv:'HF_TOKEN', keyHint:'hf_…', free:true, desc:'Serverless inference on thousands of open models.', capabilities:['chat','code'] },
  { id:'cloudflare',   name:'Cloudflare AI',    tier:'free-cloud', icon:'☁', color:'#f97316', defaultPriority:3, defaultModel:'@cf/meta/llama-3.3-70b-instruct-fp8-fast', models:['@cf/meta/llama-3.3-70b-instruct-fp8-fast','@cf/mistral/mistral-7b-instruct-v0.2-lora'], keyEnv:'CLOUDFLARE_API_TOKEN', keyHint:'cf_…', free:true, desc:'Edge-deployed inference. Pair with CLOUDFLARE_ACCOUNT_ID.', capabilities:['chat'] },
  { id:'dashscope',    name:'Qwen DashScope',   tier:'free-cloud', icon:'◎', color:'#10b981', defaultPriority:3, defaultModel:'qwen-plus', models:['qwen-plus','qwen-max','qwen-turbo','qwen-coder-plus'], keyEnv:'DASHSCOPE_API_KEY', keyHint:'sk-…', free:false, desc:'Alibaba Qwen family — strong multilingual + code.', capabilities:['chat','code'] },
  { id:'minimax',      name:'MiniMax',          tier:'free-cloud', icon:'⊡', color:'#7c3aed', defaultPriority:3, defaultModel:'MiniMax-Text-01', models:['MiniMax-Text-01','abab6.5s-chat'], keyEnv:'MINIMAX_API_KEY', keyHint:'eyJ…', free:false, desc:'Long context (1M+) Chinese AI provider.', capabilities:['chat'] },
  { id:'zhipu',        name:'ZhipuAI',          tier:'free-cloud', icon:'◬', color:'#14b8a6', defaultPriority:3, defaultModel:'glm-4-flash', models:['glm-4-flash','glm-4','glm-4-air'], keyEnv:'ZHIPU_API_KEY', keyHint:'zhipu-…', free:true, desc:'GLM-4 family from Zhipu AI. Free flash model.', capabilities:['chat','code'] },
  { id:'zai',          name:'Z.ai (GLM)',       tier:'free-cloud', icon:'◆', color:'#3b82f6', defaultPriority:3, defaultModel:'glm-5.2', models:['glm-5.2','glm-5.1','glm-4-flash','glm-4','glm-4-air'], keyEnv:'ZAI_API_KEY', keyHint:'zai-…', free:true, desc:'GLM-5.2 international endpoint. Free, high-quality, fast.', capabilities:['chat','code','reasoning'] },
  { id:'moonshot',     name:'Moonshot (Kimi)',  tier:'free-cloud', icon:'☽', color:'#fbbf24', defaultPriority:3, defaultModel:'moonshot-v1-8k', models:['moonshot-v1-8k','moonshot-v1-32k','moonshot-v1-128k'], keyEnv:'MOONSHOT_API_KEY', keyHint:'sk-…', free:true, desc:'Long context (128k) Chinese AI provider.', capabilities:['chat','code'] },
  { id:'aerolink',     name:'Aerolink (Claude)',tier:'commercial', icon:'✈', color:'#0ea5e9', defaultPriority:4, defaultModel:'claude-sonnet-4-6', models:['claude-opus-4-8','claude-opus-4-7','claude-fable-5','claude-sonnet-5','claude-sonnet-4-6','claude-opus-4-6','claude-haiku-4-5-20251001'], keyEnv:'AEROLINK_API_KEY', keyHint:'aero-…', free:false, desc:'Claude gateway with $10/week budget. Reliable paid fallback when free providers are rate-limited.', capabilities:['chat','code','reasoning'] },
  { id:'anthropic',    name:'Anthropic',        tier:'commercial', icon:'◬', color:'#d97757', defaultPriority:4, defaultModel:'claude-opus-4-5', models:['claude-opus-4-5','claude-sonnet-4-5','claude-haiku-4-5','claude-3-5-sonnet-20241022'], keyEnv:'ANTHROPIC_API_KEY', keyHint:'sk-ant-…', free:false, desc:'Claude family. Commercial fallback — tried last.', capabilities:['chat','code','reasoning','vision'] },
  { id:'openrouter',   name:'OpenRouter',       tier:'commercial', icon:'⇄', color:'#6366f1', defaultPriority:4, defaultModel:'configurable', models:['configurable'], keyEnv:'OPENROUTER_API_KEY', keyHint:'sk-or-…', free:false, desc:'Unified gateway to 200+ models. Pay-per-use.', capabilities:['chat','code','reasoning'] },
  { id:'bedrock',      name:'AWS Bedrock',      tier:'commercial', icon:'▲', color:'#ff9900', defaultPriority:4, defaultModel:'us.anthropic.claude-opus-4-7', models:['us.anthropic.claude-opus-4-7','us.anthropic.claude-sonnet-4-5','amazon.nova-pro-v1:0'], keyEnv:'AWS_ACCESS_KEY_ID', keyHint:'AKIA…', free:false, desc:'AWS-hosted Claude + Amazon Nova via Converse API.', capabilities:['chat','code','reasoning'] },
  // E2B is a sandbox execution runtime (not an LLM provider) — listed here
  // because this is the catalogue users browse for env-configured
  // integrations. The live enabled/health badge is driven by the /runtimes
  // endpoint (RuntimeManager.list_runtimes() includes 'e2b' when
  // E2B_API_KEY is set), so this card is informational only.
  { id:'e2b',          name:'E2B Sandbox',      tier:'free-cloud', icon:'■', color:'#9333ea', defaultPriority:0, defaultModel:'base', models:['base'], keyEnv:'E2B_API_KEY', keyHint:'e2b_…', free:true, desc:'Firecracker micro-VM sandbox for isolated code execution. Auto-on when E2B_API_KEY is set.', capabilities:['code','shell','git'] },
];

const TIER_CONFIG = {
  local:       { label:'Local',       color:'#5da2ff', bg:'rgba(93,162,255,0.08)',   order:0 },
  free:        { label:'Free Hosted', color:'#76b900', bg:'rgba(118,185,0,0.08)',    order:1 },
  'free-cloud':{ label:'Free Cloud',  color:'#46d9a4', bg:'rgba(70,217,164,0.06)',   order:2 },
  commercial:  { label:'Commercial',  color:'#ffbd66', bg:'rgba(255,189,102,0.06)',  order:3 },
};

// Ollama local models
const OLLAMA_MODELS = [
  { name:'qwen3-coder:30b',   size:'19.9 GB', status:'pulled',    type:'coder',    ctx:'32k' },
  { name:'qwen3-coder:7b',    size:'5.2 GB',  status:'pulled',    type:'coder',    ctx:'32k' },
  { name:'deepseek-r1:32b',   size:'20.1 GB', status:'pulled',    type:'reasoning',ctx:'32k' },
  { name:'gemma4:9b',         size:'5.8 GB',  status:'pulled',    type:'general',  ctx:'128k' },
  { name:'qwen3-coder:235b',  size:'140 GB',  status:'available', type:'coder',    ctx:'32k' },
  { name:'deepseek-v3:685b',  size:'410 GB',  status:'available', type:'coder',    ctx:'131k' },
  { name:'llama4-scout:17b',  size:'10.1 GB', status:'available', type:'general',  ctx:'10M' },
  { name:'llama4-maverick:17b',size:'12.4 GB',status:'available', type:'general',  ctx:'1M' },
  { name:'qwen3.6:35b',       size:'22.3 GB', status:'available', type:'general',  ctx:'128k' },
];

// MCP servers.
//
// There is deliberately no hardcoded default list here any more. This screen
// used to substitute four invented entries (filesystem, github, postgres,
// brave-search) whenever the API returned nothing, complete with fabricated
// "connected" statuses and tool counts. None of those servers existed in the
// deployment, and the two that did — the in-process server and Render — were
// missing. The list now comes entirely from GET /api/mcp/servers, where
// platform-managed rows carry measured status; an empty list renders as empty.

function errText(e, fallback) {
  const detail = e?.response?.data?.detail;
  return detail ? api.fmtErr(detail) : (e?.message || fallback);
}

function CapBadge({ cap }) {
  const colors = { chat:'#5da2ff', code:'#46d9a4', reasoning:'#c4b5fd', vision:'#ffbd66' };
  return <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.08em', textTransform:'uppercase', padding:'2px 7px', borderRadius:999, color:colors[cap]||'var(--text-muted)', background:`${colors[cap]||'#fff'}12`, border:`1px solid ${colors[cap]||'#fff'}22` }}>{cap}</span>;
}

// A real, persisted provider record from GET /api/providers.
function BackendProviderCard({ provider, onTest, onSetDefault, onDelete, onEdit, busy }) {
  const [testState, setTestState] = React.useState(null); // null | 'testing' | 'ok' | 'error'
  const [testMsg, setTestMsg]     = React.useState('');
  const isDefault = !!provider.is_default;
  const status    = provider.status || 'configured';
  const statusColor = status === 'online' ? '#46d9a4' : status === 'error' ? '#ff6b7d' : 'var(--text-muted)';

  const test = async () => {
    setTestState('testing'); setTestMsg('');
    try {
      const { data } = await onTest(provider.provider_id);
      const n = Array.isArray(data?.models) ? data.models.length : null;
      setTestState('ok'); setTestMsg(n != null ? `${n} model${n===1?'':'s'} reachable` : 'Reachable');
    } catch (e) {
      setTestState('error'); setTestMsg(errText(e, 'Test failed'));
    }
  };

  return (
    <div style={{ borderRadius:18, border:`1px solid ${provider.is_brain?'rgba(245,166,35,0.35)':isDefault?'rgba(70,217,164,0.30)':'rgba(255,255,255,0.10)'}`, background:provider.is_brain?'rgba(245,166,35,0.04)':isDefault?'rgba(70,217,164,0.05)':'rgba(255,255,255,0.03)', padding:'14px' }}>
      <div style={{ display:'flex', alignItems:'flex-start', gap:9, marginBottom:9 }}>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap', marginBottom:2 }}>
            <span style={{ fontSize:14, fontWeight:800, color:'#fff', letterSpacing:'-0.02em' }}>{provider.name || provider.provider_id}</span>
            {isDefault && <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'#46d9a4', background:'rgba(70,217,164,0.10)', border:'1px solid rgba(70,217,164,0.22)' }}>★ default</span>}
            {provider.is_brain && <span title={provider.role_reason || 'Used as the brain for agent execution'} style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'#f5a623', background:'rgba(245,166,35,0.12)', border:'1px solid rgba(245,166,35,0.30)', fontWeight:700, letterSpacing:'0.04em' }}>🧠 BRAIN</span>}
            {provider.role === 'fallback' && <span title={provider.role_reason || 'Paid fallback — only used when no free provider is configured'} style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'#ffbd66', background:'rgba(255,189,102,0.10)', border:'1px solid rgba(255,189,102,0.22)' }}>fallback</span>}
            {provider.role === 'sub-agent' && <span title={provider.role_reason || 'Reachable backup used by failover'} style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'#c4b5fd', background:'rgba(196,181,253,0.08)', border:'1px solid rgba(196,181,253,0.20)' }}>sub-agent</span>}
            {provider.role === 'unconfigured' && <span title={provider.role_reason || 'Missing base URL or API key'} style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'#ff6b7d', background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)' }}>unconfigured</span>}
            <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'var(--text-muted)', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', textTransform:'uppercase', letterSpacing:'0.08em' }}>{provider.type || 'openai-compatible'}</span>
          </div>
          <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{provider.base_url || '—'}</div>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:5, flexShrink:0 }}>
          <span style={{ width:7, height:7, borderRadius:'50%', background:statusColor }}/>
          <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:statusColor, textTransform:'uppercase', letterSpacing:'0.08em' }}>{status}</span>
        </div>
      </div>

      <div style={{ display:'flex', gap:10, fontSize:11, color:'var(--text-muted)', marginBottom:10, flexWrap:'wrap' }}>
        <span>Model: <span style={{ color:'var(--text-secondary)', fontFamily:'var(--font-mono)' }}>{provider.default_model || '—'}</span></span>
        {provider.api_key_masked ? <span>Key: <span style={{ color:'var(--text-secondary)', fontFamily:'var(--font-mono)' }}>{provider.api_key_masked}</span></span> : <span style={{ color:'#46d9a4' }}>no key</span>}
        <span title="Higher number = tried first. Negative values allowed.">Priority: <span style={{ color:'var(--text-secondary)', fontFamily:'var(--font-mono)' }}>{provider.priority ?? '—'}</span></span>
      </div>

      {testState && (
        <div style={{ fontSize:11, marginBottom:9, color: testState==='ok'?'#46d9a4':testState==='error'?'#ff6b7d':'var(--text-muted)', fontFamily:'var(--font-mono)' }}>
          {testState==='testing' ? 'Testing…' : testMsg}
        </div>
      )}

      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button onClick={test} disabled={testState==='testing'} style={{ padding:'6px 12px', borderRadius:9, fontSize:12, fontWeight:600, cursor:'pointer', background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)' }}>Test</button>
        <button onClick={()=>onEdit(provider)} disabled={busy} style={{ padding:'6px 12px', borderRadius:9, fontSize:12, fontWeight:600, cursor:'pointer', background:'rgba(196,181,253,0.10)', border:'1px solid rgba(196,181,253,0.25)', color:'#c4b5fd' }}>Edit</button>
        {!isDefault &&        <button onClick={()=>onSetDefault(provider.provider_id)} disabled={busy} title="Fallback provider when no routing rule matches" style={{ padding:'6px 12px', borderRadius:9, fontSize:12, fontWeight:600, cursor:'pointer', background:'rgba(70,217,164,0.08)', border:'1px solid rgba(70,217,164,0.22)', color:'#46d9a4' }}>Set default</button>}
        <button onClick={()=>onDelete(provider)} disabled={busy} style={{ padding:'6px 12px', borderRadius:9, fontSize:12, fontWeight:600, cursor:'pointer', background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', color:'#ff6b7d', marginLeft:'auto' }}>Delete</button>
      </div>
    </div>
  );
}

// Add / configure a real provider (POST /api/providers).
function AddProviderForm({ onCreate, onClose }) {
  const [providerId, setProviderId] = React.useState('');
  const [name, setName]   = React.useState('');
  const [type, setType]   = React.useState('openai-compatible');
  const [baseUrl, setBaseUrl] = React.useState('');
  const [apiKey, setApiKey]   = React.useState('');
  const [model, setModel] = React.useState('');
  const [busy, setBusy]   = React.useState(false);
  const [error, setError] = React.useState(null);

  const applyTemplate = (p) => {
    // Catalogue templates don't carry a base_url; clear it for the user to fill in.
    setProviderId(p.id); setName(p.name); setBaseUrl('');
    setModel(p.defaultModel || ''); setType(p.id === 'ollama' ? 'ollama' : 'openai-compatible');
  };

  const submit = async () => {
    if (!providerId.trim() || !name.trim() || busy) return;
    if (type !== 'ollama' && !baseUrl.trim()) { setError('Base URL is required for OpenAI-compatible providers.'); return; }
    setBusy(true); setError(null);
    try {
      await onCreate({
        provider_id: providerId.trim(),
        name: name.trim(),
        type,
        base_url: baseUrl.trim(),
        api_key: apiKey.trim(),
        default_model: model.trim(),
        is_default: false,
      });
      onClose();
    } catch (e) {
      setError(errText(e, 'Failed to create provider.'));
      setBusy(false);
    }
  };

  const fld = { width:'100%', padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)' };
  return (
    <div style={{ borderRadius:18, border:'1px solid rgba(93,162,255,0.20)', background:'rgba(93,162,255,0.04)', padding:'16px', marginBottom:14 }}>
      <div style={{ fontSize:13, fontWeight:800, color:'#fff', marginBottom:12 }}>Add provider</div>
      <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em', marginBottom:6 }}>Quick-fill from catalogue</div>
      <div style={{ display:'flex', gap:5, flexWrap:'wrap', marginBottom:12 }}>
        {ALL_PROVIDERS.slice(0,8).map(p => (
          <button key={p.id} onClick={()=>applyTemplate(p)} style={{ padding:'4px 10px', borderRadius:999, fontSize:11, cursor:'pointer', background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)' }}>{p.icon} {p.name}</button>
        ))}
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:10 }}>
        <input value={providerId} onChange={e=>setProviderId(e.target.value)} placeholder="provider id (e.g. groq)" style={{ ...fld, fontFamily:'var(--font-mono)' }}/>
        <input value={name} onChange={e=>setName(e.target.value)} placeholder="Display name" style={fld}/>
      </div>
      <div style={{ display:'flex', gap:8, marginBottom:10 }}>
        {['openai-compatible','ollama'].map(t => (
          <button key={t} onClick={()=>setType(t)} style={{ padding:'7px 14px', borderRadius:999, fontSize:12, fontWeight:600, cursor:'pointer', background:type===t?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${type===t?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.09)'}`, color:type===t?'#fff':'var(--text-muted)' }}>{t}</button>
        ))}
      </div>
      <input value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} placeholder={type==='ollama'?'Ollama base URL (optional)':'Base URL (https://api.example.com/v1)'} style={{ ...fld, fontFamily:'var(--font-mono)', marginBottom:10 }}/>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:12 }}>
        <input type="password" value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="API key (optional)" style={{ ...fld, fontFamily:'var(--font-mono)' }}/>
        <input value={model} onChange={e=>setModel(e.target.value)} placeholder="Default model" style={{ ...fld, fontFamily:'var(--font-mono)' }}/>
      </div>
      {error && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:12 }}>{error}</div>}
      <div style={{ display:'flex', gap:8 }}>
        <button onClick={submit} disabled={busy} style={{ flex:1, padding:'10px', borderRadius:12, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:13, fontWeight:800, border:'none', cursor:busy?'wait':'pointer', opacity:busy?0.7:1 }}>{busy ? 'Saving…' : '+ Add provider'}</button>
        <button onClick={onClose} disabled={busy} style={{ padding:'10px 18px', borderRadius:12, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:13, cursor:'pointer' }}>Cancel</button>
      </div>
    </div>
  );
}

// Edit an existing provider in place (PUT /api/providers/{id}) — #508.
// Lets operators change priority / key / model / name / base_url after creation.
function EditProviderForm({ provider, onUpdate, onClose }) {
  const [name, setName]       = React.useState(provider.name || '');
  const [baseUrl, setBaseUrl] = React.useState(provider.base_url || '');
  const [apiKey, setApiKey]   = React.useState('');  // blank = keep existing key
  const [model, setModel]     = React.useState(provider.default_model || '');
  const [priority, setPriority] = React.useState(
    provider.priority === null || provider.priority === undefined ? '' : String(provider.priority)
  );
  const [busy, setBusy]   = React.useState(false);
  const [error, setError] = React.useState(null);

  const submit = async () => {
    if (busy) return;
    setBusy(true); setError(null);
    const payload = {
      name: name.trim(),
      base_url: baseUrl.trim(),
      default_model: model.trim(),
    };
    // Only send the key when the operator typed a new one — never blank it out.
    if (apiKey.trim()) payload.api_key = apiKey.trim();
    if (priority.trim() !== '') {
      const raw = priority.trim();
      if (!/^-?\d+$/.test(raw)) { setError('Priority must be a whole number.'); setBusy(false); return; }
      payload.priority = Number(raw);
    }
    try {
      await onUpdate(provider.provider_id, payload);
      onClose();
    } catch (e) {
      setError(errText(e, 'Failed to update provider.'));
      setBusy(false);
    }
  };

  const fld = { width:'100%', padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)' };
  return (
    <div style={{ borderRadius:18, border:'1px solid rgba(196,181,253,0.25)', background:'rgba(196,181,253,0.05)', padding:'16px', marginBottom:14 }}>
      <div style={{ fontSize:13, fontWeight:800, color:'#fff', marginBottom:2 }}>Edit provider</div>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', marginBottom:12 }}>{provider.provider_id}</div>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:10 }}>
        <input value={name} onChange={e=>setName(e.target.value)} placeholder="Display name" style={fld}/>
        <input value={priority} onChange={e=>setPriority(e.target.value)} placeholder="Priority (lower = first)" inputMode="numeric" style={{ ...fld, fontFamily:'var(--font-mono)' }}/>
      </div>
      <input value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} placeholder="Base URL (https://api.example.com/v1)" style={{ ...fld, fontFamily:'var(--font-mono)', marginBottom:10 }}/>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:12 }}>
        <input type="password" value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder={provider.api_key_masked ? `Leave blank to keep (${provider.api_key_masked})` : 'API key (optional)'} style={{ ...fld, fontFamily:'var(--font-mono)' }}/>
        <input value={model} onChange={e=>setModel(e.target.value)} placeholder="Default model" style={{ ...fld, fontFamily:'var(--font-mono)' }}/>
      </div>
      {error && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:12 }}>{error}</div>}
      <div style={{ display:'flex', gap:8 }}>
        <button onClick={submit} disabled={busy} style={{ flex:1, padding:'10px', borderRadius:12, background:'linear-gradient(135deg,#c4b5fd,#a78bfa)', color:'#06111f', fontSize:13, fontWeight:800, border:'none', cursor:busy?'wait':'pointer', opacity:busy?0.7:1 }}>{busy ? 'Saving…' : 'Save changes'}</button>
        <button onClick={onClose} disabled={busy} style={{ padding:'10px 18px', borderRadius:12, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:13, cursor:'pointer' }}>Cancel</button>
      </div>
    </div>
  );
}

// Read-only reference card for the popular-integrations catalogue.
function CatalogCard({ provider }) {
  const tier = TIER_CONFIG[provider.tier] || TIER_CONFIG.commercial;
  return (
    <div style={{ borderRadius:16, border:'1px solid rgba(255,255,255,0.08)', background:'rgba(255,255,255,0.025)', padding:'12px' }}>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:6 }}>
        <div style={{ width:30, height:30, borderRadius:9, flexShrink:0, background:`${provider.color}15`, border:`1px solid ${provider.color}28`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:14 }}>{provider.icon}</div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:12, fontWeight:700, color:'#fff' }}>{provider.name}</div>
          <div style={{ fontSize:9, fontFamily:'var(--font-mono)', color:tier.color, textTransform:'uppercase', letterSpacing:'0.10em' }}>{tier.label}</div>
        </div>
      </div>
      <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.4, marginBottom:6 }}>{provider.desc}</div>
      {provider.keyEnv && <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-tertiary)' }}>env: {provider.keyEnv}</div>}
    </div>
  );
}

// Ollama model management tab
function OllamaTab() {
  const [liveModels, setLiveModels]   = React.useState(null);   // null = loading
  const [loadErr,    setLoadErr]      = React.useState(null);
  const [pulling,    setPulling]      = React.useState(null);
  const [pullErr,    setPullErr]      = React.useState(null);
  const [customModel, setCustomModel] = React.useState('');

  // Load real Ollama model list from backend
  const loadModels = React.useCallback(async () => {
    setLoadErr(null);
    try {
      const { data } = await api.listModels();
      const ollamaModels = (data.models || [])
        .filter(m => m.source === 'ollama-local')
        .map(m => ({
          name:   m.name,
          size:   m.size ? `${(m.size / 1e9).toFixed(1)} GB` : '?',
          status: 'pulled',
          type:   m.details?.family || (m.name.includes('coder') ? 'coder' : m.name.includes('r1') || m.name.includes('reason') ? 'reasoning' : 'general'),
          ctx:    m.details?.parameter_size || '?',
        }));
      // Merge with catalogue: show catalogue items not yet pulled as 'available'
      const pulledNames = new Set(ollamaModels.map(m => m.name));
      const catalogAvail = OLLAMA_MODELS
        .filter(m => !pulledNames.has(m.name))
        .map(m => ({ ...m, status: 'available' }));
      setLiveModels([...ollamaModels, ...catalogAvail]);
    } catch (e) {
      setLoadErr('Could not reach Ollama — is it running?');
      // Fall back to catalogue
      setLiveModels(OLLAMA_MODELS);
    }
  }, []);

  React.useEffect(() => { loadModels(); }, [loadModels]);

  const models = liveModels || OLLAMA_MODELS;

  const pull = async (name) => {
    setPulling(name); setPullErr(null);
    try {
      await api.pullModel(name);
      await loadModels();
    } catch (e) {
      setPullErr(`Pull failed: ${e?.response?.data?.detail || e.message}`);
    } finally { setPulling(null); }
  };

  const removeModel = async (name) => {
    try {
      await api.deleteModel(name);
      await loadModels();
    } catch {
      setLiveModels(p => (p||[]).map(m => m.name === name ? { ...m, status: 'available' } : m));
    }
  };

  const typeColor = { coder:'#5da2ff', reasoning:'#c4b5fd', general:'#46d9a4' };

  return (
    <div>
      <div style={{ padding:'10px 14px', borderRadius:14, background:'rgba(93,162,255,0.05)', border:'1px solid rgba(93,162,255,0.15)', marginBottom:16, fontSize:12, color:'var(--text-secondary)', lineHeight:1.6 }}>
        <strong style={{ color:'var(--accent)' }}>Local Ollama</strong> — Models run entirely on your hardware. No API key, no data leaves your machine. Add any model by name using the form below, or pull from the list.
      </div>

      {/* Custom pull */}
      <div style={{ display:'flex', gap:8, marginBottom:14 }}>
        <input value={customModel} onChange={e=>setCustomModel(e.target.value)} placeholder="e.g. phi4:latest or llava:13b"
          style={{ flex:1, padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-mono)', transition:'border-color 0.2s' }}
          onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.12)'}/>
        <button onClick={()=>{ if(customModel.trim()){ pull(customModel.trim()); setCustomModel(''); }}} style={{ padding:'9px 16px', borderRadius:10, background:'rgba(93,162,255,0.15)', border:'1px solid rgba(93,162,255,0.30)', color:'var(--accent)', fontSize:12, fontWeight:700, cursor:'pointer' }}>Pull model</button>
        <a href="https://ollama.com/library" target="_blank" rel="noreferrer" style={{ padding:'9px 12px', borderRadius:10, background:'transparent', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:12, textDecoration:'none', display:'inline-flex', alignItems:'center', whiteSpace:'nowrap' }}>Browse library →</a>
      </div>

      {(loadErr || pullErr) && (
        <div style={{ padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', color:'#ff6b7d', fontSize:12, marginBottom:10 }}>
          {loadErr || pullErr}
        </div>
      )}

      {liveModels === null && !loadErr && (
        <div style={{ padding:'18px 0', fontSize:13, color:'var(--text-muted)', textAlign:'center' }}>Loading models from Ollama…</div>
      )}

      <div style={{ display:'flex', flexDirection:'column', gap:7 }}>
        {models.map(m => {
          const isPulled = m.status === 'pulled';
          const isRunning = pulling === m.name;
          const tc = typeColor[m.type] || 'var(--text-muted)';
          return (
            <div key={m.name} style={{ display:'flex', alignItems:'center', gap:10, padding:'11px 14px', borderRadius:13, border:`1px solid ${isPulled?'rgba(70,217,164,0.18)':'rgba(255,255,255,0.08)'}`, background:isPulled?'rgba(70,217,164,0.04)':'rgba(255,255,255,0.025)' }}>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:2, flexWrap:'wrap' }}>
                  <span style={{ fontSize:13, fontWeight:600, color:isPulled?'#fff':'var(--text-tertiary)', fontFamily:'var(--font-mono)' }}>{m.name}</span>
                  <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase', padding:'1px 6px', borderRadius:999, color:tc, background:`${tc}12`, border:`1px solid ${tc}22` }}>{m.type}</span>
                  {isPulled && <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'1px 6px', borderRadius:999, color:'#46d9a4', background:'rgba(70,217,164,0.10)', border:'1px solid rgba(70,217,164,0.20)', textTransform:'uppercase', letterSpacing:'0.10em' }}>on device</span>}
                </div>
                <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{m.size} · {m.ctx} context</div>
              </div>
              {isRunning ? (
                <div style={{ display:'flex', alignItems:'center', gap:7, fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)' }}>
                  <div style={{ width:12, height:12, border:'2px solid rgba(93,162,255,0.2)', borderTopColor:'var(--accent)', borderRadius:'50%', animation:'spin 0.8s linear infinite' }}/>Pulling…
                </div>
              ) : isPulled ? (
                <button onClick={()=>removeModel(m.name)} style={{ padding:'5px 12px', borderRadius:8, fontSize:11, cursor:'pointer', background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', color:'#ff6b7d' }}>Remove</button>
              ) : (
                <button onClick={()=>pull(m.name)} style={{ padding:'5px 12px', borderRadius:8, fontSize:11, fontWeight:600, cursor:'pointer', background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.22)', color:'var(--accent)' }}>↓ Pull</button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// MCP servers tab
function MCPTab() {
  const [servers,  setServers]  = React.useState(null);  // null = loading
  const [loadErr,  setLoadErr]  = React.useState(null);
  const [showAdd,  setShowAdd]  = React.useState(false);
  const [saving,   setSaving]   = React.useState(false);
  const [newName,  setNewName]  = React.useState('');
  const [newCmd,   setNewCmd]   = React.useState('');
  const [newDesc,  setNewDesc]  = React.useState('');

  // Only 'error' is red. 'unconfigured' is amber (an operator can act on it),
  // and 'unavailable' is muted — a server the backend structurally cannot dial
  // is not broken, and colouring it red sends people hunting for a fault.
  const statusColor = {
    connected:'#46d9a4', error:'#ff6b7d',
    unconfigured:'#ffbd66', unavailable:'var(--text-muted)',
    idle:'var(--text-muted)',
  };

  const loadServers = React.useCallback(async () => {
    setLoadErr(null);
    try {
      const { data } = await api.listMcpServers();
      // Show exactly what the server reports, including an empty list. Filling
      // a blank screen with invented entries is what made this page mislead.
      setServers(data.servers || []);
    } catch {
      setLoadErr('Could not load MCP servers.');
      setServers([]);
    }
  }, []);

  React.useEffect(() => { loadServers(); }, [loadServers]);

  const addServer = async () => {
    if (!newName.trim() || !newCmd.trim()) return;
    setSaving(true);
    try {
      await api.createMcpServer({ name: newName.trim(), cmd: newCmd.trim(), desc: newDesc, status: 'idle', tools: 0 });
      setNewName(''); setNewCmd(''); setNewDesc(''); setShowAdd(false);
      await loadServers();
    } catch (e) {
      alert('Could not add server: ' + (e?.response?.data?.detail || e.message));
    } finally { setSaving(false); }
  };

  // Both handlers apply only to user rows. Platform-managed servers render a
  // Re-check button instead, because their status is measured server-side and
  // there is no stored record to toggle or delete.
  const toggleConnect = async (srv) => {
    if (srv.managed) return;
    const newStatus = srv.status === 'connected' ? 'idle' : 'connected';
    // Optimistic update
    setServers(p => (p||[]).map(s => s.id === srv.id ? { ...s, status: newStatus } : s));
    try {
      await api.updateMcpServer(srv.id, { status: newStatus });
    } catch {
      // Roll back to the real value — an optimistic status that silently
      // sticks is how this screen came to show things that were not true.
      setServers(p => (p||[]).map(s => s.id === srv.id ? { ...s, status: srv.status } : s));
    }
  };

  const removeServer = async (srv) => {
    if (srv.managed) return;
    setServers(p => (p||[]).filter(s => s.id !== srv.id));
    try {
      if (srv.id) await api.deleteMcpServer(srv.id);
    } catch { await loadServers(); }
  };

  return (
    <div>
      <McpCard/>

      <div style={{ padding:'10px 14px', borderRadius:14, background:'rgba(196,181,253,0.05)', border:'1px solid rgba(196,181,253,0.15)', marginBottom:16, fontSize:12, color:'var(--text-secondary)', lineHeight:1.6 }}>
        <strong style={{ color:'#c4b5fd' }}>Model Context Protocol</strong> — MCP servers expose tools, resources, and prompts to agents. Connect any MCP-compatible server to give agents new capabilities (filesystem, databases, search, APIs).
      </div>

      <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:12 }}>
        <button onClick={()=>setShowAdd(o=>!o)} style={{ padding:'8px 16px', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(196,181,253,0.12)', border:'1px solid rgba(196,181,253,0.25)', color:'#c4b5fd' }}>+ Add MCP server</button>
      </div>

      {showAdd && (
        <div style={{ padding:'14px', borderRadius:14, background:'rgba(196,181,253,0.05)', border:'1px solid rgba(196,181,253,0.18)', marginBottom:12, animation:'fadeSlideUp 0.2s ease-out' }}>
          <div style={{ display:'flex', flexDirection:'column', gap:9 }}>
            <input value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Server name (e.g. my-database)"
              style={{ padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-mono)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='rgba(196,181,253,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
            <input value={newCmd} onChange={e=>setNewCmd(e.target.value)} placeholder="Start command (e.g. npx @modelcontextprotocol/server-postgres $DB_URL)"
              style={{ padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-mono)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='rgba(196,181,253,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
            <input value={newDesc} onChange={e=>setNewDesc(e.target.value)} placeholder="Description (optional)"
              style={{ padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='rgba(196,181,253,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
            <div style={{ display:'flex', gap:8 }}>
              <button onClick={addServer} disabled={saving} style={{ flex:1, padding:'9px', borderRadius:10, background:saving?'rgba(196,181,253,0.07)':'rgba(196,181,253,0.15)', border:'1px solid rgba(196,181,253,0.30)', color:'#c4b5fd', fontSize:13, fontWeight:800, cursor:saving?'not-allowed':'pointer' }}>{saving ? 'Adding…' : 'Add server'}</button>
              <button onClick={()=>setShowAdd(false)} style={{ padding:'9px 14px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:13, cursor:'pointer' }}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {loadErr && <div style={{ padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', color:'#ff6b7d', fontSize:12, marginBottom:10 }}>{loadErr}</div>}
      {servers === null && !loadErr && <div style={{ padding:'18px 0', fontSize:13, color:'var(--text-muted)', textAlign:'center' }}>Loading MCP servers…</div>}

      <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
        {(servers || []).map(srv => {
          const sc = statusColor[srv.status] || 'var(--text-muted)';
          return (
            <div key={srv.id} style={{ padding:'12px 14px', borderRadius:14, border:`1px solid ${srv.status==='connected'?'rgba(70,217,164,0.18)':srv.status==='error'?'rgba(255,107,125,0.18)':'rgba(255,255,255,0.08)'}`, background:srv.status==='connected'?'rgba(70,217,164,0.04)':srv.status==='error'?'rgba(255,107,125,0.04)':'rgba(255,255,255,0.025)' }}>
              <div style={{ display:'flex', alignItems:'flex-start', gap:9, marginBottom:5 }}>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:3, flexWrap:'wrap' }}>
                    <span style={{ fontSize:13, fontWeight:700, color:'#fff', fontFamily:'var(--font-mono)' }}>{srv.name}</span>
                    <div style={{ display:'flex', alignItems:'center', gap:4 }}>
                      <span style={{ width:6, height:6, borderRadius:'50%', background:sc, animation:srv.status==='connected'?'pulse 2s infinite':'none' }}/>
                      <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:sc, letterSpacing:'0.10em', textTransform:'uppercase' }}>{srv.status}</span>
                    </div>
                    {srv.tools > 0 && <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', padding:'1px 6px', borderRadius:5, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.09)' }}>{srv.tools} tools</span>}
                    {srv.managed && <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'#5da2ff', padding:'1px 6px', borderRadius:5, background:'rgba(93,162,255,0.08)', border:'1px solid rgba(93,162,255,0.18)' }} title="Declared by this deployment; status is measured live">platform</span>}
                  </div>
                  <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.5, marginBottom:4 }}>{srv.desc}</div>
                  {/* Why a server is not connected is the actionable part — an
                      "unconfigured" badge with no reason just relocates the question. */}
                  {srv.reason && srv.status !== 'connected' && (
                    <div style={{ fontSize:10, color:sc, lineHeight:1.5, marginBottom:4 }}>{srv.reason}</div>
                  )}
                  <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'rgba(255,255,255,0.35)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{srv.cmd}</div>
                </div>
                {/* Platform-managed servers come from configuration, so there is
                    nothing to delete and no client-side connect to toggle. */}
                {srv.managed ? (
                  <div style={{ display:'flex', gap:5, flexShrink:0 }}>
                    <button onClick={loadServers} style={{ padding:'4px 10px', borderRadius:8, fontSize:11, cursor:'pointer', background:'rgba(93,162,255,0.08)', border:'1px solid rgba(93,162,255,0.20)', color:'#5da2ff' }} title="Re-probe this server">Re-check</button>
                  </div>
                ) : (
                <div style={{ display:'flex', gap:5, flexShrink:0 }}>
                  <button onClick={()=>removeServer(srv)} style={{ padding:'4px 8px', borderRadius:8, fontSize:10, cursor:'pointer', background:'rgba(255,107,125,0.06)', border:'1px solid rgba(255,107,125,0.15)', color:'rgba(255,107,125,0.6)' }} title="Remove">✕</button>
                  <button onClick={()=>toggleConnect(srv)} style={{ padding:'4px 10px', borderRadius:8, fontSize:11, cursor:'pointer', background:srv.status==='connected'?'rgba(255,107,125,0.08)':'rgba(70,217,164,0.10)', border:`1px solid ${srv.status==='connected'?'rgba(255,107,125,0.20)':'rgba(70,217,164,0.22)'}`, color:srv.status==='connected'?'#ff6b7d':'#46d9a4' }}>
                    {srv.status==='connected'?'Disconnect':'Connect'}
                  </button>
                </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProvidersScreen() {
  const [tab, setTab]         = React.useState('providers');
  const [showAdd, setShowAdd] = React.useState(false);
  const [editingId, setEditingId] = React.useState(null);
  const [busy, setBusy]       = React.useState(false);
  const [actionErr, setActionErr] = React.useState(null);
  const [showCatalog, setShowCatalog] = React.useState(false);

  // Paid-provider kill switch state
  const [policy, setPolicy] = React.useState(null);  // null = loading
  const [policyBusy, setPolicyBusy] = React.useState(false);
  const [policyErr, setPolicyErr] = React.useState(null);
  // Per-surface provider assignments
  const [surfaces, setSurfaces] = React.useState(null);
  const [surfaceBusy, setSurfaceBusy] = React.useState(null);  // which surface is saving

  const loadSurfaces = React.useCallback(async () => {
    try {
      const { data } = await api.getProviderPolicy();
      setSurfaces(data.surfaces || {});
    } catch {
      setSurfaces({});
    }
  }, []);

  React.useEffect(() => { loadSurfaces(); }, [loadSurfaces]);


  const loadPolicy = React.useCallback(async () => {
    setPolicyErr(null);
    try {
      const { data } = await api.getProviderPolicy();
      setPolicy(data);
    } catch {
      setPolicyErr('Could not load provider policy.');
      setPolicy({ allow_paid: false });  // failsafe default
    }
  }, []);

  React.useEffect(() => {
    const ac = new AbortController();
    let cancelled = false;
    const fetchPolicy = async () => {
      setPolicyErr(null);
      try {
        const { data } = await api.getProviderPolicy();
        if (!cancelled) setPolicy(data);
      } catch {
        if (!cancelled) {
          setPolicyErr('Could not load provider policy.');
          setPolicy({ allow_paid: false });
        }
      }
    };
    fetchPolicy();
    return () => { cancelled = true; };
  }, []);

  // The console's segmented control names the state it wants rather than
  // flipping whatever is current, so a double-click cannot race itself into
  // the opposite of what the operator clicked.
  const setPaidAccess = async (next) => {
    if (policyBusy || !policy || next === policy.allow_paid) return;
    setPolicyBusy(true); setPolicyErr(null);
    try {
      const { data } = await api.updateProviderPolicy({ allow_paid: next });
      setPolicy(data);
    } catch (e) {
      setPolicyErr(api.fmtErr(e?.response?.data?.detail) || 'Failed to update policy.');
    } finally { setPolicyBusy(false); }
  };

  const togglePolicy = async () => {
    if (policyBusy || !policy) return;
    const next = !policy.allow_paid;
    setPolicyBusy(true); setPolicyErr(null);
    try {
      const { data } = await api.updateProviderPolicy({ allow_paid: next });
      setPolicy(data);
    } catch (e) {
      setPolicyErr(api.fmtErr(e?.response?.data?.detail) || 'Failed to update policy.');
    } finally { setPolicyBusy(false); }
  };

  
  const saveSurface = async (surface, providerId) => {
    if (!surfaces) return;
    const prev = {...surfaces};
    const next = {...surfaces, [surface]: providerId};
    setSurfaces(next);
    setSurfaceBusy(surface);
    try {
      const { data } = await api.updateProviderPolicy({
        allow_paid: policy?.allow_paid ?? false,
        surfaces: next,
      });
      setSurfaces(data.surfaces || next);
    } catch {
      setSurfaces(prev);  // revert on error
    } finally {
      setSurfaceBusy(null);
    }
  };

  const [data, states, refetch] = useSafeData(null, { providers: '/api/providers' }, { refreshMs: 0 });
  const providers = data.providers?.providers || [];
  const defaultProvider = providers.find(p => p.is_default) || providers[0];

  const handleCreate = async (payload) => {
    await api.createProvider(payload);
    refetch();
  };
  const handleSetDefault = async (id) => {
    setBusy(true); setActionErr(null);
    try { await api.updateProvider(id, { is_default: true }); refetch(); }
    catch (e) { setActionErr(errText(e, 'Could not set default.')); }
    finally { setBusy(false); }
  };
  const handleDelete = async (provider) => {
    if (!window.confirm(`Delete provider "${provider.name || provider.provider_id}"?`)) return;
    setBusy(true); setActionErr(null);
    try { await api.deleteProvider(provider.provider_id); refetch(); }
    catch (e) { setActionErr(errText(e, 'Could not delete provider.')); }
    finally { setBusy(false); }
  };
  const handleUpdate = async (id, payload) => {
    await api.updateProvider(id, payload);  // throws → surfaced by EditProviderForm
    refetch();
  };

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:1000, margin:'0 auto' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:6 }}>Infrastructure</div>
      <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:14 }}>
        <div>
          <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Providers & Models</h1>
          <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:520 }}>Every model call routes through one gateway. This page is where you see which provider is serving, why, and what to do when one degrades.</p>
        </div>
        {/* The "default provider" badge used to live here and routinely
            disagreed with the brain card below it — one read the database,
            the other read live routing. The console's SERVING row is now the
            single answer to that question. */}
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:14 }}>
        {['providers','ollama','mcp'].map(t => (
          <button key={t} onClick={()=>setTab(t)} style={{ padding:'7px 18px', borderRadius:999, fontSize:12, fontWeight:600, cursor:'pointer', textTransform:t==='mcp'?'uppercase':'capitalize', letterSpacing:t==='mcp'?'0.10em':'normal', transition:'all 0.15s', background:tab===t?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${tab===t?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.08)'}`, color:tab===t?'#fff':'var(--text-muted)' }}>
            {t==='mcp'?'MCP Servers':t==='ollama'?'Ollama / Local':'Providers'}
          </button>
        ))}
      </div>

      {tab === 'providers' && (
        <>
          {/* The unified Provider Console (ADR-008).
              Replaces what used to be five stacked surfaces here — a brain
              card, a local-brain switch, a provider-health switch, a paid
              kill switch, and two separate provider grids. A provider now
              appears exactly once, ranked by live health, with every control
              for it inside its own row. */}
          <ProviderConsole
            storedProviders={providers}
            policy={policy}
            policyBusy={policyBusy}
            onTogglePaid={setPaidAccess}
            onEditProvider={(prov) => { setEditingId(prov.provider_id); setShowAdd(false); }}
            onDeleteProvider={handleDelete}
            onTestProvider={api.testProvider}
            refreshStored={refetch}
          />

          {policyErr && (
            <div style={{ marginTop: 10, fontSize: 11.5, color: '#ff6b7d', fontFamily: 'var(--font-mono)' }}>{policyErr}</div>
          )}
          {actionErr && (
            <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 10, background: 'rgba(255,107,125,0.10)', border: '1px solid rgba(255,107,125,0.25)', color: '#ff6b7d', fontSize: 12 }}>{actionErr}</div>
          )}
          {states.providers?.error && (
            <div style={{ marginTop: 10, fontSize: 12, color: '#ffbd66' }}>
              Couldn't load saved providers: {states.providers.error}
            </div>
          )}

          {/* Add / edit a database-persisted provider. */}
          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={() => { setShowAdd(o => !o); setEditingId(null); }} style={{ padding: '8px 16px', borderRadius: 10, fontSize: 12, fontWeight: 700, cursor: 'pointer', background: 'rgba(93,162,255,0.12)', border: '1px solid rgba(93,162,255,0.30)', color: 'var(--accent)' }}>
              {showAdd ? 'Cancel' : '+ Add custom provider'}
            </button>
          </div>
          {showAdd && <div style={{ marginTop: 10 }}><AddProviderForm onCreate={handleCreate} onClose={() => setShowAdd(false)} /></div>}
          {editingId && (() => {
            const editing = providers.find(p => p.provider_id === editingId);
            return editing ? (
              <div style={{ marginTop: 10 }}>
                <EditProviderForm provider={editing} onUpdate={handleUpdate} onClose={() => setEditingId(null)} />
              </div>
            ) : null;
          })()}

          {/* Routing rules. Previously rendered *inside* the "N configured
              providers" label, which nested a grid inside a text node and
              made the whole block read as an accident. It is its own section
              now, next to the console it modifies. */}
          {surfaces && Object.keys(surfaces).length > 0 && (
            <div style={{ marginTop: 18, borderRadius: 16, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.025)', padding: '14px 17px' }}>
              <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 4 }}>
                Per-surface overrides
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', lineHeight: 1.5, marginBottom: 11 }}>
                Pin a surface to one provider, or leave it on Auto to use the routing strategy above.
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 7 }}>
                {Object.entries(surfaces).map(([surface, providerId]) => (
                  <div key={surface} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '7px 9px', borderRadius: 9, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}>
                    <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'capitalize', minWidth: 50 }}>{surface}</span>
                    <select
                      value={providerId || 'auto'}
                      onChange={(e) => saveSurface(surface, e.target.value)}
                      disabled={surfaceBusy === surface}
                      style={{ flex: 1, padding: '4px 6px', borderRadius: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.10)', color: '#fff', fontSize: 11, fontFamily: 'var(--font-mono)', outline: 'none', cursor: 'pointer', opacity: surfaceBusy === surface ? 0.5 : 1 }}
                    >
                      <option value="auto">Auto (strategy)</option>
                      {providers.map(p => (
                        <option key={p.provider_id} value={p.provider_id}>{p.name || p.provider_id}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Legacy brain controls. Kept, because they still do things the
              console does not — per-role model assignment and the
              cross-machine local-brain switch — but folded away so they stop
              competing with the console for the answer to "what is running". */}
          <details style={{ marginTop: 18 }}>
            <summary style={{ cursor: 'pointer', fontSize: 12.5, fontWeight: 700, color: 'var(--text-secondary)', padding: '8px 0', listStyle: 'none', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>▸</span>
              Brain &amp; local-runtime controls
              <span style={{ fontSize: 10.5, fontWeight: 400, color: 'var(--text-tertiary)' }}>
                per-role models, local GLM toggle, legacy provider breakers
              </span>
            </summary>
            <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <BrainCard />
              <LocalBrainToggleCard />
              <ProviderHealthToggleCard />
            </div>
          </details>
        </>
      )}
      {tab === 'ollama' && <OllamaTab/>}
      {tab === 'mcp'     && <MCPTab/>}
    </div>
  );
}

export { ProvidersScreen };
export default ProvidersScreen;
