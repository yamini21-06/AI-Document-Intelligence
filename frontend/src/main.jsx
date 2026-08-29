import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const API = 'http://localhost:8000/api';

function App(){
  const [docs,setDocs]=useState([]), [question,setQuestion]=useState(''), [answer,setAnswer]=useState(null);
  const [busy,setBusy]=useState(false), [uploading,setUploading]=useState(false), [selected,setSelected]=useState([]), [error,setError]=useState('');
  const [ollama,setOllama]=useState(null);
  const readyDocs=useMemo(()=>docs.filter(d=>d.status==='ready'),[docs]);
  const load=async()=>{try{const r=await fetch(`${API}/documents`); if(!r.ok) throw Error('Backend is not reachable'); setDocs(await r.json());}catch(e){setError(e.message)}};
  const check=async()=>{try{const r=await fetch(`${API}/health/ollama`);setOllama(await r.json())}catch{setOllama({ok:false,error:'Backend is not reachable'})}};
  useEffect(()=>{load();check(); const t=setInterval(()=>{load();check()},5000); return()=>clearInterval(t)},[]);
  const upload=async(e)=>{const f=e.target.files?.[0]; if(!f)return; setUploading(true);setError(''); const fd=new FormData();fd.append('file',f);try{const r=await fetch(`${API}/documents/upload`,{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw Error(d.detail||'Upload failed');await load();await check()}catch(x){setError(x.message)}finally{setUploading(false);e.target.value=''}};
  const ask=async()=>{if(!question.trim()||busy)return;setBusy(true);setError('');setAnswer(null);try{const r=await fetch(`${API}/chat`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,document_ids:selected.length?selected:null})});const d=await r.json();if(!r.ok)throw Error(d.detail||'Chat failed');setAnswer(d)}catch(x){setError(x.message)}finally{setBusy(false)}};
  const remove=async(id)=>{try{const r=await fetch(`${API}/documents/${id}`,{method:'DELETE'});if(!r.ok)throw Error('Delete failed');setSelected(s=>s.filter(x=>x!==id));await load()}catch(e){setError(e.message)}};
  const toggle=id=>setSelected(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id]);
  return <div className="app">
    <header><div><div className="eyebrow">AI DOCUMENT INTELLIGENCE</div><h1>Ask your documents.</h1><p>Upload files, retrieve relevant passages, and get grounded answers with source citations.</p></div><label className="upload">{uploading?'Processing…':'＋ Upload document'}<input type="file" accept=".pdf,.docx,.txt" onChange={upload} disabled={uploading}/></label></header>
    <div className="statusbar"><span className={ollama?.ok?'dot good':'dot'}></span> Ollama: {ollama?.ok?'Connected':'Not connected'} <span className="sep">•</span> Embeddings: {ollama?.embedding_model_present?'Ready':'Missing'} <span className="sep">•</span> LLM: {ollama?.llm_model_present?'Ready':'Missing'} <span className="sep">•</span> Documents: {readyDocs.length}</div>
    {error&&<div className="error">{error}</div>}
    <main><aside><div className="sidehead"><div><h2>Knowledge base</h2><p className="muted">Select documents to scope retrieval.</p></div><span className="count">{readyDocs.length}</span></div>{docs.length===0?<div className="empty">No documents yet.<br/>Upload a PDF, DOCX, or TXT.</div>:docs.map(d=><div className="doc" key={d.id}><input type="checkbox" disabled={d.status!=='ready'} checked={selected.includes(d.id)} onChange={()=>toggle(d.id)}/><div className="docbody"><strong title={d.filename}>{d.filename}</strong><span className={`badge ${d.status}`}>{d.status}</span><span>{d.chunks} chunks</span>{d.error&&<small>{d.error}</small>}</div><button className="delete" onClick={()=>remove(d.id)} title="Delete">×</button></div>)}</aside>
      <section className="chat"><div className="question"><textarea value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ask something about your documents…" onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask()}}}/><button onClick={ask} disabled={busy||readyDocs.length===0}>{busy?'Thinking…':'Ask'}</button></div>{answer&&<div className="result"><div className="resulttitle"><h2>Answer</h2><button className="clear" onClick={()=>setAnswer(null)}>Clear</button></div><div className="answer">{answer.answer}</div><h3>Retrieved sources</h3>{answer.sources.map((s,i)=><div className="source" key={s.chunk_id}><div><b>#{i+1} {s.filename}{s.page?` · p.${s.page}`:''}</b><span>similarity {s.score.toFixed(3)}</span></div><p>{s.excerpt}{s.excerpt.length>=400?'…':''}</p></div>)}</div>}{!answer&&!busy&&<div className="hint"><b>Try asking:</b><div>“What are the key risks mentioned in the document?”</div><div>“Summarize the main requirements.”</div><div>“Which section discusses pricing?”</div><div>“What evidence supports the conclusion?”</div></div>}{busy&&<div className="loading"><span></span><span></span><span></span> Searching documents and generating an answer…</div>}</section>
    </main></div>
}
createRoot(document.getElementById('root')).render(<App/>);
