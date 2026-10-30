// Order Dispatch Tester UI. All user-visible strings come from /api/i18n (order_tester/i18n/<lang>.json).
// ---------------- i18n ----------------
let I18N={},LANG='zh';
function t(k,v){let s=I18N[k];if(s==null)s=k;if(v)s=s.replace(/\{(\w+)\}/g,(m,n)=>v[n]!=null?v[n]:m);return s}
function applyI18n(){document.documentElement.lang=LANG=='en'?'en':'zh';document.title=t('app.title');
 document.querySelectorAll('[data-i18n]').forEach(e=>e.textContent=t(e.dataset.i18n));
 document.querySelectorAll('[data-i18n-ph]').forEach(e=>e.placeholder=t(e.dataset.i18nPh));
 document.querySelectorAll('[data-i18n-title]').forEach(e=>e.title=t(e.dataset.i18nTitle));$('langsel').value=LANG;syncSrvToggleLabels()}
async function loadI18n(){let want=null;try{want=localStorage.getItem('odtLang')}catch(e){}
 let q=[];if(want)q.push('lang='+encodeURIComponent(want));q.push('_='+(Date.now()));let r=await (await fetch('/api/i18n?'+q.join('&'),{cache:'no-store'})).json();I18N=r.t;LANG=r.lang;applyI18n()}
async function setLang(l){try{localStorage.setItem('odtLang',l)}catch(e){}await post('/api/config',{lang:l});location.reload()}
async function loadVersion(){try{let r=await (await fetch('/api/version?_='+(Date.now()),{cache:'no-store'})).json();
 let el=$('ver_footer');if(!el||!r||!r.ok)return;el.textContent='v'+(r.version||'?')+' · '+(r.buildDate||'')}catch(e){}}
const stName=s=>s==DRAFT?t('state.draft'):s=='其它'?t('state.other'):s;
// ---------------- state / settings ----------------
let allSt=[],stMap={},stations=[],pools={start:[],end:[]},view={s:1,ox:0,oy:0},sel=new Set();
const $=id=>document.getElementById(id);
async function post(u,b){return (await fetch(u,{method:'POST',body:JSON.stringify(b)})).json()}
const NOSAVE=new Set(['q','tf','paste','hidedone','f_veh','f_grp','f_st','f_id','f_stuck','newpool','tpl_raw','tpl_json','tpl_imp','tpl_title','tpl_name','langsel','swa','swb']);let loaded=false,saveT=null;
function poolNames(){let n=Object.keys(pools);for(const r of (cur&&cur.pools)||[])if(!n.includes(r))n.push(r);return n}
let currentServerId=null,serverList=[];
function collect(){let f={};document.querySelectorAll('input[id],select[id],textarea[id]').forEach(e=>{if(NOSAVE.has(e.id)||e.closest('#steps')||e.closest('#srv_side'))return;f[e.id]=e.type=='checkbox'?e.checked:e.value});
 let pm=$('pm');
 return {base:$('base').value,pollSec:+$('poll').value,fields:f,pm:pm&&pm.value?pm.value:'start',pools,starts:pools.start||[],ends:pools.end||[],activeTemplate:cur?cur.name:'',strategy:$('strategy').value,currentServerId:currentServerId,adapter:($('adsel')&&$('adsel').value)||'rds'}}
let pmSaved='start';
function applySettings(st){if(!st||typeof st!='object')return;let f=st.fields||{};
 if(st.currentServerId)currentServerId=st.currentServerId;if(Array.isArray(st.servers))serverList=st.servers;
 if(f.base==null&&'base' in st)f.base=st.base||'';if(st.pollSec&&f.poll==null)f.poll=st.pollSec;
 if($('base')&&'base' in st&&(st.base==null||st.base===''))$('base').value='';
 if(st.adapter&&$('adsel')){$('adsel').value=st.adapter;$('m4box').style.display=st.adapter==='m4'?'':'none'}
 if(f.grp)fillGroups(null,f.grp);
 for(const[k,v]of Object.entries(f)){let e=$(k);if(!e||NOSAVE.has(k))continue;if(e.type=='checkbox')e.checked=!!v;else if(v!=null)e.value=v}
 if(st.pools&&typeof st.pools=='object')pools=JSON.parse(JSON.stringify(st.pools));else pools={start:Array.isArray(st.starts)?st.starts:[],end:Array.isArray(st.ends)?st.ends:[]};
 if(st.strategy)$('strategy').value=st.strategy;pmSaved=st.pm=='S'?'start':st.pm=='E'?'end':(st.pm||'start');
 renderSrvList()}
/* In-page dialogs: native confirm/prompt/alert are suppressed in some embedded browsers (they return at once and nothing happens) */
function uiDlg(msg,o){o=o||{};return new Promise(res=>{let L=LANG=='en',ov=document.createElement('div');ov.className='uidlg';
 ov.innerHTML=`<div class=uidlg-box role=dialog aria-modal=true><div class=uidlg-msg></div>${o.input?'<input class=uidlg-in>':''}<div class=uidlg-btns>${o.cancel?`<button class=uidlg-no>${t('btn.cancel')}</button>`:''}<button class=uidlg-ok>${t('btn.ok')}</button></div></div>`;
 ov.querySelector('.uidlg-msg').textContent=String(msg==null?'':msg);let inp=ov.querySelector('.uidlg-in');if(inp)inp.value=o.def==null?'':String(o.def);
 let done=v=>{document.removeEventListener('keydown',key,true);ov.remove();res(v)},ok=()=>done(o.input?inp.value:true),no=()=>done(o.input?null:false);
 let key=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();o.cancel?no():ok()}else if(e.key==='Enter'&&!(e.target&&e.target.tagName==='TEXTAREA')){e.preventDefault();e.stopPropagation();ok()}};
 ov.querySelector('.uidlg-ok').onclick=ok;let nb=ov.querySelector('.uidlg-no');if(nb)nb.onclick=no;document.addEventListener('keydown',key,true);
 document.body.appendChild(ov);(inp||ov.querySelector('.uidlg-ok')).focus();if(inp)inp.select()})}
function uiConfirm(msg){return uiDlg(msg,{cancel:true})}
function uiPrompt(msg,def){return uiDlg(msg,{cancel:true,input:true,def})}
function uiAlert(msg){return uiDlg(msg,{})}
function isM4(){return ($('adsel')&&$('adsel').value)==='m4'}
function m4ActiveName(){return (M4P&&M4P.active)||'default'}
function persistDispatcherUrl(){let url=$('base').value.trim();
 if(isM4()){let p=m4Form();if(url)p.base=url;return post('/api/m4',{name:m4ActiveName(),profile:p}).then(async r=>{if(r&&r.ok){M4P=r;/* don't m4Fill — would reset focus/password */;await refreshServers()}if(r&&!r.ok)$('m4msg').textContent=(r&&r.err)||'?';return r})}
 if(!url)return Promise.resolve();
 return post('/api/config',{base:url,pollSec:+$('poll').value})}
function lsKey(){return 'odtSettings:'+(currentServerId||'default')}
function saveNow(){if(!loaded)return;let st=collect();try{localStorage.setItem(lsKey(),JSON.stringify(st));localStorage.setItem('odtSettings',JSON.stringify(st))}catch(e){}
 let body={pollSec:st.pollSec,settings:st};if(!isM4()){body.base=st.base}else{if(body.settings)delete body.settings.base;persistDispatcherUrl()}
 return post('/api/config',body).catch(()=>{})}
function saveLater(){if(!loaded)return;clearTimeout(saveT);saveT=setTimeout(saveNow,600)}
async function initSettings(){let st=null,fromLocal=false;try{st=await (await fetch('/api/settings')).json()}catch(e){}
 if(!st||!Object.keys(st).length){try{st=JSON.parse(localStorage.getItem('odtSettings')||'null');fromLocal=!!st}catch(e){}}
 applySettings(st);await loadTemplates(st&&st.activeTemplate);loaded=true;renderPool();renderSt();showTab($('tab').value||'cfg');$('geominfo').textContent=t('map.needScene');let cached=false;try{let r=await (await fetch('/api/scene_geom?cached=1')).json();if(r.ok&&!r.sceneErr&&r.stations&&r.stations.length){setScene(r.stations);setGeom(r);cached=true;$('info').textContent=sceneAt()}}catch(e){}
 if(!cached&&poolNames().some(r=>(pools[r]||[]).length))ensureScene(true).then(ok=>{if(ok){$('info').textContent=t('msg.loadedScene',{n:allSt.length});renderPool();renderSt();prevLater()}});
 document.querySelectorAll('input,select,textarea').forEach(e=>{if(e.id&&NOSAVE.has(e.id))return;if(e.closest('#steps')||e.closest('#srv_side'))return;e.addEventListener('input',saveLater);e.addEventListener('change',saveLater)});
 ['grp','veh','pri','label'].forEach(i=>{$(i).addEventListener('input',prevLater);$(i).addEventListener('change',prevLater)});
 $('info').textContent=[st&&Object.keys(st).length?(fromLocal?t('msg.fromLocal'):t('msg.loaded')):'',sceneAt()].filter(Boolean).join(' · ');if(fromLocal)saveNow()}
async function saveCfg(){let st=collect();try{localStorage.setItem(lsKey(),JSON.stringify(st));localStorage.setItem('odtSettings',JSON.stringify(st))}catch(e){}
 let body={pollSec:st.pollSec,settings:Object.assign({},st)};if(isM4()){delete body.settings.base;await persistDispatcherUrl()}else body.base=st.base;
 // also persist adapter into current server bucket
 if(st.adapter)body.settings.adapter=st.adapter;
 let r=await post('/api/config',body);if(r&&!r.ok){let msg=$('m4msg')||$('adapterinfo');if(msg)msg.textContent=(r.err||'?')}
 // refresh list labels (base may have changed)
 await refreshServers();return r}
async function loadSt(){saveCfg();let ok=await loadScene(true,false);if(!ok)return;stations=allSt.slice();$('info').textContent=sceneAt();fitAll();renderSt();renderPool();prevLater()}
function setScene(list){allSt=list||[];stMap={};for(const s of allSt)stMap[s.name]=s}
let busyN=0;function busy(on){busyN=Math.max(0,busyN+(on?1:-1));const o=$('busy');if(!o)return;if(busyN){$('busytxt').textContent=t('busy.scene');o.classList.add('on');if(document.activeElement)document.activeElement.blur()}else{o.classList.remove('on','prog');$('busystage').textContent='';$('busyfill').style.width='0'}}
document.addEventListener('keydown',e=>{if(busyN){e.preventDefault();e.stopPropagation()}},true);
const STW={request:[0,5],download:[5,50],parse:[50,57],pointcloud:[57,60],mapdl:[60,85],mapparse:[85,92],downsample:[92,96],mapcache:[92,96],cache:[96,100]};
const fmtB=n=>n<1e6?Math.round(n/1e3)+' KB':(n/1e6).toFixed(1)+' MB';
function showProg(s){const o=$('busy'),bar=$('busybar'),fill=$('busyfill');o.classList.add('prog');let w=STW[s.stage]||[0,0],pct=w[0],ind=false,extra='';
 if(s.stage=='downsample'&&s.done)extra=' ('+s.done.toLocaleString()+' '+t('prog.points')+')';
 else if(s.stage=='download'||s.stage=='mapdl'){if(s.total){let f=Math.min(1,(s.done||0)/s.total);pct=w[0]+(w[1]-w[0])*f;extra=' '+Math.round(f*100)+'% ('+fmtB(s.done||0)+' / '+fmtB(s.total)+')'}else{ind=true;extra=' '+fmtB(s.done||0)}}
 else if(s.stage=='request')ind=true;
 bar.classList.toggle('ind',ind);fill.style.width=pct.toFixed(1)+'%';$('busystage').textContent=t('prog.'+s.stage)+extra+' · '+t('prog.elapsed',{s:Math.round(s.elapsed||0)})}
async function sceneJob(url){/* background scene load with progress */
 let j=await (await fetch(url+(url.includes('?')?'&':'?')+'async=1')).json();if(!j.ok||!j.job)return j;
 let t0=Date.now();for(;;){await new Promise(r=>setTimeout(r,300));let s;try{s=await (await fetch('/api/scene_job?id='+j.job)).json()}catch(e){continue}
  if(!s.ok)return s;showProg(s);if(s.finished)return s.result||{ok:false,err:'no result'}}}
async function sceneFetch(url,quiet){busy(true);try{let job=url.startsWith('/api/scene_geom')&&!url.includes('cached=1');let r=job?await sceneJob(url):await (await fetch(url)).json();if(r.sceneErr){r.ok=false;r.err=r.sceneErr}if(!r.ok&&!quiet)uiAlert(t('msg.sceneFail')+': '+(r.err||''));return r}catch(e){if(!quiet)uiAlert(t('msg.sceneFail')+': '+e);throw e}finally{busy(false)}}
let sceneP=null;
function sceneAt(){if(!geom||!geom.loadedAt)return '';let d=new Date(geom.loadedAt*1000),p=n=>String(n).padStart(2,'0'),today=new Date().toDateString()==d.toDateString();return t('scene.loadedAt',{t:(today?'':(d.getMonth()+1)+'-'+d.getDate()+' ')+p(d.getHours())+':'+p(d.getMinutes())})+' · '+t('msg.nStations',{n:allSt.length})}
async function loadScene(refresh,quiet){/* the one scene loader: stations + pre-points + groups + geometry + point cloud */
 let r;try{r=await sceneFetch('/api/scene_geom'+(refresh?'?refresh=1':''),quiet)}catch(e){r={ok:false,err:String(e)}}
 if(!r.ok){$('info').innerHTML=`<b style=color:red>${t('msg.sceneFail')}: ${esc(r.err||'')}</b> <button onclick="loadSt()">${t('btn.retry')}</button>`;return false}
 setScene(r.stations);C.dataset.fitted='';setGeom(r);if(stations.some(s=>s.missing||s.x==null))stations=stations.map(s=>stMap[s.name]?{...stMap[s.name]}:{...s,missing:true});return true}
async function ensureScene(quiet){if(allSt.length)return true;if(sceneP)return sceneP;sceneP=loadScene(false,quiet).finally(()=>{sceneP=null});return sceneP}
async function usePaste(){let names=[...new Set($('paste').value.split(/[\s,，;；]+/).filter(x=>x))];await ensureScene();
 stations=names.map(n=>stMap[n]?{...stMap[n]}:{name:n,type:n.replace(/\d.*/,''),x:null,y:null,pre:'',missing:true});
 let miss=stations.filter(s=>s.missing).map(s=>s.name);$('info').innerHTML=t('msg.pasted',{n:names.length})+(allSt.length?'':' '+t('msg.noSceneCoords'))+(miss.length&&allSt.length?` <b style=color:red>${t('msg.notInScene')}: ${esc(miss.join(', '))}</b>`:'');renderSt();renderPool();fitAll()}
function preOvParse(){/* same rules as server parse_pre_text: STATION=PRE or STATION=PRE1|PRE2 per line, # comment */
 let m={},errs=[];$('pre_ov').value.split(/\n/).forEach((raw,k)=>{let l=raw.split('#')[0].trim();if(!l)return;let x=l.match(/^([^\s=:|,，]+)\s*(?:[=:]\s*|[\s,，]+)(.*?)\s*$/),v=x?x[2].split('|').map(s=>s.trim()):[];
  if(!x||!v.length||v.some(s=>!/^[^\s=:|,，]+$/.test(s))){errs.push(t('srv.preLineBad',{n:k+1,line:raw.trim()}));return}if(m[x[1]]){errs.push(t('srv.preLineDup',{n:k+1,st:x[1]}));return}m[x[1]]=[...new Set(v)]});return {m,errs}}
function preOv(){let r=preOvParse().m,o={};for(const k in r)o[k]=r[k][0];return o}
function preAll(n){/* every candidate pre-point (manual list, else scene list); [0] = default */let m=preOvParse().m[n];if(m&&m.length)return m;let s=stMap[n]||stations.find(x=>x.name==n)||{};let c=(s.preInfo||[]).map(x=>x.name);if(!c.length&&s.preCands)c=s.preCands;if(!c.length&&s.pre)c=[s.pre];return c}
function preOf(n){let o=preOv();/* default (nearest) pre-point */if(o[n])return o[n];let s=stMap[n]||stations.find(x=>x.name==n);return s&&s.pre||''}
function pmRole(){let r=$('pm');return r&&r.value?r.value:pmSaved}
function pick(n,role){role=role||pmRole();let a=pools[role]||(pools[role]=[]);let i=a.indexOf(n);i>=0?a.splice(i,1):a.push(n);renderPool();renderSt();prevLater()}
// incremental table rows (keeps scroll / selection / open JSON boxes)
function syncRows(tb,items){let ex=new Map();for(const tr of [...tb.rows])if(tr.dataset.k)ex.set(tr.dataset.k,tr);
 let want=new Set(items.map(i=>i.k));for(const[k,tr]of ex)if(!want.has(k))tr.remove();let prev=null;
 for(const it of items){let tr=ex.get(it.k);if(!tr){tr=document.createElement('tr');tr.dataset.k=it.k;tr._c=[]}
  if(tr._cls!==(it.cls||'')){tr.className=it.cls||'';tr._cls=it.cls||''}if(tr._st!==(it.st||'')){tr.setAttribute('style',it.st||'');tr._st=it.st||''}
  while(tr.cells.length>it.c.length){tr.deleteCell(-1);tr._c.length=tr.cells.length}
  it.c.forEach((c,i)=>{let h=typeof c=='string'?c:c.h,sp=typeof c=='string'?1:(c.span||1),td=tr.cells[i]||tr.insertCell(-1);if(td.colSpan!==sp)td.colSpan=sp;if(c&&c.title!=null&&td.title!==c.title)td.title=c.title;if(tr._c[i]!==h){td.innerHTML=h;tr._c[i]=h}});
  let next=prev?prev.nextSibling:tb.firstChild;if(next!==tr)tb.insertBefore(tr,next);prev=tr}}
function mkTable(host,hdr){let tb=document.createElement('table');tb.innerHTML='<thead><tr>'+hdr.map(h=>'<th>'+h+'</th>').join('')+'</tr></thead><tbody></tbody>';host.appendChild(tb);return tb}
// pool colours: start=green, end=red, other pools from the palette
const PAL=['#1a9a1a','#d01010','#1060d0','#c07000','#008b8b','#a0309a','#606000'];
function pcol(r){if(r=='start')return PAL[0];if(r=='end')return PAL[1];let i=poolNames().filter(x=>x!='start'&&x!='end').indexOf(r);return PAL[2+((i<0?0:i)%(PAL.length-2))]}
function plab(r){return r=='start'?t('pool.start'):r=='end'?t('pool.end'):r}
let stTable=null,stSig='';
function candHtml(s,manual){let c=s.preInfo||(s.preCands||[]).map(n=>({name:n})),out=[];
 if(manual&&manual.length>1)out.push(t('pre.manualList')+': '+manual.map(esc).join(' | '));
 if(c.length>1||(c.length==1&&c[0].dir))out.push(c.map((x,i)=>`${i+1}.${esc(x.name)}${x.dir?'('+t('pre.dir.'+x.dir)+(x.dist!=null?' '+x.dist.toFixed(1)+'m':'')+(x.lm===false?' ·'+t('pre.notLm'):'')+')':''}`).join(' '));
 return out.length?'<br><span class=dim style=font-size:11px>'+out.join('<br>')+'</span>':''}
function renderSt(){let pe=preOvParse().errs;if($('pre_err'))$('pre_err').textContent=pe.join('\n');let q=$('q').value.toLowerCase(),tf=$('tf').value.toLowerCase(),ov=preOv(),pn=poolNames(),sig=pn.join('|');
 if(stSig!==sig){$('st').innerHTML='';stTable=null;stSig=sig}
 if(!stTable)stTable=mkTable($('st'),[t('st.name'),t('st.type'),t('st.xy'),t('st.pre'),t('st.pick')]);
 let inSel={};pn.forEach(r=>(pools[r]||[]).forEach(n=>{(inSel[n]=inSel[n]||[]).includes(r)||inSel[n].push(r)}));
 let rows=Object.keys(inSel).map(n=>stMap[n]||stations.find(x=>x.name==n)||{name:n,type:n.replace(/\d.*/,''),x:null,y:null,pre:'',missing:true}).filter(s=>s.name.toLowerCase().includes(q)&&((s.type||'')+s.name).toLowerCase().includes(tf));
 $('st_empty').textContent=Object.keys(inSel).length?'':t('st.emptySel');
 syncRows(stTable.tBodies[0],rows.map(s=>{let miss=(s.missing||!stMap[s.name])&&allSt.length,pp=ov[s.name]||s.pre||'',pall=preOvParse().m[s.name],tt=(s.preSrc||'')+(ov[s.name]?' ('+t('pre.manual')+')':''),cl=candHtml(s,pall);
  return {k:s.name,st:miss?'background:#fdd':'',c:[esc(s.name)+(miss?` <b style=color:red>${t('msg.notInScene')}</b>`:''),esc(s.type||''),s.x!=null?s.x.toFixed(2)+','+s.y.toFixed(2):'',
  {h:'<b>'+esc(pp)+'</b>'+cl,title:tt},
  inSel[s.name].map(r=>`<span class=chip style="color:${pcol(r)};border-color:${pcol(r)};background:${pcol(r)}14">${esc(plab(r))}</span>`).join(' ')]}}));draw()}
let hlSt=new Set();
function chips(a,r){let ov=preOv(),c=pcol(r);return a.map(n=>{let pp=ov[n]||(stMap[n]||stations.find(x=>x.name==n)||{}).pre||'';
 let tt=t('pre.of')+': '+(pp||(allSt.length?t('pre.none'):t('pre.loading')))+(ov[n]?' ('+t('pre.manual')+')':'');
 return `<span class="chip${hlSt.has(n)?' hl':''}" style="color:${c};border-color:${c};background:${c}14" data-n="${esc(n)}" data-r="${esc(r)}" title="${esc(tt)}">${esc(n)}<i title="${t('btn.del')} ${esc(n)}">×</i></span>`}).join('')||`<span class=dim>${t('pool.empty')}</span>`}
function chipClick(e){let c=e.target.closest('.chip');if(!c)return;let n=c.dataset.n,r=c.dataset.r;
 if(e.target.tagName=='I'){let a=pools[r]||[],i=a.indexOf(n);if(i>=0)a.splice(i,1);renderPool();renderSt();saveNow();prevLater();return}
 hlSt.has(n)?hlSt.delete(n):hlSt.add(n);renderPool();draw()}
function renderPools(){let pn=poolNames(),used=(cur&&cur.pools)||[];
 $('pools').innerHTML=pn.map(r=>`<div class=poolrow><span class=pn style="color:${pcol(r)}">${esc(plab(r))}</span> <span class=dim>(${(pools[r]||[]).length})</span>${used.includes(r)?'':` <span class=dim>${t('pool.unused')}</span>`}: <span class=chips data-r="${esc(r)}">${chips(pools[r]||[],r)}</span> <button onclick="clearPool('${r}')">${t('btn.clear')}</button>${r=='start'||r=='end'?'':` <button onclick="renamePool('${r}')">${t('pool.rename')}</button> <button onclick="delPool('${r}')">${t('pool.del')}</button>`}</div>`).join('');
 document.querySelectorAll('#pools .chips').forEach(e=>e.onclick=chipClick);
 for(const s of ['swa','swb']){let e=$(s),v=e.value;e.innerHTML=pn.map(r=>`<option value="${esc(r)}">${esc(plab(r))}</option>`).join('');e.value=pn.includes(v)?v:(s=='swa'?pn[0]:pn[1]||pn[0])}
 let pm=pmRole();
 $('pm_box').innerHTML=`<select id=pm onchange=saveLater()>`+pn.map(r=>`<option value="${esc(r)}" ${r==pm?'selected':''}>${esc(plab(r))}</option>`).join('')+`</select>`;
 if($('pm')&&pn.length&&!pn.includes($('pm').value))$('pm').value=pn[0]}
function clearPool(r){pools[r]=[];renderPool();renderSt();saveNow();prevLater()}
async function delPool(r){if(!await uiConfirm(t('pool.delQ',{p:r})))return;delete pools[r];renderPool();renderSt();refreshStepPools();saveNow()}
async function renamePool(r){let n=await uiPrompt(t('pool.renameQ',{p:r}),r);if(n==null)return;n=n.trim();if(n==r)return;if(!/^[A-Za-z_][\w]*$/.test(n)){uiAlert(t('pool.badName'));return}if(pools[n]){uiAlert(t('pool.exists',{p:n}));return}
 let np={};for(const k of Object.keys(pools))np[k==r?n:k]=pools[k];pools=np;let ch=false;if(cur)for(const s of cur.steps)if(s.location&&s.location.type=='pool'&&s.location.pool==r){s.location.pool=n;ch=true}
 renderSteps();if(ch)tplChanged();renderPool();renderSt();saveNow()}
function addPool(){let n=$('newpool').value.trim();if(!/^[A-Za-z_][\w]*$/.test(n)){uiAlert(t('pool.badName'));return}if(!pools[n])pools[n]=[];$('newpool').value='';renderPool();renderSt();refreshStepPools();saveNow()}
function stratCount(){let roles=(cur&&cur.pools)||[],sz=roles.map(r=>(pools[r]||[]).length),s=$('strategy').value;if(!sz.length)return 0;
 if(s=='cartesian'){let ns=$('noself').checked,c=0,tot=sz.reduce((a,b)=>a*b,1);if(tot>200000)return tot;const rec=(i,used)=>{if(i==roles.length){c++;return}for(const x of pools[roles[i]]||[]){if(ns&&used.includes(x))continue;rec(i+1,used.concat([x]))}};rec(0,[]);return c}
 if(s=='round_robin')return Math.max(...sz);return sz[0]}
function renderPool(){renderPools();setTimeout(renderSum,0);if($('cnt_auto').value=='1')$('cnt').value=stratCount();let roles=(cur&&cur.pools)||[],s=$('strategy').value;$('noreuse_l').style.display=s=='random'?'':'none';
 $('poolline').innerHTML=t('gen.line.'+s,{pools:roles.map(r=>esc(plab(r))+'('+(pools[r]||[]).length+')').join(' × ')})+t('gen.total',{n:`<span style=color:#06c>${$('cnt').value}</span>`})+(s=='random'&&$('noreuse').checked?' · '+t('gen.noreuseShort'):'');saveLater();
 let need=needRoles();
 if(!allSt.length&&roles.some(r=>(pools[r]||[]).length)){$('pre_info').innerHTML=`<span class=dim>${t('pre.loading')}</span>`;draw();return}
 $('pre_info').innerHTML=roles.map(r=>{let a=pools[r]||[],miss=a.filter(e=>!preOf(e));
  return `<b>${t('pre.of')} · ${esc(plab(r))}</b>: `+a.map(e=>{let al=preAll(e);return esc(e)+'→'+(al.length?'<b>'+esc(al[0])+'</b>'+(al.length>1?'<span class=dim>/'+al.slice(1).map(esc).join('/')+'</span>':''):`<b style=color:${need.has(r)?'red':'#a60'}>${t('pre.none')}</b>`)}).join(' ')+
  (miss.length?(need.has(r)?`<br><b style=color:red>${t('pre.missNeeded')}: ${esc(miss.join(', '))}</b>`:`<br><span style=color:#a60>⚠ ${t('pre.missUnneeded')}: ${esc(miss.join(', '))}</span>`):'')}).join('<br>');draw()}
// pools whose stations need a pre-point (an enabled 'pre' step derives from them)
function stepRef(S,id){let s=S.find(x=>x.id==id);if(s)return s;let m=/^(?:step)?(\d+)$/.exec(id||'');return m?S[+m[1]-1]||null:null}
function needRoles(){let n=new Set();if(!cur)return n;let S=cur.steps;
 for(const s of S){if(s.enabled===false||s.location.type!='pre')continue;let r=stepRef(S,s.location.step),k=0;while(r&&r.location.type=='pre'&&k++<20)r=stepRef(S,r.location.step);if(r&&r.location.type=='pool')n.add(r.location.pool)}return n}
// ---------------- config sub-tabs + summary ----------------
const SUBS=['conn','pool','tpl','gen'];
function showSub(k){if(!SUBS.includes(k))k='pool';document.querySelectorAll('#tab-cfg .sub').forEach(e=>e.classList.toggle('on',e.dataset.sub==k));
 document.querySelectorAll('#subbar button[data-s]').forEach(b=>b.classList.toggle('on',b.dataset.s==k));try{localStorage.setItem('odtSub',k)}catch(e){}if(k=='pool')renderSt()}
function initSub(){let k=null;try{k=localStorage.getItem('odtSub')}catch(e){}showSub(k||'pool')}
function renderSum(){if(!cur)return;let roles=cur.pools||[];$('cfgsum').innerHTML=t('sum.line',{tpl:`<b>${esc(cur.name)}</b>`,pools:roles.length?roles.map(r=>esc(plab(r))+'('+(pools[r]||[]).length+')').join(' × '):t('sum.noPool'),n:`<b style=color:#06c>${$('cnt').value}</b>`,strat:t($('strategy').selectedOptions[0]?$('strategy').selectedOptions[0].dataset.i18n:'gen.random')})}
// ---------------- template editor ----------------
let TPL={},cur=null,tplT=null,prevT=null,dirty=false;
async function loadTemplates(active){let r=await (await fetch('/api/templates')).json();TPL=r.templates||{};$('adapterinfo').textContent=t('cfg.adapter')+': '+r.adapter;
 let names=Object.keys(TPL);if(!names.length){cur=null;dirty=false;fillTplList('');if($('tpl_name'))$('tpl_name').value='';if($('tpl_title'))$('tpl_title').value='';
  if($('steps')&&$('steps').tBodies[0])$('steps').tBodies[0].innerHTML='';if($('tpl_json'))$('tpl_json').value='';tplStatus(t('tpl.emptyHint'));if(loaded)renderPool();return}
 active=active&&TPL[active]?active:(TPL[r.active]?r.active:names[0]);setCur(TPL[active])}
function fillTplList(v){let ul=$('tpl_list');if(!ul)return;ul.innerHTML=Object.keys(TPL).sort().map(n=>`<li class="${n===v?'on':''}" onclick="selectTpl('${esc(n)}')">${esc(n)}</li>`).join('')}
function setCur(tp){cur=JSON.parse(JSON.stringify(tp));dirty=false;if($('tpl_name'))$('tpl_name').value=cur.name||'';$('tpl_title').value=cur.title||'';renderSteps();if($('tpl_raw').checked)$('tpl_json').value=JSON.stringify(cur,null,1);tplStatus('');fillTplList(cur.name);if(loaded)renderPool();prevLater()}
function selectTpl(n){if(!TPL[n]||(cur&&n===cur.name))return;if(dirty)saveTpl();setCur(TPL[n]);saveNow()}
async function renameTpl(){if(!cur||!$('tpl_name')){if($('tpl_name'))$('tpl_name').value='';return}let n=($('tpl_name').value||'').trim();if(!n||n===cur.name){$('tpl_name').value=cur.name||'';return}
 if(!/^[A-Za-z0-9_.\-\u4e00-\u9fff]{1,64}$/.test(n)){uiAlert(t('tpl.badName'));$('tpl_name').value=cur.name;return}
 let ow=!!TPL[n];if(ow&&!await uiConfirm(t('tpl.overwriteQ',{n}))){$('tpl_name').value=cur.name;return}
 if(dirty&&!(await saveTpl())){$('tpl_name').value=cur.name;return}
 let old=cur.name,r=await post('/api/template_rename',{old:old,new:n,overwrite:ow,activate:true});
 if(!r.ok){uiAlert(r.err||t('tpl.saveErr'));$('tpl_name').value=old;return}
 delete TPL[old];cur.name=n;TPL[n]=r.template||Object.assign({},cur,{name:n});setCur(TPL[n]);saveNow()}
function tplStatus(s,cls){$('tpl_status').innerHTML=s?`<span class=${cls||'dim'}>${s}</span>`:''}
function tplChanged(){dirty=true;cur.pools=locPools();tplStatus(t('tpl.unsaved'));clearTimeout(tplT);tplT=setTimeout(saveTpl,700);renderPool();prevLater()}
function locPools(){let S=cur.steps,u=new Set();for(const s of S){if(s.enabled===false||!s.location)continue;if(s.location.type=='pool'&&s.location.pool)u.add(s.location.pool);else if(s.location.type=='pre'){let r=stepRef(S,s.location.step),k=0;while(r&&r.location.type=='pre'&&k++<20)r=stepRef(S,r.location.step);if(r&&r.location.type=='pool'&&r.location.pool)u.add(r.location.pool)}}
 let p=[];for(const s of S)if(s.location&&s.location.type=='pool'&&u.has(s.location.pool)&&!p.includes(s.location.pool))p.push(s.location.pool);return p}
async function saveTpl(){clearTimeout(tplT);cur.pools=locPools();let r=await post('/api/template_save',{template:cur,activate:true});
 if(!r.ok){tplStatus(t('tpl.saveErr')+': '+esc(r.err),'err');return false}TPL[cur.name]=r.template;cur.pools=r.template.pools;dirty=false;tplStatus(t('tpl.saved'),'ok');renderPools();return true}
async function askName(def){let n=await uiPrompt(t('tpl.namePrompt'),def||'');if(n==null)return null;n=n.trim();if(!/^[A-Za-z0-9_.\-\u4e00-\u9fff]{1,64}$/.test(n)){uiAlert(t('tpl.badName'));return null}if(TPL[n]&&!await uiConfirm(t('tpl.overwriteQ',{n})))return null;return n}
function newStep(id,name,loc){return {id,name,enabled:true,location:loc,operation:'Wait',opMode:'binTask',args:{},vsOn:false,variableShape:{head:1.539,tail:1.539}}}
async function newTpl(){let n=await askName('my_template');if(!n)return;cur={name:n,title:'',version:1,pools:['start','end'],steps:[newStep('s',t('step.defPick'),{type:'pool',pool:'start'}),newStep('e',t('step.defDrop'),{type:'pool',pool:'end'})]};
 if(await saveTpl()){setCur(TPL[n]);saveNow()}}
async function copyTpl(){if(!cur){uiAlert(t('tpl.emptyHint'));return}let n=await askName(cur.name+'_copy');if(!n)return;cur=JSON.parse(JSON.stringify(cur));cur.name=n;if(await saveTpl()){setCur(TPL[n]);saveNow()}}
async function delTpl(){if(!cur){uiAlert(t('tpl.emptyHint'));return}if(!await uiConfirm(t('tpl.delQ',{n:cur.name})))return;let r=await post('/api/template_delete',{name:cur.name});if(!r.ok){uiAlert(r.err);return}
 delete TPL[cur.name];let names=Object.keys(TPL).sort();if(!names.length){cur=null;dirty=false;fillTplList('');if($('tpl_name'))$('tpl_name').value='';if($('tpl_title'))$('tpl_title').value='';
  if($('steps')&&$('steps').tBodies[0])$('steps').tBodies[0].innerHTML='';tplStatus(t('tpl.emptyHint'));saveNow();return}
 setCur(TPL[names[0]]);saveNow()}
function exportTpl(){if(!cur){uiAlert(t('tpl.emptyHint'));return}let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(cur,null,1)],{type:'application/json'}));a.download=cur.name+'.json';document.body.appendChild(a);a.click();a.remove()}
async function importTpl(){let f=$('tpl_imp').files[0];if(!f)return;let tp;try{tp=JSON.parse(await f.text())}catch(e){uiAlert(t('tpl.badJson')+': '+e.message);return}finally{$('tpl_imp').value=''}
 await importTplObj(tp,f.name)}
async function importTplObj(tp,fname){let n=await askName(tp.name||String(fname||'imported').replace(/\.json$/i,''));if(!n)return false;tp.name=n;let v=await post('/api/template_validate',{template:tp});if(!v.ok){uiAlert(t('tpl.invalid')+':\n'+v.errors.join('\n'));return false}
 cur=v.template;if(await saveTpl()){setCur(TPL[n]);saveNow();return true}return false}
function toggleRaw(){let raw=$('tpl_raw').checked;if(raw)$('tpl_json').value=JSON.stringify(cur,null,1);else renderSteps();$('tpl_form').style.display=raw?'none':'';$('tpl_rawbox').style.display=raw?'':'none'}
function rawChanged(){let v;try{v=JSON.parse($('tpl_json').value)}catch(e){tplStatus(t('tpl.badJson')+': '+esc(e.message),'err');return}
 if(!v||typeof v!='object'||!Array.isArray(v.steps)||v.steps.some(s=>!s||typeof s!='object'||!s.location)){tplStatus(t('tpl.invalid'),'err');return}v.name=cur.name;cur=v;$('tpl_title').value=cur.title||'';tplChanged()}
const OPS=['Wait','ForkLoad','ForkUnload','ForkHeight','Script','JackLoad','JackUnload','none'];
function locCell(s,i,dis){dis=dis||'';let L=s.location,ty=L.type,pn=poolNames(),opts=cur.steps.map((x,j)=>j==i?'':`<option value="${esc(x.id)}" ${L.step==x.id?'selected':''}>${j+1}. ${esc(x.name||x.id)}</option>`).join('');
 return `<select class=loctype onchange="setLoc(${i},'type',this.value)" ${dis}>${['pool','pre','fixed'].map(x=>`<option value=${x} ${ty==x?'selected':''}>${t('loc.'+x)}</option>`).join('')}</select><br>`+
 (ty=='pool'?poolSelect(L.pool,i,dis):
  ty=='pre'?`<select class=locstep onchange="setLoc(${i},'step',this.value)" ${dis}><option value="">-</option>${opts}</select><br>`+selCell(L,i,dis):`<input class=locfixed size=10 value="${esc(L.station||'')}" placeholder="LM1" onchange="setLoc(${i},'station',this.value)" ${dis}>`)}
const PSEL=['nearest','index','name','dir','random'];
function selCell(L,i,dis){dis=dis||'';let by=L.select||'nearest',arg=L.selArg==null?'':String(L.selArg);
 let h=`<select class=locsel title="${esc(t('sel.tip'))}" onchange="setLoc(${i},'select',this.value)" ${dis}>${PSEL.map(x=>`<option value=${x} ${by==x?'selected':''}>${t('sel.'+x)}</option>`).join('')}</select>`;
 if(by=='dir')h+=` <select class=locselarg onchange="setLoc(${i},'selArg',this.value)" ${dis}>${['in','out'].map(x=>`<option value=${x} ${arg==x?'selected':''}>${t('pre.dir.'+x)}</option>`).join('')}</select>`;
 else if(by=='index')h+=` <input class=locselarg type=number min=1 style=width:4em value="${esc(arg||'1')}" onchange="setLoc(${i},'selArg',this.value)" ${dis}>`;
 else if(by=='name')h+=` <input class=locselarg size=8 value="${esc(arg)}" placeholder="LM1*" onchange="setLoc(${i},'selArg',this.value)" ${dis}>`;
 return h}
// pool dropdown for a 'pool' step: every existing pool (display names) + the step's own value if it is not a pool yet.
// (was <input list=datalist>: browsers filter datalist suggestions by the current value, so only 'start' was offered)
function poolSelect(v,i,dis){dis=dis||'';let pn=poolNames();if(v&&!pn.includes(v))pn=pn.concat([v]);
 return `<select class=locpool onchange="setLoc(${i},'pool',this.value)" ${dis}>${pn.map(r=>`<option value="${esc(r)}" ${r==v?'selected':''}>${esc(plab(r))}${r!='start'&&r!='end'||plab(r)==r?'':' ('+r+')'}</option>`).join('')}</select>`}
// re-render the step table only when the pool list changed and no step control has focus (never clobber an open dropdown/input)
let stepPoolSig='';function refreshStepPools(){let sig=poolNames().join('|');if(sig===stepPoolSig)return;
 let a=document.activeElement;if(a&&a.closest&&a.closest('#steps')){setTimeout(refreshStepPools,500);return}if(cur)renderSteps()}
function stepOpMode(s){if(s.opMode==='binTask'||s.opMode==='operation')return s.opMode;
 let am=s.args&&s.args.m4Mode;if(am==='binTask'||am==='operation')return am;return isM4()?'binTask':'operation'}
function renderSteps(){stepPoolSig=poolNames().join('|');let tb=$('steps').tBodies[0];tb.innerHTML='';let m4=isM4();$('steps').classList.toggle('no-vs',m4);
 cur.steps.forEach((s,i)=>{let tr=document.createElement('tr');let om=stepOpMode(s);tr.className=(s.enabled===false?'off ':'')+(om==='binTask'?'om-bin':'om-op');tr.dataset.i=i;
 let vs=s.variableShape||{head:1.539,tail:1.539};let dis=s.enabled===false?'disabled':'';
 tr.innerHTML=`<td><div class=act><span class=hdl draggable=true title="${t('step.drag')}">☰</span><button class=up onclick=mvStep(${i},-1) ${dis||(i?'':'disabled')}>↑</button><button class=down onclick=mvStep(${i},1) ${dis||(i<cur.steps.length-1?'':'disabled')}>↓</button><button class=rm onclick=rmStep(${i}) title="${t('btn.del')}" ${dis}>✕</button></div></td><td>${i+1}</td>
 <td><input type=checkbox class=sten ${s.enabled===false?'':'checked'} onchange="setF(${i},'enabled',this.checked)"></td>
 <td><input class=stid size=6 value="${esc(s.id)}" onchange="setF(${i},'id',this.value.trim())" ${dis}></td>
 <td><input class=stname size=9 value="${esc(s.name||'')}" onchange="setF(${i},'name',this.value)" ${dis}></td><td>${locCell(s,i,dis)}</td>
 <td><select class=stom onchange="setOpMode(${i},this.value)" ${dis}><option value=binTask ${om==='binTask'?'selected':''}>binTask</option><option value=operation ${om==='operation'?'selected':''}>operation</option></select></td>
 <td><input class=stop list=dl_ops size=12 value="${esc(s.operation||(om==='binTask'?'':'none'))}" ${om==='operation'?`onfocus="this.placeholder=this.value;this.value=''" onblur="if(!this.value)this.value=this.placeholder"`:''} ${dis} onchange="if(this.value.trim())setF(${i},'operation',this.value.trim())"></td>
 <td class=stargs-td>${om==='binTask'?'':`<textarea class=stargs rows=7 spellcheck=false ${dis} onchange="setArgs(${i},this)">${esc(JSON.stringify(s.args||{},null,2))}</textarea><span class="err argerr"></span>`}</td>
 <td class=vs-col><label><input type=checkbox class=stvs ${s.vsOn?'checked':''} ${dis} onchange="setVs(${i},'on',this.checked)">${t('step.vsOn')}</label><br><input type=number step=0.001 value="${vs.head}" ${dis} onchange="setVs(${i},'head',this.value)"> <input type=number step=0.001 value="${vs.tail}" ${dis} onchange="setVs(${i},'tail',this.value)"></td>
 <td class=m4-col><input type=checkbox class=stkfs title="${t('step.kfsTip')}" ${s.keepFinalPathSpace?'checked':''} ${dis} onchange="setKfs(${i},this.checked)"></td>`;
 let hdl=tr.querySelector('.hdl');if(dis){hdl.removeAttribute('draggable');hdl.style.pointerEvents='none';hdl.style.opacity='.4'}else hdl.addEventListener('dragstart',e=>{e.dataTransfer.setData('text/plain',String(i));e.dataTransfer.effectAllowed='move'});
 tr.addEventListener('dragover',e=>{e.preventDefault();tr.classList.add('drag')});tr.addEventListener('dragleave',()=>tr.classList.remove('drag'));
 tr.addEventListener('drop',e=>{e.preventDefault();tr.classList.remove('drag');moveStep(parseInt(e.dataTransfer.getData('text/plain')),i)});tb.appendChild(tr)});
 if(!$('dl_ops')){let d=document.createElement('datalist');d.id='dl_ops';d.innerHTML=OPS.map(o=>`<option value="${o}">`).join('');document.body.appendChild(d)}}
function setF(i,k,v){let s=cur.steps[i];if(k=='id'){let old=s.id;if(!v||cur.steps.some((x,j)=>j!=i&&x.id==v)){uiAlert(t('step.dupId'));renderSteps();return}cur.steps.forEach(x=>{if(x.location.type=='pre'&&x.location.step==old)x.location.step=v})}
 if(k=='blockSuffix'&&!v)delete s.blockSuffix;else s[k]=v;renderSteps();tplChanged()}
function setLoc(i,k,v){let L=cur.steps[i].location;if(k=='type'){cur.steps[i].location=v=='pool'?{type:'pool',pool:poolNames()[0]||'start'}:v=='pre'?{type:'pre',step:(cur.steps.find((x,j)=>j!=i&&x.location.type=='pool')||{}).id||''}:{type:'fixed',station:''}}else if(k=='select'){if(v=='nearest'){delete L.select;delete L.selArg}else{L.select=v;L.selArg=v=='dir'?'in':v=='index'?'1':v=='name'?(L.selArg&&L.select=='name'?L.selArg:''):undefined;if(L.selArg===undefined)delete L.selArg}}else L[k]=v.trim();renderSteps();tplChanged()}
function setArgs(i,ta){let v;try{v=JSON.parse(ta.value||'{}');if(!v||typeof v!='object'||Array.isArray(v))throw new Error(t('step.argsObj'))}catch(e){ta.nextElementSibling.textContent=e.message;return}ta.nextElementSibling.textContent='';cur.steps[i].args=v;tplChanged()}
function setOpMode(i,v){let s=cur.steps[i];s.opMode=(v==='operation')?'operation':'binTask';if(s.args&&s.args.m4Mode){delete s.args.m4Mode}renderSteps();tplChanged()}
function setKfs(i,v){let s=cur.steps[i];if(v)s.keepFinalPathSpace=true;else delete s.keepFinalPathSpace;tplChanged()}
function setVs(i,k,v){let s=cur.steps[i];s.variableShape=s.variableShape||{head:1.539,tail:1.539};if(k=='on')s.vsOn=v;else{let n=parseFloat(v);if(!isFinite(n)){uiAlert(t('vs.num'));return}s.variableShape[k]=n}tplChanged()}
function mvStep(i,d){moveStep(i,i+d)}
function moveStep(a,b){if(a==b||isNaN(a)||b<0||b>=cur.steps.length)return;let [s]=cur.steps.splice(a,1);cur.steps.splice(b,0,s);renderSteps();tplChanged()}
async function rmStep(i){if(cur.steps.length<=1){uiAlert(t('step.lastOne'));return}if(!await uiConfirm(t('step.delQ',{n:cur.steps[i].name||cur.steps[i].id})))return;let id=cur.steps[i].id;cur.steps.splice(i,1);renderSteps();tplChanged()}
function addStep(){let k=1;while(cur.steps.some(s=>s.id=='step'+k))k++;cur.steps.push(newStep('step'+k,'step'+k,{type:'pool',pool:poolNames()[0]||'start'}));renderSteps();tplChanged()}
function prevLater(){clearTimeout(prevT);prevT=setTimeout(doPreview,300)}
async function doPreview(){if(!cur)return;let r;try{r=await post('/api/preview',Object.assign(dispCfg(),{template:Object.assign({},cur,{pools:locPools()}),pools}))}catch(e){return}
 if(!r.ok){$('prev_info').innerHTML=`<span class=err>${esc(r.err)}</span>`;$('tpl_prev').textContent='';return}
 $('prev_info').textContent=t('tpl.prevInfo',{p:Object.entries(r.picks).map(([k,v])=>plab(k)+'='+v).join(', ')});$('tpl_prev').textContent=JSON.stringify(r.payload,null,1)}
// ---------------- map ----------------
const C=$('map'),X=C.getContext('2d');let geom=null,pcOff=null,pcK=1;
function showTab(tb){if(!['cfg','map','rob','ord'].includes(tb))tb='cfg';$('tab').value=tb;document.querySelectorAll('.tab').forEach(e=>e.classList.toggle('on',e.id=='tab-'+tb));
 document.querySelectorAll('#tabbar button').forEach(b=>b.classList.toggle('on',b.dataset.t==tb));saveLater();if(tb=='map'){let first=!C.dataset.sized;resizeMap();if(first)fitAll()}else{document.documentElement.classList.remove('map-fill');document.body.classList.remove('map-fill')}}
function resizeMap(){
 if($('tab').value!='map'){document.documentElement.classList.remove('map-fill');document.body.classList.remove('map-fill');return}
 document.documentElement.classList.add('map-fill');document.body.classList.add('map-fill');
 let box=C.parentElement,br=box.getBoundingClientRect(),tr=$('maptool').getBoundingClientRect();
 let w=Math.max(300,Math.floor(br.width)),h=Math.max(200,Math.floor(br.bottom-tr.bottom-4));
 if(C.width!==w||C.height!==h){C.width=w;C.height=h;C.dataset.sized=1;draw()}
 else {C.dataset.sized=1}
}
window.addEventListener('resize',()=>{if($('tab').value=='map')resizeMap()});
function setGeom(r){geom=r;if(r.stations&&r.stations.length){if(!allSt.length)setScene(r.stations);if(!stations.length){stations=r.stations;}
 else if(stations.some(s=>s.missing||s.x==null))stations=stations.map(s=>stMap[s.name]?{...stMap[s.name]}:{...s,missing:true});renderSt();renderPool();prevLater()}buildPC();$('geominfo').innerHTML=(r.loadedAt?esc(sceneAt().split(' · ')[0])+' · ':'')+t('map.geomInfo',{c:r.curves.length,cs:r.curveSrc?' ('+esc(r.curveSrc)+')':'',p:r.npoints,ps:r.pointSrc?' ('+esc(r.pointSrc)+')':''})+(r.notes&&r.notes.length?` <span style=color:#a60 title="${esc(r.notes.join('\n'))}">⚠${esc(r.notes[r.notes.length-1])}</span>`:'');
 if(!stations.filter(s=>s.x!=null).length||!C.dataset.fitted)fitAll();draw()}
function buildPC(){pcOff=null;if(!geom||!geom.npoints)return;let P=geom.points,x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
 for(let i=0;i<P.length;i+=2){let x=P[i],y=P[i+1];if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y}
 pcK=Math.min(4096/((x1-x0)||1),4096/((y1-y0)||1),1/Math.max(geom.cell||0.05,0.02));let w=Math.ceil((x1-x0)*pcK)+1,h=Math.ceil((y1-y0)*pcK)+1;
 let off=document.createElement('canvas');off.width=w;off.height=h;let g=off.getContext('2d'),im=g.createImageData(w,h),d=new Uint32Array(im.data.buffer);
 for(let i=0;i<P.length;i+=2){let px=Math.floor((P[i]-x0)*pcK),py=Math.floor((y1-P[i+1])*pcK);d[py*w+px]=0xff8c8c8c}
 g.putImageData(im,0,0);pcOff={c:off,x0,y1,w,h}}
function fitAll(){let b=geom&&geom.bounds?{...geom.bounds}:null;for(const s of (allSt.length?allSt:stations)){if(s.x==null)continue;if(!b)b={minx:s.x,maxx:s.x,miny:s.y,maxy:s.y};b.minx=Math.min(b.minx,s.x);b.maxx=Math.max(b.maxx,s.x);b.miny=Math.min(b.miny,s.y);b.maxy=Math.max(b.maxy,s.y)}
 if(!b)return;view.s=Math.min((C.width-40)/((b.maxx-b.minx)||1),(C.height-40)/((b.maxy-b.miny)||1));view.ox=(C.width-(b.maxx-b.minx)*view.s)/2-b.minx*view.s;view.oy=(C.height+(b.maxy-b.miny)*view.s)/2+b.miny*view.s;
 if(C.dataset.sized)C.dataset.fitted=1;draw()}
const tx=x=>x*view.s+view.ox,ty=y=>view.oy-y*view.s;let robotsCache=[],ordersCache=[];
function draw(){X.setTransform(1,0,0,1,0,0);X.clearRect(0,0,C.width,C.height);X.font='11px sans-serif';
 if($('ly_pc').checked&&pcOff){X.imageSmoothingEnabled=false;let sc=view.s/pcK,k=Math.max(1,Math.min(4,+($('pcsize')&&$('pcsize').value)||1)),o=(k-1)/2;/* point size in screen px: stamp the cloud k×k times, independent of zoom */
  for(let i=0;i<k;i++)for(let j=0;j<k;j++)X.drawImage(pcOff.c,tx(pcOff.x0)+i-o,ty(pcOff.y1)+j-o,pcOff.w*sc,pcOff.h*sc)}
 if($('ly_rt').checked&&geom){X.strokeStyle='#2a8a8a';X.lineWidth=1.2;X.beginPath();for(const c of geom.curves){let p=c.p;X.moveTo(tx(p[0][0]),ty(p[0][1]));for(let i=1;i<p.length;i++)X.lineTo(tx(p[i][0]),ty(p[i][1]))}X.stroke();
  if(view.s>12){X.fillStyle='#2a8a8a';for(const c of geom.curves){let p=c.p,m=Math.floor(p.length/2),a=p[Math.max(0,m-1)],b=p[Math.min(p.length-1,m)];let ang=Math.atan2(-(b[1]-a[1]),b[0]-a[0]),cx=tx((a[0]+b[0])/2),cy=ty((a[1]+b[1])/2);
   X.beginPath();X.moveTo(cx+6*Math.cos(ang),cy+6*Math.sin(ang));X.lineTo(cx+6*Math.cos(ang+2.5),cy+6*Math.sin(ang+2.5));X.lineTo(cx+6*Math.cos(ang-2.5),cy+6*Math.sin(ang-2.5));X.fill()}}}
 if($('ly_st').checked)drawStations();if($('ly_dir')&&$('ly_dir').checked)drawHeadings();
 if($('ly_rb').checked)for(const r of robotsCache){if(r.x==null)continue;let stk=r.idle>+$('still').value&&r.orderActive;X.fillStyle=stk?'red':r.orderActive?'#f80':'#fc0';X.strokeStyle='#000';
  X.fillRect(tx(r.x)-7,ty(r.y)-7,14,14);X.strokeRect(tx(r.x)-7,ty(r.y)-7,14,14);X.fillStyle='#000';X.font='bold 12px sans-serif';X.fillText(r.name+(r.orderActive?' ['+r.order+' '+(r.orderState||'')+']':'')+(stk?' ⚠':''),tx(r.x)+9,ty(r.y)+12);X.font='11px sans-serif'}}
// stations: each pool its colour; station in 2+ pools = split + purple ring; pre-points lighter + dashed line to the station
const RING='#8a2be2';
function stPos(n){let s=stMap[n]||(allSt.length?allSt:stations).find(x=>x.name==n);return s&&s.x!=null?s:null}
function lbl(s,x,y,c){X.save();X.font='bold 12px sans-serif';X.lineWidth=3;X.strokeStyle='rgba(255,255,255,.9)';X.strokeText(s,x,y);X.fillStyle=c;X.fillText(s,x,y);X.restore()}
function dot(x,y,r,c1,c2,ring){X.save();if(c2&&c2!==c1){X.fillStyle=c1;X.beginPath();X.arc(x,y,r,Math.PI/2,Math.PI*1.5);X.fill();X.fillStyle=c2;X.beginPath();X.arc(x,y,r,-Math.PI/2,Math.PI/2);X.fill()}
 else{X.fillStyle=c1;X.beginPath();X.arc(x,y,r,0,7);X.fill()}X.lineWidth=ring?2.5:1.5;X.strokeStyle=ring||'#fff';X.beginPath();X.arc(x,y,r,0,7);X.stroke();X.restore()}
const light=c=>c+'70';
function drawHeadings(){/* station heading arrows (scene 'dir', radians); stations without an angle are not touched */
 X.save();X.strokeStyle='#7a3db8';X.fillStyle='#7a3db8';X.lineWidth=1.5;const L=12;
 for(const s of (allSt.length?allSt:stations)){if(s.x==null||typeof s.dir!='number')continue;let x=tx(s.x),y=ty(s.y),c=Math.cos(s.dir),n=Math.sin(s.dir),ex=x+L*c,ey=y-L*n;
  let col=s.ignoreDir?'#b9a6cf':'#7a3db8';X.strokeStyle=col;X.fillStyle=col;X.beginPath();X.moveTo(x,y);X.lineTo(ex,ey);X.stroke();X.beginPath();X.moveTo(ex,ey);X.lineTo(ex-5*c+3*n,ey+5*n+3*c);X.lineTo(ex-5*c-3*n,ey+5*n-3*c);X.closePath();X.fill()}
 X.restore()}
function hoverSt(e){if(!$('ly_st').checked){C.title='';return}let best=null,bd=144;for(const s of (allSt.length?allSt:stations)){if(s.x==null)continue;let d=(tx(s.x)-e.offsetX)**2+(ty(s.y)-e.offsetY)**2;if(d<bd){bd=d;best=s}}
 let tt=best?best.name+' ('+best.type+')'+(typeof best.dir=='number'?' · '+t('map.angle')+' '+(best.dirDeg!=null?best.dirDeg:(best.dir*180/Math.PI).toFixed(1))+'°'+(best.ignoreDir?' ('+t('map.ignoreDir')+')':''):''):'';if(C.title!==tt)C.title=tt}
function drawStations(){let pn=poolNames(),inP={},pre={};
 let alt={};for(const r of pn)for(const n of pools[r]||[]){(inP[n]=inP[n]||[]).push(r);preAll(n).forEach((p,i)=>{pre[p]=pre[p]||{};(pre[p][r]=pre[p][r]||[]).push(n);if(i)alt[p+'|'+n]=1})}
 for(const s of (allSt.length?allSt:stations)){if(s.x==null||inP[s.name]||pre[s.name])continue;
  X.fillStyle=(s.type.includes('Action')||s.name.startsWith('AP'))?'#06c':'#999';X.beginPath();X.arc(tx(s.x),ty(s.y),3,0,7);X.fill();X.fillStyle='#333';X.fillText(s.name,tx(s.x)+4,ty(s.y)-4)}
 X.save();X.setLineDash([4,3]);X.lineWidth=1.2;
 for(const p in pre){let a=stPos(p);if(!a)continue;for(const r in pre[p])for(const n of pre[p][r]){let b=stPos(n);if(!b)continue;X.strokeStyle=pcol(r);X.globalAlpha=alt[p+'|'+n]?.3:.7;X.beginPath();X.moveTo(tx(a.x),ty(a.y));X.lineTo(tx(b.x),ty(b.y));X.stroke()}}
 X.restore();
 for(const p in pre){if(inP[p])continue;let a=stPos(p);if(!a)continue;let rs=Object.keys(pre[p]),multi=rs.length>1;
  dot(tx(a.x),ty(a.y),4.5,light(pcol(rs[0])),multi?light(pcol(rs[1])):null,multi?RING:pcol(rs[0]));lbl(p,tx(a.x)+6,ty(a.y)+13,multi?RING:pcol(rs[0]))}
 for(const n in inP){let a=stPos(n);if(!a)continue;let rs=inP[n],b=rs.length>1,x=tx(a.x),y=ty(a.y);
  dot(x,y,7,pcol(rs[0]),b?pcol(rs[1]):null,b?RING:null);lbl(n,x+9,y-6,b?RING:pcol(rs[0]))}
 for(const n of hlSt){let a=stPos(n);if(!a)continue;X.save();X.strokeStyle='#f80';X.lineWidth=3;X.beginPath();X.arc(tx(a.x),ty(a.y),12,0,7);X.stroke();X.restore()}
 drawLegend(pn)}
function drawLegend(pn){let items=pn.map(r=>['dot',pcol(r),null,null,`${plab(r)} (${(pools[r]||[]).length})`]).concat([['dot',PAL[0],PAL[1],RING,t('lg.multi')]],
 pn.map(r=>['pre',light(pcol(r)),null,pcol(r),t('lg.preOf',{p:plab(r)})]),[['dot','#06c',null,null,t('lg.otherAP')],['dot','#999',null,null,t('lg.other')]]);
 let x0=10,y0=C.height-items.length*17-14;X.save();X.setTransform(1,0,0,1,0,0);X.fillStyle='rgba(255,255,255,.88)';X.strokeStyle='#bbb';X.fillRect(x0,y0,200,items.length*17+8);X.strokeRect(x0,y0,200,items.length*17+8);
 X.font='12px sans-serif';items.forEach((it,i)=>{let y=y0+13+i*17,cx=x0+12;if(it[0]=='pre'){X.save();X.setLineDash([4,3]);X.strokeStyle=it[3];X.beginPath();X.moveTo(cx+5,y);X.lineTo(cx+16,y);X.stroke();X.restore();dot(cx,y,4.5,it[1],null,it[3])}
  else if(it[1]=='#06c'||it[1]=='#999'){X.fillStyle=it[1];X.beginPath();X.arc(cx,y,3,0,7);X.fill()}else dot(cx,y,6,it[1],it[2],it[3]);X.fillStyle='#222';X.fillText(it[4],x0+30,y+4)});X.restore()}
let drag=null;C.onmousedown=e=>drag={x:e.offsetX,y:e.offsetY,m:0};C.onmousemove=e=>{if(!drag){hoverSt(e);return}let dx=e.offsetX-drag.x,dy=e.offsetY-drag.y;if(Math.abs(dx)+Math.abs(dy)>2)drag.m=1;view.ox+=dx;view.oy+=dy;drag.x=e.offsetX;drag.y=e.offsetY;draw()};
C.onmouseup=e=>{if(drag&&!drag.m&&$('ly_st').checked){let best=null,bd=144;for(const s of (allSt.length?allSt:stations)){if(s.x==null)continue;let d=(tx(s.x)-e.offsetX)**2+(ty(s.y)-e.offsetY)**2;if(d<bd){bd=d;best=s}}if(best)pick(best.name)}drag=null};
C.onmouseleave=()=>drag=null;
C.onwheel=e=>{e.preventDefault();let f=e.deltaY<0?1.2:1/1.2;view.ox=e.offsetX-(e.offsetX-view.ox)*f;view.oy=e.offsetY-(e.offsetY-view.oy)*f;view.s*=f;draw()};
// ---------------- generate / drafts ----------------
function dispCfg(){return {base:$('base').value,vehicle:$('veh').value.trim(),group:$('grp').value,priority:+$('pri').value,label:$('label').value.trim(),preOverrides:preOvParse().m,preOverridesText:$('pre_ov').value}}
function incTag(o){let c=o.inc;if(!c||typeof c!='object')return '';let col=c.status=='done'?'#2a7':c.status=='stopped'?'#c33':c.warn?'#e67e00':'#06c',tip=[t('inc.'+c.status),c.reason||'',c.warn||'',c.lastErr||'',c.resumed?t('inc.resumed'):''].filter(Boolean).join('\n');
 return ` <span style="background:#eef;color:${col};padding:0 3px;font-size:11px" title="${esc(tip)}">${t('inc.tag')} ${c.sent}/${c.total}${c.status=='stopped'?' '+t('inc.stopped')+(c.reason?': '+esc(c.reason):''):c.status=='done'?' ✓':c.warn?' '+t('inc.waiting')+': '+esc(c.warn):''}</span>`}
async function generate(){if(dirty&&!(await saveTpl()))return;{let pe=preOvParse().errs;if(pe.length){uiAlert(pe.join('\n'));return}}let roles=cur.pools||[];
 let empty=roles.filter(r=>!(pools[r]||[]).length);if(empty.length){uiAlert(t('gen.poolEmpty',{p:empty.map(plab).join(', ')}));return}
 if($('noself').checked&&roles.length>1&&roles.every(r=>pools[r].length==1)&&new Set(roles.map(r=>pools[r][0])).size<roles.length){uiAlert(t('gen.sameOnly'));return}
 let need=needRoles(),miss=[];if(need.size&&!allSt.length&&!(await ensureScene()))return;if(allSt.length)for(const r of need){let m=(pools[r]||[]).filter(e=>!preOf(e));if(m.length)miss.push(plab(r)+': '+m.join(', '))}
 if(miss.length&&!await uiConfirm(t('gen.missQ',{list:miss.join('\n')})))return;
 $('genmsg').textContent=t('gen.running');$('genmsg2').textContent=t('gen.running');
 let r=await post('/api/generate',Object.assign(dispCfg(),{templateName:cur.name,pools,strategy:$('strategy').value,noSelf:$('noself').checked,noReuse:$('noreuse').checked,count:+$('cnt').value,settings:collect()}));
 if(!r.ok){$('genmsg').textContent='';$('genmsg2').textContent='';uiAlert(r.err);return}
 $('genmsg').innerHTML=`<b style=color:green>${t('gen.done',{n:r.n})}</b>`+(r.skipped&&r.skipped.length?` <span style=color:red title="${esc(r.skipped.map(s=>s.err).join('\n'))}">${t('gen.skipped',{n:r.skipped.length})}</span>`:'')+` <button onclick="showTab('ord')">${t('gen.goSend')}</button>`;
 $('genmsg2').innerHTML=$('genmsg').innerHTML;r.ids.forEach(i=>sel.add(i));if(r.warn)uiAlert(r.warn);tick()}
let grpSig='';function fillGroups(groups,keep){let s=$('grp'),cv=keep!=null?keep:s.value,names=(groups||[]).map(g=>g.name);if(cv&&!names.includes(cv))names.push(cv);
 let sig=names.join('|');if(sig===grpSig&&keep==null)return;grpSig=sig;s.innerHTML=`<option value="">${t('disp.none')}</option>`+names.map(n=>`<option value="${esc(n)}">${esc(n)}</option>`).join('');s.value=cv}
function swapPools(){let a=$('swa').value,b=$('swb').value;if(!a||!b||a==b)return;[pools[a],pools[b]]=[pools[b]||[],pools[a]||[]];renderPool();renderSt();saveNow();prevLater()}
async function swapDrafts(){let ds=ordersCache.filter(o=>o.state==DRAFT&&sel.has(o.id));if(!ds.length){uiAlert(t('ord.noDraftSel'));return}
 if(dirty&&!(await saveTpl()))return;
 if(!await uiConfirm(t('ord.swapQ',{n:ds.length,tpl:cur.name})+'\n\n'+ds.slice(0,8).map(o=>{let p=[...o.pair];if(p.length>1)[p[0],p[p.length-1]]=[p[p.length-1],p[0]];return `${o.id}: ${o.pairS}  ⇒  ${p.join(' → ')}`}).join('\n')+(ds.length>8?'\n... '+ds.length:'')))return;
 let r=await post('/api/swap_drafts',Object.assign(dispCfg(),{templateName:cur.name,ids:ds.map(o=>o.id)}));if(!r.ok){uiAlert(r.err);return}
 ds.forEach(o=>delete jsonCache[o.id]);ds.forEach(o=>{let id=o.id;if(jsonOpen.has(id))fetch('/api/order?id='+encodeURIComponent(id)).then(x=>x.json()).then(j=>{jsonCache[id]=JSON.stringify(j.body,null,1);tick()})});
 uiAlert(t('ord.swapped',{n:r.n})+(r.errors.length?'\n'+t('ord.notSwapped',{n:r.errors.length})+'\n'+r.errors.map(e=>`${e.id}${e.pair?' ('+e.pair.join('→')+')':''}: ${e.err}`).join('\n'):''));tick()}
const DRAFT='待下发';
function selDrafts(on){ordersCache.filter(o=>o.state==DRAFT).forEach(o=>on?sel.add(o.id):sel.delete(o.id));if(!on)sel.clear();tick()}
async function sendSel(){let ids=ordersCache.filter(o=>o.state==DRAFT&&sel.has(o.id)).sort((a,b)=>a.created-b.created).map(o=>o.id);if(!ids.length){uiAlert(t('ord.noDraftSel'));return}
 if(!await uiConfirm(t('ord.sendQ',{base:$('base').value,n:ids.length,iv:$('iv').value,ma:$('maxa').value||t('ord.unl')})))return;
 let r=await post('/api/send',{ids,base:$('base').value,interval:+$('iv').value,maxActive:+$('maxa').value,blockByBlock:$('bbb').checked,incPollSec:+$('bbb_poll').value||1});if(!r.ok)uiAlert(r.err);else ids.forEach(i=>sel.delete(i));tick()}
async function delDrafts(){let ids=ordersCache.filter(o=>o.state==DRAFT&&sel.has(o.id)).map(o=>o.id);if(!ids.length){uiAlert(t('ord.noDraftSel'));return}
 if(!await uiConfirm(t('ord.delQ',{n:ids.length})))return;await post('/api/delete_drafts',{ids});ids.forEach(i=>sel.delete(i));tick()}
let jsonOpen=new Set(),jsonCache={},ordTable=null;
async function toggleJson(id){if(jsonOpen.has(id)){jsonOpen.delete(id)}else{jsonOpen.add(id);if(!jsonCache[id]){let r=await (await fetch('/api/order?id='+encodeURIComponent(id))).json();jsonCache[id]=r.body?JSON.stringify(r.body,null,1):t('ord.none')}}tick()}
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
function stop(){post('/api/stop',{})}
async function cancel(all){let ids=ordersCache.filter(o=>o.state!=DRAFT&&sel.has(o.id)).map(o=>o.id);if(!all&&!ids.length){uiAlert(t('ord.noSentSel'));return}
 if(!await uiConfirm(all?t('ord.cancelAllQ'):t('ord.cancelQ',{n:ids.length})))return;let r=await post('/api/cancel',{all,ids});console.log(r);ids.forEach(i=>sel.delete(i))}
// ---------------- robots ----------------
let grpClosed=new Set(JSON.parse(localStorage.getItem('rdsGrpClosed')||'[]')),lastState=null;
function grpToggle(n){grpClosed.has(n)?grpClosed.delete(n):grpClosed.add(n);localStorage.setItem('rdsGrpClosed',JSON.stringify([...grpClosed]));if(lastState)renderRobots(lastState,+$('still').value)}
function grpAll(close){let names=[...document.querySelectorAll('#rt .grp')].map(e=>e.dataset.g);grpClosed=new Set(close?names:[]);localStorage.setItem('rdsGrpClosed',JSON.stringify([...grpClosed]));if(lastState)renderRobots(lastState,+$('still').value)}
function renderRobots(r,still){lastState=r;let groups=(r.groups||[]).map(g=>({name:g.name,ids:g.robots}));let byName={};r.robots.forEach(b=>byName[b.name]=b);let used=new Set();
 let secs=groups.map(g=>{let rs=g.ids.map(id=>byName[id]).filter(Boolean);rs.forEach(b=>used.add(b.name));return {name:g.name,rs,missing:g.ids.filter(id=>!byName[id])}});
 let rest=r.robots.filter(b=>!used.has(b.name)),extra={},UNG=t('rob.ungrouped');rest.forEach(b=>{let k=b.group&&!groups.length?b.group:UNG;(extra[k]=extra[k]||[]).push(b)});
 for(const[k,v]of Object.entries(extra))secs.push({name:k,rs:v,missing:[]});
 const box=$('rt');let ex=new Map([...box.children].map(d=>[d.dataset.g,d]));let want=new Set(secs.map(x=>x.name));for(const[k,d]of ex)if(!want.has(k))d.remove();let prev=null;
 for(const sec of secs){let d=ex.get(sec.name);if(!d){d=document.createElement('div');d.dataset.g=sec.name;let h=document.createElement('div');h.className='grp';h.dataset.g=sec.name;h.onclick=()=>grpToggle(sec.name);d.appendChild(h);
   mkTable(d,['rob.name','rob.xy','rob.station','rob.order','rob.ostate','rob.disp','rob.conn','rob.blocked','rob.batt','rob.idle'].map(k=>t(k)))}
  let rs=sec.rs.sort((a,b)=>a.name.localeCompare(b.name)),nOrd=rs.filter(b=>b.orderActive).length,nW=rs.filter(b=>b.orderActive&&b.idle>still).length,closed=grpClosed.has(sec.name);
  let hh=`${closed?'▶':'▼'} ${esc(sec.name)}<span class=c>${t('rob.sum',{n:rs.length,o:nOrd})}${nW?` · <b style=color:red>⚠${nW}</b>`:''}${sec.missing.length?` · <span class=dim>${t('rob.offline')}: ${esc(sec.missing.join(', '))}</span>`:''}</span>`;
  let h=d.firstChild;if(h._h!==hh){h.innerHTML=hh;h._h=hh}let tb=d.querySelector('table');tb.style.display=closed?'none':'';
  if(!closed)syncRows(tb.tBodies[0],rs.map(b=>{let stk=b.orderActive&&b.idle>still,NO=t('rob.noOrder');
   let oc=b.orderActive?esc(b.order):(b.order?`${NO} <span class=dim title="${esc(b.order)}">(${t('rob.prev')} ${esc(b.order.slice(0,14))}…)</span>`:NO),sc=b.orderActive?`<b>${b.orderState||'?'}</b>`:(b.order?`${NO} <span class=dim>(${b.orderState||''})</span>`:NO);
   return {k:b.name,cls:stk?'stuck':'',c:[esc(b.name),b.x!=null?b.x.toFixed(2)+','+b.y.toFixed(2):'',esc(b.station||''),oc,sc,String(b.dispatchable),String(b.connected),String(b.blocked),b.battery!=null?(b.battery*100).toFixed(0)+'%':'',fmt(b.idle)+(stk?' ⚠'+t('rob.deadlock'):'')]}}));
  let next=prev?prev.nextSibling:box.firstChild;if(next!==d)box.insertBefore(d,next);prev=d}}
const fmt=s=>s<60?s.toFixed(0)+'s':(s/60).toFixed(1)+'m';
const p2=n=>String(n).padStart(2,'0');
function fmtTs(v){if(!v)return '<span class=dim>-</span>';let d=new Date(v*1000),n=new Date(),hms=p2(d.getHours())+':'+p2(d.getMinutes())+':'+p2(d.getSeconds());
 return d.toDateString()==n.toDateString()?hms:(d.getFullYear()!=n.getFullYear()?d.getFullYear()+'-':'')+p2(d.getMonth()+1)+'-'+p2(d.getDate())+' '+hms}
function fmtDur(s){if(s==null||!isFinite(s))return '<span class=dim>-</span>';s=Math.max(0,Math.round(s));let h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;return h?h+':'+p2(m)+':'+p2(x):m+':'+p2(x)}
// ---------------- orders table ----------------
const OCOLK=['','col.id','col.pair','col.vs','col.veh','col.state','col.blocks','col.created','col.age','col.idle','col.started','col.ended','col.dur','col.err','col.json'];
const OSORT=[null,'id','pairS','vsTag','vehicle','state','blocks','_created','_age','_idle','started','ended','_dur','error',null];
let ordSort=(()=>{try{let v=JSON.parse(localStorage.getItem('ordSort')||'null');if(v&&OSORT[v.i])return v}catch(e){}return {i:7,d:-1}})();
function setOrdSort(i){ordSort=ordSort.i==i?{i,d:-ordSort.d}:{i,d:OSORT[i].startsWith('_')||['started','ended'].includes(OSORT[i])?-1:1};try{localStorage.setItem('ordSort',JSON.stringify(ordSort))}catch(e){}updSortInd();tick()}
function updSortInd(){if(!ordTable)return;for(const th of ordTable.tHead.rows[0].cells){let sp=th.querySelector('.sind');if(sp)sp.textContent=+th.dataset.i===ordSort.i?(ordSort.d>0?' ▲':' ▼'):''}}
function ordCmp(a,b){let k=OSORT[ordSort.i],x=a[k],y=b[k],nx=x==null||x==='',ny=y==null||y==='';
 if(nx||ny)return nx&&ny?(b._created-a._created):nx?1:-1; // empty values always last
 let r=typeof x=='number'&&typeof y=='number'?x-y:String(x).localeCompare(String(y),'zh',{numeric:true});return r*ordSort.d||(b._created-a._created)}
const FSTATES=['待下发','SENT','CREATED','TOBEDISPATCHED','RUNNING','WAITING','FAILED','FINISHED','STOPPED','CANCELED','SEND_FAIL','其它'];
const FKNOWN=new Set(FSTATES.slice(0,-1));
let ordFilt=(()=>{try{return JSON.parse(localStorage.getItem('ordFilter')||'{}')||{}}catch(e){return {}}})();
let grpCollapsed=new Set((()=>{try{return JSON.parse(localStorage.getItem('ordCollapsed')||'[]')}catch(e){return []}})());
let lastGroups=[];
function initFilt(){$('f_states').innerHTML=FSTATES.map(s=>`<label style="margin-right:4px"><input type=checkbox class=fst value="${s}">${stName(s)}</label>`).join('')+` <span class=dim style=font-size:11px>${t('f.noneAll')}</span>`;
 let f=ordFilt;document.querySelectorAll('.fst').forEach(x=>x.checked=(f.states||[]).includes(x.value));$('f_veh').value=f.veh||'';$('f_st').value=f.st||'';$('f_id').value=f.id||'';$('f_stuck').checked=!!f.stuck;$('hidedone').checked=!!f.hide;
 if(f.grp){$('f_grp').innerHTML+=`<option value="${esc(f.grp)}">${esc(f.grp)}</option>`;$('f_grp').value=f.grp}
 document.querySelectorAll('#ofilt input,#ofilt select').forEach(e=>{e.addEventListener('input',saveFilt);e.addEventListener('change',saveFilt)})}
function saveFilt(){ordFilt={states:[...document.querySelectorAll('.fst:checked')].map(x=>x.value),veh:$('f_veh').value.trim(),grp:$('f_grp').value,st:$('f_st').value.trim(),id:$('f_id').value.trim(),stuck:$('f_stuck').checked,hide:$('hidedone').checked};
 try{localStorage.setItem('ordFilter',JSON.stringify(ordFilt))}catch(e){}tick()}
function clearFilt(){document.querySelectorAll('#ofilt input[type=checkbox]').forEach(x=>x.checked=false);['f_veh','f_st','f_id'].forEach(i=>$(i).value='');$('f_grp').value='';saveFilt()}
function fillFiltGroups(names){let s=$('f_grp'),cv=s.value;names=[...new Set(names.concat(cv?[cv]:[]))];let sig=names.join('|');if(s._sig===sig)return;s._sig=sig;
 s.innerHTML=`<option value="">${t('f.all')}</option>`+names.map(n=>`<option value="${esc(n)}">${esc(n)}</option>`).join('');s.value=cv}
function saveCollapsed(){try{localStorage.setItem('ordCollapsed',JSON.stringify([...grpCollapsed]))}catch(e){}}
function toggleGrp(k){grpCollapsed.has(k)?grpCollapsed.delete(k):grpCollapsed.add(k);saveCollapsed();tick()}
function grpCollapseAll(c){for(const g of lastGroups)c?grpCollapsed.add(g.k):grpCollapsed.delete(g.k);saveCollapsed();tick()}
function selGrp(k,on){let g=lastGroups.find(x=>x.k==k);if(!g)return;g.rows.forEach(o=>on?sel.add(o.id):sel.delete(o.id));tick()}
function batchName(m,k){if(k=='drafts')return t('state.draft');if(k=='nobatch')return t('ord.nobatch');let n=m.name||k;if(/^#\d+$/.test(n))return (m.kind=='hist'?t('ord.histBatch'):t('ord.batch'))+' '+n;
 let mm=/^(历史批次|批次) (#\d+)$/.exec(n);return mm?(mm[1]=='历史批次'?t('ord.histBatch'):t('ord.batch'))+' '+mm[2]:n}
const TERM=['FINISHED','STOPPED','MANUAL_FINISHED','CANCELED','CANCELLED','WITHDRAWN','TERMINATED','SEND_FAIL','SKIPPED'];/* FAILED is NOT terminal: keeps counting and can be stuck */
async function tick(){try{let r=await (await fetch('/api/state')).json();if(r.groups&&r.groups.length)fillGroups(r.groups);robotsCache=r.robots;ordersCache=r.orders;
 $('run').textContent=(r.running?t('run.on'):t('run.off'))+' · '+t('run.sent')+' '+r.sent+' '+r.msg+(r.incPending?' · '+t('inc.pending',{n:r.incPending}):'')+' · '+t('run.log')+': '+r.log;
 let now=r.now||Date.now()/1000,T=+$('stuck').value,still=+$('still').value,term=TERM;
 let cnt={};r.orders.forEach(o=>cnt[o.state]=(cnt[o.state]||0)+1);let isAct=o=>!term.includes(o.state)&&o.state!=DRAFT,hasVeh=o=>!!o.assigned,nst=r.orders.filter(o=>isAct(o)&&hasVeh(o)&&o.idle>T).length,ndr=cnt[DRAFT]||0;
 $('sum').innerHTML=Object.entries(cnt).map(([k,v])=>esc(stName(k))+':'+v).join(' ')+(nst?` <b style=color:red>${t('ord.nStuck',{n:nst})}</b>`:'');
 let rst=r.robots.filter(b=>b.orderActive&&b.idle>still).length,nact=r.orders.filter(isAct).length;
 $('tb_rob').innerHTML=`${t('tab.rob')}(${r.robots.length}${rst?`, <span style=color:red>⚠${rst}</span>`:''})`;
 $('tb_ord').innerHTML=`${t('tab.ord')}(${ndr?`${t('state.draft')}${ndr}, `:''}${t('ord.active')}${nact}${nst?`, <span style=color:red>⚠${nst}</span>`:''})`;$('mapsum').innerHTML='| '+t('map.veh')+' '+r.robots.length+(rst?` <b style=color:red>${t('map.stillWithOrder')} ${rst}</b>`:'')+' | '+t('map.orders')+' '+$('sum').innerHTML;
 let selD=r.orders.filter(o=>o.state==DRAFT&&sel.has(o.id)).length;$('selinfo').innerHTML=t('ord.selInfo',{n:ndr,s:`<b>${selD}</b>`});
 for(const o of r.orders){let dr=o.state==DRAFT,done=term.includes(o.state),endT=done?(o.ended||o.changed||now):now;
  o._created=o.created||o.sent;o._age=dr?null:done?Math.max(0,endT-o.sent):o.age;o._idle=dr||(!done&&!hasVeh(o))?null:done?Math.max(0,endT-o.changed):o.idle;
  o._dur=o.started?(o.ended||(done?null:now))-o.started:null;o.pair=o.pair||['?','?'];o.pair=Array.isArray(o.pair)?o.pair:[String(o.pair)];o.pairS=o.pair.join(' → ')}
 let f=ordFilt,fst=new Set(f.states||[]),rgOf={};(r.groups||[]).forEach(g=>g.robots.forEach(id=>rgOf[id]=g.name));
 const ogrp=o=>o.group||(o.body&&o.body.group)||(o.vehicle&&rgOf[o.vehicle])||'';
 fillFiltGroups([...(r.groups||[]).map(g=>g.name),...r.orders.map(ogrp).filter(Boolean)]);
 const stkOf=o=>isAct(o)&&hasVeh(o)&&o.idle>T;
 const match=o=>{let st=o.state;if(fst.size&&!(fst.has(st)||(fst.has('其它')&&!FKNOWN.has(st))))return false;
  if(f.hide&&term.includes(o.state))return false;if(f.stuck&&!stkOf(o))return false;
  /* grp/veh: sent only; drafts without assigned group/vehicle stay visible */
  if(f.veh&&(o.state!=DRAFT||(o.vehicle||''))&&!(o.vehicle||'').toLowerCase().includes(f.veh.toLowerCase()))return false;if(f.grp&&(o.state!=DRAFT||ogrp(o))&&ogrp(o)!==f.grp)return false;
  if(f.st&&!o.pairS.toLowerCase().includes(f.st.toLowerCase()))return false;if(f.id&&!o.id.toLowerCase().includes(f.id.toLowerCase()))return false;return true};
 let gm=new Map();for(const o of r.orders){let k=o.state==DRAFT?'drafts':(o.batch||'nobatch');if(!gm.has(k)){let m=o.batchMeta||{};
   gm.set(k,{k,name:batchName(k=='drafts'||k=='nobatch'?{}:m,k),meta:k=='drafts'||k=='nobatch'?{}:m,all:[],rows:[]})}
  let g=gm.get(k);g.all.push(o);if(match(o))g.rows.push(o)}
 let gs=[...gm.values()].sort((a,b)=>(b.k=='drafts')-(a.k=='drafts')||((b.meta.start||Math.max(0,...b.all.map(o=>o.sent||0)))-(a.meta.start||Math.max(0,...a.all.map(o=>o.sent||0)))));
 let nMatch=gs.reduce((a,g)=>a+g.rows.length,0),fon=fst.size||f.hide||f.stuck||f.veh||f.grp||f.st||f.id;
 $('f_info').innerHTML=fon?t('f.match',{n:`<b>${nMatch}</b>`,t:r.orders.length}):'';
 gs=gs.filter(g=>g.rows.length);lastGroups=gs;
 if(!ordTable){$('ot').innerHTML='<thead><tr>'+OCOLK.map((h,i)=>{h=h?t(h):'';return OSORT[i]?`<th data-i=${i} style="cursor:pointer;user-select:none" onclick="setOrdSort(${i})">${h}<span class=sind></span></th>`:'<th>'+h+'</th>'}).join('')+'</tr></thead><tbody></tbody>';ordTable=$('ot');updSortInd()}
 let items=[];for(const g of gs){g.rows.sort(ordCmp);let col=grpCollapsed.has(g.k),m=g.meta,sc={};g.rows.forEach(o=>{let s=stName(o.state);sc[s]=(sc[s]||0)+1});
  let nst=g.rows.filter(stkOf).length,stv=g.all.map(o=>o.started).filter(Boolean),anyAct=g.all.some(o=>o.state!=DRAFT&&!term.includes(o.state)),env=g.all.map(o=>o.ended).filter(Boolean);
  let t0=stv.length?Math.min(...stv):null,t1=anyAct?now:(env.length?Math.max(...env):null),allSel=g.rows.every(o=>sel.has(o.id));
  let SC={FINISHED:'#888',FAILED:'#e67e00',RUNNING:'#06c',CANCELED:'#a0a',STOPPED:'#a0a'};SC[t('state.draft')]='#a60';
  let info=[`<b>${col?'▶':'▼'} ${esc(g.name)}</b>`,m.start?t('ord.sentAt')+' '+fmtTs(m.start):'',t('ord.nOrders',{n:`${fon?g.rows.length+'/':''}${g.all.length}`}),
   Object.entries(sc).map(([s,n])=>`<span style="color:${SC[s]||'#333'}">${esc(s)}:${n}</span>`).join(' '),nst?`<b style=color:red>${t('ord.stuckN',{n:nst})}</b>`:'',
   t0?t('ord.total')+' '+fmtDur((t1||now)-t0)+(anyAct?' ('+t('ord.inprog')+')':''):'',m.group?`<span style="background:#eef7e6;padding:0 3px;font-size:11px">${t('ord.grp')}:${esc(m.group)}</span>`:'',
   m.maxActive!=null?`<span class=dim>${t('ord.maxa')} ${m.maxActive}${m.interval!=null?' '+t('ord.ivShort')+' '+m.interval+'s':''}</span>`:'',m.kind=='hist'?`<span class=dim title="${t(m.src=='log'?'ord.histLogTip':'ord.histGapTip')}">(${t(m.src=='log'?'ord.histLog':'ord.histGap')})</span>`:''].filter(Boolean).join(' &nbsp; ');
  items.push({k:'grp:'+g.k,cls:'ghdr',st:'background:#e8eef7',c:[`<input type=checkbox title="${t('ord.selGrp')}" ${allSel?'checked':''} onclick="event.stopPropagation()" onchange="selGrp('${g.k}',this.checked)">`,{h:`<div onclick="toggleGrp('${g.k}')" style="cursor:pointer;user-select:none">${info}</div>`,span:14}]});
  if(col)continue;
  for(const o of g.rows){let dr=o.state==DRAFT,done=term.includes(o.state),stk=isAct(o)&&hasVeh(o)&&o.idle>T;
  let age=o._age,idle=o._idle,dur=o._dur;
  items.push({k:o.id,cls:stk?'stuck':done?'done':'',st:dr?'background:#fffbe6':'',c:[`<input type=checkbox ${sel.has(o.id)?'checked':''} onchange="this.checked?sel.add('${o.id}'):sel.delete('${o.id}')">`,esc(o.id)+(o.template&&o.template!='default'?` <span class=dim>[${esc(o.template)}]</span>`:''),(o.preChosen&&o.preChosen.length?`<span title="${esc(o.preChosen.map(c=>c.where+': '+c.station+' → '+c.pre+' ('+c.select+')').join('\n'))}">${esc(o.pairS)} <span class=dim>ⓟ</span></span>`:esc(o.pairS)),
   o.vsTag?`<span style="background:#e6f0ff;padding:0 3px;font-size:11px">${esc(o.vsTag)}</span>`:'<span class=dim>-</span>',esc(o.vehicle||'')+(o.group?`${o.vehicle?' ':''}<span style="background:#eef7e6;padding:0 3px;font-size:11px" title="${t('disp.groupTip')}">${t('ord.grp')}:${esc(o.group)}</span>`:''),(dr?`<b style=color:#a60>${t('state.draft')}</b>`:o.state=='FAILED'?`<b style=color:#e67e00 title="${t('ord.failedTip')}">FAILED</b>`:o.gone?`<b style=color:#a0a title="${esc(t('ord.goneTip')+' '+(o.goneMsg||''))}">${esc(o.state)} (${t('ord.gone')})</b>`:esc(o.state))+incTag(o),esc(o.blocks||''),fmtTs(o._created),dr?`<span class=dim>${t('ord.genAgo',{t:fmt(o.age)})}</span>`:fmt(age),dr?'':idle==null?{h:'<span class=dim>-</span>',title:t('ord.noVehTip')}:{h:fmt(idle),title:''},dr?'':{h:fmtTs(o.started),title:o.startedSrc=='rds'?t('ord.backfillTip'):''},dr?'':{h:fmtTs(o.ended),title:o.endedSrc=='rds'?t('ord.backfillTip'):''},dr?'':{h:fmtDur(dur),title:o.ended?'':t('ord.inprog')},esc(o.error||''),
   `<button onclick="toggleJson('${o.id}')">${jsonOpen.has(o.id)?t('ord.hide'):t('ord.view')}</button>`]});
  if(jsonOpen.has(o.id))items.push({k:'json:'+o.id,c:['',{h:`<pre class=jbox style="margin:0;max-height:300px;overflow:auto;background:#f6f6f6;font-size:11px">${esc(jsonCache[o.id]||t('msg.loading'))}</pre>`,span:14}]})}}
 syncRows(ordTable.tBodies[0],items);
 renderRobots(r,still);draw()}catch(e){console.error(e)}}
loadI18n().then(async()=>{initFilt();initSub();initSrvSide();await loadVersion();await m4Load();await initSettings();if(isM4())m4Fill()}).finally(()=>{setInterval(tick,1500);tick()});


// ---------------- dispatcher servers (per-server settings) ----------------
function srvCollapsed(){return document.body.classList.contains('srv-collapsed')}
function syncSrvToggleLabels(){let on=srvCollapsed(),edge=$('srv_edge');
 if(edge){edge.textContent=on?'»':'«';edge.setAttribute('aria-expanded',on?'false':'true');edge.title=t(on?'srv.expand':'srv.collapse')}}
function applySrvCollapsed(on){document.body.classList.toggle('srv-collapsed',!!on);
 try{localStorage.setItem('odtSrvCollapsed',on?'1':'0')}catch(e){}
 syncSrvToggleLabels();if($('tab')&&$('tab').value=='map')resizeMap()}
function toggleSrvSide(){applySrvCollapsed(!srvCollapsed())}
function initSrvSide(){let on=false;try{on=localStorage.getItem('odtSrvCollapsed')==='1'}catch(e){}applySrvCollapsed(on)}
async function refreshServers(){try{let s=await (await fetch('/api/servers')).json();if(s&&s.servers){serverList=s.servers;if(s.currentServerId)currentServerId=s.currentServerId;renderSrvList()}}catch(e){}}
function renderSrvList(){let ul=$('srv_list');if(!ul)return;
 ul.innerHTML=(serverList||[]).map(s=>{let on=s.id===currentServerId?'on':'';
  return `<li class="${on}" data-id="${esc(s.id)}" onclick="selectServer('${esc(s.id)}')"><span class=sn>${esc(s.name||s.base||s.id)}</span><span class=sb>${esc((s.adapter||'rds').toUpperCase()+' · '+(s.base||''))}</span></li>`}).join('')||`<li class=dim>${esc(t('srv.empty'))}</li>`}
function clearServerUi(){/* wipe map/stations/PC/robots so previous server leaves zero leftover */
 pools={start:[],end:[]};stations=[];setScene([]);geom=null;pcOff=null;sel.clear();jsonOpen.clear();
 robotsCache=[];ordersCache=[];lastState=null;try{const box=$('rt');if(box)box.innerHTML=''}catch(e){}
 if($('geominfo'))$('geominfo').textContent=t('map.needScene');try{if(C&&C.getContext)draw()}catch(e){}}
async function selectServer(id){if(!id||id===currentServerId)return;
 if(loaded){try{await saveCfg()}catch(e){}}
 let r=await post('/api/servers/select',{id});if(!r||!r.ok){uiAlert((r&&r.err)||t('srv.switchFail'));return}
 currentServerId=r.currentServerId||id;let st=r.settings||{};
 // reset transient UI state bound to previous server
 clearServerUi();
 applySettings(st);await loadTemplates(st&&st.activeTemplate);renderPool();renderSt();prevLater();
 if(isM4()){await m4Load();m4Fill()}else{adapterUi()}
 // reload cached scene for this server if any
 try{let g=await (await fetch('/api/scene_geom?cached=1')).json();if(g.ok&&!g.sceneErr&&g.stations&&g.stations.length){setScene(g.stations);setGeom(g);$('info').textContent=sceneAt()}else{$('info').textContent=t('msg.loaded');$('geominfo').textContent=t('map.needScene')}}catch(e){}
 renderSrvList();tick()}
async function addServer(){let name=await uiPrompt(t('srv.addName'),'');if(name==null)return;name=name.trim();
 if(!name){uiAlert(t('srv.nameRequired'));return}
 if(loaded){try{await saveCfg()}catch(e){}}
 // New server: blank URL, RDS adapter (never inherit M4), no scene; backend seeds default template.
 let r=await post('/api/servers/add',{name,adapter:'rds',activate:true});
 if(!r||!r.ok){uiAlert((r&&r.err)||'?');return}
 currentServerId=r.id;serverList=r.servers||serverList;let st=r.settings||{};
 if($('adsel')){$('adsel').value='rds';$('m4box').style.display='none'}
 clearServerUi();
 applySettings(st);await loadTemplates(st&&st.activeTemplate);renderPool();renderSt();
 adapterUi();
 $('info').textContent=t('srv.added');renderSrvList();tick()}
async function renameServer(){if(!currentServerId)return;let cur=(serverList||[]).find(s=>s.id===currentServerId);let name=await uiPrompt(t('srv.renameQ'),(cur&&cur.name)||'');
 if(name==null)return;name=name.trim();if(!name)return;
 let r=await post('/api/servers/rename',{id:currentServerId,name});if(!r||!r.ok){uiAlert((r&&r.err)||'?');return}
 serverList=r.servers||serverList;renderSrvList()}
async function delServer(){if(!currentServerId)return;if((serverList||[]).length<=1){uiAlert(t('srv.last'));return}
 let cur=(serverList||[]).find(s=>s.id===currentServerId);if(!await uiConfirm(t('srv.delQ',{name:(cur&&cur.name)||currentServerId})))return;
 let r=await post('/api/servers/delete',{id:currentServerId});if(!r||!r.ok){uiAlert((r&&r.err)||'?');return}
 currentServerId=r.currentServerId;serverList=r.servers||[];let st=r.settings||{};
 clearServerUi();
 applySettings(st);await loadTemplates(st&&st.activeTemplate);renderPool();renderSt();
 if(isM4()){await m4Load();m4Fill()}else adapterUi();
 try{let g=await (await fetch('/api/scene_geom?cached=1')).json();if(g.ok&&!g.sceneErr&&g.stations&&g.stations.length){setScene(g.stations);setGeom(g)}}catch(e){}
 renderSrvList();tick()}

// ---------------- dispatcher adapter (RDS default) / M4 connection profiles ----------------
// M4 secrets (app-key, password) are stored server-side only (settings.json, gitignored); the API returns them masked.
let M4P={active:'default',profiles:{}};
async function m4Load(){try{let r=await (await fetch('/api/m4')).json();M4P=r;$('adsel').value=r.adapter||'rds';$('m4box').style.display=r.adapter==='m4'?'':'none';m4Fill();m4OpUi()}catch(e){}}
function m4Fill(){let n=m4ActiveName();if(!(M4P.profiles||{})[n]){let ks=Object.keys(M4P.profiles||{});n=ks[0]||n;M4P.active=n}m4Show(n)}
function m4SceneLabel(s){if(!s)return '';let id=s.id!=null?String(s.id):'';let n=(s.name||'').trim();if(n&&n!==id)return n+'（'+id+'）';return id}
function m4SceneNameFromOpt(opt,id){if(!opt)return '';let t=(opt.textContent||'').trim();if(!t||t===id)return '';let i=t.indexOf('（');if(i>0&&t.endsWith('）'))return t.slice(0,i).trim();return t!==id?t:''}
function m4SetScene(id,name){let sel=$('m4scenes');if(!sel)return;id=id||'';
 let opt=[...sel.options].find(o=>o.value===id);if(id&&!opt){opt=document.createElement('option');opt.value=id;opt.textContent=id;sel.appendChild(opt)}
 if(opt){let n=(name||'').trim();if(!n)n=m4SceneNameFromOpt(opt,id);opt.textContent=m4SceneLabel({id,name:n})}
 sel.value=id}
function m4NormAuth(p){p=p||{};let a=p.auth;if(a==='appkey'||a==='login')return a;return (p.appId&&p.appKey)?'appkey':'login'}
function m4AuthUi(){let a=$('m4auth').value==='appkey'?'appkey':'login';$('m4auth').value=a;
 $('m4authKey').style.display=a==='appkey'?'':'none';$('m4authLogin').style.display=a==='login'?'':'none'}
function adapterUi(){let m=$('adsel').value==='m4';let tbl=$('steps');if(tbl)tbl.classList.toggle('no-vs',m);if(cur)renderSteps()}
function m4OpUi(){adapterUi()}
function m4Show(n){n=n||m4ActiveName();let p=(M4P.profiles||{})[n]||{};if(p.base)$('base').value=p.base;m4SetScene(p.sceneId||'', p.sceneName||'');$('m4auth').value=m4NormAuth(p);
 $('m4appid').value=p.appId||'';$('m4appkey').value=p.appKey||'';$('m4user').value=p.username||'';$('m4pass').value=p.password||'';m4AuthUi()}
function m4Form(){let a=$('m4auth').value==='appkey'?'appkey':'login';let sid=$('m4scenes').value.trim(),opt=$('m4scenes').selectedOptions[0];
 return {base:$('base').value.trim(),sceneId:sid,sceneName:m4SceneNameFromOpt(opt,sid),auth:a,appId:$('m4appid').value.trim(),appKey:$('m4appkey').value,
 username:$('m4user').value.trim(),password:$('m4pass').value}}
async function m4Save(){let r=await post('/api/m4',{name:m4ActiveName(),profile:m4Form()});if(r.ok){M4P=r;m4Fill();await refreshServers()}else $('m4msg').textContent=r.err||'?'}
async function m4Test(){$('m4msg').textContent='…';let r=await post('/api/m4_test',{name:m4ActiveName(),profile:m4Form()});
 if(!r.ok){$('m4msg').textContent=t('m4.testFail',{err:r.err||r.ping||''});return}
 let sc=r.scenes||[],cur=$('m4scenes').value||'';
 $('m4scenes').innerHTML=`<option value="">${esc(t('m4.pickScene'))}</option>`+sc.map(s=>`<option value="${esc(s.id)}">${esc(m4SceneLabel(s)+(s.disabled?' ✗':''))}</option>`).join('');
 if(cur&&sc.some(s=>s.id===cur))m4SetScene(cur, (sc.find(s=>s.id===cur)||{}).name);else if(sc.length===1)m4SetScene(sc[0].id, sc[0].name);
 let pick=$('m4scenes').value;if(pick){let s=sc.find(x=>x.id===pick);if(s)m4SetScene(pick,s.name)}
 $('m4msg').textContent=t('m4.testOk',{auth:r.auth,n:sc.length});
 // remember name so reload shows exol（id） without re-test
 try{await post('/api/m4',{name:m4ActiveName(),profile:{sceneId:pick||'',sceneName:(sc.find(x=>x.id===pick)||{}).name||''}})}catch(e){}}
async function setAdapter(a){
 // leaving RDS → keep settings.base; leaving M4 → write URL into active profile first
 if(a==='m4')await post('/api/config',{base:$('base').value.trim(),pollSec:+$('poll').value,settings:{adapter:'m4'}});
 else{await post('/api/m4',{name:m4ActiveName(),profile:{base:$('base').value.trim()}})}
 let r=await post('/api/adapter',{adapter:a});if(!r.ok){uiAlert(r.err);return}
 $('m4box').style.display=a==='m4'?'':'none';$('m4msg').textContent='';
 if(r.base)$('base').value=r.base;if(a==='m4'){await m4Load()}else m4OpUi();
 try{loadTemplates()}catch(e){}
 await refreshServers()}
