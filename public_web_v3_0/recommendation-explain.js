(() => {
  'use strict';

  const AXIS_LABELS = {
    sweetness:'甘さ', cooling:'清涼感', body:'ボディ感', acidity:'酸味',
    creaminess:'クリーミーさ', spice_intensity:'スパイス感', floral_intensity:'フローラル感'
  };
  const reasonByLabel = new Map();

  function normalize(value){
    return String(value || '').trim().replace(/\s+/g,' ').toLowerCase();
  }

  function el(tag,className,text){
    const node = document.createElement(tag);
    if(className) node.className = className;
    if(text != null) node.textContent = text;
    return node;
  }

  function attachReason(card,row){
    if(!card || !row?.mix_label) return;
    const reason = {
      mix_label:row.mix_label,
      score:Number(row.score || 0),
      confidence_coverage:Number(row.confidence_coverage || 0),
      top_match_axes:Array.isArray(row.top_match_axes) ? row.top_match_axes : [],
      uncertain_axes:Array.isArray(row.uncertain_axes) ? row.uncertain_axes : [],
      match_axes:Array.isArray(row.match_axes) ? row.match_axes : [],
      reason_version:row.reason_version || null,
    };
    card.dataset.recommendationReason = JSON.stringify(reason);
    reasonByLabel.set(normalize(row.mix_label),reason);
  }

  function installRecommendationCapture(){
    const original = window.renderRecommendations;
    if(typeof original !== 'function' || original.__recommendationExplainWrapped) return;
    const wrapped = function(result){
      const before = new Set(document.querySelectorAll('.rec-card'));
      const value = original.apply(this,arguments);
      const fresh = Array.from(document.querySelectorAll('.rec-card')).filter(card => !before.has(card));
      let cursor = Math.min((result?.singles || []).length,3);
      (result?.pairs || []).slice(0,3).forEach((row) => attachReason(fresh[cursor++],row));
      (result?.triples || []).slice(0,2).forEach((row) => attachReason(fresh[cursor++],row));
      return value;
    };
    wrapped.__recommendationExplainWrapped = true;
    window.renderRecommendations = wrapped;
  }

  function axisLine(item){
    const label = AXIS_LABELS[item.axis] || item.axis;
    const target = Math.round(Number(item.target || 0));
    const score = Math.round(Number(item.score || 0));
    const similarity = Math.round(Number(item.similarity || 0) * 100);
    const confidence = Math.round(Number(item.confidence || 0) * 100);
    return `${label}: 好み ${target} / MIX ${score} · 近さ ${similarity}% · 根拠 ${confidence}%`;
  }

  function buildReasonSection(reason){
    const section = el('div','flavor-detail-section');
    section.dataset.recommendationExplanation = '1';
    section.appendChild(el('div','flavor-detail-section-title','なぜこのMIXがおすすめ？'));

    const topLabels = reason.top_match_axes.map(axis => AXIS_LABELS[axis] || axis);
    const intro = topLabels.length
      ? `今回の推薦条件では、${topLabels.join('・')}の一致が特に大きく効いています。`
      : '今回の推薦条件との適合度をもとに選ばれています。';
    section.appendChild(el('div','flavor-detail-evidence',intro));

    const metrics = el('div','flavor-detail-tags');
    metrics.style.marginTop = '10px';
    metrics.appendChild(el('span','flavor-detail-tag',`適合スコア ${Number(reason.score || 0).toFixed(1)}`));
    metrics.appendChild(el('span','flavor-detail-tag',`根拠カバレッジ ${Math.round(Number(reason.confidence_coverage || 0)*100)}%`));
    section.appendChild(metrics);

    if(reason.match_axes.length){
      const title = el('div','flavor-detail-section-title','特に合っているポイント');
      title.style.marginTop = '14px';
      section.appendChild(title);
      reason.match_axes.forEach((item) => {
        section.appendChild(el('div','flavor-detail-evidence',axisLine(item)));
      });
    }

    if(reason.uncertain_axes.length){
      const uncertain = reason.uncertain_axes.map(axis => AXIS_LABELS[axis] || axis).join('・');
      section.appendChild(el(
        'div',
        'flavor-detail-footnote',
        `${uncertain}は、今回使われた好み軸の中では根拠の確度が相対的に低めです。これは「相性が悪い」という意味ではなく、判断材料が薄めという意味です。`
      ));
    }

    const foot = el(
      'div',
      'flavor-detail-footnote',
      'この説明は推薦エンジンが実際に評価した軸・目標値・MIX値・confidenceから生成しています。推薦順位やスコア自体は、この説明機能の追加では変更していません。'
    );
    section.appendChild(foot);
    return section;
  }

  function renderOpenReason(){
    const overlay = document.getElementById('flavorDetailOverlay');
    const panel = document.getElementById('flavorDetailPanel');
    if(!overlay?.classList.contains('open') || !panel) return;
    if(panel.querySelector('[data-recommendation-explanation="1"]')) return;
    const title = panel.querySelector('#flavorDetailTitle')?.textContent || '';
    const reason = reasonByLabel.get(normalize(title));
    if(!reason || !reason.reason_version) return;
    const section = buildReasonSection(reason);
    const firstComponent = panel.querySelector('.flavor-detail-component');
    if(firstComponent) panel.insertBefore(section,firstComponent);
    else panel.appendChild(section);
  }

  installRecommendationCapture();

  const observer = new MutationObserver(() => queueMicrotask(renderOpenReason));
  const startObserver = () => {
    const overlay = document.getElementById('flavorDetailOverlay');
    const panel = document.getElementById('flavorDetailPanel');
    if(overlay) observer.observe(overlay,{attributes:true,attributeFilter:['class']});
    if(panel) observer.observe(panel,{childList:true,subtree:true});
  };
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded',startObserver,{once:true});
  else startObserver();
})();
