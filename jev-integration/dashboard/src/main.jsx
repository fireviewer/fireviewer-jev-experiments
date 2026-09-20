import React, {useCallback, useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {toPng} from 'html-to-image';
import {Flame, FlaskConical, Files, Database, Camera, Download, Play, Clock, Image as ImageIcon, FileText, X, Check, Circle, AlertTriangle, Upload, LoaderCircle} from 'lucide-react';
import './style.css';

const STAGES = ['Collecte', 'Vision', 'Évaluation des preuves', 'Géolocalisation', 'Périmètre'];
const TITLES = {source_relevance:'Pertinence de la source', claim_support:'Appui de l’affirmation', review_route:'Orientation de la revue'};
const LABELS = {relevant:'Pertinente', irrelevant:'Hors sujet', uncertain:'Incertain', supports:'Appuyée', contradicts:'Contredite', insufficient:'Preuves insuffisantes', text_review:'Revue textuelle', vision_review:'Revue visuelle', geolocation_review:'Revue géographique', abstain:'Abstention'};
const EMPTY = {events:[], cases:[], result:null, running:false, typesafe_ready:false};
function sampleFor(component){
  const text='Une colonne de fumée est signalée. Le témoin précise que les flammes ne sont pas visibles depuis son point de vue.';
  const semantic_input=Object.fromEntries(component.input_fields.map(k=>[k,'']));
  for(const key of ['text','source_text','reference_text','supporting_text']) if(key in semantic_input) semantic_input[key]=text;
  if('claim' in semantic_input) semantic_input.claim='Les flammes sont directement visibles depuis ce point de vue.';
  if('vision_observation_text' in semantic_input) semantic_input.vision_observation_text='Observation fictive modèle : classe flamme. Résultat IA non confirmé.';
  return [{case_id:'synthetic-'+component.id,group_id:'synthetic-interface',component_id:component.id,fixture_kind:'synthetic',data_use:'public_authorized',semantic_input,structured_fields:{place:'',date:'',provenance:''},source:{text,provenance:'Exemple synthétique pour vérifier le contrat, aucune performance mesurée.'},observations:[]}];
}


async function api(path, body){
  const response=await fetch(path, body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {});
  const data=await response.json();
  if(!response.ok) throw new Error(data.error || 'Erreur de connexion');
  return data;
}
function download(name, text, type='application/json'){
  const url=URL.createObjectURL(new Blob([text],{type}));
  const a=document.createElement('a'); a.href=url; a.download=name; a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function pretty(value){return typeof value==='string'?value:JSON.stringify(value ?? '—');}

function PipelinePanel({variant, record, active, item, component}){
  const baseline=variant==='baseline';
  const answers=baseline ? (record?.baseline_receipt ? record.baseline_answers : {}) : record?.response?.answers;
  const status=active?'En cours':({ok:'Réponse reçue',planned:'Préparé, aucun appel',error:'Échec, pipeline actuel conservé',rule_applies:'Règle existante applicable',budget_exhausted:'Budget atteint, pipeline actuel conservé'}[record?.status] || 'Non exécuté');
  return <section className="panel pipeline"><h2>{baseline?'Référence de la brique':'Jev · avis textuel'}</h2>
    <p><b>{component ? component.id+' · '+component.title : record ? 'Ancien contrôle de connexion' : 'Choisir une brique'}</b></p>
    <p>{baseline?(record?.baseline_receipt?'Reçu importé · '+(record.baseline_receipt.method || 'ancien protocole'):'Aucune mesure de référence importée'):status}</p>
    {!baseline && record?.rule_reason && <p className="panel-note">{record.rule_reason}</p>}
    {Object.keys(answers || {}).length>0 && <div className="decisions">{Object.entries(answers).map(([id,answer])=><div key={id}><span>{TITLES[id] || id}</span><strong>{answer?.type==='noul'?'Probabilité : '+(answer.noul*100).toFixed(1)+' %':answer?.type==='score'?'Niveau : '+answer.score.toFixed(2):LABELS[answer?.choice || answer] || pretty(answer?.choice ?? answer)}</strong>{answer?.probabilities && <details><summary>Distribution et confiance</summary>{Object.entries(answer.probabilities).map(([choice,p])=><div className="probability" key={choice}><label>{LABELS[choice] || choice}</label><meter min="0" max="1" value={p}/><span>{(p*100).toFixed(1)} %</span></div>)}<p>Confiance : {(answer.confidence*100).toFixed(1)} % · ne vaut pas validation.</p></details>}</div>)}</div>}
    <p className="panel-note">{baseline?'Le reçu doit concerner cette même brique et les mêmes preuves figées.':'Les avis peuvent corroborer, contredire ou nuancer une affirmation. Ils ne changent ni les pixels, ni les détections, ni les coordonnées.'}</p>
    {record && <details className="panel-note"><summary>Traçabilité</summary><p>Révision : {record.revision || 'ancien contrôle à trois jugements'}</p><p>Entrée : {record.input_sha256}</p><p>Questions : {record.questions_sha256 || 'ancien format'}</p></details>}
  </section>;
}

function SourcePanel({item,media,setMedia,onImport}){
  const ref=useRef();
  const [showAnnotations,setShowAnnotations]=useState(true);
  const choose=event=>{const file=event.target.files?.[0];if(!file)return; if(media?.url)URL.revokeObjectURL(media.url);setMedia({url:URL.createObjectURL(file),video:file.type.startsWith('video/'),name:file.name});};
  const boxes=item?.media_annotations?.boxes || [];
  return <section className="panel source"><h2>Source analysée</h2><input ref={ref} type="file" accept="image/*,video/*" onChange={choose} hidden/>
    <div className={'media '+(media?'has-media':'')}>
      {media ? <>{media.video?<video controls src={media.url}/>:<img src={media.url} alt={media.name}/>} {!media.video && showAnnotations && <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="annotations" aria-label="Annotations importées">{boxes.map((box,i)=><rect key={i} x={box.xywh[0]} y={box.xywh[1]} width={box.xywh[2]} height={box.xywh[3]} stroke={box.label==='smoke'?'#38bdf8':'#f97316'} fill="none" strokeWidth="0.005"/>)}</svg>}</> : <button onClick={()=>ref.current.click()} className="media-placeholder"><ImageIcon size={40}/><strong>Sélectionner une source</strong><span>Image ou vidéo locale à inspecter.</span></button>}
    </div>
    {media && <div className="media-tools"><button onClick={()=>ref.current.click()}>Changer le média</button>{boxes.length>0 && <label><input type="checkbox" checked={showAnnotations} onChange={e=>setShowAnnotations(e.target.checked)}/>Annotations importées</label>}</div>}
    <dl><dt>Incident</dt><dd>{item?.incident?.name || '—'}</dd><dt>Date</dt><dd>{item?.incident?.date || '—'}</dd><dt>Provenance</dt><dd>{item?.source?.provenance || item?.source?.url || '—'}</dd></dl>
    {item?.semantic_input && <details open><summary>Entrée textuelle de la brique</summary><pre className="semantic-input">{JSON.stringify(item.semantic_input,null,2)}</pre></details>}
    {item?.source?.text && <details open><summary>Texte de la source</summary><p className="source-text">{item.source.text}</p><p><b>Affirmation :</b> {pretty(item.claim)}</p></details>}
    {item?.fixture_kind==='synthetic' && <p className="synthetic"><AlertTriangle size={14}/>Cas synthétique — aucune preuve de performance</p>}
    {item?.fixture_kind==='public_source_probe' && <p className="synthetic"><AlertTriangle size={14}/>Essai d’intégration sur une source publique — pas un benchmark indépendant</p>}
    {item?.source?.attribution && <p className="panel-note">Crédit : {item.source.attribution}</p>}
    {item && <p className="panel-note">Le média local sert à l’inspection. Seuls les champs textuels de l’export sont évalués.</p>}
  </section>;
}

function Comparison({record,report}){
  const measured=record?.status==='ok' && !!record?.component_id;
  const paired=measured && !!record?.baseline_receipt && record.fixture_kind!=='synthetic';
  const baseLatency=paired?record.baseline_receipt.latency_ms:null, baseCost=paired?record.baseline_receipt.cost_usd:null;
  const rows=[['Durée de la brique',baseLatency!=null?`${baseLatency.toFixed(0)} ms`:null,measured?`${record.latency_ms.toFixed(0)} ms`:null,measured && baseLatency!=null?`${(record.latency_ms-baseLatency).toFixed(0)} ms`:null],['Coût de la brique',baseCost!=null?`${baseCost.toFixed(6)} $`:null,measured?`${record.cost_usd.toFixed(6)} $`:null,measured && baseCost!=null?`${(record.cost_usd-baseCost).toFixed(6)} $`:null]];
  return <section className="panel comparison"><h2>Comparaison de la brique sélectionnée</h2><div className="table-scroll"><table><thead><tr><th>Mesure</th><th>Référence importée</th><th>Jev</th><th>Écart apparié</th></tr></thead><tbody>{rows.map(row=><tr key={row[0]}>{row.map((v,i)=>i===0?<th scope="row" key={i}>{v}</th>:<td key={i}>{v ?? '—'}</td>)}</tr>)}</tbody></table></div>
    <p className="panel-note">Le coût complet du pipeline et la qualité des périmètres nécessitent des exécutions complètes. Un essai sur export ne les mesure pas. Les anciens contrôles de connexion et les exemples synthétiques sont exclus des comparaisons.</p>
    {report && <p className="panel-note">{report.cases} cas · {report.successful_requests} appels réussis · {report.failed_requests} erreurs · {report.paired_export_cases ?? 0} exports appariés · {report.synthetic_cases ?? 0} synthétiques.</p>}
    {report?.metrics && <details><summary>Mesures sur labels disponibles</summary><pre>{JSON.stringify(report.metrics,null,2)}</pre></details>}
  </section>;
}

function RunLog({events}){
  const labels={run_started:'Démarrage de l’essai',case_started:'Évaluation du cas',case_finished:'Résultat enregistré',run_finished:'Essai terminé',run_failed:'Essai interrompu'};
  return <section className="panel log"><h2>Journal de progression</h2>{events.length?<ol>{events.map(e=><li key={e.sequence}><time>{new Date(e.at).toLocaleTimeString('fr-FR')}</time><span>{labels[e.type] || e.type}</span><code>{e.case_id || e.record?.case_id || ''}</code><small>{e.record?.status || e.mode || ''}</small></li>)}</ol>:<div className="log-empty"><FileText size={26}/><p>Les événements apparaîtront ici pendant l’exécution.</p></div>}</section>;
}

function RunDialog({ready,onClose,onStart,initialCases,components,initialComponent}){
  const [componentId,setComponentId]=useState(initialComponent || 'FV-01');
  const [cases,setCases]=useState((initialCases || []).filter(c=>c.component_id===(initialComponent || 'FV-01'))), [mode,setMode]=useState('offline_plan'),[error,setError]=useState('');
  const component=components.find(c=>c.id===componentId);
  const importFile=async e=>{try{const text=await e.target.files[0].text();let parsed;try{parsed=JSON.parse(text);}catch{parsed=text.split('\n').filter(x=>x.trim()).map(x=>JSON.parse(x));}const values=Array.isArray(parsed)?parsed:parsed.cases;if(!Array.isArray(values))throw new Error('Tableau JSON ou JSONL requis.');if(values.some(c=>c.component_id!==componentId))throw new Error('Tous les cas doivent appartenir à la brique sélectionnée.');setCases(values);setError('');}catch(e){setError(e.message);}};
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><button className="close" aria-label="Fermer" onClick={onClose}><X/></button><h2 id="dialog-title">Essai d’une seule brique</h2><label className="key-field">Brique évaluée<select value={componentId} onChange={e=>{setComponentId(e.target.value);setCases([]);setError('');}}>{components.map(c=><option key={c.id} value={c.id}>{c.id} · {c.title}</option>)}</select></label><p>{component?.prerequisite}</p><p>Importer les textes autorisés et, pour une comparaison, un reçu de cette brique sur les mêmes preuves. Les labels restent hors de la requête Jev.</p><label className="file-label"><Upload size={18}/>Importer JSON / JSONL<input type="file" accept=".json,.jsonl" onChange={importFile}/></label>{component && !['FV-03','DS-03','LOC-01'].includes(componentId) && <button className="text-button" onClick={()=>setCases(sampleFor(component))}>Charger un exemple synthétique</button>}<p>{cases.length} cas · lots techniques de 50 maximum ; ce plafond ne limite pas le corpus quotidien.</p><label className="mode"><input type="radio" name="mode" checked={mode==='offline_plan'} onChange={()=>setMode('offline_plan')}/><span><b>Préparation hors ligne</b><small>Valide le contrat. Aucun appel de modèle.</small></span></label><label className="mode"><input type="radio" name="mode" checked={mode==='live'} onChange={()=>setMode('live')} disabled={!ready}/><span><b>Essai textuel Jev en direct</b><small>{ready?'Clé serveur présente · réserve maximale 0,50 $ par lot.':'Configurer l’accès côté serveur.'} Ce n’est pas une exécution du pipeline complet.</small></span></label>{error && <p role="alert" className="error">{error}</p>}<div className="modal-actions"><button onClick={onClose}>Annuler</button><button className="primary" disabled={!cases.length || !component} onClick={async()=>{try{await onStart(cases,mode,componentId);onClose();}catch(e){setError(e.message);}}}><Play size={16}/>{mode==='live'?'Exécuter la brique':'Préparer l’essai'}</button></div></section></div>;
}

function KeyDialog({onClose,onSaved}){
  const [key,setKey]=useState(''),[error,setError]=useState('');
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="key-title"><button className="close" aria-label="Fermer" onClick={onClose}><X/></button><h2 id="key-title">Accès TypeSafe</h2><p>Crée une clé dans la <a href="https://console.typesafe.ai" target="_blank" rel="noreferrer">console TypeSafe</a>, puis saisis-la ici. Elle reste en mémoire sur ce serveur local, sans journalisation ni enregistrement sur disque. Les crédits TypeSafe sont distincts des crédits AWS.</p><label className="key-field">Clé API<input type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder="Saisir la clé ici, jamais dans le chat"/></label>{error && <p className="error" role="alert">{error}</p>}<div className="modal-actions"><button onClick={onClose}>Annuler</button><button className="primary" disabled={!key} onClick={async()=>{try{await api('/api/credentials',{api_key:key});setKey('');await onSaved();onClose();}catch(e){setError(e.message);}}}>Utiliser pour cette session</button></div></section></div>;
}

function App(){
  const [state,setState]=useState(EMPTY),[selectedComponent,setSelectedComponent]=useState('FV-01'),[dialog,setDialog]=useState(false),[notice,setNotice]=useState(''),[media,setMedia]=useState(null),[selected,setSelected]=useState(null),[view,setView]=useState('Laboratoire'),[runs,setRuns]=useState([]),[replay,setReplay]=useState(null),[autoCapture,setAutoCapture]=useState(true),[keyDialog,setKeyDialog]=useState(false),[captures,setCaptures]=useState([]),[capturing,setCapturing]=useState(false);
  const screen=useRef(),captureBusy=useRef(false),capturedSequence=useRef('');
  useEffect(()=>{let stopped=false;const update=()=>api('/api/state').then(value=>{if(!stopped)setState(value);}).catch(()=>{if(!stopped)setNotice('Connexion au laboratoire indisponible.');});update();const timer=setInterval(update,700);return()=>{stopped=true;clearInterval(timer);};},[]);
  const visible=replay || state;
  const finished=visible.events.filter(e=>e.type==='case_finished').map(e=>e.record);
  const last=visible.events.filter(e=>e.type==='case_started').at(-1);
  const item=visible.cases.find(c=>c.case_id===(selected || last?.case_id)) || visible.cases[0];
  const record=finished.find(r=>r.case_id===item?.case_id);
  const active=visible.running && last?.case_id===item?.case_id && !record;
  const report=visible.result?.report;
  const componentCatalog=state.components || [];
  const componentId=record?.component_id || report?.component_id || visible.component_id;
  const component=componentCatalog.find(c=>c.id===componentId);
  const capture=useCallback(async(manual=false)=>{if(captureBusy.current)return;captureBusy.current=true;setCapturing(true);try{const png=await toPng(screen.current,{cacheBust:false,pixelRatio:1,filter:node=>!node.classList?.contains('modal-backdrop')});if(state.run_id && !replay)await api('/api/capture',{run_id:state.run_id,png:png.split(',')[1]});if(manual){const a=document.createElement('a');a.download=`fireviewer-${visible.run_id || 'attente'}-${Date.now()}.png`;a.href=png;a.click();setNotice('Capture PNG enregistrée.');}}catch(e){setNotice(`Capture impossible : ${e?.message || "le média ne peut pas être rendu"}`);}finally{captureBusy.current=false;setCapturing(false);}},[state.run_id,replay,visible.run_id]);
  useEffect(()=>{const seq=`${state.run_id}:${state.events.length}`;if(autoCapture && !replay && state.run_id && state.events.length && seq!==capturedSequence.current){capturedSequence.current=seq;const timer=setTimeout(()=>capture(false),250);return()=>clearTimeout(timer);}},[state.events.length,state.run_id,autoCapture,replay,capture]);
  const selectView=async name=>{setView(name);if(name==='Sources'){setDialog(true);return;}if(name==='Expériences'||name==='Captures'){try{setRuns(await api('/api/runs'));if(name==='Captures')setCaptures(await api('/api/captures'));}catch(e){setNotice(e.message);}}};
  const exportRun=async()=>{download(`fireviewer-${visible.run_id || 'attente'}.json`,JSON.stringify(visible,null,2));setNotice('Journal, résultats et entrées exportés.');};
  const status=replay?'Relecture d’un essai enregistré':visible.running?'Exécution en cours':visible.run_id?(visible.mode==='offline_plan'?'Préparation hors ligne terminée — aucun appel de modèle':'Exécution terminée'):'En attente de première exécution réelle';
  return <div className="app" ref={screen}><aside><div className="brand"><Flame fill="#ff671f" strokeWidth={1.5}/><strong>FireViewer</strong></div><nav>{[[FlaskConical,'Laboratoire'],[Files,'Expériences'],[Database,'Sources'],[Camera,'Captures']].map(([Icon,name])=><button key={name} className={view===name?'selected':''} onClick={()=>selectView(name)}><Icon size={21}/>{name}</button>)}</nav><button className="connection" onClick={()=>setKeyDialog(true)}><span className={state.typesafe_ready?'dot connected':'dot'}/>{state.typesafe_ready?'Clé TypeSafe disponible':'Configurer TypeSafe'}</button></aside><main>
    <header><div><h1>Jev · comparaison par brique</h1><p>Jugement textuel · vision conservée · validation humaine.</p></div><div className="header-actions"><a href="/daily/">Campagne quotidienne</a><button onClick={exportRun}><Download size={18}/>Exporter</button><button className="primary" disabled={state.running} onClick={()=>setDialog(true)}><Play size={17} fill="currentColor"/>Nouvel essai</button></div></header>
    <div className="status" role="status"><Clock size={20}/><span>{status}</span>{visible.cases.length>0 && <strong>{finished.length} / {visible.cases.length} cas</strong>}{replay && <button onClick={()=>setReplay(null)}>Retour au direct</button>}</div>
    {notice && <div className="notice" role="status">{notice}<button onClick={()=>setNotice('')} aria-label="Fermer le message"><X size={16}/></button></div>}
    {view==='Captures' && <section className="panel capture-gallery"><h2>Captures enregistrées</h2>{captures.length?<div>{captures.map(c=><a key={c.url} href={c.url} target="_blank" rel="noreferrer"><img src={c.url} alt={'Capture de '+c.run_id}/><span>{c.run_id}</span></a>)}</div>:<p>Aucune capture enregistrée.</p>}</section>}{view==='Expériences' && <section className="panel history"><h2>{view}</h2>{runs.length?runs.map(run=><button key={run.id} onClick={async()=>{setReplay(await api('/api/run/'+run.id));setSelected(null);setView('Laboratoire');}}><FileText size={16}/>{run.id}<small>{run.captures} captures · {run.complete?'terminé':'incomplet'}</small></button>):<p>Aucun essai enregistré.</p>}</section>}
    {visible.cases.length>1 && <label className="case-select">Cas analysé <select value={item?.case_id} onChange={e=>setSelected(e.target.value)}>{visible.cases.map(c=><option key={c.case_id}>{c.case_id}</option>)}</select></label>}
    <section className="panel component-catalog"><h2>12 briques indépendantes</h2><p>Une seule brique change par essai. Les adaptateurs sur exports sont disponibles ; le branchement au pipeline complet reste à réaliser.</p><div className="component-grid">{componentCatalog.map(c=><button key={c.id} onClick={()=>{setSelectedComponent(c.id);setDialog(true);}}><b>{c.id}</b><span>{c.title}</span><small>{c.primitives.join(' + ')}</small></button>)}</div><p className="panel-note">Collecte → traitement visuel nécessaire → recoupement → validation humaine. Satellite, thermique et terrain restent dans leurs branches respectives.</p><a href="/daily/JEV_AUDIT.md">Lire l’audit et le protocole</a></section>
    <div className="workspace"><SourcePanel item={item} media={media} setMedia={setMedia}/><PipelinePanel variant="baseline" record={record} active={false} item={item} component={component}/><PipelinePanel variant="typesafe" record={record} active={active} item={item} component={component}/></div>
    <Comparison record={record} report={report}/><RunLog events={visible.events}/>
    <footer><label><input type="checkbox" checked={autoCapture} onChange={e=>setAutoCapture(e.target.checked)}/>Captures automatiques pendant le suivi</label><button className="capture" disabled={capturing} onClick={()=>capture(true)}><Camera size={19}/>Capturer la vue</button></footer>
    <p className="footnote">Les captures suivent l’écran ouvert. Les événements et résultats sont enregistrés même si le navigateur est fermé.</p>
  </main>{keyDialog && <KeyDialog onClose={()=>setKeyDialog(false)} onSaved={async()=>setState(await api('/api/state'))}/>} {dialog && <RunDialog ready={state.typesafe_ready} components={componentCatalog} initialComponent={selectedComponent} initialCases={visible.cases} onClose={()=>setDialog(false)} onStart={async(cases,mode,component_id)=>{await api('/api/run',{cases,mode,component_id});setReplay(null);setSelected(null);setView('Laboratoire');setState(await api('/api/state'));}}/>}</div>;
}

createRoot(document.getElementById('root')).render(<App/>);
