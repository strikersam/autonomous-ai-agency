/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import Glyph from '../components/ui/Glyph';
import { Link } from 'react-router-dom';
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
  { id:'ollama',       name:'Local Ollama',     tier:'local',      icon:'◎', color:'var(--accent)', defaultPriority:1, defaultModel:'qwen3-coder:30b', models:['qwen3-coder:7b','qwen3-coder:30b','qwen3-coder:235b','qwen3.6:35b','deepseek-r1:32b','deepseek-r1:671b','deepseek-v3:685b','gemma4:9b','gemma4:27b','llama4-scout:17b','llama4-maverick:17b'], keyEnv:null, free:true, desc:'Fully local, private, on-device. Manage models from the Ollama tab.', capabilities:['chat','code','reasoning','vision'] },
  { id:'colibri',      name:'Local Colibri',    tier:'local',      icon:'⌘', color:'var(--success)', defaultPriority:2, defaultModel:'glm-5.2', models:['glm-5.2'], keyEnv:null, free:true, desc:'Local GLM-5.2 744B MoE served via JustVugg/colibri. Starts on port 8081.', capabilities:['chat','code','reasoning'] },
  { id:'groq',         name:'Groq',             tier:'free-cloud', icon:'⚡', color:'var(--warning)', defaultPriority:3, defaultModel:'llama-3.3-70b-versatile', models:['llama-3.3-70b-versatile','llama-3.1-8b-instant','mixtral-8x7b-32768','gemma2-9b-it'], keyEnv:'GROQ_API_KEY', keyHint:'gsk_…', free:true, desc:'Ultra-fast inference. Free tier available.', capabilities:['chat','code'] },
  { id:'deepseek',     name:'DeepSeek API',     tier:'free-cloud', icon:'◈', color:'var(--accent)', defaultPriority:3, defaultModel:'deepseek-chat', models:['deepseek-chat','deepseek-reasoner','deepseek-coder'], keyEnv:'DEEPSEEK_API_KEY', keyHint:'sk-…', free:true, desc:'Excellent coder + reasoner. Very competitive pricing.', capabilities:['chat','code','reasoning'] },
  { id:'gemini',       name:'Google Gemini',    tier:'free-cloud', icon:'✦', color:'#4285f4', defaultPriority:3, defaultModel:'gemini-2.0-flash', models:['gemini-2.0-flash','gemini-1.5-pro','gemini-1.5-flash','gemini-2.0-flash-thinking-exp'], keyEnv:'GOOGLE_API_KEY', keyHint:'AIza…', free:true, desc:'Generous free tier with vision support.', capabilities:['chat','code','vision','reasoning'] },
  { id:'cerebras',     name:'Cerebras',         tier:'free-cloud', icon:'◉', color:'var(--danger)', defaultPriority:3, defaultModel:'llama-3.3-70b', models:['llama-3.3-70b','llama-3.1-8b','llama-3.1-70b'], keyEnv:'CEREBRAS_API_KEY', keyHint:'csk-…', free:true, desc:'Fastest inference. Purpose-built wafer-scale chip.', capabilities:['chat','code'] },
  { id:'sambanova',    name:'SambaNova',        tier:'free-cloud', icon:'◇', color:'#8b5cf6', defaultPriority:3, defaultModel:'Meta-Llama-3.3-70B-Instruct', models:['Meta-Llama-3.3-70B-Instruct','Meta-Llama-3.1-405B-Instruct'], keyEnv:'SAMBANOVA_API_KEY', keyHint:'snova-…', free:true, desc:'Large context streaming-focused inference.', capabilities:['chat','code'] },
  { id:'together',     name:'Together AI',      tier:'free-cloud', icon:'⊕', color:'#06b6d4', defaultPriority:3, defaultModel:'Llama-3.3-70B-Instruct-Turbo-Free', models:['Llama-3.3-70B-Instruct-Turbo-Free','Mixtral-8x7B-Instruct-v0.1-Free'], keyEnv:'TOGETHER_API_KEY', keyHint:'together-…', free:true, desc:'Wide model catalogue, many free options.', capabilities:['chat','code','reasoning'] },
  { id:'mistral',      name:'Mistral',          tier:'free-cloud', icon:'≋', color:'var(--warning)', defaultPriority:3, defaultModel:'mistral-small-latest', models:['mistral-small-latest','mistral-large-latest','codestral-latest','mistral-nemo'], keyEnv:'MISTRAL_API_KEY', keyHint:'mis-…', free:false, desc:'Strong multilingual and code. European provider.', capabilities:['chat','code'] },
  { id:'huggingface',  name:'Hugging Face',     tier:'free-cloud', icon:'🤗', color:'var(--warning)', defaultPriority:3, defaultModel:'serverless', models:['serverless'], keyEnv:'HF_TOKEN', keyHint:'hf_…', free:true, desc:'Serverless inference on thousands of open models.', capabilities:['chat','code'] },
  { id:'cloudflare',   name:'Cloudflare AI',    tier:'free-cloud', icon:'☁', color:'var(--warning)', defaultPriority:3, defaultModel:'@cf/meta/llama-3.3-70b-instruct-fp8-fast', models:['@cf/meta/llama-3.3-70b-instruct-fp8-fast','@cf/mistral/mistral-7b-instruct-v0.2-lora'], keyEnv:'CLOUDFLARE_API_TOKEN', keyHint:'cf_…', free:true, desc:'Edge-deployed inference. Pair with CLOUDFLARE_ACCOUNT_ID.', capabilities:['chat'] },
  { id:'dashscope',    name:'Qwen DashScope',   tier:'free-cloud', icon:'◎', color:'var(--success)', defaultPriority:3, defaultModel:'qwen-plus', models:['qwen-plus','qwen-max','qwen-turbo','qwen-coder-plus'], keyEnv:'DASHSCOPE_API_KEY', keyHint:'sk-…', free:false, desc:'Alibaba Qwen family — strong multilingual + code.', capabilities:['chat','code'] },
  { id:'minimax',      name:'MiniMax',          tier:'free-cloud', icon:'⊡', color:'#7c3aed', defaultPriority:3, defaultModel:'MiniMax-Text-01', models:['MiniMax-Text-01','abab6.5s-chat'], keyEnv:'MINIMAX_API_KEY', keyHint:'eyJ…', free:false, desc:'Long context (1M+) Chinese AI provider.', capabilities:['chat'] },
  { id:'zhipu',        name:'ZhipuAI',          tier:'free-cloud', icon:'◬', color:'#14b8a6', defaultPriority:3, defaultModel:'glm-4-flash', models:['glm-4-flash','glm-4','glm-4-air'], keyEnv:'ZHIPU_API_KEY', keyHint:'zhipu-…', free:true, desc:'GLM-4 family from Zhipu AI. Free flash model.', capabilities:['chat','code'] },
  { id:'zai',          name:'Z.ai (GLM)',       tier:'free-cloud', icon:'◆', color:'#3b82f6', defaultPriority:3, defaultModel:'glm-5.2', models:['glm-5.2','glm-5.1','glm-4-flash','glm-4','glm-4-air'], keyEnv:'ZAI_API_KEY', keyHint:'zai-…', free:true, desc:'GLM-5.2 international endpoint. Free, high-quality, fast.', capabilities:['chat','code','reasoning'] },
  { id:'moonshot',     name:'Moonshot (Kimi)',  tier:'free-cloud', icon:'☽', color:'var(--warning)', defaultPriority:3, defaultModel:'moonshot-v1-8k', models:['moonshot-v1-8k','moonshot-v1-32k','moonshot-v1-128k'], keyEnv:'MOONSHOT_API_KEY', keyHint:'sk-…', free:true, desc:'Long context (128k) Chinese AI provider.', capabilities:['chat','code'] },
  { id:'aerolink',     name:'Aerolink (Claude)',tier:'commercial', icon:'✈', color:'#0ea5e9', defaultPriority:4, defaultModel:'claude-sonnet-4-6', models:['claude-opus-4-8','claude-opus-4-7','claude-fable-5','claude-sonnet-5','claude-sonnet-4-6','claude-opus-4-6','claude-haiku-4-5-20251001'], keyEnv:'AEROLINK_API_KEY', keyHint:'aero-…', free:false, desc:'Claude gateway with $10/week budget. Reliable paid fallback when free providers are rate-limited.', capabilities:['chat','code','reasoning'] },
  { id:'anthropic',    name:'Anthropic',        tier:'commercial', icon:'◬', color:'#d97757', defaultPriority:4, defaultModel:'claude-opus-4-5', models:['claude-opus-4-5','claude-sonnet-4-5','claude-haiku-4-5','claude-3-5-sonnet-20241022'], keyEnv:'ANTHROPIC_API_KEY', keyHint:'sk-ant-…', free:false, desc:'Claude family. Commercial fallback — tried last.', capabilities:['chat','code','reasoning','vision'] },
  { id:'openrouter',   name:'OpenRouter',       tier:'commercial', icon:'⇄', color:'var(--accent)', defaultPriority:4, defaultModel:'configurable', models:['configurable'], keyEnv:'OPENROUTER_API_KEY', keyHint:'sk-or-…', free:false, desc:'Unified gateway to 200+ models. Pay-per-use.', capabilities:['chat','code','reasoning'] },
  { id:'bedrock',      name:'AWS Bedrock',      tier:'commercial', icon:'▲', color:'var(--warning)', defaultPriority:4, defaultModel:'us.anthropic.claude-opus-4-7', models:['us.anthropic.claude-opus-4-7','us.anthropic.claude-sonnet-4-5','amazon.nova-pro-v1:0'], keyEnv:'AWS_ACCESS_KEY_ID', keyHint:'AKIA…', free:false, desc:'AWS-hosted Claude + Amazon Nova via Converse API.', capabilities:['chat','code','reasoning'] },
  // E2B is a sandbox execution runtime (not an LLM provider) — listed here
  // because this is the catalogue users browse for env-configured
  // integrations. The live enabled/health badge is driven by the /runtimes
  // endpoint (RuntimeManager.list_runtimes() includes 'e2b' when
  // E2B_API_KEY is set), so this card is informational only.
  { id:'e2b',          name:'E2B Sandbox',      tier:'free-cloud', icon:'■', color:'#9333ea', defaultPriority:0, defaultModel:'base', models:['base'], keyEnv:'E2B_API_KEY', keyHint:'e2b_…', free:true, desc:'Firecracker micro-VM sandbox for isolated code execution. Auto-on when E2B_API_KEY is set.', capabilities:['code','shell','git'] },
];

const TIER_CONFIG = {
  local:       { label:'Local',       color:'var(--accent)', bg:'color-mix(in oklab, var(--accent) 8%, transparent)',   order:0 },
  free:        { label:'Free Hosted', color:'#76b900', bg:'color-mix(in oklab, var(--success) 8%, transparent)',    order:1 },
  'free-cloud':{ label:'Free Cloud',  color:'var(--success)', bg:'color-mix(in oklab, var(--success) 6%, transparent)',   order:2 },
  commercial:  { label:'Commercial',  color:'var(--warning)', bg:'color-mix(in oklab, var(--warning) 6%, transparent)',  order:3 },
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
  const colors = { chat:'var(--accent)', code:'var(--success)', reasoning:'var(--violet)', vision:'var(--warning)' };
  return <span style={{ fontSize:13, padding:'2px 7px', borderRadius:999, color:colors[cap]||'var(--text-muted)', background:`color-mix(in oklab, ${colors[cap]||'var(--text-muted)'} 7%, transparent)`, border:`1px solid color-mix(in oklab, ${colors[cap]||'var(--text-muted)'} 13%, transparent)` }}>{cap}</span>;
}

// A real, persisted provider record from GET /api/providers.
function BackendProviderCard({ provider, onTest, onSetDefault, onDelete, onEdit, busy }) {
  const [testState, setTestState] = React.useState(null); // null | 'testing' | 'ok' | 'error'
  const [testMsg, setTestMsg]     = React.useState('');
  const isDefault = !!provider.is_default;
  const status    = provider.status || 'configured';
  const statusColor = status === 'online' ? 'var(--success)' : status === 'error' ? 'var(--danger)' : 'var(--text-muted)';

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
    <div style={{ borderRadius:14, border:`1px solid ${provider.is_brain?'color-mix(in oklab, var(--warning) 35%, transparent)':isDefault?'color-mix(in oklab, var(--success) 30%, transparent)':'color-mix(in oklab, var(--ink) 10%, transparent)'}`, background:provider.is_brain?'color-mix(in oklab, var(--warning) 4%, transparent)':isDefault?'color-mix(in oklab, var(--success) 5%, transparent)':'color-mix(in oklab, var(--ink) 3%, transparent)', padding:'14px' }}>
      <div style={{ display:'flex', alignItems:'flex-start', gap:9, marginBottom:9 }}>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap', marginBottom:2 }}>
            <span style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.02em' }}>{provider.name || provider.provider_id}</span>
            {isDefault && <span style={{ fontSize:13, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'var(--success)', background:'color-mix(in oklab, var(--success) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 22%, transparent)' }}><Glyph g="★"/> default</span>}
            {provider.is_brain && <span title={provider.role_reason || 'Used as the brain for agent execution'} style={{ fontSize:13, fontVariantNumeric:'tabular-nums', padding:'2px 6px', borderRadius:999, color:'#f5a623', background:'color-mix(in oklab, var(--warning) 12%, transparent)', border:'1px solid color-mix(in oklab, var(--warning) 30%, transparent)', fontWeight:700 }}><Glyph g="🧠"/> BRAIN</span>}
            {provider.role === 'fallback' && <span title={provider.role_reason || 'Paid fallback — only used when no free provider is configured'} style={{ fontSize:13, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'var(--warning)', background:'color-mix(in oklab, var(--warning) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--warning) 22%, transparent)' }}>fallback</span>}
            {provider.role === 'sub-agent' && <span title={provider.role_reason || 'Reachable backup used by failover'} style={{ fontSize:13, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'var(--violet)', background:'color-mix(in oklab, var(--violet) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--violet) 20%, transparent)' }}>sub-agent</span>}
            {provider.role === 'unconfigured' && <span title={provider.role_reason || 'Missing base URL or API key'} style={{ fontSize:13, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'var(--danger)', background:'color-mix(in oklab, var(--danger) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 20%, transparent)' }}>unconfigured</span>}
            <span style={{ fontSize:13, padding:'2px 6px', borderRadius:999, color:'var(--text-muted)', background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)' }}>{provider.type || 'openai-compatible'}</span>
          </div>
          <div style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{provider.base_url || '—'}</div>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:5, flexShrink:0 }}>
          <span style={{ width:7, height:7, borderRadius:'50%', background:statusColor }}/>
          <span style={{ fontSize:13, color:statusColor }}>{status}</span>
        </div>
      </div>

      <div style={{ display:'flex', gap:10, fontSize:13, color:'var(--text-muted)', marginBottom:10, flexWrap:'wrap' }}>
        <span>Model: <span style={{ color:'var(--text-secondary)', fontVariantNumeric:'tabular-nums' }}>{provider.default_model || '—'}</span></span>
        {provider.api_key_masked ? <span>Key: <span style={{ color:'var(--text-secondary)', fontVariantNumeric:'tabular-nums' }}>{provider.api_key_masked}</span></span> : <span style={{ color:'var(--success)' }}>no key</span>}
        <span title="Higher number = tried first. Negative values allowed.">Priority: <span style={{ color:'var(--text-secondary)', fontVariantNumeric:'tabular-nums' }}>{provider.priority ?? '—'}</span></span>
      </div>

      {testState && (
        <div style={{ fontSize:13, marginBottom:9, color: testState==='ok'?'var(--success)':testState==='error'?'var(--danger)':'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>
          {testState==='testing' ? 'Testing…' : testMsg}
        </div>
      )}

      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
        <button onClick={test} disabled={testState==='testing'} style={{ padding:'6px 12px', borderRadius:9, fontSize:13, fontWeight:600, cursor:'pointer', background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)' }}>Test</button>
        <button onClick={()=>onEdit(provider)} disabled={busy} style={{ padding:'6px 12px', borderRadius:9, fontSize:13, fontWeight:600, cursor:'pointer', background:'color-mix(in oklab, var(--violet) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--violet) 25%, transparent)', color:'var(--violet)' }}>Edit</button>
        {!isDefault &&        <button onClick={()=>onSetDefault(provider.provider_id)} disabled={busy} title="Fallback provider when no routing rule matches" style={{ padding:'6px 12px', borderRadius:9, fontSize:13, fontWeight:600, cursor:'pointer', background:'color-mix(in oklab, var(--success) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 22%, transparent)', color:'var(--success)' }}>Set default</button>}
        <button onClick={()=>onDelete(provider)} disabled={busy} style={{ padding:'6px 12px', borderRadius:9, fontSize:13, fontWeight:600, cursor:'pointer', background:'color-mix(in oklab, var(--danger) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 20%, transparent)', color:'var(--danger)', marginLeft:'auto' }}>Delete</button>
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

  const fld = { width:'100%', padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)' };
  return (
    <div style={{ borderRadius:14, border:'1px solid color-mix(in oklab, var(--accent) 20%, transparent)', background:'color-mix(in oklab, var(--accent) 4%, transparent)', padding:'16px', marginBottom:14 }}>
      <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', marginBottom:12 }}>Add provider</div>
      <div style={{ fontSize:13, color:'var(--text-muted)', marginBottom:6 }}>Quick-fill from catalogue</div>
      <div style={{ display:'flex', gap:5, flexWrap:'wrap', marginBottom:12 }}>
        {ALL_PROVIDERS.slice(0,8).map(p => (
          <button key={p.id} onClick={()=>applyTemplate(p)} style={{ padding:'4px 10px', borderRadius:999, fontSize:13, cursor:'pointer', background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-muted)' }}>{p.icon} {p.name}</button>
        ))}
      </div>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:10 }}>
        <input value={providerId} onChange={e=>setProviderId(e.target.value)} placeholder="provider id (e.g. groq)" style={{ ...fld, fontFamily:'var(--font-mono)' }}/>
        <input value={name} onChange={e=>setName(e.target.value)} placeholder="Display name" style={fld}/>
      </div>
      <div style={{ display:'flex', gap:8, marginBottom:10 }}>
        {['openai-compatible','ollama'].map(t => (
          <button key={t} onClick={()=>setType(t)} style={{ padding:'7px 14px', borderRadius:999, fontSize:13, fontWeight:600, cursor:'pointer', background:type===t?'color-mix(in oklab, var(--accent) 15%, transparent)':'color-mix(in oklab, var(--ink) 4%, transparent)', border:`1px solid ${type===t?'color-mix(in oklab, var(--accent) 35%, transparent)':'color-mix(in oklab, var(--ink) 9%, transparent)'}`, color:type===t?'var(--text-primary)':'var(--text-muted)' }}>{t}</button>
        ))}
      </div>
      <input value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} placeholder={type==='ollama'?'Ollama base URL (optional)':'Base URL (https://api.example.com/v1)'} style={{ ...fld, fontFamily:'var(--font-mono)', marginBottom:10 }}/>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:12 }}>
        <input type="password" value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder="API key (optional)" style={{ ...fld, fontVariantNumeric:'tabular-nums' }}/>
        <input value={model} onChange={e=>setModel(e.target.value)} placeholder="Default model" style={{ ...fld, fontVariantNumeric:'tabular-nums' }}/>
      </div>
      {error && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 25%, transparent)', color:'var(--danger)', fontSize:13 }}>{error}</div>}
      <div style={{ display:'flex', gap:8 }}>
        <button onClick={submit} disabled={busy} style={{ flex:1, padding:'10px', borderRadius:12, background:'linear-gradient(135deg,var(--accent),var(--accent))', color:'var(--on-accent)', fontSize:14, fontWeight:700, border:'none', cursor:busy?'wait':'pointer', opacity:busy?0.7:1 }}>{busy ? 'Saving…' : '+ Add provider'}</button>
        <button onClick={onClose} disabled={busy} style={{ padding:'10px 18px', borderRadius:12, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-muted)', fontSize:14, cursor:'pointer' }}>Cancel</button>
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
  // When set, also push the key/base_url into the Render env so the runtime
  // brain (which reads keys from the environment, not Mongo) picks them up.
  const [pushRender, setPushRender] = React.useState(false);
  const [renderNote, setRenderNote] = React.useState('');

  const submit = async () => {
    if (busy) return;
    setBusy(true); setError(null); setRenderNote('');
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
    } catch (e) {
      setError(errText(e, 'Failed to update provider.'));
      setBusy(false);
      return;
    }
    // Optional: push key/base_url to Render env (runtime). Kept separate from
    // the Mongo save so a Render-side failure doesn't lose the saved config.
    if (pushRender && (apiKey.trim() || baseUrl.trim())) {
      const rp = {};
      if (apiKey.trim())  rp.api_key = apiKey.trim();
      if (baseUrl.trim()) rp.base_url = baseUrl.trim();
      try {
        const { data } = await api.syncProviderToRender(provider.provider_id, rp);
        setRenderNote(data?.note || 'Saved to Render.');
        setBusy(false);
        return;  // keep the form open so the operator sees the Render note
      } catch (e) {
        setError(errText(e, 'Saved to config, but Render env update failed.'));
        setBusy(false);
        return;
      }
    }
    onClose();
  };

  const fld = { width:'100%', padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)' };
  return (
    <div style={{ borderRadius:14, border:'1px solid color-mix(in oklab, var(--violet) 25%, transparent)', background:'color-mix(in oklab, var(--violet) 5%, transparent)', padding:'16px', marginBottom:14 }}>
      <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', marginBottom:2 }}>Edit provider</div>
      <div style={{ fontSize:13, fontFamily:'var(--font-mono)', color:'var(--text-muted)', marginBottom:12 }}>{provider.provider_id}</div>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(160px, 1fr))', gap:10, marginBottom:10 }}>
        <input value={name} onChange={e=>setName(e.target.value)} placeholder="Display name" style={fld}/>
        <input value={priority} onChange={e=>setPriority(e.target.value)} placeholder="Priority (lower = first)" inputMode="numeric" style={{ ...fld, fontFamily:'var(--font-mono)' }}/>
      </div>
      <input value={baseUrl} onChange={e=>setBaseUrl(e.target.value)} placeholder="Base URL (https://api.example.com/v1)" style={{ ...fld, fontFamily:'var(--font-mono)', marginBottom:10 }}/>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(160px, 1fr))', gap:10, marginBottom:12 }}>
        <input type="password" value={apiKey} onChange={e=>setApiKey(e.target.value)} placeholder={provider.api_key_masked ? `Leave blank to keep (${provider.api_key_masked})` : 'API key (optional)'} style={{ ...fld, fontVariantNumeric:'tabular-nums' }}/>
        <input value={model} onChange={e=>setModel(e.target.value)} placeholder="Default model" style={{ ...fld, fontVariantNumeric:'tabular-nums' }}/>
      </div>
      {/* Runtime persistence: the brain reads provider keys from Render env, not
          Mongo, so this pushes the key/base_url there. Off by default — it's a
          production env write and requires RENDER_MCP_ALLOW_WRITES on the backend. */}
      <label style={{ display:'flex', alignItems:'flex-start', gap:8, marginBottom:12, cursor:'pointer', fontSize:13, color:'var(--text-secondary)', lineHeight:1.45 }}>
        <input type="checkbox" checked={pushRender} onChange={e=>setPushRender(e.target.checked)} style={{ marginTop:2 }}/>
        <span>Also save the key / base URL to <strong>Render</strong> (runtime). The live brain reads keys from the environment — without this, the edit only updates the dashboard record. Takes effect on the next deploy.</span>
      </label>
      {renderNote && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--success) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 25%, transparent)', color:'var(--success)', fontSize:13 }}>{renderNote}</div>}
      {error && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 25%, transparent)', color:'var(--danger)', fontSize:13 }}>{error}</div>}
      <div style={{ display:'flex', gap:8 }}>
        <button onClick={submit} disabled={busy} style={{ flex:1, padding:'10px', borderRadius:12, background:'linear-gradient(135deg,var(--violet),#a78bfa)', color:'var(--on-accent)', fontSize:14, fontWeight:700, border:'none', cursor:busy?'wait':'pointer', opacity:busy?0.7:1 }}>{busy ? 'Saving…' : 'Save changes'}</button>
        <button onClick={onClose} disabled={busy} style={{ padding:'10px 18px', borderRadius:12, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-muted)', fontSize:14, cursor:'pointer' }}>Cancel</button>
      </div>
    </div>
  );
}

// Read-only reference card for the popular-integrations catalogue.
function CatalogCard({ provider }) {
  const tier = TIER_CONFIG[provider.tier] || TIER_CONFIG.commercial;
  return (
    <div style={{ borderRadius:16, border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', background:'color-mix(in oklab, var(--ink) 2.5%, transparent)', padding:'12px' }}>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:6 }}>
        <div style={{ width:30, height:30, borderRadius:9, flexShrink:0, background:`color-mix(in oklab, ${provider.color} 8%, transparent)`, border:`1px solid color-mix(in oklab, ${provider.color} 16%, transparent)`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:14 }}><Glyph g={provider.icon}/></div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:13, fontWeight:700, color:'var(--text-primary)' }}>{provider.name}</div>
          <div style={{ fontSize:13, color:tier.color }}>{tier.label}</div>
        </div>
      </div>
      <div style={{ fontSize:13, color:'var(--text-muted)', lineHeight:1.4, marginBottom:6 }}>{provider.desc}</div>
      {provider.keyEnv && <div style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-tertiary)' }}>env: {provider.keyEnv}</div>}
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
      setPullErr(`Pull failed: ${api.fmtErr(e?.response?.data?.detail) || e.message}`);
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

  const typeColor = { coder:'var(--accent)', reasoning:'var(--violet)', general:'var(--success)' };

  return (
    <div>
      <div style={{ padding:'10px 14px', borderRadius:14, background:'color-mix(in oklab, var(--accent) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 15%, transparent)', marginBottom:16, fontSize:13, color:'var(--text-secondary)', lineHeight:1.6 }}>
        <strong style={{ color:'var(--accent)' }}>Local Ollama</strong> — Models run entirely on your hardware. No API key, no data leaves your machine. Add any model by name using the form below, or pull from the list.
      </div>

      {/* Custom pull */}
      <div style={{ display:'flex', gap:8, marginBottom:14 }}>
        <input value={customModel} onChange={e=>setCustomModel(e.target.value)} placeholder="e.g. phi4:latest or llava:13b"
          style={{ flex:1, padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 12%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontVariantNumeric:'tabular-nums', transition:'border-color 0.2s' }}
          onFocus={e=>e.target.style.borderColor='color-mix(in oklab, var(--accent) 45%, transparent)'} onBlur={e=>e.target.style.borderColor='color-mix(in oklab, var(--ink) 12%, transparent)'}/>
        <button onClick={()=>{ if(customModel.trim()){ pull(customModel.trim()); setCustomModel(''); }}} style={{ padding:'9px 16px', borderRadius:10, background:'color-mix(in oklab, var(--accent) 15%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 30%, transparent)', color:'var(--accent)', fontSize:13, fontWeight:700, cursor:'pointer' }}>Pull model</button>
        <a href="https://ollama.com/library" target="_blank" rel="noreferrer" style={{ padding:'9px 12px', borderRadius:10, background:'transparent', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-muted)', fontSize:13, textDecoration:'none', display:'inline-flex', alignItems:'center', whiteSpace:'nowrap' }}>Browse library →</a>
      </div>

      {(loadErr || pullErr) && (
        <div style={{ padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 20%, transparent)', color:'var(--danger)', fontSize:13, marginBottom:10 }}>
          {loadErr || pullErr}
        </div>
      )}

      {liveModels === null && !loadErr && (
        <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)', textAlign:'center' }}>Loading models from Ollama…</div>
      )}

      <div style={{ display:'flex', flexDirection:'column', gap:7 }}>
        {models.map(m => {
          const isPulled = m.status === 'pulled';
          const isRunning = pulling === m.name;
          const tc = typeColor[m.type] || 'var(--text-muted)';
          return (
            <div key={m.name} style={{ display:'flex', alignItems:'center', gap:10, padding:'11px 14px', borderRadius:13, border:`1px solid ${isPulled?'color-mix(in oklab, var(--success) 18%, transparent)':'color-mix(in oklab, var(--ink) 8%, transparent)'}`, background:isPulled?'color-mix(in oklab, var(--success) 4%, transparent)':'color-mix(in oklab, var(--ink) 2.5%, transparent)' }}>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:2, flexWrap:'wrap' }}>
                  <span style={{ fontSize:14, fontWeight:600, color:isPulled?'var(--text-primary)':'var(--text-tertiary)', fontVariantNumeric:'tabular-nums' }}>{m.name}</span>
                  <span style={{ fontSize:13, padding:'1px 6px', borderRadius:999, color:tc, background:`color-mix(in oklab, ${tc} 7%, transparent)`, border:`1px solid color-mix(in oklab, ${tc} 13%, transparent)` }}>{m.type}</span>
                  {isPulled && <span style={{ fontSize:13, padding:'1px 6px', borderRadius:999, color:'var(--success)', background:'color-mix(in oklab, var(--success) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 20%, transparent)' }}>on device</span>}
                </div>
                <div style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)' }}>{m.size} · {m.ctx} context</div>
              </div>
              {isRunning ? (
                <div style={{ display:'flex', alignItems:'center', gap:7, fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--accent)' }}>
                  <div style={{ width:12, height:12, border:'2px solid color-mix(in oklab, var(--accent) 20%, transparent)', borderTopColor:'var(--accent)', borderRadius:'50%', animation:'spin 0.8s linear infinite' }}/>Pulling…
                </div>
              ) : isPulled ? (
                <button onClick={()=>removeModel(m.name)} style={{ padding:'5px 12px', borderRadius:8, fontSize:13, cursor:'pointer', background:'color-mix(in oklab, var(--danger) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 20%, transparent)', color:'var(--danger)' }}>Remove</button>
              ) : (
                <button onClick={()=>pull(m.name)} style={{ padding:'5px 12px', borderRadius:8, fontSize:13, fontWeight:600, cursor:'pointer', background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 22%, transparent)', color:'var(--accent)' }}>↓ Pull</button>
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

  // Only 'error' is red. 'unconfigured' is amber (an operator can act on it).
  // 'available' is green: the server is configured and its capability is served
  // another way (github through the backend's github_tools), even though the
  // backend cannot dial the stdio process — that is a working state, not a
  // fault. 'unavailable' stays muted for the same not-a-fault reason. Colouring
  // either red sends people hunting for a break that isn't there.
  const statusColor = {
    connected:'var(--success)', available:'var(--success)', error:'var(--danger)',
    unconfigured:'var(--warning)', unavailable:'var(--text-muted)',
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
      alert('Could not add server: ' + (api.fmtErr(e?.response?.data?.detail) || e.message));
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

      <div style={{ padding:'10px 14px', borderRadius:14, background:'color-mix(in oklab, var(--violet) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--violet) 15%, transparent)', marginBottom:16, fontSize:13, color:'var(--text-secondary)', lineHeight:1.6 }}>
        <strong style={{ color:'var(--violet)' }}>Model Context Protocol</strong> — MCP servers expose tools, resources, and prompts to agents. Connect any MCP-compatible server to give agents new capabilities (filesystem, databases, search, APIs).
      </div>

      <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:12 }}>
        <button onClick={()=>setShowAdd(o=>!o)} style={{ padding:'8px 16px', borderRadius:10, fontSize:13, fontWeight:700, cursor:'pointer', background:'color-mix(in oklab, var(--violet) 12%, transparent)', border:'1px solid color-mix(in oklab, var(--violet) 25%, transparent)', color:'var(--violet)' }}>+ Add MCP server</button>
      </div>

      {showAdd && (
        <div style={{ padding:'14px', borderRadius:14, background:'color-mix(in oklab, var(--violet) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--violet) 18%, transparent)', marginBottom:12, animation:'fadeSlideUp 0.2s ease-out' }}>
          <div style={{ display:'flex', flexDirection:'column', gap:9 }}>
            <input value={newName} onChange={e=>setNewName(e.target.value)} placeholder="Server name (e.g. my-database)"
              style={{ padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-mono)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='color-mix(in oklab, var(--violet) 45%, transparent)'} onBlur={e=>e.target.style.borderColor='color-mix(in oklab, var(--ink) 10%, transparent)'}/>
            <input value={newCmd} onChange={e=>setNewCmd(e.target.value)} placeholder="Start command (e.g. npx @modelcontextprotocol/server-postgres $DB_URL)"
              style={{ padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-mono)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='color-mix(in oklab, var(--violet) 45%, transparent)'} onBlur={e=>e.target.style.borderColor='color-mix(in oklab, var(--ink) 10%, transparent)'}/>
            <input value={newDesc} onChange={e=>setNewDesc(e.target.value)} placeholder="Description (optional)"
              style={{ padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='color-mix(in oklab, var(--violet) 45%, transparent)'} onBlur={e=>e.target.style.borderColor='color-mix(in oklab, var(--ink) 10%, transparent)'}/>
            <div style={{ display:'flex', gap:8 }}>
              <button onClick={addServer} disabled={saving} style={{ flex:1, padding:'9px', borderRadius:10, background:saving?'color-mix(in oklab, var(--violet) 7%, transparent)':'color-mix(in oklab, var(--violet) 15%, transparent)', border:'1px solid color-mix(in oklab, var(--violet) 30%, transparent)', color:'var(--violet)', fontSize:14, fontWeight:700, cursor:saving?'not-allowed':'pointer' }}>{saving ? 'Adding…' : 'Add server'}</button>
              <button onClick={()=>setShowAdd(false)} style={{ padding:'9px 14px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-muted)', fontSize:14, cursor:'pointer' }}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {loadErr && <div style={{ padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 20%, transparent)', color:'var(--danger)', fontSize:13, marginBottom:10 }}>{loadErr}</div>}
      {servers === null && !loadErr && <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)', textAlign:'center' }}>Loading MCP servers…</div>}

      <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
        {(servers || []).map(srv => {
          const sc = statusColor[srv.status] || 'var(--text-muted)';
          // 'available' is a healthy state (configured, capability served
          // elsewhere), so it gets the same green card treatment as 'connected'.
          const healthy = srv.status === 'connected' || srv.status === 'available';
          return (
            <div key={srv.id} style={{ padding:'12px 14px', borderRadius:14, border:`1px solid ${healthy?'color-mix(in oklab, var(--success) 18%, transparent)':srv.status==='error'?'color-mix(in oklab, var(--danger) 18%, transparent)':'color-mix(in oklab, var(--ink) 8%, transparent)'}`, background:healthy?'color-mix(in oklab, var(--success) 4%, transparent)':srv.status==='error'?'color-mix(in oklab, var(--danger) 4%, transparent)':'color-mix(in oklab, var(--ink) 2.5%, transparent)' }}>
              <div style={{ display:'flex', alignItems:'flex-start', gap:9, marginBottom:5 }}>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:3, flexWrap:'wrap' }}>
                    <span style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', fontVariantNumeric:'tabular-nums' }}>{srv.name}</span>
                    <div style={{ display:'flex', alignItems:'center', gap:4 }}>
                      <span style={{ width:6, height:6, borderRadius:'50%', background:sc, animation:srv.status==='connected'?'pulse 2s infinite':'none' }}/>
                      <span style={{ fontSize:13, color:sc }}>{srv.status}</span>
                    </div>
                    {srv.tools > 0 && <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)', padding:'1px 6px', borderRadius:5, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 9%, transparent)' }}>{srv.tools} tools</span>}
                    {srv.managed && <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--accent)', padding:'1px 6px', borderRadius:5, background:'color-mix(in oklab, var(--accent) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 18%, transparent)' }} title="Declared by this deployment; status is measured live">platform</span>}
                  </div>
                  <div style={{ fontSize:13, color:'var(--text-muted)', lineHeight:1.5, marginBottom:4 }}>{srv.desc}</div>
                  {/* Why a server is not connected is the actionable part — an
                      "unconfigured" badge with no reason just relocates the question. */}
                  {srv.reason && srv.status !== 'connected' && (
                    <div style={{ fontSize:13, color:sc, lineHeight:1.5, marginBottom:4 }}>{srv.reason}</div>
                  )}
                  <div style={{ fontSize:13, fontFamily:'var(--font-mono)', color:'color-mix(in oklab, var(--ink) 35%, transparent)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{srv.cmd}</div>
                </div>
                {/* Platform-managed servers come from configuration, so there is
                    nothing to delete and no client-side connect to toggle. */}
                {srv.managed ? (
                  <div style={{ display:'flex', gap:5, flexShrink:0 }}>
                    <button onClick={loadServers} style={{ padding:'4px 10px', borderRadius:8, fontSize:13, cursor:'pointer', background:'color-mix(in oklab, var(--accent) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 20%, transparent)', color:'var(--accent)' }} title="Re-probe this server">Re-check</button>
                  </div>
                ) : (
                <div style={{ display:'flex', gap:5, flexShrink:0 }}>
                  <button onClick={()=>removeServer(srv)} style={{ padding:'4px 8px', borderRadius:8, fontSize:13, cursor:'pointer', background:'color-mix(in oklab, var(--danger) 6%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 15%, transparent)', color:'color-mix(in oklab, var(--danger) 60%, transparent)' }} title="Remove">✕</button>
                  <button onClick={()=>toggleConnect(srv)} style={{ padding:'4px 10px', borderRadius:8, fontSize:13, cursor:'pointer', background:srv.status==='connected'?'color-mix(in oklab, var(--danger) 8%, transparent)':'color-mix(in oklab, var(--success) 10%, transparent)', border:`1px solid ${srv.status==='connected'?'color-mix(in oklab, var(--danger) 20%, transparent)':'color-mix(in oklab, var(--success) 22%, transparent)'}`, color:srv.status==='connected'?'var(--danger)':'var(--success)' }}>
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

// Tabs, in the order an operator reaches for them. Brain & Routing used to be a
// collapsed block at the very bottom of the Providers tab — reachable only after
// scrolling past every provider row, and its cards still fetched on every load.
const TABS = [
  { id: 'providers', label: 'Providers' },
  { id: 'brain',     label: 'Brain & Routing' },
  { id: 'ollama',    label: 'Local (Ollama)' },
  { id: 'mcp',       label: 'MCP' },
];

function initialTab() {
  const hash = ((typeof window !== 'undefined' && window.location.hash) || '').replace('#', '');
  return TABS.some(t => t.id === hash) ? hash : 'providers';
}

function ProvidersScreen() {
  const [tab, setTabState]    = React.useState(initialTab);
  const [showAdd, setShowAdd] = React.useState(false);
  const [editingId, setEditingId] = React.useState(null);
  const [busy, setBusy]       = React.useState(false);
  const [actionErr, setActionErr] = React.useState(null);

  // Paid-provider policy and per-surface assignments come from one endpoint;
  // they used to be fetched twice on every load.
  const [policy, setPolicy] = React.useState(null);  // null = loading
  const [policyBusy, setPolicyBusy] = React.useState(false);
  const [policyErr, setPolicyErr] = React.useState(null);
  const [surfaces, setSurfaces] = React.useState(null);
  const [surfaceBusy, setSurfaceBusy] = React.useState(null);  // which surface is saving

  const setTab = (next) => {
    setTabState(next);
    try { window.history.replaceState(null, '', `#${next}`); } catch { /* non-browser */ }
  };

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.getProviderPolicy();
        if (cancelled) return;
        setPolicy(data);
        setSurfaces(data.surfaces || {});
      } catch {
        if (cancelled) return;
        setPolicyErr('Could not load provider policy.');
        setPolicy({ allow_paid: false });  // failsafe default
        setSurfaces({});
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // The segmented control names the state it wants rather than flipping
  // whatever is current, so a double-click cannot race itself into the
  // opposite of what the operator clicked.
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

  const consoleProps = {
    storedProviders: providers,
    policy, policyBusy,
    onTogglePaid: setPaidAccess,
    onEditProvider: (prov) => { setEditingId(prov.provider_id); setShowAdd(false); },
    onDeleteProvider: handleDelete,
    onTestProvider: api.testProvider,
    onSetRenderKey: api.syncProviderToRender,
    onSetDefault: handleSetDefault,
    editingId,
    renderEditor: (prov) => (
      <EditProviderForm provider={prov} onUpdate={handleUpdate} onClose={() => setEditingId(null)} />
    ),
    refreshStored: refetch,
  };

  const errBox = { marginTop: 10, padding: '8px 12px', borderRadius: 10, background: 'color-mix(in oklab, var(--danger) 10%, transparent)', border: '1px solid color-mix(in oklab, var(--danger) 25%, transparent)', color: 'var(--danger)', fontSize:13 };
  const section = { borderRadius: 16, border: '1px solid color-mix(in oklab, var(--ink) 8%, transparent)', background: 'color-mix(in oklab, var(--ink) 2.5%, transparent)', padding: '14px 16px' };
  const sectionTitle = { fontSize:14, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 };
  const sectionHint = { fontSize:13, color: 'var(--text-tertiary)', lineHeight: 1.5, marginBottom: 11 };

  return (
    <div style={{ padding:'16px 16px 48px', maxWidth:1200, margin:'0 auto' }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:12 }}>
        <h1 style={{ fontSize:24, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.04em', lineHeight:1.1 }}>Providers & models</h1>
        {tab === 'providers' && (
          <button onClick={() => { setShowAdd(o => !o); setEditingId(null); }} style={{ padding: '9px 16px', borderRadius: 10, fontSize:14, fontWeight: 700, cursor: 'pointer', background: 'color-mix(in oklab, var(--accent) 12%, transparent)', border: '1px solid color-mix(in oklab, var(--accent) 30%, transparent)', color: 'var(--accent)' }}>
            {showAdd ? 'Cancel' : '+ Add provider'}
          </button>
        )}
      </div>

      {/* Tabs — scroll sideways on a phone rather than wrapping into two rows. */}
      <div role="tablist" style={{ display:'flex', gap:6, marginBottom:14, overflowX:'auto', WebkitOverflowScrolling:'touch', paddingBottom:2 }}>
        {TABS.map(t => (
          <button key={t.id} role="tab" aria-selected={tab===t.id} onClick={()=>setTab(t.id)} style={{ flex:'0 0 auto', padding:'9px 16px', borderRadius:999, fontSize:14, fontWeight:600, cursor:'pointer', whiteSpace:'nowrap', background:tab===t.id?'color-mix(in oklab, var(--accent) 15%, transparent)':'color-mix(in oklab, var(--ink) 4%, transparent)', border:`1px solid ${tab===t.id?'color-mix(in oklab, var(--accent) 35%, transparent)':'color-mix(in oklab, var(--ink) 8%, transparent)'}`, color:tab===t.id?'var(--text-primary)':'var(--text-muted)' }}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'providers' && (
        <>
          {showAdd && <div style={{ marginBottom: 12 }}><AddProviderForm onCreate={handleCreate} onClose={() => setShowAdd(false)} /></div>}
          <ProviderConsole {...consoleProps} section="providers" />
          {actionErr && <div style={errBox}>{actionErr}</div>}
          {states.providers?.error && (
            <div style={{ marginTop: 10, fontSize:13, color: 'var(--warning)' }}>
              Couldn't load saved providers: {states.providers.error}
            </div>
          )}
        </>
      )}

      {tab === 'brain' && (
        <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
          <ProviderConsole {...consoleProps} section="routing" />
          {policyErr && <div style={errBox}>{policyErr}</div>}

          <BrainCard />
          <LocalBrainToggleCard />

          {surfaces && Object.keys(surfaces).length > 0 && (
            <div style={section}>
              <div style={sectionTitle}>Per-surface overrides</div>
              <div style={sectionHint}>Pin a surface to one provider, or leave it on Auto to follow the routing strategy.</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 7 }}>
                {Object.entries(surfaces).map(([surface, providerId]) => (
                  <label key={surface} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '7px 9px', borderRadius: 9, background: 'color-mix(in oklab, var(--ink) 3%, transparent)', border: '1px solid color-mix(in oklab, var(--ink) 7%, transparent)' }}>
                    <span style={{ fontSize:13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'capitalize', minWidth: 56 }}>{surface}</span>
                    <select
                      value={providerId || 'auto'}
                      onChange={(e) => saveSurface(surface, e.target.value)}
                      disabled={surfaceBusy === surface}
                      style={{ flex: 1, minWidth: 0, padding: '6px 6px', borderRadius: 6, background: 'color-mix(in oklab, var(--ink) 5%, transparent)', border: '1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:13, outline: 'none', cursor: 'pointer', opacity: surfaceBusy === surface ? 0.5 : 1 }}
                    >
                      <option value="auto">Auto (strategy)</option>
                      {providers.map(p => (
                        <option key={p.provider_id} value={p.provider_id}>{p.name || p.provider_id}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
            </div>
          )}

          <ProviderHealthToggleCard />
          <p style={{ fontSize:13, lineHeight: 1.6, color: 'var(--text-tertiary)' }}>
            Global brain policy (preferred brain, local fallback) lives in{' '}
            <Link to="/v5/controls" style={{ color: 'var(--accent)' }}>Controls → Brain &amp; Model Routing</Link>.
          </p>
        </div>
      )}

      {tab === 'ollama' && <OllamaTab/>}
      {tab === 'mcp'     && <MCPTab/>}
    </div>
  );
}

export { ProvidersScreen };
export default ProvidersScreen;
