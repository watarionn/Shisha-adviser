(() => {
  'use strict';

  const DETAILS_URL = '/flavor-details.json';
  const AXIS_ORDER = ['sweetness','cooling','acidity','creaminess','body','spice_intensity','floral_intensity'];
  const AXIS_LABELS = {
    sweetness:'甘さ', cooling:'清涼感', acidity:'酸味', creaminess:'クリーミーさ',
    body:'ボディ感', spice_intensity:'スパイス感', floral_intensity:'フローラル感'
  };
  const TRUSTED_CONFIDENCE = .45;
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
    if(hint) hint.textContent = 'タップでMIX全体＋各フレーバーを見る';
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
    if(conf >= TRUSTED_CONFIDENCE) return '参考値';
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
      if(Number(data.confidence || 0) < TRUSTED_CONFIDENCE) row.classList.add('low-confidence');
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

  function normalizeRatios(components){
    const finite = components.map((component) => Number(component.ratio)).filter((ratio) => Number.isFinite(ratio) && ratio > 0);
    const sum = finite.reduce((acc,ratio) => acc + ratio,0);
    if(sum > 0){
      return components.map((component) => ({...component,normalizedRatio:(Number(component.ratio) > 0 ? Number(component.ratio) / sum : 0)}));
    }
    const fallback = components.length ? 1 / components.length : 0;
    return components.map((component) => ({...component,normalizedRatio:fallback}));
  }

  function aggregateMix(components,data){
    const weightedComponents = normalizeRatios(components).map((component) => ({
      component,
      detail:lookup(data,component),
    }));
    const axes = {};

    AXIS_ORDER.forEach((axis) => {
      const trusted = weightedComponents.filter(({component,detail}) => {
        const item = detail?.axes?.[axis];
        return item && Number(item.confidence || 0) >= TRUSTED_CONFIDENCE && component.normalizedRatio > 0;
      });
      const coveredRatio = trusted.reduce((sum,{component}) => sum + component.normalizedRatio,0);
      if(coveredRatio <= 0) return;

      const value = trusted.reduce((sum,{component,detail}) => (
        sum + component.normalizedRatio * Number(detail.axes[axis].value || 0)
      ),0) / coveredRatio;
      const evidenceConfidence = trusted.reduce((sum,{component,detail}) => (
        sum + component.normalizedRatio * Number(detail.axes[axis].confidence || 0)
      ),0) / coveredRatio;
      const confidence = evidenceConfidence * coveredRatio;
      axes[axis] = {
        value:Math.max(0,Math.min(100,value)),
        confidence:Math.max(0,Math.min(1,confidence)),
        covered_ratio:coveredRatio,
      };
    });

    const flavorNotes = [];
    weightedComponents
      .slice()
      .sort((a,b) => b.component.normalizedRatio - a.component.normalizedRatio)
      .forEach(({detail}) => {
        (detail?.flavor_notes_ja || []).forEach((note) => {
          if(note && !flavorNotes.includes(note)) flavorNotes.push(note);
        });
      });

    return {axes,flavor_notes_ja:flavorNotes.slice(0,8),weightedComponents};
  }

  function axisPhrase(axis,value){
    if(axis === 'sweetness'){
      if(value >= 72) return 'しっかり甘め';
      if(value >= 56) return 'ほどよく甘め';
      if(value <= 34) return '甘さ控えめ';
    }
    if(axis === 'cooling'){
      if(value >= 78) return 'かなりひんやり';
      if(value >= 60) return 'ひんやり感あり';
      if(value <= 28) return '冷涼感ひかえめ';
    }
    if(axis === 'acidity'){
      if(value >= 68) return 'キュッと酸味強め';
      if(value >= 52) return 'ほどよく酸味あり';
    }
    if(axis === 'creaminess'){
      if(value >= 68) return 'クリーミー';
      if(value <= 28) return 'クリーム感ひかえめ';
    }
    if(axis === 'body'){
      if(value >= 70) return 'しっかりした味わい';
      if(value <= 30) return '軽やか寄り';
    }
    if(axis === 'spice_intensity'){
      if(value >= 62) return 'スパイス感あり';
    }
    if(axis === 'floral_intensity'){
      if(value >= 62) return '華やかさあり';
    }
    return null;
  }

  function mixSummary(components,aggregate){
    const weighted = aggregate.weightedComponents || [];
    const sorted = weighted.slice().sort((a,b) => b.component.normalizedRatio - a.component.normalizedRatio);
    const ratioIntro = (() => {
      if(!sorted.length) return '';
      const top = sorted[0];
      const second = sorted[1];
      if(second && top.component.normalizedRatio - second.component.normalizedRatio >= .12){
        return `${top.component.name}を軸にした配合。`;
      }
      if(sorted.length === 2) return '2つのフレーバーをバランスよく重ねる配合。';
      return '3つのフレーバーを重ねた配合。';
    })();

    const phrases = AXIS_ORDER
      .map((axis) => {
        const item = aggregate.axes?.[axis];
        if(!item || Number(item.confidence || 0) < TRUSTED_CONFIDENCE) return null;
        return axisPhrase(axis,Number(item.value || 0));
      })
      .filter(Boolean)
      .slice(0,4);

    if(!phrases.length){
      return `${ratioIntro} MIX全体として断定できる味わい軸はまだ少なめです。各フレーバーの詳細を参考にしてください。`;
    }
    return `${ratioIntro} 監査済みデータを配合比で合成すると、${phrases.join('、')}寄りのイメージです。`;
  }

  function mixImpressionTags(aggregate){
    const tags = [];
    AXIS_ORDER.forEach((axis) => {
      const item = aggregate.axes?.[axis];
      if(!item || Number(item.confidence || 0) < TRUSTED_CONFIDENCE) return;
      const phrase = axisPhrase(axis,Number(item.value || 0));
      if(phrase && !tags.includes(phrase)) tags.push(phrase);
    });
    return tags.slice(0,6);
  }

  function buildOverallSection(components,data){
    const aggregate = aggregateMix(components,data);
    const section = el('div','flavor-detail-section');
    section.appendChild(el('div','flavor-detail-section-title','MIX全体のイメージ'));
    const summary = el('div','flavor-detail-evidence',mixSummary(components,aggregate));
    section.appendChild(summary);

    const impressionTags = mixImpressionTags(aggregate);
    if(impressionTags.length){
      const tagTitle = el('div','flavor-detail-section-title','総合イメージ');
      tagTitle.style.marginTop = '14px';
      section.appendChild(tagTitle);
      addTags(section,impressionTags);
    }

    if(aggregate.flavor_notes_ja.length){
      const noteTitle = el('div','flavor-detail-section-title','構成の香味キーワード');
      noteTitle.style.marginTop = '14px';
      section.appendChild(noteTitle);
      addTags(section,aggregate.flavor_notes_ja);
    }

    const trustedAxes = {};
    AXIS_ORDER.forEach((axis) => {
      const item = aggregate.axes?.[axis];
      if(item) trustedAxes[axis] = item;
    });
    if(Object.keys(trustedAxes).length){
      const profile = el('div','flavor-detail-section');
      profile.style.marginTop = '16px';
      addAxes(profile,{axes:trustedAxes});
      section.appendChild(profile);
    }

    const supported = Object.values(aggregate.axes || {}).filter((item) => Number(item.confidence || 0) >= TRUSTED_CONFIDENCE).length;
    section.appendChild(el(
      'div',
      'flavor-detail-footnote',
      `MIX全体の数値は、各フレーバーの監査済み軸を配合比で加重して算出しています。7軸中${supported}軸が総合説明に使える信頼度です。低信頼・未収録の軸は説明から除外しています。実際の印象はボウル、熱管理、吸い方でも変わります。`
    ));
    return section;
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

    panel.appendChild(buildOverallSection(components,data));

    const componentTitle = el('div','flavor-detail-section-title','各フレーバーの詳細');
    componentTitle.style.marginTop = '22px';
    panel.appendChild(componentTitle);
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
