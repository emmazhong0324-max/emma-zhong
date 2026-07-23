const form=document.querySelector('#form'),statusEl=document.querySelector('#status'),results=document.querySelector('#results'),files=document.querySelector('#files')||document.querySelector('input[name="files"]'),drop=document.querySelector('#drop-zone')||document.querySelector('.drop'),note=document.querySelector('#file-note');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const intentInput=document.querySelector('#intent'),intentSuggestions=document.querySelector('#intent-suggestions');
const syncIntentSuggestions=()=>{
  if(!intentInput||!intentSuggestions)return;
  const query=intentInput.value.trim();
  const buttons=[...intentSuggestions.querySelectorAll('button')];
  let visible=0;
  buttons.forEach(button=>{
    const match=!query||button.dataset.intent.includes(query);
    button.hidden=!match;if(match)visible++;
  });
  intentSuggestions.hidden=!visible;
};
if(intentInput&&intentSuggestions){
  intentInput.addEventListener('focus',syncIntentSuggestions);
  intentInput.addEventListener('input',syncIntentSuggestions);
  intentSuggestions.addEventListener('click',event=>{
    const button=event.target.closest('button[data-intent]');
    if(!button)return;
    intentInput.value=button.dataset.intent;
    intentSuggestions.hidden=true;
    intentInput.focus();
  });
  document.addEventListener('click',event=>{
    if(!event.target.closest('.intent-field'))intentSuggestions.hidden=true;
  });
}
if(files)files.addEventListener('change',()=>{if(note&&files.files.length)note.textContent=files.files.length===1?files.files[0].name:`已选择 ${files.files.length} 个文件`});
if(drop){
  ['dragenter','dragover'].forEach(x=>drop.addEventListener(x,()=>drop.classList.add('dragover')));
  ['dragleave','drop'].forEach(x=>drop.addEventListener(x,()=>drop.classList.remove('dragover')));
}
form.addEventListener('submit',async e=>{
  e.preventDefault();results.innerHTML='';
  const selectedFiles=[...(files?.files||[])];
  if(!selectedFiles.length){
    statusEl.innerHTML='<div class="status-box"><span>请先选择需要评审的文件</span></div>';
    return;
  }
  statusEl.innerHTML='<div class="status-box"><span class="loader"></span><span>正在准备批量评审…</span></div>';
  const b=form.querySelector('button'),buttonText=b.querySelector('span');b.disabled=true;if(buttonText)buttonText.textContent='智能体运行中…';
  const allResults=[];
  let failedRequests=0;
  try{
    for(let index=0;index<selectedFiles.length;index++){
      const file=selectedFiles[index];
      statusEl.innerHTML=`<div class="status-box"><span class="loader"></span><span>正在评审第 ${index+1} / ${selectedFiles.length} 个文件：${esc(file.name)}</span></div>`;
      const payload=new FormData();
      payload.append('dataset_type',form.elements.dataset_type.value);
      payload.append('intent',form.elements.intent.value);
      payload.append('files',file,file.name);
      try{
        const r=await fetch('/api/judge',{method:'POST',body:payload});
        const contentType=r.headers.get('content-type')||'';
        let d;
        if(contentType.includes('application/json'))d=await r.json();
        else{
          await r.text();
          throw Error(r.ok?'服务器返回格式异常':`服务器暂时不可用（HTTP ${r.status}）`);
        }
        if(!r.ok)throw Error(d.detail||'请求失败');
        allResults.push(...d.results);
      }catch(err){
        failedRequests++;
        const id=file.name.replace(/\.[^.]+$/,'');
        const message=err instanceof TypeError
          ?'网络连接中断，请稍后单独重试该文件'
          :err.message;
        allResults.push({id,error:message});
      }
      results.innerHTML=allResults.map(x=>x.error?`<article class="card fail"><h2>${esc(x.id)}：处理失败</h2><p>${esc(x.error)}</p></article>`:`<article class="card ${x.label==='不通过'?'fail':''}"><h2>${esc(x.id)}：${esc(x.label)}</h2></article>`).join('');
    }
    const summary=failedRequests
      ?`批量评审结束 · ${selectedFiles.length-failedRequests} 个成功，${failedRequests} 个需要重试`
      :`评审完成 · 共处理 ${selectedFiles.length} 个文件`;
    statusEl.innerHTML=`<div class="status-box done"><span class="loader"></span><span>${summary}</span></div>`;
    results.scrollIntoView({behavior:'smooth',block:'start'});
  }catch(err){statusEl.innerHTML=`<div class="status-box"><span>运行失败 · ${esc(err.message)}</span></div>`}
  finally{b.disabled=false;if(buttonText)buttonText.textContent='启动智能评审'}
});
