const $ = id => document.getElementById(id);
let selected = null, recorder = null, chunks = [], projects = [], aiOptions = null;

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error((await response.text()) || response.statusText);
  return response.json();
}
function esc(value) { const node = document.createElement('div'); node.textContent = value ?? ''; return node.innerHTML; }

async function loadProjects() {
  projects = await api('/api/projects');
  const options = projects.map(p => `<option value="${p.id}">${esc(p.name)} · ${esc(p.workspace_type)}</option>`).join('');
  $('project').innerHTML = options;
  $('projectFilter').innerHTML = '<option value="">All workspaces</option>' + options;
  const previous = $('activeBook').value;
  $('activeBook').innerHTML = options;
  if (previous) $('activeBook').value = previous;
  if (projects.length) await loadWorkspace(Number($('activeBook').value));
}

async function loadWorkspace(id) {
  if (!id) return;
  const book = await api(`/api/books/${id}`);
  $('bookInstructions').value = book.instructions;
  $('exportBook').href = `/api/books/${id}/export`;
  $('bookSections').innerHTML = book.sections.length ? book.sections.map(section =>
    `<article class="bookSection"><h3>${esc(section.title)}</h3><div>${esc(section.content)}</div><small>Sources: ${(section.source_note_ids || []).map(i => `[Note ${i}]`).join(', ') || 'none recorded'}</small></article>`
  ).join('') : '<p class="muted">No integrated content yet. New analyzed thoughts will build this working document.</p>';
}
async function loadOpportunities(){const items=await api('/api/opportunities');$('opportunities').innerHTML=items.length?items.map(item=>`<article class="opportunity"><span>${esc(item.kind)}</span><h3>${esc(item.title)}</h3><p>${esc(item.description)}</p><small>${esc(item.rationale)}</small><button data-explore="${item.id}">Explore as workspace</button></article>`).join(''):'<p class="muted">No new suggestions yet.</p>';document.querySelectorAll('[data-explore]').forEach(button=>button.onclick=async()=>{await api(`/api/opportunities/${button.dataset.explore}/explore`,{method:'POST'});await Promise.all([loadProjects(),loadOpportunities()]);});}

function showAIModels() {
  const provider = aiOptions.providers.find(item => item.id === $('aiProvider').value);
  const chosen = aiOptions.selected.provider === provider.id ? aiOptions.selected.model : '';
  const models = [...provider.models]; if (chosen && !models.includes(chosen)) models.unshift(chosen);
  $('aiModel').innerHTML = models.length ? models.map(m => `<option>${esc(m)}</option>`).join('') : '<option value="">No models detected</option>';
  $('aiModel').value = chosen || models[0] || '';
  $('aiStatus').textContent = provider.configured ? 'Ready' : provider.id === 'ollama' ? 'Start Ollama and pull a model' : `Add the ${provider.label} API key to .env`;
}
async function loadAI() {
  aiOptions = await api('/api/ai/options');
  $('aiProvider').innerHTML = aiOptions.providers.map(p => `<option value="${p.id}">${esc(p.label)}${p.configured ? '' : ' — not ready'}</option>`).join('');
  $('aiProvider').value = aiOptions.selected.provider; showAIModels();
}

async function refresh() {
  const query = new URLSearchParams({q: $('search').value.trim(), category: $('categoryFilter').value});
  if ($('projectFilter').value) query.set('project_id', $('projectFilter').value);
  const notes = await api('/api/notes?' + query);
  $('notes').innerHTML = notes.length ? notes.map(n => `<div class="note ${selected === n.id ? 'active' : ''}" data-id="${n.id}"><strong>${esc(n.title)}</strong><small>${esc(n.project_name || 'Unfiled')} · ${esc(n.category)} · ${esc(n.analysis_status)}</small></div>`).join('') : '<p class="muted">No matching sources.</p>';
  document.querySelectorAll('.note').forEach(node => node.onclick = () => openNote(Number(node.dataset.id)));
}
function list(label, items, render = x => esc(x)) { return items?.length ? `<section><h3>${label}</h3><ul>${items.map(x => `<li>${render(x)}</li>`).join('')}</ul></section>` : ''; }
function showAnalysis(a = {}) {
  $('analysis').innerHTML = list('Idea domains', a.idea_domains) + list('Characters', a.characters, x => `<b>${esc(x.name)}</b> — ${esc(x.role)}`) + list('Scenes', a.scenes, x => `<b>${esc(x.title)}</b> — ${esc(x.synopsis)}`) + list('Themes', a.themes) + list('Story ideas', a.story_ideas) + list('Key ideas', a.key_ideas) + list('Decisions', a.decisions) + list('Tasks', a.assigned_tasks, x => esc(x.task)) + list('Risks', a.risks) + list('Questions', a.open_questions) + list('Follow-ups', a.follow_up_items);
}
async function openNote(id) {
  const note = await api(`/api/notes/${id}`); selected = id; $('noteForm').hidden = false; document.querySelector('.emptyMessage').hidden = true;
  $('title').value = note.title; $('category').value = note.category; $('project').value = note.project_id || ''; $('tags').value = note.tags.join(', '); $('summary').value = note.summary; $('transcript').textContent = note.transcript; $('audio').src = `/api/notes/${id}/audio`; $('analysisState').textContent = `AI analysis: ${note.analysis_status}`; showAnalysis(note.analysis); refresh();
}

$('activeBook').onchange = () => loadWorkspace(Number($('activeBook').value));
$('refreshOpportunities').onclick=loadOpportunities;
$('saveInstructions').onclick = async () => { const id = Number($('activeBook').value); await api(`/api/books/${id}/instructions`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({instructions:$('bookInstructions').value})}); $('bookStatus').textContent = 'Direction saved.'; };
$('reorganize').onclick = async () => { try { const id = Number($('activeBook').value); $('bookStatus').textContent = 'Reorganizing the working document…'; await api(`/api/books/${id}/reorganize`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({feedback:$('reorgFeedback').value})}); $('reorgFeedback').value = ''; await loadWorkspace(id); $('bookStatus').textContent = 'Reorganization complete; previous version preserved.'; } catch (error) { $('bookStatus').textContent = 'Reorganization failed: ' + error.message; } };
$('newProject').onclick = async () => { const name = prompt('Workspace name'); if (!name) return; const workspace_type = prompt('Type: book, business, project, or general', 'book') || 'book'; await api('/api/projects', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,description:'',workspace_type})}); await loadProjects(); };
$('aiProvider').onchange = showAIModels;
$('saveAI').onclick = async () => { try { const provider=$('aiProvider').value, model=$('aiModel').value; if(!model) throw new Error('No model available'); aiOptions=await api('/api/ai/selection',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider,model})}); $('aiStatus').textContent=`Active: ${provider} / ${model}`; updateHealth(); } catch(error) {$('aiStatus').textContent='Could not switch: '+error.message;} };
$('noteForm').onsubmit = async event => { event.preventDefault(); await api(`/api/notes/${selected}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:$('title').value,category:$('category').value,project_id:Number($('project').value)||null,tags:$('tags').value.split(',').map(x=>x.trim()).filter(Boolean),summary:$('summary').value})}); await openNote(selected); };
$('analyze').onclick = async () => { try {$('analysisState').textContent='Analyzing and integrating…'; await api(`/api/notes/${selected}/analyze`,{method:'POST'}); await loadProjects(); await openNote(selected); await loadWorkspace(Number($('activeBook').value));} catch(error){$('analysisState').textContent='Unavailable: '+error.message;} };
$('ask').onclick = async () => { try {$('answer').textContent='Thinking…'; const result=await api('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('question').value,project_id:Number($('activeBook').value)||null,selected_note_ids:[]})}); $('answer').textContent=result.answer;} catch(error){$('answer').textContent='Unavailable: '+error.message;} };
$('scan').onclick = async () => { await api('/api/scan',{method:'POST'}); $('captureStatus').textContent='Source scan requested.'; };
$('search').oninput=refresh; $('categoryFilter').onchange=refresh; $('projectFilter').onchange=refresh;
async function upload(blob,name){const body=new FormData();body.append('file',blob,name);await api('/api/upload',{method:'POST',body});$('captureStatus').textContent='Saved. Automatic processing will begin shortly.';}
$('upload').onchange=async e=>{const f=e.target.files[0];if(f)await upload(f,f.name);e.target.value='';};
$('contentUpload').onchange=async event=>{const file=event.target.files[0];if(!file)return;const body=new FormData();body.append('file',file,file.name);await api('/api/import',{method:'POST',body});$('captureStatus').textContent='Content accepted. Extraction, classification, and integration will run automatically.';event.target.value='';};
$('record').onclick=async()=>{if(recorder?.state==='recording'){recorder.stop();return;}const stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];recorder=new MediaRecorder(stream);recorder.ondataavailable=e=>chunks.push(e.data);recorder.onstop=async()=>{stream.getTracks().forEach(t=>t.stop());$('record').textContent='Start recording';await upload(new Blob(chunks,{type:recorder.mimeType}),`thought-${new Date().toISOString().replaceAll(':','-')}.webm`);};recorder.start();$('record').textContent='Stop and save';};
async function updateHealth(){try{const h=await api('/health');$('health').textContent=`● Worker ${h.watcher_alive?'running':'stopped'} · ${h.ai_provider}/${h.ai_model} · ${h.ai_enabled?'ready':'not configured'}`;}catch{$('health').textContent='Offline';}}
Promise.all([loadAI(),loadProjects(),loadOpportunities(),refresh()]); setInterval(refresh,5000); updateHealth();
