(() => {
'use strict';
let siteData=JSON.parse(document.getElementById('site-data').textContent);
const runtime=JSON.parse(document.getElementById('runtime-data').textContent);
let dirty=false,refreshing=false;
let detailSequence=0,detailState=null;
const detailCache=new Map();
let catalog = JSON.parse(document.getElementById('catalog').textContent);
let champions = catalog.champions.slice().sort((a,b) => a.name.localeCompare(b.name,'ko'));
let byId = new Map(champions.map(c => [c.id,c]));
const lanes = [{id:'top',name:'탑',path:'M4 4h16v4H8v12H4z M12 12h8v8h-8z'},{id:'jungle',name:'정글',path:'m5 3 5 7-1 5 3 6 3-6-1-5 5-7-1 10-6 8-6-8z'},{id:'mid',name:'미드',path:'M4 4h8L4 12z M20 12v8h-8z M17 3l4 4L7 21l-4-4z'},{id:'bottom',name:'바텀',path:'M4 4h8v8H4z M16 4h4v16H4v-4h12z'},{id:'support',name:'서포터',path:'m12 3 3 5h6l-5 5v5l-4 3-4-3v-5L3 8h6z'}];
const presets = {
top:'Aatrox Akali Ambessa Aurora Camille Cassiopeia Chogath Darius DrMundo Fiora Gangplank Garen Gnar Gragas Gwen Heimerdinger Illaoi Irelia Jax Jayce Kayle Kennen Kled KSante Malphite Maokai Mordekaiser Nasus Olaf Ornn Pantheon Poppy Quinn Renekton Rengar Riven Rumble Ryze Sett Shen Singed Sion Skarner Swain TahmKench Teemo Trundle Tryndamere Udyr Urgot Vayne Vladimir Volibear Warwick MonkeyKing Yasuo Yone Yorick Zaahen Zac',
jungle:'Amumu Belveth Brand Briar Diana DrMundo Ekko Elise Evelynn Fiddlesticks Gragas Graves Gwen Hecarim Ivern JarvanIV Jax Karthus Kayn Khazix Kindred LeeSin Lillia Maokai MasterYi Morgana Naafiri Nidalee Nocturne Nunu Olaf Pantheon Poppy Qiyana Rammus RekSai Rengar Rumble Sejuani Shaco Shyvana Skarner Sylas Taliyah Talon Trundle Udyr Vi Viego Volibear Warwick MonkeyKing XinZhao Zaahen Zac Zed Zyra',
mid:'Ahri Akali Akshan Anivia Annie AurelionSol Aurora Azir Brand Cassiopeia Chogath Corki Diana Ekko Fizz Galio Gragas Heimerdinger Hwei Irelia Jayce Karma Kassadin Katarina Kennen Leblanc Lissandra Locke Lux Malphite Malzahar Mel Naafiri Neeko Orianna Pantheon Qiyana Rumble Ryze Seraphine Smolder Swain Sylas Syndra Taliyah Talon Tristana TwistedFate Veigar Velkoz Vex Viktor Vladimir Xerath Yasuo Yone Zed Ziggs Zilean Zoe',
bottom:'Aphelios Ashe Caitlyn Corki Draven Ezreal Jhin Jinx Kaisa Kalista Karthus KogMaw Lucian MissFortune Nilah Samira Senna Seraphine Sivir Smolder Swain Tristana Twitch Varus Vayne Xayah Yasuo Yunara Zeri Ziggs',
support:'Alistar Ashe Bard Blitzcrank Brand Braum Fiddlesticks Galio Hwei Janna Karma Leona Lulu Lux Maokai Mel Milio Morgana Nami Nautilus Neeko Pantheon Poppy Pyke Rakan Rell Renata Senna Seraphine Shaco Shen Sona Soraka Swain TahmKench Taric Thresh Velkoz Xerath Yuumi Zac Zilean Zyra'
};
for (const lane of lanes) presets[lane.id] = presets[lane.id].split(' ').filter(id => byId.has(id));
const categories = [{id:'both',name:'모두 우위 (추천)',description:'주도권과 솔킬 모두 유리한 추천 챔피언'},{id:'pressure',name:'주도권 우위',description:'상대보다 라인 주도권을 잡기 유리'},{id:'solo',name:'솔킬 우위',description:'상대를 단독으로 처치하기 유리'}];
const categoryIds = categories.map(c => c.id);
const tierIds = ['1','2','3','4','5'];
const seed = JSON.parse(document.getElementById('board-data').textContent);
const storageKey = 'counter-note:publisher:v3:' + seed.id + ':' + siteData.revision;
let board = normalize(seed);
let storageAvailable = true;
let initialMessage = '';
try {
  const saved = runtime.publisher ? localStorage.getItem(storageKey) : null;
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      board = normalize(parsed);dirty=true;
      if(parsed.schemaVersion===1){
        initialMessage = '새 분류에 맞춰 기존 상성 기록을 초기화했습니다. 티어와 순위는 유지됩니다.';
        try {localStorage.setItem(storageKey,JSON.stringify(board));} catch {storageAvailable=false;}
      }
    } catch { initialMessage = '저장된 데이터가 손상되어 파일에 담긴 상성표를 열었습니다.'; }
  }
  const probe = storageKey + ':check';
  localStorage.setItem(probe,'1');
  localStorage.removeItem(probe);
} catch { storageAvailable = false; }
let lane = 'top';
let selected = 'Garen';
let editing = false;
let tierEditing = false;
let counterTarget = null;
let tierTarget = null;
let tierPoolSearch = '';
let tierPoolFilter = 'lane';
let rosterAll = false;
let search = '';
let poolSearch = '';
let poolFilter = 'all';
let undoStack = [];
let toastTimer;
let suppressClickUntil = 0;
const remembered = {top:'Garen',jungle:'LeeSin',mid:'Ahri',bottom:'Jinx',support:'Thresh'};
const app = document.getElementById('app');
const dialog = document.getElementById('choice-dialog');
const dialogContent = document.getElementById('choice-content');
const esc = str => String(str).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const searchIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>';
const snapshot = () => JSON.parse(JSON.stringify(board));
function normalize(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || ![1,2].includes(value.schemaVersion) || typeof value.id !== 'string' || !/^[a-zA-Z0-9_-]{1,120}$/.test(value.id) || !value.matchups || typeof value.matchups !== 'object' || Array.isArray(value.matchups)) throw new Error('지원하지 않는 데이터 형식입니다.');
  const legacy=value.schemaVersion===1;
  const validCategories=legacy?['lane','game','both']:categoryIds;
  const result = {schemaVersion:2,id:value.id,matchups:{},earlyDisadvantage:{},tiers:{},rosterSort:value.rosterSort ?? 'alpha'};
  if(!['alpha','tier'].includes(result.rosterSort))throw new Error('정렬 방식이 올바르지 않습니다.');
  const tiers=value.tiers ?? {};
  if(!tiers || typeof tiers!=='object' || Array.isArray(tiers))throw new Error('티어 정보가 올바르지 않습니다.');
  for(const [line,groups] of Object.entries(tiers)){
    if(!lanes.some(l=>l.id===line) || !groups || typeof groups!=='object' || Array.isArray(groups))throw new Error('티어의 라인 정보가 올바르지 않습니다.');
    const seen=new Set();result.tiers[line]={};
    for(const [tier,ids] of Object.entries(groups)){
      if(!tierIds.includes(tier) || !Array.isArray(ids) || ids.length>champions.length)throw new Error('티어 목록이 올바르지 않습니다.');
      result.tiers[line][tier]=ids.map(id=>{
        if(!byId.has(id)||seen.has(id))throw new Error('중복되거나 잘못된 티어 챔피언입니다.');
        seen.add(id);return id;
      });
    }
  }
  for (const [line, entries] of Object.entries(value.matchups)) {
    if (!lanes.some(l => l.id === line) || !entries || typeof entries !== 'object' || Array.isArray(entries)) throw new Error('라인 정보가 올바르지 않습니다.');
    result.matchups[line] = {};
    for (const [enemy, groups] of Object.entries(entries)) {
      if (!byId.has(enemy) || !groups || typeof groups !== 'object' || Array.isArray(groups)) throw new Error('챔피언 정보가 올바르지 않습니다.');
      const seen = new Set();
      const clean = {};
      if (Object.keys(groups).some(key => !validCategories.includes(key))) throw new Error('상성 분류가 올바르지 않습니다.');
      for (const cat of validCategories) {
        const ids = groups[cat] ?? [];
        if (!Array.isArray(ids) || ids.length > champions.length) throw new Error('상성 목록이 올바르지 않습니다.');
        clean[cat] = ids.map(id => {
          if (!byId.has(id) || id === enemy || seen.has(id)) throw new Error('중복되거나 잘못된 챔피언이 있습니다.');
          seen.add(id);
          return id;
        });
      }
      if (!legacy && seen.size) result.matchups[line][enemy] = clean;
    }
  }
  if(legacy){result.matchups={};return result;}
  const warnings=value.earlyDisadvantage ?? {};
  if(!warnings || typeof warnings!=='object' || Array.isArray(warnings))throw new Error('초반 불리 정보가 올바르지 않습니다.');
  for(const [line,entries] of Object.entries(warnings)){
    if(!lanes.some(l=>l.id===line) || !entries || typeof entries!=='object' || Array.isArray(entries))throw new Error('초반 불리 라인이 올바르지 않습니다.');
    result.earlyDisadvantage[line]={};
    for(const [enemy,ids] of Object.entries(entries)){
      if(!byId.has(enemy) || !Array.isArray(ids) || ids.length>champions.length || new Set(ids).size!==ids.length)throw new Error('초반 불리 목록이 올바르지 않습니다.');
      const registered=new Set(Object.values(result.matchups[line]?.[enemy] || {}).flat());
      if(ids.some(id=>!registered.has(id)))throw new Error('상성에 없는 초반 불리 챔피언입니다.');
      if(ids.length)result.earlyDisadvantage[line][enemy]=ids.slice();
    }
  }
  return result;
}
function getGroups(line=lane,enemy=selected) { return board.matchups[line]?.[enemy] || {both:[],pressure:[],solo:[]}; }
function isEarly(id){return (board.earlyDisadvantage[lane]?.[selected] || []).includes(id);}
function warningIcon(){return '<svg viewBox="0 0 24 22" aria-hidden="true"><path d="M10.2 2.4a2.1 2.1 0 0 1 3.6 0l9 15.6a2 2 0 0 1-1.8 3H3a2 2 0 0 1-1.8-3Z" fill="#e4474f"/><path d="M12 7v6" stroke="white" stroke-width="2.3" stroke-linecap="round"/><circle cx="12" cy="17" r="1.25" fill="white"/></svg>';}
function earlyMarker(id){return isEarly(id)?`<span class="early-warning" role="img" aria-label="초반 불리" title="${esc(byId.get(selected).name)} 상대로 초반 불리">${warningIcon()}</span>`:'';}
function earlyCheckbox(id){return `<label class="early-check"><input type="checkbox" id="early-${id}" data-early-id="${id}" aria-label="${esc(byId.get(id).name)}: ${esc(byId.get(selected).name)} 상대로 초반 불리" ${isEarly(id)?'checked':''}><span>초반 불리</span></label>`;}
function setEarly(id,checked){
  if(!editing || tierEditing || !Object.values(getGroups()).some(ids=>ids.includes(id)) || isEarly(id)===checked)return;
  commit(()=>{
    board.earlyDisadvantage[lane]??={};
    const ids=(board.earlyDisadvantage[lane][selected] || []).filter(c=>c!==id);
    if(checked)ids.push(id);
    if(ids.length)board.earlyDisadvantage[lane][selected]=ids;else delete board.earlyDisadvantage[lane][selected];
  },`${byId.get(id).name} · ${byId.get(selected).name} 상대로 초반 불리 표시를 ${checked?'켰습니다':'해제했습니다'}.`);
}
function totalFor(id,line=lane) { return Object.values(getGroups(line,id)).reduce((sum,ids) => sum + ids.length,0); }
function totalBoard() { return Object.values(board.matchups).reduce((total,records) => total + Object.values(records).filter(groups => Object.values(groups).some(ids => ids.length)).length,0); }
function tierOf(id,line=lane){return tierIds.find(tier=>(board.tiers[line]?.[tier] || []).includes(id)) || 'unranked';}
function tierName(tier){return tier==='unranked'?'미지정':tier+'티어';}
function normalText(str) { return str.toLowerCase().replace(/[\s.'’·-]/g,''); }
function initialText(str) { return Array.from(str,c => {const n=c.charCodeAt(0)-44032;return n>=0&&n<11172?'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'[Math.floor(n/588)]:c;}).join(''); }
function matches(c,term) { const q=normalText(term);return !q || normalText(c.name).includes(q) || c.id.toLowerCase().includes(q) || initialText(c.name).includes(q); }
function img(c,extra='') { return `<img src="${c.image}" alt="" draggable="false" width="48" height="48" ${extra}>`; }
function portrait(c) { return `<span class="champ-portrait">${img(c)}${earlyMarker(c.id)}</span>`; }
function championButton(c,context,assigned=false) {
  const isOpponent = context === 'opponent';
  const isTier = context === 'tier-pool' || context === 'tier-board';
  const tier=isOpponent||isTier?tierOf(c.id):'unranked';
  const rank=tier!=='unranked'?board.tiers[lane][tier].indexOf(c.id)+1:0;
  const target=isTier?tierTarget:!isOpponent?counterTarget:null;
  const member=!!target&&(isTier?tierTarget!=='unranked'&&tier===tierTarget:getGroups()[counterTarget].includes(c.id));
  const targetName=isTier?tierName(target):categories.find(cat=>cat.id===target)?.name;
  const title = isOpponent ? `${c.name} 상대 상성 보기${rank?` · ${tierName(tier)} ${rank}순위`:''}` : target?`${c.name} · ${isTier&&target==='unranked'?'티어 해제':member?targetName+'에서 제외':targetName+'에 넣기'}`:isTier?`${c.name} 티어 설정 · ${tierName(tier)}${rank?' '+rank+'순위':''}`:`${c.name} 분류하기`;
  const draggable=editing&&!isOpponent;
  const badge=isTier?(context==='tier-board'?rank+'순위':tierName(tier)):board.rosterSort==='tier'?rank+'순위':tierName(tier);
  return `<button type="button" id="champ-${context}-${c.id}" class="champ${isOpponent&&c.id===selected?' selected':''}${isOpponent&&totalFor(c.id)?' has-data':''}${assigned?' assigned':''}${member?' target-member':''}" data-action="${isOpponent?'select':isTier?'choose-tier':'choose'}" data-id="${c.id}" data-context="${context}" ${draggable?`data-drag-id="${c.id}" data-drag-kind="${isTier?'tier':'counter'}" draggable="true"`:''} ${isOpponent||context==='tier-board'?`data-tier-champion="${c.id}"`:''} aria-label="${esc(title)}" ${isOpponent?`aria-pressed="${c.id===selected}"`:target?`aria-pressed="${member}"`:''} title="${esc(title)}">${isOpponent||isTier?img(c):portrait(c)}<span class="champ-name">${esc(c.name)}</span>${rank||isTier?`<span class="tier-badge tier-${tier}">${badge}</span>`:''}</button>`;
}
function targetHint(kind){
  const target=kind==='tier'?tierTarget:counterTarget;
  const name=kind==='tier'?tierName(target):categories.find(cat=>cat.id===target)?.name;
  return `<div class="target-hint${target?' has-target':''}"><p role="status">${target?`<strong>${name} 선택됨</strong><span>${target==='unranked'?'챔피언을 클릭하면 티어가 해제됩니다.':'챔피언 클릭으로 추가 · 같은 칸의 챔피언은 다시 클릭하면 제외됩니다.'}</span>`:'티어·칸을 먼저 선택한 뒤 챔피언을 클릭하세요. 같은 칸에 있으면 제외됩니다.'}</p>${target?`<button type="button" class="quiet" data-action="clear-target" data-kind="${kind}">선택 해제</button>`:''}</div>`;
}
function selectTarget(kind,value){
  if(!editing||!runtime.publisher)return;
  if(kind==='tier'&&tierEditing&&[...tierIds,'unranked'].includes(value))tierTarget=tierTarget===value?null:value;
  else if(kind==='counter'&&!tierEditing&&categoryIds.includes(value))counterTarget=counterTarget===value?null:value;
  else return;
  render();
}
function clearTargets(){counterTarget=null;tierTarget=null;}
function searchField(id,value,label) { return `<div class="search-wrap">${searchIcon}<label class="sr-only" for="${id}">${label}</label><input type="search" id="${id}" placeholder="${label}" value="${esc(value)}" autocomplete="off" spellcheck="false"></div>`; }
function rosterItems() {
  const available = new Set([...presets[lane],...Object.keys(board.matchups[lane] || {}),...Object.values(board.tiers[lane] || {}).flat(),selected]);
  const list = champions.filter(c => (rosterAll || available.has(c.id)) && matches(c,search));
  if(!list.length)return '<p class="empty-search">검색 결과가 없습니다.<br>전체 챔피언에서도 찾아보세요.</p>';
  if(board.rosterSort==='alpha')return list.map(c => championButton(c,'opponent')).join('');
  const visible=new Set(list.map(c=>c.id));
  return [...tierIds,'unranked'].map(tier=>{
    const ids=tier==='unranked'?list.filter(c=>tierOf(c.id)==='unranked').map(c=>c.id):(board.tiers[lane]?.[tier] || []).filter(id=>visible.has(id));
    if(!ids.length)return '';
    return `<section class="tier-group tier-${tier}" aria-label="${tierName(tier)}"><div class="tier-group-heading"><h3>${tierName(tier)}</h3><span>${ids.length}명</span></div><div class="tier-grid">${ids.map(id=>championButton(byId.get(id),'opponent')).join('')}</div></section>`;
  }).join('');
}
function rosterControls(){
  return `<div class="roster-sort" aria-label="상대 챔피언 정렬"><button type="button" class="${board.rosterSort==='alpha'?'active':''}" data-action="sort" data-sort="alpha" aria-pressed="${board.rosterSort==='alpha'}">가나다순</button><button type="button" class="${board.rosterSort==='tier'?'active':''}" data-action="sort" data-sort="tier" aria-pressed="${board.rosterSort==='tier'}">티어순</button></div>${runtime.publisher?`<button type="button" class="tier-edit-open ${tierEditing?'active':'quiet'}" data-action="tier-edit" aria-pressed="${tierEditing}">${tierEditing?'티어 수정 중':'티어 수정'}</button>`:``}${board.rosterSort==='tier'?'<p class="tier-help">직접 설정한 티어 · 미지정은 가나다순</p>':''}`;
}
function tierPoolItems(){
  const available=new Set([...presets[lane],...Object.keys(board.matchups[lane]||{}),...Object.values(board.tiers[lane]||{}).flat()]);
  const list=champions.filter(c=>matches(c,tierPoolSearch)&&(tierPoolFilter==='all'||(tierPoolFilter==='unranked'?tierOf(c.id)==='unranked':available.has(c.id))));
  return list.length?list.map(c=>championButton(c,'tier-pool')).join(''):'<p class="empty-search">조건에 맞는 챔피언이 없습니다.<br>목록 범위를 전체로 바꿔보세요.</p>';
}
function tierWorkspace(){
  const line=lanes.find(l=>l.id===lane);
  return `<section class="tier-workspace" aria-labelledby="tier-workspace-title"><header class="tier-workspace-head panel"><div><span class="eyebrow">라인별 티어 편집</span><h2 id="tier-workspace-title">${line.name} 티어 수정</h2><p>티어를 선택한 뒤 챔피언을 클릭해 넣거나 빼세요. 드래그로 이동하거나 순서를 바꿀 수도 있습니다.</p></div><div class="tier-workspace-actions"><button type="button" data-action="undo" ${undoStack.length?'':'disabled'}>되돌리기</button><button type="button" class="primary" data-action="tier-close">티어 수정 완료</button></div></header><div class="tier-workspace-body"><div class="tier-board" aria-label="티어 배치">${tierIds.map(tier=>{
    const ids=board.tiers[lane]?.[tier] || [];
    return `<section class="tier-board-row tier-${tier}${tierTarget===tier?' click-target':''}" data-tier-zone="${tier}" aria-label="${tierName(tier)}"><button type="button" id="select-tier-${tier}" class="tier-board-label" data-action="select-target" data-kind="tier" data-target="${tier}" aria-label="${tierName(tier)} 선택" aria-pressed="${tierTarget===tier}"><span class="tier-label-title">${tierName(tier)}</span><span>${ids.length}명</span><span class="target-state">${tierTarget===tier?'선택됨':'선택'}</span></button><div class="tier-board-cards">${ids.length?ids.map(id=>championButton(byId.get(id),'tier-board')).join(''):'<p class="tier-board-empty">칸 선택 후 챔피언 클릭<br>또는 드래그해서 넣기</p>'}${ids.length?'<div class="tier-board-tail" title="이 티어의 마지막으로 이동" aria-label="이 티어의 마지막으로 이동">+</div>':''}</div></section>`;
  }).join('')}<button type="button" id="select-tier-unranked" class="tier-unassign${tierTarget==='unranked'?' click-target':''}" data-tier-zone="unranked" data-action="select-target" data-kind="tier" data-target="unranked" aria-pressed="${tierTarget==='unranked'}"><strong>미지정으로 이동${tierTarget==='unranked'?' · 선택됨':''}</strong><span>이 칸 선택 후 챔피언을 클릭하면 티어가 해제됩니다.</span></button></div><section class="tier-library panel" aria-labelledby="tier-library-title"><div class="tier-library-head"><div class="row-between"><h3 id="tier-library-title">챔피언 목록</h3><span class="eyebrow">클릭 또는 드래그</span></div><div class="tier-library-controls">${searchField('tier-pool-search',tierPoolSearch,'티어를 수정할 챔피언 검색')}<label class="sr-only" for="tier-pool-filter">티어 편집 챔피언 범위</label><select id="tier-pool-filter"><option value="lane" ${tierPoolFilter==='lane'?'selected':''}>${line.name} 챔피언</option><option value="all" ${tierPoolFilter==='all'?'selected':''}>전체 챔피언</option><option value="unranked" ${tierPoolFilter==='unranked'?'selected':''}>미지정만</option></select></div>${targetHint('tier')}</div><div id="tier-pool-grid" class="tier-library-grid">${tierPoolItems()}</div></section></div></section>`;
}
function poolItems() {
  const groups = getGroups();
  const assigned = new Set(Object.values(groups).flat());
  const list = champions.filter(c => c.id!==selected && matches(c,poolSearch) && (poolFilter==='all' || (poolFilter==='unassigned'?!assigned.has(c.id):presets[lane].includes(c.id))));
  return list.length ? list.map(c => championButton(c,'pool',assigned.has(c.id))).join('') : '<p class="empty-search">조건에 맞는 챔피언이 없습니다.</p>';
}
function categoryMarkup(cat) {
  const ids = getGroups()[cat.id];
  return `<section class="category panel ${cat.id}${editing&&counterTarget===cat.id?' click-target':''}" data-zone="${cat.id}" aria-labelledby="category-${cat.id}"><div class="category-head"><div class="category-title"><h3 id="category-${cat.id}">${editing?`<button type="button" id="select-counter-${cat.id}" class="category-select" data-action="select-target" data-kind="counter" data-target="${cat.id}" aria-pressed="${counterTarget===cat.id}">${cat.name}<span class="target-state">${counterTarget===cat.id?'선택됨':'선택'}</span></button>`:cat.name}</h3><span class="count">${ids.length}</span></div><p>${cat.description}</p></div><div class="drop-zone">${ids.length?ids.map(id => `<div class="counter-wrap" data-counter="${id}">${editing?championButton(byId.get(id),'counter'):`<button type="button" class="champ" data-action="details" data-id="${id}" aria-label="${esc(byId.get(id).name)} 매치업 상세">${portrait(byId.get(id))}<span class="champ-name">${esc(byId.get(id).name)}</span></button>`}${editing?`<button class="remove-counter" type="button" data-action="remove" data-id="${id}" aria-label="${esc(byId.get(id).name)} 삭제" title="삭제">×</button>${earlyCheckbox(id)}<button type="button" class="detail-small" data-action="details" data-id="${id}">통계 보기</button>`:''}</div>`).join(''):`<div class="empty-category"><span class="empty-mark" aria-hidden="true">${editing?'+':'—'}</span><span>${editing?'칸 선택 후 챔피언 클릭<br>또는 드래그해서 넣기':'아직 등록된 챔피언이 없습니다'}</span></div>`}</div></section>`;
}
function render() {
  const c = byId.get(selected);
  const line = lanes.find(l => l.id===lane);
  const previousFocus = document.activeElement;
  const focusId = previousFocus?.id;
  const focusChampion = previousFocus?.dataset.id;
  const focusContext = previousFocus?.dataset.context;
  const rosterScroll = document.getElementById('roster-grid')?.scrollTop || 0;
  const tierPoolScroll = document.getElementById('tier-pool-grid')?.scrollTop || 0;
  const poolScroll = document.getElementById('pool-grid')?.scrollTop || 0;
  app.innerHTML = `<div class="shell${editing?' editable':''}"><header class="topbar"><div class="brand"><div class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></div><div><h1>상성노트</h1><p>LEAGUE OF LEGENDS</p></div></div>${toolbarMarkup()}</header>
  <div class="intro-row"><div><h2 class="intro-title">라인별 챔피언 상성표</h2><p>라인과 상대를 고르고, 챔피언별 주도권·솔로킬·빌드를 비교하세요.</p></div>${metadataMarkup()}</div>
  <nav class="lanes" aria-label="라인 선택">${lanes.map(l=>`<button type="button" class="lane-tab${lane===l.id?' active':''}" data-action="lane" data-lane="${l.id}" aria-pressed="${lane===l.id}"><svg class="lane-symbol" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="${l.path}"/></svg>${l.name}</button>`).join('')}</nav>
  ${editing?`<div class="edit-banner">${tierEditing?'티어':'상성'} 수정 중 · 칸 선택 후 챔피언 클릭으로 추가·제외할 수 있습니다. 드래그도 사용할 수 있습니다.</div>`:''}
  <main class="workspace"><aside class="roster panel" aria-label="상대 챔피언 선택"><div class="roster-head"><div class="row-between"><h2>상대 챔피언</h2><span class="eyebrow">${line.name}</span></div><div class="roster-controls">${searchField('opponent-search',search,'챔피언 검색 · 초성 가능')}<div class="roster-filter" aria-label="챔피언 목록 범위"><button type="button" class="${!rosterAll?'active':''}" data-action="roster-filter" data-value="lane" aria-pressed="${!rosterAll}">${line.name} 목록</button><button type="button" class="${rosterAll?'active':''}" data-action="roster-filter" data-value="all" aria-pressed="${rosterAll}">전체</button></div></div>${rosterControls()}</div><div id="roster-grid" class="roster-grid${board.rosterSort==='tier'?' tier-view':''}">${rosterItems()}</div><p class="roster-foot">표시점은 상성이 등록된 챔피언<br>다른 라인 픽은 ‘전체’에서 선택할 수 있습니다.</p></aside>
  <div class="main-panel">${tierEditing?tierWorkspace():`<section class="opponent panel" aria-labelledby="opponent-title">${img(c)}<div class="opponent-copy"><span class="eyebrow">${line.name} · 상대 챔피언</span><h2 id="opponent-title">${esc(c.name)}</h2><p class="subtitle">${esc(c.title)}</p></div><span class="opponent-badge">상성 ${totalFor(selected)}명</span></section><div class="board-heading"><h3>${esc(c.name)} 상대로 좋은 챔피언</h3>${editing?`<button type="button" class="quiet undo-button" data-action="undo" ${undoStack.length?'':'disabled'}>되돌리기</button>`:'<span class="view-label">통계 · 배포자 설정</span>'}</div><div class="categories">${categories.map(categoryMarkup).join('')}</div><p class="early-legend">${warningIcon()}<span>초반 불리 · ${esc(c.name)} 상대로 초반에는 불리한 챔피언${editing?'은 아이콘 아래에서 체크하세요.':'입니다.'}</span></p>
  ${statsPanel()}${editing?targetHint('counter'):'<div class="mode-note"><span>수집 표본을 기준으로 분류합니다. 챔피언을 누르면 지표와 빌드 통계를 볼 수 있습니다.</span></div>'}
  ${editing?`<section class="pool panel" aria-labelledby="pool-title"><div class="pool-head"><div class="row-between"><h3 id="pool-title">유리한 챔피언 추가</h3><span class="eyebrow">드래그 또는 선택</span></div><p>상대 챔피언을 제외한 모든 챔피언을 고를 수 있습니다.</p><div class="pool-tools">${searchField('pool-search',poolSearch,'추가할 챔피언 검색')}<label class="sr-only" for="pool-filter">추가 챔피언 범위</label><select id="pool-filter"><option value="all" ${poolFilter==='all'?'selected':''}>전체 챔피언</option><option value="lane" ${poolFilter==='lane'?'selected':''}>${line.name} 목록</option><option value="unassigned" ${poolFilter==='unassigned'?'selected':''}>미등록만</option></select></div></div><div class="pool-grid" id="pool-grid">${poolItems()}</div></section>`:''}`}
  </div></main>${storageAvailable||!runtime.publisher?'':'<div class="storage-warning" role="status">브라우저 저장 공간을 사용할 수 없습니다. 창을 닫기 전에 ‘데이터 백업’을 눌러 수정 내용을 보관하세요.</div>'}
  <footer class="footer"><div><p>분류된 상대 ${totalBoard()}명 · 챔피언 ${champions.length}명 · 이름·아이콘: <a href="https://developer.riotgames.com/docs/lol#data-dragon" target="_blank" rel="noopener noreferrer">Riot Data Dragon</a></p><p>통계는 수집한 경기 표본입니다. 배포자의 변경은 이 주소에서 자동으로 확인됩니다.</p><p class="legal">상성노트 is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.</p></div>${runtime.publisher?'<div class="footer-actions"><button type="button" data-action="backup">데이터 백업</button><button type="button" data-action="import">기존 상성 불러오기</button></div>':''}</footer></div>`;
  const focusElement=focusId?document.getElementById(focusId):null;
  if(focusElement)focusElement.focus({preventScroll:true});
  else if(focusChampion){
    const pool=focusContext?.startsWith('tier')?'tier-pool':'pool';
    (document.getElementById(`champ-${pool}-${focusChampion}`)||document.getElementById(pool==='tier-pool'?'tier-pool-search':'pool-search'))?.focus({preventScroll:true});
  }
  document.getElementById('roster-grid').scrollTop = rosterScroll;
  if(tierEditing)document.getElementById('tier-pool-grid').scrollTop=tierPoolScroll;
  if(document.getElementById('pool-grid'))document.getElementById('pool-grid').scrollTop=poolScroll;
}
function toast(message) {
  const el=document.getElementById('toast');
  clearTimeout(toastTimer);
  el.textContent=message;
  el.classList.add('show');
  toastTimer=setTimeout(()=>el.classList.remove('show'),4200);
}
function save() {
  if(!runtime.publisher)return;
  dirty=true;
  try {localStorage.setItem(storageKey,JSON.stringify(board));storageAvailable=true;} catch {storageAvailable=false;}
}
function commit(operation,message) {
  undoStack.push({board:snapshot(),lane,selected});
  if(undoStack.length>50)undoStack.shift();
  operation();
  save();
  const oldScroll = document.getElementById('pool-grid')?.scrollTop || 0;
  const rosterScroll = document.getElementById('roster-grid')?.scrollTop || 0;
  render();
  if(document.getElementById('pool-grid'))document.getElementById('pool-grid').scrollTop=oldScroll;
  document.getElementById('roster-grid').scrollTop=rosterScroll;
  toast(message);
}
function assign(id,cat,beforeId=null) {
  if(!editing || !byId.has(id) || id===selected || !categoryIds.includes(cat)) return false;
  const groups=getGroups();
  const next=Object.fromEntries(categoryIds.map(key=>[key,groups[key].filter(champ=>champ!==id)]));
  const index=beforeId?next[cat].indexOf(beforeId):-1;
  if(index>=0)next[cat].splice(index,0,id);else next[cat].push(id);
  if(JSON.stringify(groups)===JSON.stringify(next))return true;
  commit(()=>{board.matchups[lane]??={};board.matchups[lane][selected]=next;},`${byId.get(id).name} · ${categories.find(c=>c.id===cat).name}에 등록했습니다.`);
  return true;
}
function remove(id) {
  if(!editing || !Object.values(getGroups()).some(ids=>ids.includes(id)))return;
  commit(()=>{const groups=getGroups();for(const key of categoryIds)groups[key]=groups[key].filter(c=>c!==id);if(!Object.values(groups).some(ids=>ids.length))delete board.matchups[lane][selected];const warnings=board.earlyDisadvantage[lane]?.[selected];if(warnings){board.earlyDisadvantage[lane][selected]=warnings.filter(c=>c!==id);if(!board.earlyDisadvantage[lane][selected].length)delete board.earlyDisadvantage[lane][selected];}},`${byId.get(id).name} 상성을 삭제했습니다.`);
}
function undo() {
  if(!editing || !undoStack.length)return;
  const previous=undoStack.pop();if(lane!==previous.lane||selected!==previous.selected)clearTargets();board=previous.board;lane=previous.lane;selected=previous.selected;remembered[lane]=selected;save();render();toast('마지막 변경을 되돌렸습니다.');
}
function setTier(id,tier,beforeId=null,position=null){
  if(!editing||!byId.has(id)||![...tierIds,'unranked'].includes(tier))return;
  const current=board.tiers[lane] || {};
  const next=Object.fromEntries(tierIds.map(key=>[key,(current[key] || []).filter(c=>c!==id)]));
  if(tier!=='unranked'){
    let index=beforeId?next[tier].indexOf(beforeId):next[tier].length;
    if(position!==null)index=Math.max(0,Math.min(next[tier].length,position-1));
    if(index<0)index=next[tier].length;
    next[tier].splice(index,0,id);
  }
  if(tierIds.every(key=>JSON.stringify(current[key]||[])===JSON.stringify(next[key])))return;
  commit(()=>{board.tiers[lane]=next;},`${lanes.find(l=>l.id===lane).name} · ${byId.get(id).name}의 ${tierName(tier)} 배치를 저장했습니다.`);
}
function chooseTier(id=selected){
  if(!editing||!tierEditing||!byId.has(id))return;
  const tier=tierOf(id);
  if(tierTarget){setTier(id,tierTarget==='unranked'||tier===tierTarget?'unranked':tierTarget);return;}
  const ids=board.tiers[lane]?.[tier] || [];
  dialogContent.innerHTML=`${img(byId.get(id),'class="dialog-champion"')}<h2 id="choice-title">${esc(byId.get(id).name)} 티어 설정</h2><p class="dialog-description">${lanes.find(l=>l.id===lane).name}에서의 티어를 선택하세요. 새 티어의 마지막에 배치됩니다.</p><div class="dialog-options">${[...tierIds,'unranked'].map(key=>`<button type="button" class="${key===tier?'active ':''}tier-${key}" data-dialog-action="tier" data-tier="${key}" data-id="${id}" aria-pressed="${key===tier}">${tierName(key)}${key===tier?' · 현재':''}</button>`).join('')}</div>${tier!=='unranked'?`<div class="tier-position"><label for="tier-position">같은 티어 내 순위</label><div><input id="tier-position" type="number" min="1" max="${ids.length}" step="1" value="${ids.indexOf(id)+1}" required><span>/ ${ids.length}</span><button type="button" data-dialog-action="rank" data-tier="${tier}" data-id="${id}">순위 적용</button></div></div>`:''}`;
  dialog.showModal();
}
function choose(id) {
  if(!editing || tierEditing || !byId.has(id) || id===selected)return;
  if(counterTarget){if(getGroups()[counterTarget].includes(id))remove(id);else assign(id,counterTarget);return;}
  const c=byId.get(id);
  const exists=Object.values(getGroups()).some(ids=>ids.includes(id));
  dialogContent.innerHTML=`${img(c,'class="dialog-champion"')}<h2 id="choice-title">${esc(c.name)} 분류하기</h2><p class="dialog-description">${esc(byId.get(selected).name)} 상대로 어떤 우위가 있나요?</p><div class="dialog-options">${categories.map(cat=>`<button type="button" class="${cat.id}" data-dialog-action="assign" data-id="${id}" data-category="${cat.id}">${cat.name}</button>`).join('')}${exists?`<button type="button" class="danger" data-dialog-action="remove" data-id="${id}">상성에서 삭제</button>`:''}</div>`;
  dialog.showModal();
}
function download(content,type,filename) {
  const url=URL.createObjectURL(new Blob([content],{type}));
  const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
}
function askImport(candidate,legacy=false) {
  dialogContent.innerHTML='<h2 id="choice-title">상성표를 불러올까요?</h2><p class="dialog-description">현재 상성표를 선택한 파일의 내용으로 바꿉니다. 불러온 후 수정 모드의 되돌리기로 복구할 수 있습니다.</p><div class="dialog-actions"><button type="button" data-dialog-action="cancel">취소</button><button type="button" class="primary" id="confirm-import">불러오기</button></div>';
  if(legacy)dialogContent.querySelector('.dialog-description').textContent='이전 분류의 백업입니다. 기존 상성 기록은 초기화하고, 백업에 담긴 티어와 순위만 불러옵니다. 현재 기록은 되돌리기로 복구할 수 있습니다.';
  document.getElementById('confirm-import').addEventListener('click',()=>{dialog.close();clearTargets();commit(()=>{board={...candidate,id:seed.id};},'상성표를 불러왔습니다.');},{once:true});
  dialog.showModal();
}
app.addEventListener('click',event=>{
  if(Date.now()<suppressClickUntil || event.target.closest('.early-check'))return;
  const button=event.target.closest('[data-action]');
  if(!button){
    const zone=findDropZone(event.target,tierEditing?'tier':'counter');
    if(zone)selectTarget(tierEditing?'tier':'counter',tierEditing?zone.dataset.tierZone:zone.dataset.zone);
    return;
  }
  if(button.disabled)return;
  const action=button.dataset.action;
  if(['edit','tier-edit','import','remove','undo','choose','choose-tier','select-target'].includes(action)&&!runtime.publisher)return;
  if(action==='details')showDetails(button.dataset.id);
  if(action==='show-matchup')showDetails(document.getElementById('detail-champion').value);
  if(action==='refresh-data')refreshData();
  if(action==='save-publisher')savePublisher();
  if(action==='select') {if(selected!==button.dataset.id)counterTarget=null;selected=button.dataset.id;remembered[lane]=selected;render();}
  if(action==='lane') {clearTargets();lane=button.dataset.lane;selected=remembered[lane];search='';poolSearch='';tierPoolSearch='';render();}
  if(action==='edit') {clearTargets();editing=!editing;if(!editing)tierEditing=false;render();}
  if(action==='select-target')selectTarget(button.dataset.kind,button.dataset.target);
  if(action==='clear-target') {if(button.dataset.kind==='tier')tierTarget=null;else counterTarget=null;render();}
  if(action==='roster-filter') {rosterAll=button.dataset.value==='all';render();}
  if(action==='sort') {board.rosterSort=button.dataset.sort;save();render();document.getElementById('roster-grid').scrollTop=0;}
  if(action==='tier-edit') {if(!tierEditing)clearTargets();editing=true;tierEditing=true;board.rosterSort='tier';save();render();if(innerWidth<=760)document.querySelector('.tier-workspace').scrollIntoView({block:'start'});}
  if(action==='tier-close') {clearTargets();tierEditing=false;editing=false;render();}
  if(action==='choose-tier')chooseTier(button.dataset.id);
  if(action==='choose')choose(button.dataset.id);
  if(action==='remove')remove(button.dataset.id);
  if(action==='undo')undo();
  if(action==='share')copyPageLink();
  if(action==='backup') {download(JSON.stringify(snapshot(),null,2),'application/json','상성노트-백업.json');toast('상성 데이터 백업 파일을 저장했습니다.');}
  if(action==='import')document.getElementById('import-file').click();
});
app.addEventListener('input',event=>{
  if(event.target.id==='opponent-search'){search=event.target.value;document.getElementById('roster-grid').innerHTML=rosterItems();}
  if(event.target.id==='pool-search'){poolSearch=event.target.value;document.getElementById('pool-grid').innerHTML=poolItems();}
  if(event.target.id==='tier-pool-search'){tierPoolSearch=event.target.value;document.getElementById('tier-pool-grid').innerHTML=tierPoolItems();}
});
app.addEventListener('change',event=>{
  if(event.target.matches('[data-early-id]'))setEarly(event.target.dataset.earlyId,event.target.checked);
  if(event.target.id==='pool-filter'){poolFilter=event.target.value;document.getElementById('pool-grid').innerHTML=poolItems();}
  if(event.target.id==='tier-pool-filter'){tierPoolFilter=event.target.value;document.getElementById('tier-pool-grid').innerHTML=tierPoolItems();}
});
dialog.addEventListener('click',event=>{
  const button=event.target.closest('[data-dialog-action]');
  if(!button)return;
  if(button.dataset.dialogAction==='rank'){
    const input=document.getElementById('tier-position');
    if(!input.reportValidity())return;
    dialog.close();setTier(button.dataset.id,button.dataset.tier,null,input.valueAsNumber);return;
  }
  dialog.close();
  if(button.dataset.dialogAction==='assign')assign(button.dataset.id,button.dataset.category);
  if(button.dataset.dialogAction==='remove')remove(button.dataset.id);
  if(button.dataset.dialogAction==='tier'&&tierOf(button.dataset.id)!==button.dataset.tier)setTier(button.dataset.id,button.dataset.tier);
});
document.getElementById('import-file').addEventListener('change',async event=>{
  const file=event.target.files?.[0];event.target.value='';if(!file)return;
  if(file.size>5*1024*1024){toast('5MB 이하의 상성노트 JSON 백업 파일을 선택해 주세요.');return;}
  try {const parsed=JSON.parse(await file.text());askImport(normalize(parsed),parsed.schemaVersion===1);} catch {toast('불러올 수 없는 파일입니다. 올바른 상성노트 JSON 백업을 선택해 주세요.');}
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'){suppressClickUntil=0;clearTouch();if(!dialog.open&&(counterTarget||tierTarget)){clearTargets();render();}}
  if(editing && (event.ctrlKey||event.metaKey) && event.key.toLowerCase()==='z' && !event.shiftKey && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName) && !dialog.open){event.preventDefault();undo();}
});
let dragId=null;
let dragKind='counter';
let dragScrollFrame=0;
let dragPoint=null;
function findDropZone(target,kind){return target?.closest(kind==='tier'?'[data-tier-zone]':'[data-zone]');}
function clearDrop(){document.querySelectorAll('.drop-active').forEach(el=>el.classList.remove('drop-active'));}
function dropAt(id,zone,target,kind='counter') {
  if(!zone || !editing)return;
  if(kind==='tier'){
    const before=target?.closest('[data-tier-champion]')?.dataset.tierChampion;
    if(before===id)return;
    setTier(id,zone.dataset.tierZone,before||null);return;
  }
  const counter=target?.closest('[data-counter]');
  if(counter?.dataset.counter===id)return;
  assign(id,zone.dataset.zone,counter?.dataset.counter||null);
}
app.addEventListener('dragstart',event=>{
  const source=event.target.closest('[data-drag-id]');
  if(!editing||!source){event.preventDefault();return;}
  dragId=source.dataset.dragId;
  dragKind=source.dataset.dragKind || 'counter';
  event.dataTransfer.setData('text/plain',dragId);
  event.dataTransfer.effectAllowed='move';
});
app.addEventListener('dragover',event=>{
  const zone=findDropZone(event.target,dragKind);
  clearDrop();
  if(editing&&dragId&&zone){event.preventDefault();event.dataTransfer.dropEffect='move';zone.classList.add('drop-active');}
  dragPoint={x:event.clientX,y:event.clientY};
  if(dragId&&dragKind==='tier'&&!dragScrollFrame)dragScrollFrame=requestAnimationFrame(scrollDrag);
});
function scrollRosterAt(x,y){
  const grid=document.getElementById('tier-pool-grid');
  if(!grid)return;
  const box=grid.getBoundingClientRect();
  if(x<box.left||x>box.right||y<box.top||y>box.bottom)return;
  if(y<box.top+35)grid.scrollBy(0,-9);else if(y>box.bottom-35)grid.scrollBy(0,9);
}
function scrollDrag(){
  dragScrollFrame=0;
  if(!dragId||dragKind!=='tier'||!dragPoint)return;
  scrollRosterAt(dragPoint.x,dragPoint.y);
  dragScrollFrame=requestAnimationFrame(scrollDrag);
}
function endDrag(){dragId=null;dragPoint=null;cancelAnimationFrame(dragScrollFrame);dragScrollFrame=0;clearDrop();}
app.addEventListener('dragleave',event=>{const zone=findDropZone(event.target,dragKind);if(zone&&!zone.contains(event.relatedTarget))zone.classList.remove('drop-active');});
app.addEventListener('drop',event=>{
  event.preventDefault();const zone=findDropZone(event.target,dragKind);
  if(dragId&&zone)dropAt(dragId,zone,event.target,dragKind);
  endDrag();
});
app.addEventListener('dragend',endDrag);
let touch=null;
function clearTouch(){if(!touch)return;clearTimeout(touch.timer);cancelAnimationFrame(touch.frame);touch.ghost?.remove();touch=null;clearDrop();document.body.classList.remove('dragging-page');}
function moveGhost(){
  if(!touch?.active)return;
  const t=touch;t.ghost.style.left=t.x+'px';t.ghost.style.top=t.y+'px';
  clearDrop();findDropZone(document.elementFromPoint(t.x,t.y),t.kind)?.classList.add('drop-active');
  if(t.kind==='tier')scrollRosterAt(t.x,t.y);
  if(t.y<100)window.scrollBy(0,-12);else if(t.y>innerHeight-100)window.scrollBy(0,12);
  t.frame=requestAnimationFrame(moveGhost);
}
app.addEventListener('pointerdown',event=>{
  if(event.pointerType==='mouse'||!editing||event.button!==0)return;
  const source=event.target.closest('[data-drag-id]');if(!source)return;
  clearTouch();touch={id:source.dataset.dragId,kind:source.dataset.dragKind || 'counter',pointer:event.pointerId,x:event.clientX,y:event.clientY,startX:event.clientX,startY:event.clientY,active:false};
  touch.timer=setTimeout(()=>{
    if(!touch)return;touch.active=true;touch.ghost=document.createElement('img');touch.ghost.src=byId.get(touch.id).image;touch.ghost.alt='';touch.ghost.className='drag-ghost';document.body.append(touch.ghost);document.body.classList.add('dragging-page');suppressClickUntil=Date.now()+60000;moveGhost();
  },240);
});
document.addEventListener('pointermove',event=>{
  if(!touch||event.pointerId!==touch.pointer)return;
  if(!touch.active){if(Math.hypot(event.clientX-touch.startX,event.clientY-touch.startY)>10)clearTouch();return;}
  if(event.cancelable)event.preventDefault();touch.x=event.clientX;touch.y=event.clientY;
},{passive:false});
document.addEventListener('touchmove',event=>{if(touch?.active&&event.cancelable)event.preventDefault();},{passive:false});
document.addEventListener('pointerup',event=>{
  if(!touch||event.pointerId!==touch.pointer)return;
  if(touch.active){const target=document.elementFromPoint(event.clientX,event.clientY);dropAt(touch.id,findDropZone(target,touch.kind),target,touch.kind);suppressClickUntil=Date.now()+400;}
  clearTouch();
});
document.addEventListener('pointercancel',()=>{if(!touch)return;suppressClickUntil=touch.active?Date.now()+300:0;clearTouch();});
window.addEventListener('blur',()=>{suppressClickUntil=0;clearTouch();endDrag();});
function toolbarMarkup(){
  return `<div class="toolbar">${runtime.publisher?`<span class="publisher-badge">배포자 관리</span><button type="button" data-action="edit" class="${editing?'active':'quiet'}" aria-pressed="${editing}" ${refreshing?'disabled':''}>${editing?'수정 완료':'수정 모드'}</button><button type="button" class="primary" data-action="save-publisher" ${refreshing?'disabled':''}>수정 사항 저장</button>`:''}<button type="button" data-action="refresh-data" ${refreshing||runtime.publisher&&editing?'disabled':''}>${refreshing?'갱신 중…':runtime.publisher?'Riot 데이터 갱신':'새 통계 확인'}</button><button type="button" class="quiet" data-action="share">링크 복사</button><span id="job-status" role="status"></span></div>`;
}
function dateText(value){if(!value)return '아직 수집 전';const d=new Date(value);return Number.isNaN(d.getTime())?'날짜 확인 불가':new Intl.DateTimeFormat('ko-KR',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Seoul'}).format(d)+' KST';}
function metadataMarkup(){const m=siteData.metadata;return `<div class="data-meta"><strong>패치 ${esc(m.patch)} <span>· ${esc(m.platform.toUpperCase())} ${m.queue===420?'솔로/듀오':'자유 랭크'}</span></strong><span>통계 갱신 ${dateText(m.updatedAt)}</span><span>배포 ${dateText(m.publishedAt)}</span><small>최근 ${m.windowDays}일 · ${m.games.toLocaleString('ko-KR')}경기 표본${m.updatedAt&&Date.now()-Date.parse(m.updatedAt)>72*3600000?' · 갱신 지연':''}</small></div>`;}
function statsPanel(){
  const records=siteData.matchupIndex[lane]?.[selected]||{};
  const available=champions.filter(c=>c.id!==selected).sort((a,b)=>(records[b.id]?.games||0)-(records[a.id]?.games||0)||a.name.localeCompare(b.name,'ko'));
  const examples=available.filter(c=>records[c.id]).slice(0,8);
  return `<section class="analysis-panel panel"><div class="row-between"><h3>매치업 상세 · 내 챔피언</h3><span class="eyebrow">표본 ${Object.values(records).reduce((n,r)=>n+r.games,0).toLocaleString('ko-KR')}경기</span></div><p>${esc(byId.get(selected).name)} 상대로 플레이한 같은 라인의 통계입니다. 분류되지 않은 매치업도 확인할 수 있습니다.</p><div class="detail-picker"><label class="sr-only" for="detail-champion">내 챔피언 선택</label><select id="detail-champion">${available.map(c=>`<option value="${c.id}">${esc(c.name)}${records[c.id]?' · '+records[c.id].games+'경기':''}</option>`).join('')}</select><button type="button" data-action="show-matchup">상세 보기</button></div>${examples.length?`<div class="matchup-shortcuts">${examples.map(c=>`<button type="button" data-action="details" data-id="${c.id}">${img(c)}<span>${esc(c.name)}<small>${records[c.id].games}경기</small></span></button>`).join('')}</div>`:`<div class="stats-empty">${siteData.metadata.games?'이 상대와 라인의 수집 표본이 아직 없습니다.':'아직 수집된 경기 데이터가 없습니다. 배포자가 Riot API 키를 설정하고 갱신하면 실제 통계가 표시됩니다.'}</div>`}<p class="sample-note">${esc(siteData.metadata.coverage)} · 자동 분류는 ${siteData.metadata.minGames}경기 이상${siteData.metadata.manualPairs?' · 배포자 수정 '+siteData.metadata.manualPairs+'개 매치업':''}</p></section>`;
}
const statsDialog=document.getElementById('stats-dialog');
const statsContent=document.getElementById('stats-content');
document.getElementById('stats-close').addEventListener('click',()=>statsDialog.close());
statsDialog.addEventListener('close',()=>{detailSequence++;detailState=null;});
statsDialog.addEventListener('click',e=>{const b=e.target.closest('[data-build-stage]');if(b&&detailState){detailState.stage=b.dataset.buildStage;renderDetails();}});
function percent(value){return value===null||value===undefined?'—':(value*100).toFixed(1)+'%';}
function pText(value){return value===null||value===undefined?'표본 부족':value<0.0001?value.toExponential(2):value.toFixed(4);}
function intervalText(value){return value?percent(value[0])+'–'+percent(value[1]):'—';}
async function getJSON(url){const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(20000)});if(!response.ok)throw new Error('데이터를 불러오지 못했습니다. 잠시 후 다시 시도하세요.');return response.json();}
async function showDetails(id){
  if(!byId.has(id)||id===selected)return;
  const request=++detailSequence;
  detailState={id,enemy:selected,line:lane,stage:'start',data:null,loading:true,error:''};renderDetails();if(!statsDialog.open)statsDialog.showModal();
  try{
    if(siteData.matchupIndex[lane]?.[selected]?.[id]){
      if(location.protocol==='file:')throw new Error('상세 통계는 Python으로 실행하거나 배포 주소에서 열어주세요.');
      const key=siteData.revision+':'+lane+':'+selected;
      if(!detailCache.has(key))detailCache.set(key,await getJSON(`${siteData.detailRoot}/${lane}-${selected}.json`));
      if(request!==detailSequence)return;
      detailState.data=detailCache.get(key)[id]||null;
    }
  }catch(error){if(request!==detailSequence)return;detailState.error=error.message;}
  if(request!==detailSequence)return;detailState.loading=false;renderDetails();
}
function renderDetails(){
  if(!detailState)return;
  const state=detailState,own=byId.get(state.id),enemy=byId.get(state.enemy),data=state.data;
  const stages=[['start','시작 아이템'],['1','1코어'],['2','2코어'],['3','3코어'],['4','4코어'],['5','5코어']];
  const header=`<header class="stats-head"><span class="eyebrow">${lanes.find(l=>l.id===state.line).name} · 패치 ${esc(siteData.metadata.patch)}</span><h2 id="stats-title">${esc(enemy.name)} <small>상대</small> vs ${esc(own.name)} <small>나</small></h2><div class="stats-versus">${img(enemy)}<span>VS</span>${img(own)}</div></header>`;
  if(state.loading||state.error||!data){statsContent.innerHTML=header+`<p class="stats-empty" role="status">${state.loading?'매치업 통계를 불러오는 중…':state.error?esc(state.error):'이 매치업의 경기 표본이 아직 없습니다. 수집 후 자동으로 표시됩니다.'}</p>`;return;}
  const stage=data.builds[state.stage];
  statsContent.innerHTML=header+`<div class="stats-summary"><span><strong>${data.games.toLocaleString('ko-KR')}</strong> 경기</span><span>승률 <strong>${percent(data.winRate)}</strong></span><span>승률 95% 구간 ${intervalText(data.ci)}</span>${!data.sufficient?'<span class="sample-low">표본 부족 · 자동 분류 보류</span>':''}</div><div class="metrics-grid">${['2','3','6'].map(level=>{const metric=data.levels[level];return `<section class="metric-card"><h3>선 ${level}레벨</h3><strong>${percent(metric.rate)}</strong><span>${esc(own.name)} / 상대 ${percent(metric.opponentRate)}</span><small>유효 ${metric.observed} · 동시 ${metric.ties} · 판단 불가 ${metric.unknown}</small></section>`;}).join('')}<section class="metric-card"><h3>15분 전 솔로킬</h3><strong>${data.solo.perGame.toFixed(2)} <small>회/경기</small></strong><span>상대 ${data.solo.opponentPerGame.toFixed(2)}회/경기</span><small>맞상대 대상 · 무어시스트 · 총 ${data.solo.kills}회</small></section></div><p class="method-note">선레벨 비율은 순서를 판별한 경기 기준이며 동시 도달도 분모에 포함합니다. LEVEL_UP 시각을 우선 사용하고, 시각이 없으면 겹치지 않는 레벨 관측 구간만 비교합니다.</p><h3 class="build-heading">${esc(own.name)}의 아이템 빌드 <span>단계별 선택 수 상위 10개</span></h3><div class="build-tabs" role="group" aria-label="빌드 단계">${stages.map(([id,name])=>`<button type="button" data-build-stage="${id}" class="${state.stage===id?'active':''}" aria-pressed="${state.stage===id}">${name}</button>`).join('')}</div><p class="build-context">${state.stage==='start'?'90초 직전 보유 아이템 조합':'신발·소모품을 제외한 완성 아이템 '+state.stage+'개까지의 구매 순서'} · 해당 단계 도달 ${stage.eligibleGames}경기 · ${stage.candidateCount}개 조합</p>${stage.rows.length?`<div class="build-table-scroll"><table class="build-table"><thead><tr><th>순위</th><th>아이템 빌드</th><th>경기 / 선택률</th><th>승률 / 95% 구간</th><th>p-value</th><th>FDR 보정 q</th></tr></thead><tbody>${stage.rows.map((row,i)=>`<tr class="${row.significant?'significant':''}"><td>${i+1}</td><td><div class="item-build">${row.items.map(itemId=>{const item=siteData.items[itemId];return `<span class="item-chip">${item?`<img src="${esc(item.image)}" alt="" width="34" height="34" loading="lazy">`:''}<span>${esc(item?.name||'아이템 '+itemId)}</span></span>`;}).join('<span class="item-arrow" aria-hidden="true">›</span>')}</div>${row.significant?'<span class="fdr-badge">FDR 유의 · 다른 빌드보다 높은 승률</span>':''}</td><td>${row.games}<small>${percent(row.pickRate)}</small></td><td>${percent(row.winRate)}<small>${intervalText(row.ci)}</small></td><td>${pText(row.p)}</td><td>${pText(row.q)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="stats-empty">이 단계까지 구매한 빌드 표본이 없습니다.</p>'}<details class="method-details"><summary>분류와 FDR 계산 기준</summary><p>선6레벨에서 먼저 도달한 횟수가 상대보다 많으면 주도권 우위, 15분 전 맞상대 솔로킬 평균이 상대보다 높으면 솔킬 우위입니다. 둘 다 충족하면 모두 우위이며, 선2·선3 중 하나라도 상대 비율에 밀리면 초반 불리를 표시합니다. 레벨 지표는 유효 ${siteData.metadata.minLevels}경기 이상일 때 적용합니다.</p><p>같은 매치업·같은 빌드 단계에서 해당 빌드와 나머지 빌드의 승패를 단측 Fisher 정확검정으로 비교합니다. 양쪽 ${siteData.metadata.minBuildGames}경기 이상인 후보를 대상으로, 상위 10개를 자르기 전 시작~5코어 전체 ${data.fdr.tests}개 검정을 ${data.fdr.method.toUpperCase()} 방식으로 보정합니다. q &lt; ${data.fdr.alpha}이며 승률이 더 높은 빌드만 강조합니다.</p><p>빌드 선택·실력·게임 길이에 따른 편향이 있어 승률 차이가 아이템의 인과 효과를 뜻하지는 않습니다. 4~5코어 통계는 그 단계까지 도달한 경기만 비교합니다.</p></details>`;
}
async function checkUpdates(manual){
  if(location.protocol==='file:'){if(manual)toast('Python 실행 주소 또는 배포된 주소에서 갱신을 확인할 수 있습니다.');return;}
  try{
    const release=await getJSON('release.json?t='+Date.now());
    if(release.revision===siteData.revision){if(manual)toast('현재 배포된 최신 내용을 보고 있습니다.');return;}
    if(runtime.publisher&&(editing||dirty)){if(manual)toast('새 배포 내용이 있습니다. 현재 초안을 백업한 뒤 새로고침해 주세요.');return;}
    const next=await getJSON('data/site.json?t='+Date.now());applyPublished(next);if(manual)toast('새 통계와 배포자 수정 내용을 반영했습니다.');
  }catch(error){if(manual)toast(error.message);}
}
function applyPublished(next){
  if(next.schemaVersion!==3||!next.catalog?.champions?.length)throw new Error('지원하지 않는 배포 데이터입니다.');
  const previous={siteData,catalog,champions,byId,board};
  try{siteData=next;catalog=next.catalog;champions=catalog.champions.slice().sort((a,b)=>a.name.localeCompare(b.name,'ko'));byId=new Map(champions.map(c=>[c.id,c]));board=normalize(next.board);}catch(error){({siteData,catalog,champions,byId,board}=previous);throw error;}
  if(!byId.has(selected))selected=champions[0].id;
  if(statsDialog.open)statsDialog.close();detailCache.clear();clearTargets();undoStack=[];render();
}
async function adminPOST(path,body){
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Counter-Token':runtime.token},body:JSON.stringify(body),signal:AbortSignal.timeout(120000)});
  const result=await response.json();if(!response.ok)throw new Error(result.error||'요청을 처리하지 못했습니다.');return result;
}
async function savePublisher(){
  if(!runtime.publisher||refreshing)return;
  try{const result=await adminPOST('/api/edits',{board:snapshot(),revision:siteData.revision});try{localStorage.removeItem(storageKey);}catch{}dirty=false;editing=false;tierEditing=false;applyPublished(result);toast('배포 파일을 생성했습니다. 프로젝트 변경을 GitHub에 올리면 사용자에게 반영됩니다.');}catch(error){toast(error.message);}
}
async function refreshData(){
  if(!runtime.publisher){await checkUpdates(true);return;}
  if(refreshing||editing)return;
  if(dirty){toast('수정 사항을 먼저 저장한 뒤 데이터를 갱신해 주세요.');return;}
  refreshing=true;render();
  try{
    await adminPOST('/api/refresh',{});
    while(refreshing){
      await new Promise(resolve=>setTimeout(resolve,1500));
      const status=await getJSON('/api/status');const label=document.getElementById('job-status');if(label)label.textContent=status.message||'';
      if(status.state==='error')throw new Error(status.message);
      if(status.state==='done'){refreshing=false;applyPublished(await getJSON('data/site.json?t='+Date.now()));toast('Riot 경기 수집과 통계 생성을 완료했습니다.');break;}
    }
  }catch(error){refreshing=false;render();toast(error.message);}
}
async function copyPageLink(){try{await navigator.clipboard.writeText(location.href);toast('현재 페이지 주소를 복사했습니다.');}catch{toast('주소 표시줄의 페이지 주소를 복사해 공유하세요.');}}

render();
if(initialMessage)toast(initialMessage);
if(location.protocol!=='file:'){setInterval(()=>checkUpdates(false),Math.max(30,siteData.pollSeconds)*1000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)checkUpdates(false);});}
const modelContext=document.modelContext;
if(modelContext?.registerTool){
  const lifecycle=new AbortController();
  try {Promise.resolve(modelContext.registerTool({name:'read_counter_note',title:'상성표 읽기',description:'사용자가 작성한 라인별 챔피언 상성표를 읽습니다.',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},execute(input){if(!input||typeof input!=='object'||Object.keys(input).length)throw new Error('빈 객체를 입력하세요.');return {version:catalog.version,champions:champions.map(({id,name})=>({id,name})),...snapshot()};}},{signal:lifecycle.signal})).catch(()=>{});}catch{}
  window.addEventListener('pagehide',()=>lifecycle.abort(),{once:true});
}
})();
