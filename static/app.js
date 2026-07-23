const form=document.querySelector('#form'),statusEl=document.querySelector('#status'),results=document.querySelector('#results'),files=document.querySelector('#files'),drop=document.querySelector('#drop-zone'),note=document.querySelector('#file-note');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
files.addEventListener('change',()=>{if(files.files.length)note.textContent=files.files.length===1?files.files[0].name:`已选择 ${files.files.length} 个文件`});
['dragenter','dragover'].forEach(x=>drop.addEventListener(x,()=>drop.classList.add('dragover')));
['dragleave','drop'].forEach(x=>drop.addEventListener(x,()=>drop.classList.remove('dragover')));
form.addEventListener('submit',async e=>{
  e.preventDefault();results.innerHTML='';statusEl.innerHTML='<div class="status-box"><span class="loader"></span><span>正在解析文档 · 发现规则 · 核验证据 · 生成裁决</span></div>';
  const b=form.querySelector('button');b.disabled=true;b.querySelector('span').textContent='智能体运行中…';
  try{
    const r=await fetch('/api/judge',{method:'POST',body:new FormData(form)}),d=await r.json();if(!r.ok)throw Error(d.detail||'请求失败');
    statusEl.innerHTML=`<div class="status-box done"><span class="loader"></span><span>评审完成 · 共生成 ${d.count} 条判断结果</span></div>`;
    results.innerHTML=d.results.map(x=>x.error?`<article class="card fail"><h2>${esc(x.id)}：处理失败</h2></article>`:`<article class="card ${x.label==='不通过'?'fail':''}"><h2>${esc(x.id)}：${esc(x.label)}</h2></article>`).join('');
    results.scrollIntoView({behavior:'smooth',block:'start'});
  }catch(err){statusEl.innerHTML=`<div class="status-box"><span>运行失败 · ${esc(err.message)}</span></div>`}
  finally{b.disabled=false;b.querySelector('span').textContent='启动智能评审'}
});
