/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';


// providers.jsx — V5.0: All providers + Ollama model management + MCP servers tab

const LS_KEY = 'llmrelay_provider_config_v5';

const ALL_PROVIDERS = [
  { id:'nvidia-nim',   name:'NVIDIA NIM',      tier:'free',       icon:'⬡', color:'#76b900', defaultPriority:0, defaultModel:'nvidia/nemotron-3-super-120b-a12b', models:['nvidia/nemotron-3-super-120b-a12b','nvidia/llama-3.1-nemotron-70b-instruct','nvidia/mistral-nemo-12b-instruct'], keyEnv:'NVIDIA_API_KEY', keyHint:'nvapi-…', free:true, desc:'Free hosted inference. No GPU needed. Priority 0 — tried first.', capabilities:['chat','code','reasoning'] },
  { id:'ollama',       name:'Local Ollama',     tier:'local',      icon:'◎', color:'#5da2ff', defaultPriority:1, defaultModel:'qwen3-coder:30b', models:['qwen3-coder:7b','qwen3-coder:30b','qwen3-coder:235b','qwen3.6:35b','deepseek-r1:32b','deepseek-r1:671b','deepseek-v3:685b','gemma4:9b','gemma4:27b','llama4-scout:17b','llama4-maverick:17b'], keyEnv:null, free:true, desc:'Fully local, private, on-device. Manage models from the Ollama tab.', capabilities:['chat','code','reasoning','vision'] },
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
  { id:'anthropic',    name:'Anthropic',        tier:'commercial', icon:'◬', color:'#d97757', defaultPriority:4, defaultModel:'claude-opus-4-5', models:['claude-opus-4-5','claude-sonnet-4-5','claude-haiku-4-5','claude-3-5-sonnet-20241022'], keyEnv:'ANTHROPIC_API_KEY', keyHint:'sk-ant-…', free:false, desc:'Claude family. Commercial fallback — tried last.', capabilities:['chat','code','reasoning','vision'] },
  { id:'openrouter',   name:'OpenRouter',       tier:'commercial', icon:'⇄', color:'#6366f1', defaultPriority:4, defaultModel:'configurable', models:['configurable'], keyEnv:'OPENROUTER_API_KEY', keyHint:'sk-or-…', free:false, desc:'Unified gateway to 200+ models. Pay-per-use.', capabilities:['chat','code','reasoning'] },
  { id:'bedrock',      name:'AWS Bedrock',      tier:'commercial', icon:'▲', color:'#ff9900', defaultPriority:4, defaultModel:'us.anthropic.claude-opus-4-7', models:['us.anthropic.claude-opus-4-7','us.anthropic.claude-sonnet-4-5','amazon.nova-pro-v1:0'], keyEnv:'AWS_ACCESS_KEY_ID', keyHint:'AKIA…', free:false, desc:'AWS-hosted Claude + Amazon Nova via Converse API.', capabilities:['chat','code','reasoning'] },
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

// MCP servers
const MCP_SERVERS_DEFAULT = [
  { id:'mcp-1', name:'filesystem',      cmd:'npx @modelcontextprotocol/server-filesystem /workspace', status:'connected', tools:5,  desc:'Read/write local filesystem. Agents use this for code edits.' },
  { id:'mcp-2', name:'github',          cmd:'npx @modelcontextprotocol/server-github',               status:'connected', tools:12, desc:'GitHub API — issues, PRs, commits, repos.' },
  { id:'mcp-3', name:'postgres',        cmd:'npx @modelcontextprotocol/server-postgres $DB_URL',     status:'error',     tools:8,  desc:'Query and update your PostgreSQL database.' },
  { id:'mcp-4', name:'brave-search',    cmd:'npx @modelcontextprotocol/server-brave-search',         status:'idle',      tools:2,  desc:'Web search via Brave. Good for research agents.' },
];

function loadConfig() { try { return JSON.parse(localStorage.getItem(LS_KEY)||'{}'); } catch { return {}; } }
function saveConfig(cfg) { try { localStorage.setItem(LS_KEY, JSON.stringify(cfg)); } catch {} }

window.__getProviderConfig = () => loadConfig();
window.__getAllProviders   = () => ALL_PROVIDERS;

function CapBadge({ cap }) {
  const colors = { chat:'#5da2ff', code:'#46d9a4', reasoning:'#c4b5fd', vision:'#ffbd66' };
  return <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.08em', textTransform:'uppercase', padding:'2px 7px', borderRadius:999, color:colors[cap]||'var(--text-muted)', background:`${colors[cap]||'#fff'}12`, border:`1px solid ${colors[cap]||'#fff'}22` }}>{cap}</span>;
}

function ProviderCard({ provider, cfg, onToggle, onKeyChange, onModelChange, onPriorityChange, isTop }) {
  const enabled  = cfg.enabled !== false;
  const key      = cfg.key || '';
  const model    = cfg.model || provider.defaultModel;
  const priority = cfg.priority ?? provider.defaultPriority;
  const tier     = TIER_CONFIG[provider.tier] || TIER_CONFIG.commercial;
  const [showKey, setShowKey] = React.useState(false);

  return (
    <div style={{ borderRadius:18, border:`1px solid ${enabled?(isTop?`${provider.color}35`:'rgba(255,255,255,0.10)'):'rgba(255,255,255,0.06)'}`, background:enabled?(isTop?`${provider.color}07`:'rgba(255,255,255,0.03)'):'rgba(255,255,255,0.015)', padding:'14px', transition:'all 0.2s ease', opacity:enabled?1:0.55 }}>
      <div style={{ display:'flex', alignItems:'flex-start', gap:9, marginBottom:9 }}>
        <div style={{ width:36, height:36, borderRadius:11, flexShrink:0, background:`${provider.color}15`, border:`1px solid ${provider.color}28`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:16 }}>{provider.icon}</div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap', marginBottom:2 }}>
            <span style={{ fontSize:13, fontWeight:800, color:enabled?'#fff':'var(--text-muted)', letterSpacing:'-0.02em' }}>{provider.name}</span>
            <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.12em', textTransform:'uppercase', padding:'2px 6px', borderRadius:999, color:tier.color, background:tier.bg, border:`1px solid ${tier.color}28` }}>{tier.label}</span>
            {isTop && <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'#46d9a4', background:'rgba(70,217,164,0.10)', border:'1px solid rgba(70,217,164,0.22)' }}>★ P{priority}</span>}
            {provider.free && !isTop && <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 6px', borderRadius:999, color:'#46d9a4', background:'rgba(70,217,164,0.07)', border:'1px solid rgba(70,217,164,0.15)' }}>free</span>}
          </div>
          <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.4 }}>{provider.desc}</div>
        </div>
        <button onClick={()=>onToggle(!enabled)} style={{ width:38, height:22, borderRadius:999, padding:3, cursor:'pointer', background:enabled?provider.color:'rgba(255,255,255,0.10)', border:`1px solid ${enabled?provider.color+'80':'rgba(255,255,255,0.15)'}`, transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:enabled?'flex-end':'flex-start', flexShrink:0 }}>
          <div style={{ width:16, height:16, borderRadius:'50%', background:'#fff', boxShadow:'0 1px 4px rgba(0,0,0,0.3)' }}/>
        </button>
      </div>
      <div style={{ display:'flex', gap:4, flexWrap:'wrap', marginBottom:9 }}>
        {provider.capabilities.map(c => <CapBadge key={c} cap={c}/>)}
      </div>
      {enabled && (
        <>
          <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:8 }}>
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexShrink:0, letterSpacing:'0.10em', textTransform:'uppercase' }}>Priority</span>
            <div style={{ display:'flex', gap:4 }}>
              {[0,1,2,3,4,5].map(p => (
                <button key={p} onClick={()=>onPriorityChange(p)} style={{ width:24, height:24, borderRadius:7, fontSize:11, fontFamily:'var(--font-mono)', fontWeight:700, cursor:'pointer', background:priority===p?provider.color:'rgba(255,255,255,0.06)', border:`1px solid ${priority===p?provider.color+'60':'rgba(255,255,255,0.10)'}`, color:priority===p?'#06111f':'var(--text-muted)', transition:'all 0.15s' }}>{p}</button>
              ))}
            </div>
            <span style={{ fontSize:10, color:'var(--text-muted)', fontFamily:'var(--font-mono)' }}>lower = tried first</span>
          </div>
          {provider.models.length > 1 && (
            <div style={{ marginBottom:8 }}>
              <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.10em', textTransform:'uppercase', marginBottom:5 }}>Default model</div>
              <div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>
                {provider.models.map(m => (
                  <button key={m} onClick={()=>onModelChange(m)} style={{ padding:'3px 9px', borderRadius:8, fontSize:11, fontFamily:'var(--font-mono)', cursor:'pointer', background:model===m?`${provider.color}18`:'rgba(255,255,255,0.04)', border:`1px solid ${model===m?provider.color+'40':'rgba(255,255,255,0.09)'}`, color:model===m?'#fff':'var(--text-muted)', transition:'all 0.15s', maxWidth:220, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{m}</button>
                ))}
              </div>
            </div>
          )}
          {provider.keyEnv && (
            <div>
              <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.10em', textTransform:'uppercase', marginBottom:5 }}>{provider.keyEnv}</div>
              <div style={{ display:'flex', gap:6, alignItems:'center' }}>
                <div style={{ flex:1, position:'relative' }}>
                  <input type={showKey?'text':'password'} value={key} onChange={e=>onKeyChange(e.target.value)} placeholder={key?'••••••••':provider.keyHint}
                    style={{ width:'100%', padding:'8px 32px 8px 12px', borderRadius:10, background:'rgba(255,255,255,0.04)', border:`1px solid ${key?`${provider.color}35`:'rgba(255,255,255,0.10)'}`, color:'#fff', fontSize:12, fontFamily:'var(--font-mono)', outline:'none', transition:'border-color 0.2s' }}
                    onFocus={e=>e.target.style.borderColor=`${provider.color}60`} onBlur={e=>e.target.style.borderColor=key?`${provider.color}35`:'rgba(255,255,255,0.10)'}/>
                  <button onClick={()=>setShowKey(s=>!s)} style={{ position:'absolute', right:8, top:'50%', transform:'translateY(-50%)', background:'none', border:'none', cursor:'pointer', fontSize:11, color:'var(--text-muted)' }}>{showKey?'🙈':'👁'}</button>
                </div>
                {key && <span style={{ fontSize:11, color:'#46d9a4', flexShrink:0, fontFamily:'var(--font-mono)' }}>✓</span>}
              </div>
            </div>
          )}
          {!provider.keyEnv && <div style={{ fontSize:11, color:'#46d9a4', fontFamily:'var(--font-mono)', marginTop:4 }}>✓ No API key needed</div>}
        </>
      )}
    </div>
  );
}

// Ollama model management tab
function OllamaTab() {
  const [models, setModels] = React.useState(OLLAMA_MODELS);
  const [pulling, setPulling] = React.useState(null);
  const [customModel, setCustomModel] = React.useState('');

  const pull = (name) => {
    setPulling(name);
    setTimeout(() => {
      setModels(p => p.map(m => m.name===name ? {...m, status:'pulled'} : m));
      setPulling(null);
    }, 2800);
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
                <button onClick={()=>setModels(p=>p.map(mod=>mod.name===m.name?{...mod,status:'available'}:mod))} style={{ padding:'5px 12px', borderRadius:8, fontSize:11, cursor:'pointer', background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', color:'#ff6b7d' }}>Remove</button>
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
  const [servers, setServers] = React.useState(MCP_SERVERS_DEFAULT);
  const [showAdd, setShowAdd] = React.useState(false);
  const [newName, setNewName] = React.useState('');
  const [newCmd,  setNewCmd]  = React.useState('');
  const [newDesc, setNewDesc] = React.useState('');

  const statusColor = { connected:'#46d9a4', error:'#ff6b7d', idle:'var(--text-muted)' };

  const addServer = () => {
    if (!newName.trim() || !newCmd.trim()) return;
    setServers(p => [...p, { id:`mcp-${Date.now()}`, name:newName.trim(), cmd:newCmd.trim(), status:'idle', tools:0, desc:newDesc }]);
    setNewName(''); setNewCmd(''); setNewDesc(''); setShowAdd(false);
  };

  return (
    <div>
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
              <button onClick={addServer} style={{ flex:1, padding:'9px', borderRadius:10, background:'rgba(196,181,253,0.15)', border:'1px solid rgba(196,181,253,0.30)', color:'#c4b5fd', fontSize:13, fontWeight:800, cursor:'pointer' }}>Add server</button>
              <button onClick={()=>setShowAdd(false)} style={{ padding:'9px 14px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:13, cursor:'pointer' }}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
        {servers.map(srv => {
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
                  </div>
                  <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.5, marginBottom:4 }}>{srv.desc}</div>
                  <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'rgba(255,255,255,0.35)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{srv.cmd}</div>
                </div>
                <div style={{ display:'flex', gap:5, flexShrink:0 }}>
                  <button onClick={()=>setServers(p=>p.map(s=>s.id===srv.id?{...s,status:s.status==='connected'?'idle':'connected'}:s))} style={{ padding:'4px 10px', borderRadius:8, fontSize:11, cursor:'pointer', background:srv.status==='connected'?'rgba(255,107,125,0.08)':'rgba(70,217,164,0.10)', border:`1px solid ${srv.status==='connected'?'rgba(255,107,125,0.20)':'rgba(70,217,164,0.22)'}`, color:srv.status==='connected'?'#ff6b7d':'#46d9a4' }}>
                    {srv.status==='connected'?'Disconnect':'Connect'}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProvidersScreen() {
  const [config, setConfig] = React.useState(loadConfig);
  const [filter, setFilter] = React.useState('all');
  const [search, setSearch] = React.useState('');
  const [tab, setTab]       = React.useState('providers');

  const update = (id, patch) => {
    setConfig(prev => { const next = {...prev, [id]:{...(prev[id]||{}), ...patch}}; saveConfig(next); return next; });
  };

  const sorted = [...ALL_PROVIDERS].sort((a,b) => {
    const pa = config[a.id]?.priority ?? a.defaultPriority;
    const pb = config[b.id]?.priority ?? b.defaultPriority;
    return pa-pb || a.name.localeCompare(b.name);
  });

  const topProvider = sorted.find(p => config[p.id]?.enabled !== false);
  const enabledCount = ALL_PROVIDERS.filter(p => config[p.id]?.enabled !== false).length;

  const tiers = ['all','local','free','free-cloud','commercial'];
  const filtered = sorted.filter(p => {
    const matchesTier   = filter==='all' || p.tier===filter;
    const matchesSearch = !search || p.name.toLowerCase().includes(search.toLowerCase()) || p.models.some(m => m.toLowerCase().includes(search.toLowerCase()));
    return matchesTier && matchesSearch;
  });

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:1000, margin:'0 auto' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:6 }}>Infrastructure</div>
      <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:14 }}>
        <div>
          <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Providers & Models</h1>
          <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:480 }}>All {ALL_PROVIDERS.length} providers · Ollama local model management · MCP server integrations. Priority order is used by all agents.</p>
        </div>
        {topProvider && (
          <div style={{ padding:'8px 14px', borderRadius:12, background:`${topProvider.color}08`, border:`1px solid ${topProvider.color}22` }}>
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em', marginBottom:2 }}>Highest priority</div>
            <div style={{ fontSize:13, fontWeight:700, color:'#fff' }}>{topProvider.name}</div>
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:topProvider.color }}>{config[topProvider.id]?.model || topProvider.defaultModel}</div>
          </div>
        )}
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
          {/* Priority chain */}
          <div style={{ padding:'10px 14px', borderRadius:12, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)', marginBottom:14 }}>
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:7 }}>Routing chain</div>
            <div style={{ display:'flex', gap:5, flexWrap:'wrap', alignItems:'center' }}>
              {sorted.filter(p=>config[p.id]?.enabled!==false).slice(0,6).map((p,i,arr) => {
                const pr = config[p.id]?.priority ?? p.defaultPriority;
                return (
                  <React.Fragment key={p.id}>
                    <div style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 9px', borderRadius:7, background:`${p.color}12`, border:`1px solid ${p.color}28` }}>
                      <span style={{ fontSize:11 }}>{p.icon}</span>
                      <span style={{ fontSize:11, fontWeight:600, color:'#fff' }}>{p.name}</span>
                      <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:p.color }}>P{pr}</span>
                    </div>
                    {i < arr.length-1 && <span style={{ color:'rgba(255,255,255,0.20)', fontSize:11 }}>→</span>}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Filters */}
          <div style={{ display:'flex', gap:7, marginBottom:12, flexWrap:'wrap', alignItems:'center' }}>
            <div style={{ display:'flex', gap:4 }}>
              {tiers.map(t => {
                const tc = TIER_CONFIG[t];
                return <button key={t} onClick={()=>setFilter(t)} style={{ padding:'4px 12px', borderRadius:999, fontSize:11, fontWeight:600, cursor:'pointer', background:filter===t?'rgba(93,162,255,0.12)':'rgba(255,255,255,0.04)', border:`1px solid ${filter===t?'rgba(93,162,255,0.32)':'rgba(255,255,255,0.09)'}`, color:filter===t?'#fff':'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s' }}>{t==='all'?'All':tc?.label||t}</button>;
              })}
            </div>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search…"
              style={{ flex:1, minWidth:120, padding:'6px 11px', borderRadius:10, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)' }}
              onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
          </div>

          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(290px,1fr))', gap:10 }}>
            {filtered.map(provider => (
              <ProviderCard key={provider.id} provider={provider} cfg={config[provider.id]||{}} isTop={topProvider?.id===provider.id}
                onToggle={v=>update(provider.id,{enabled:v})} onKeyChange={v=>update(provider.id,{key:v})}
                onModelChange={v=>update(provider.id,{model:v})} onPriorityChange={v=>update(provider.id,{priority:v})}/>
            ))}
          </div>
        </>
      )}
      {tab === 'ollama' && <OllamaTab/>}
      {tab === 'mcp'     && <MCPTab/>}
    </div>
  );
}

export { ProvidersScreen };
export default ProvidersScreen;
