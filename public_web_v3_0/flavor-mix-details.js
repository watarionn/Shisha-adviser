(() => {
  'use strict';

  const DETAILS_URL = '/flavor-details.json';
  const AXIS_ORDER = ['sweetness','cooling','acidity','creaminess','body','spice_intensity','floral_intensity'];
  const AXIS_LABELS = {
    sweetness:'甘さ', cooling:'清涼感', acidity:'酸味', creaminess:'クリーミーさ',
    body:'ボディ感', spice_intensity:'スパイス感', floral_intensity:'フローラル感'
  };
  let catalogPromise = null;

  function normalize(value){
    return String(value || '').trim().replace(/\s+/g,' ').toLowerCase();
  }

  function hydrate(raw){
    if(!raw?.f || !Array.isArray(raw.f) || !Array.isArray(raw.o)) return raw;
    const flavors = {};
    raw.f.forEach((row) => {
      const [brand,name,flavorId,summary,impressionTags,flavorNotes,evidenceCue,values,confidences,coverage] = row;
      const axes = {};
      raw.o.forEach((axis,index) => {
        axes[axis] = {value:Number(values?.[index] ?? 50), confidence:Number(confidences?.[index] ?? 0)};
      });
      flavors[`${normalize(brand)}|${normalize(name)}`] = {
        flavor_id:flavorId, brand, name, summary,
        impression_tags:impressionTags || [], flavor_notes_ja:flavorNotes || [],
        evidence_cue:evidenceCue || '', axes, evidence_coverage:Number(coverage || 0)
      };
    });
    return {flavors};
  }

  async function loadCatalog(){
    if(catalogPromise) return catalogPromise;
    catalogPromise = (async() => {
      const res = await fetch(DETAILS_URL,{cache:'no-store'});
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      const root = await res.json();
      if(!Array.isArray(root?.shards)) return hydrate(root);
      const parts = await Promise.all(root.shards.map(async(url) => {
        const r = await fetch(url,{cache:'no-store'});
        if(!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
        return r.json();
      }));
      return hydrate({v:root.v || 1,o:parts[0]?.o || [],f:parts.flatMap(p => p.f || [])});
    })().catch((err) => {
      console.warn('Mix detail catalog unavailable:',err);
      return {flavors:{}};
    });
    return catalogPromise;
  }

  function lookup(data,component){
    return data?.flavors?.[`${normalize(component.brand)}|${normalize(component.name)}`] || null;
  }

  function componentFrom(row,index){
    const name = row?.[`component_${index}`];
    const brand = row?.[`brand_${index}`];
    const ratio = Number(row?.[`ratio_${index}`]);
    if(!name || !brand) return null;
    return {name:String(name),brand:String(brand),ratio:Number.isFinite(ratio) ? ratio : null};
  }

  function attachPayload(card,kind,row){
    if(!card || !row) return;
    const count = kind === 'TRIPLE' ? 3 : 2;
    const components = [];
    for(let i=1;i<=count;i++){
      const c = componentFrom(row,i);
      if(c) components.push(c);
    }
    if(components.length < 2) return;
    card.dataset.mixDetailKind = kind;
    card.dataset.mixDetailLabel = row.mix_label || '';
    card.dataset.mixDetailComponents = JSON.stringify(components);
    const hint = card.querySelector('.flavor-detail-hint');
    if(hint) hint.textContent = 'タップで各フレーバーの詳細を見る';
  }

  function installRecommendationCapture(){
    const original = window.renderRecommendations;
    if(typeof original !== 'function' || original.__mixDetailWrapped) return;
    const wrapped = function(result){
      const before = new Set(document.querySelectorAll('.rec-card'));
      const value = original.apply(this,arguments);
      const fresh = Array.from(document.querySelectorAll('.rec-card')).filter(card => !before.has(card));
      let cursor = Math.min((result?.singles || []).length,3);
      (result?.pairs || []).slice(0,3).forEach((row) => attachPayload(fresh[cursor++],'MIX',row));
      (result?.triples || []).slice(0,2).forEach((row) => attachPayload(fresh[cursor++],'TRIPLE',row));
      return value;
    };
    wrapped.__mixDetailWrapped = true;
    window.renderRecommendations = wrapped;
  }

  function confidenceLabel(conf){
    if(conf >= .8) return '根拠強め';
    if(conf >= .45) return '参考値';
    return '推定値';
  }

  function el(tag,className,text){
    const node = document.createElement(tag);
    if(className) node.className = className;
    if(text != null) node.textContent = text;
    return node;
  }

  function addTags(parent,tags){
    if(!Array.isArray(tags) || !tags.length) return;
    const wrap = el('div','flavor-detail-tags');
    tags.forEach((tag) => wrap.appendChild(el('span','flavor-detail-tag',tag)));
    parent.appendChild(wrap);
  }

  function addAxes(parent,detail){
    const axes = detail?.axes || {};
    const available = AXIS_ORDER.filter(axis => axes[axis]);
    if(!available.length) return;
    parent.appendChild(el('div','flavor-detail-section-title','味わいプロフィール'));
    available.forEach((axis) => {
      const data = axes[axis];
      const row = el('div','flavor-axis');
      if(Number(data.confidence || 0) < .45) row.classList.add('low-confidence');
      row.appendChild(el('div','flavor-axis-name',AXIS_LABELS[axis] || axis));
      const track = el('div','flavor-axis-track');
      const fill = el('div','flavor-axis-fill');
      fill.style.width = `${Math.max(0,Math.min(100,Number(data.value || 0)))}%`;
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(el('div','flavor-axis-value',String(Math.round(Number(data.value || 0)))));
      row.appendChild(el('div','flavor-axis-note',`${confidenceLabel(Number(data.confidence || 0))} · confidence ${Number(data.confidence || 0).toFixed(2)}`));
      parent.appendChild(row);
    });
  }

  function buildComponent(detail,component,index){
    const box = el('details','flavor-detail-component');
    box.style.cursor = 'pointer';
    const summary = el('summary','');
    summary.style.listStyle = 'none';
    summary.style.display = 'flex';
    summary.style.justifyContent = 'space-between';
    summary.style.gap = '12px';
    summary.style.alignItems = 'baseline';
    const title = el('strong','',`${index}. ${component.brand} / ${component.name}`);
    summary.appendChild(title);
    if(component.ratio != null){
      const ratio = el('span','flavor-detail-tag',`${Math.round(component.ratio*100)}%`);
      ratio.style.flex = '0 0 auto';
      summary.appendChild(ratio);
    }
    box.appendChild(summary);

    if(!detail){
      box.appendChild(el('p','', 'このフレーバーの監査済み詳細データはまだ準備中です。'));
      return box;
    }

    box.appendChild(el('p','',detail.summary || 'プロフィール情報を表示します。'));
    addTags(box,detail.impression_tags);

    const expanded = el('div','flavor-detail-section');
    if(detail.flavor_notes_ja?.length){
      expanded.appendChild(el('div','flavor-detail-section-title','香味の手がかり'));
      addTags(expanded,detail.flavor_notes_ja);
    }
    addAxes(expanded,detail);
    if(detail.evidence_cue){
      expanded.appendChild(el('div','flavor-detail-section-title','出典由来の香味メモ'));
      expanded.appendChild(el('div','flavor-detail-evidence',detail.evidence_cue));
    }
    expanded.appendChild(el('div','flavor-detail-footnote',`監査済みデータ上で、7軸中${Number(detail.evidence_coverage || 0)}軸に一定以上の根拠があります。薄い軸は低信頼の推定です。`));
    box.appendChild(expanded);
    return box;
  }

  async function openMixDetails(card){
    const overlay = document.getElementById('flavorDetailOverlay');
    const panel = document.getElementById('flavorDetailPanel');
    if(!overlay || !panel) return;
    let components = [];
    try{ components = JSON.parse(card.dataset.mixDetailComponents || '[]'); }catch(_){ return; }
    const data = await loadCatalog();

    panel.replaceChildren();
    const top = el('div','flavor-detail-top');
    const heading = el('div','');
    heading.appendChild(el('div','flavor-detail-kicker',card.dataset.mixDetailKind === 'TRIPLE' ? 'TRIPLE DETAIL' : 'MIX DETAIL'));
    const title = el('div','flavor-detail-title',card.dataset.mixDetailLabel || card.querySelector('strong')?.textContent || 'Mix');
    title.id = 'flavorDetailTitle';
    heading.appendChild(title);
    top.appendChild(heading);
    const close = el('button','flavor-detail-close','×');
    close.type = 'button';
    close.setAttribute('aria-label','詳細を閉じる');
    close.addEventListener('click',() => {
      overlay.classList.remove('open');
      document.body.style.overflow = '';
    });
    top.appendChild(close);
    panel.appendChild(top);
    panel.appendChild(el('div','flavor-detail-summary','各フレーバーを開くと、味・香り・イメージ・味わいプロフィールを確認できます。配合比やセッティングでミックス全体の印象は変わります。'));

    components.forEach((component,index) => {
      panel.appendChild(buildComponent(lookup(data,component),component,index+1));
    });

    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
    panel.focus();
  }

  document.addEventListener('click',(event) => {
    const card = event.target.closest?.('.rec-card[data-mix-detail-components]');
    if(!card) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openMixDetails(card);
  },true);

  document.addEventListener('keydown',(event) => {
    if(event.key !== 'Enter' && event.key !== ' ') return;
    const card = event.target.closest?.('.rec-card[data-mix-detail-components]');
    if(!card) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    openMixDetails(card);
  },true);

  installRecommendationCapture();
})();
