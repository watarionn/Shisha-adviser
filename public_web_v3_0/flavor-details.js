(() => {
  'use strict';

  const DETAILS_URL = '/flavor-details.json';
  const AXIS_ORDER = [
    'sweetness',
    'cooling',
    'acidity',
    'creaminess',
    'body',
    'spice_intensity',
    'floral_intensity',
  ];
  const AXIS_LABELS = {
    sweetness: '甘さ',
    cooling: '清涼感',
    acidity: '酸味',
    creaminess: 'クリーミーさ',
    body: 'ボディ感',
    spice_intensity: 'スパイス感',
    floral_intensity: 'フローラル感',
  };

  let catalog = null;
  let catalogError = false;

  function normalize(value) {
    return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
  }

  function hydrateCatalog(raw) {
    if (!raw?.f || !Array.isArray(raw.f) || !Array.isArray(raw.o)) return raw;
    const flavors = {};
    raw.f.forEach((row) => {
      const [brand, name, flavorId, summary, impressionTags, flavorNotes, evidenceCue, values, confidences, coverage] = row;
      const axes = {};
      raw.o.forEach((axis, index) => {
        axes[axis] = {
          value: Number(values?.[index] ?? 50),
          confidence: Number(confidences?.[index] ?? 0),
        };
      });
      flavors[`${normalize(brand)}|${normalize(name)}`] = {
        flavor_id: flavorId,
        brand,
        name,
        summary,
        impression_tags: impressionTags || [],
        flavor_notes_ja: flavorNotes || [],
        evidence_cue: evidenceCue || '',
        axes,
        evidence_coverage: Number(coverage || 0),
      };
    });
    return {flavors};
  }

  async function loadCatalog() {
    if (catalog || catalogError) return catalog;
    try {
      const res = await fetch(DETAILS_URL, {cache: 'no-store'});
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      catalog = hydrateCatalog(await res.json());
      return catalog;
    } catch (err) {
      catalogError = true;
      console.warn('Flavor detail catalog unavailable:', err);
      return null;
    }
  }

  function injectStyles() {
    if (document.getElementById('flavor-detail-style')) return;
    const style = document.createElement('style');
    style.id = 'flavor-detail-style';
    style.textContent = `
      .rec-card.flavor-detail-enabled{
        cursor:pointer;position:relative;padding-right:38px;transition:border-color .15s ease,transform .15s ease,background .15s ease;
      }
      .rec-card.flavor-detail-enabled:hover,
      .rec-card.flavor-detail-enabled:focus{
        border-color:#8a6b84;background:#171219;outline:none;transform:translateY(-1px);
      }
      .rec-card.flavor-detail-enabled::after{
        content:'›';position:absolute;right:14px;top:50%;transform:translateY(-52%);
        color:var(--accent);font-size:1.45rem;line-height:1;
      }
      .flavor-detail-hint{display:block;color:#8f838e;font-size:.72rem;margin-top:5px}
      .flavor-detail-overlay{
        position:fixed;inset:0;z-index:1000;background:rgba(5,4,6,.74);backdrop-filter:blur(7px);
        display:none;align-items:flex-end;justify-content:center;padding:18px;
      }
      .flavor-detail-overlay.open{display:flex}
      .flavor-detail-panel{
        width:min(680px,100%);max-height:min(84vh,780px);overflow:auto;
        background:#17131a;border:1px solid #4b3c4e;border-radius:22px;
        box-shadow:0 24px 80px rgba(0,0,0,.52);padding:22px 22px 26px;
      }
      .flavor-detail-top{display:flex;gap:14px;justify-content:space-between;align-items:flex-start}
      .flavor-detail-kicker{font-size:.72rem;color:var(--accent);font-weight:850;letter-spacing:.11em}
      .flavor-detail-title{font-size:1.45rem;font-weight:850;line-height:1.25;margin-top:4px}
      .flavor-detail-close{
        flex:0 0 auto;width:36px;height:36px;border-radius:999px;border:1px solid var(--line);
        color:var(--muted);background:#0f0d11;cursor:pointer;font-size:1.1rem
      }
      .flavor-detail-summary{color:#e8dfe8;line-height:1.75;margin:18px 0 14px}
      .flavor-detail-section{margin-top:20px}
      .flavor-detail-section-title{font-size:.74rem;color:var(--accent);font-weight:850;letter-spacing:.08em;margin-bottom:10px}
      .flavor-detail-tags{display:flex;flex-wrap:wrap;gap:7px}
      .flavor-detail-tag{
        border:1px solid #493b4c;background:#100e12;border-radius:999px;padding:6px 10px;
        color:#ded2dd;font-size:.78rem
      }
      .flavor-axis{display:grid;grid-template-columns:90px 1fr 42px;gap:10px;align-items:center;margin:9px 0}
      .flavor-axis-name{color:#d8ced7;font-size:.8rem}
      .flavor-axis-track{height:8px;background:#2a232d;border-radius:999px;overflow:hidden}
      .flavor-axis-fill{height:100%;background:linear-gradient(90deg,#8b6681,#edc1df);border-radius:999px}
      .flavor-axis-value{font-variant-numeric:tabular-nums;text-align:right;color:#eee4ed;font-size:.78rem}
      .flavor-axis.low-confidence{opacity:.48}
      .flavor-axis-note{grid-column:2 / 4;color:#877b86;font-size:.68rem;margin-top:-6px}
      .flavor-detail-evidence{
        background:#100e12;border:1px solid #382f3b;border-radius:12px;padding:12px 13px;
        color:#c8bcc7;font-size:.8rem;line-height:1.6
      }
      .flavor-detail-footnote{color:#8f838e;font-size:.72rem;line-height:1.55;margin-top:17px}
      .flavor-detail-empty{color:var(--muted);line-height:1.7;padding:8px 0 4px}
      .flavor-detail-component{
        border:1px solid #3d313f;border-radius:14px;background:#100e12;padding:13px;margin:9px 0
      }
      .flavor-detail-component strong{display:block}
      .flavor-detail-component p{color:#b9adb9;font-size:.82rem;margin:6px 0 0;line-height:1.6}
      @media(min-width:700px){
        .flavor-detail-overlay{align-items:center}
      }
    `;
    document.head.appendChild(style);
  }

  function createModal() {
    if (document.getElementById('flavorDetailOverlay')) return;
    const overlay = document.createElement('div');
    overlay.id = 'flavorDetailOverlay';
    overlay.className = 'flavor-detail-overlay';
    overlay.setAttribute('role', 'presentation');

    const panel = document.createElement('section');
    panel.id = 'flavorDetailPanel';
    panel.className = 'flavor-detail-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-labelledby', 'flavorDetailTitle');
    panel.tabIndex = -1;
    overlay.appendChild(panel);

    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeModal();
    });
    document.body.appendChild(overlay);
  }

  function closeModal() {
    const overlay = document.getElementById('flavorDetailOverlay');
    if (!overlay) return;
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }

  function openPanel(builder) {
    const overlay = document.getElementById('flavorDetailOverlay');
    const panel = document.getElementById('flavorDetailPanel');
    if (!overlay || !panel) return;

    panel.replaceChildren();

    const top = document.createElement('div');
    top.className = 'flavor-detail-top';

    const headingWrap = document.createElement('div');
    const kicker = document.createElement('div');
    kicker.className = 'flavor-detail-kicker';
    kicker.textContent = 'FLAVOR DETAIL';
    headingWrap.appendChild(kicker);

    const title = document.createElement('div');
    title.id = 'flavorDetailTitle';
    title.className = 'flavor-detail-title';
    headingWrap.appendChild(title);
    top.appendChild(headingWrap);

    const close = document.createElement('button');
    close.className = 'flavor-detail-close';
    close.type = 'button';
    close.setAttribute('aria-label', '詳細を閉じる');
    close.textContent = '×';
    close.addEventListener('click', closeModal);
    top.appendChild(close);
    panel.appendChild(top);

    builder(panel, title, kicker);

    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
    panel.focus();
  }

  function confidenceLabel(conf) {
    if (conf >= 0.8) return '根拠強め';
    if (conf >= 0.45) return '参考値';
    return '推定値';
  }

  function addSectionTitle(panel, text) {
    const t = document.createElement('div');
    t.className = 'flavor-detail-section-title';
    t.textContent = text;
    return t;
  }

  function renderFlavorDetail(detail, requestedTitle) {
    openPanel((panel, title, kicker) => {
      kicker.textContent = 'FLAVOR DETAIL';
      title.textContent = detail ? `${detail.brand} / ${detail.name}` : requestedTitle;

      if (!detail) {
        const empty = document.createElement('div');
        empty.className = 'flavor-detail-empty';
        empty.textContent = 'このフレーバーは推薦候補として表示されていますが、説明に使える監査済み詳細データがまだありません。データ拡充後にここへ味やイメージを追加します。';
        panel.appendChild(empty);
        return;
      }

      const summary = document.createElement('div');
      summary.className = 'flavor-detail-summary';
      summary.textContent = detail.summary || 'プロフィール情報を表示します。';
      panel.appendChild(summary);

      if (Array.isArray(detail.impression_tags) && detail.impression_tags.length) {
        const sec = document.createElement('div');
        sec.className = 'flavor-detail-section';
        sec.appendChild(addSectionTitle(panel, 'こんなイメージ'));
        const tags = document.createElement('div');
        tags.className = 'flavor-detail-tags';
        detail.impression_tags.forEach((tag) => {
          const chip = document.createElement('span');
          chip.className = 'flavor-detail-tag';
          chip.textContent = tag;
          tags.appendChild(chip);
        });
        sec.appendChild(tags);
        panel.appendChild(sec);
      }

      if (Array.isArray(detail.flavor_notes_ja) && detail.flavor_notes_ja.length) {
        const sec = document.createElement('div');
        sec.className = 'flavor-detail-section';
        sec.appendChild(addSectionTitle(panel, '香味の手がかり'));
        const tags = document.createElement('div');
        tags.className = 'flavor-detail-tags';
        detail.flavor_notes_ja.forEach((note) => {
          const chip = document.createElement('span');
          chip.className = 'flavor-detail-tag';
          chip.textContent = note;
          tags.appendChild(chip);
        });
        sec.appendChild(tags);
        panel.appendChild(sec);
      }

      const axes = detail.axes || {};
      const availableAxes = AXIS_ORDER.filter((axis) => axes[axis]);
      if (availableAxes.length) {
        const sec = document.createElement('div');
        sec.className = 'flavor-detail-section';
        sec.appendChild(addSectionTitle(panel, '味わいプロフィール'));

        availableAxes.forEach((axis) => {
          const data = axes[axis];
          const row = document.createElement('div');
          row.className = 'flavor-axis';
          if (Number(data.confidence || 0) < 0.45) row.classList.add('low-confidence');

          const name = document.createElement('div');
          name.className = 'flavor-axis-name';
          name.textContent = AXIS_LABELS[axis] || axis;
          row.appendChild(name);

          const track = document.createElement('div');
          track.className = 'flavor-axis-track';
          const fill = document.createElement('div');
          fill.className = 'flavor-axis-fill';
          fill.style.width = `${Math.max(0, Math.min(100, Number(data.value || 0)))}%`;
          track.appendChild(fill);
          row.appendChild(track);

          const value = document.createElement('div');
          value.className = 'flavor-axis-value';
          value.textContent = Math.round(Number(data.value || 0));
          row.appendChild(value);

          const note = document.createElement('div');
          note.className = 'flavor-axis-note';
          note.textContent = `${confidenceLabel(Number(data.confidence || 0))} · confidence ${Number(data.confidence || 0).toFixed(2)}`;
          row.appendChild(note);

          sec.appendChild(row);
        });
        panel.appendChild(sec);
      }

      if (detail.evidence_cue) {
        const sec = document.createElement('div');
        sec.className = 'flavor-detail-section';
        sec.appendChild(addSectionTitle(panel, '出典由来の香味メモ'));
        const evidence = document.createElement('div');
        evidence.className = 'flavor-detail-evidence';
        evidence.textContent = detail.evidence_cue;
        sec.appendChild(evidence);
        panel.appendChild(sec);
      }

      const foot = document.createElement('div');
      foot.className = 'flavor-detail-footnote';
      const coverage = Number(detail.evidence_coverage || 0);
      foot.textContent = `監査済みデータ上で、7軸中${coverage}軸に一定以上の根拠があります。薄く表示された軸は低信頼の推定を含むため、味の断定には使っていません。`;
      panel.appendChild(foot);
    });
  }

  function findDetailFromLabel(label, data) {
    if (!data?.flavors) return null;
    const cleaned = String(label || '').replace(/\s+/g, ' ').trim();
    const slash = cleaned.indexOf(' / ');
    if (slash > 0) {
      const brand = cleaned.slice(0, slash);
      const name = cleaned.slice(slash + 3);
      return data.flavors[`${normalize(brand)}|${normalize(name)}`] || null;
    }

    const target = normalize(cleaned);
    const matches = Object.values(data.flavors).filter((x) => normalize(x.name) === target);
    return matches.length === 1 ? matches[0] : null;
  }

  function splitMixTitle(title) {
    return String(title || '')
      .split(/\s+\+\s+/)
      .map((x) => x.trim())
      .filter(Boolean);
  }

  function renderMixDetail(titleText, components, data) {
    openPanel((panel, title, kicker) => {
      kicker.textContent = 'MIX DETAIL';
      title.textContent = titleText;

      const intro = document.createElement('div');
      intro.className = 'flavor-detail-summary';
      intro.textContent = 'ミックスを構成する各フレーバーの特徴です。組み合わせ全体の味は配合比やセッティングでも変わります。';
      panel.appendChild(intro);

      components.forEach((label) => {
        const detail = findDetailFromLabel(label, data);
        const box = document.createElement('div');
        box.className = 'flavor-detail-component';

        const strong = document.createElement('strong');
        strong.textContent = detail ? `${detail.brand} / ${detail.name}` : label;
        box.appendChild(strong);

        const p = document.createElement('p');
        p.textContent = detail
          ? detail.summary
          : 'この構成要素の詳細データはまだ準備中です。';
        box.appendChild(p);

        if (detail?.impression_tags?.length) {
          const tags = document.createElement('div');
          tags.className = 'flavor-detail-tags';
          tags.style.marginTop = '9px';
          detail.impression_tags.slice(0, 3).forEach((tag) => {
            const chip = document.createElement('span');
            chip.className = 'flavor-detail-tag';
            chip.textContent = tag;
            tags.appendChild(chip);
          });
          box.appendChild(tags);
        }

        box.addEventListener('click', () => {
          if (detail) renderFlavorDetail(detail, label);
        });
        panel.appendChild(box);
      });
    });
  }

  async function showCardDetail(card) {
    const strong = card.querySelector('strong');
    const titleText = strong?.textContent?.trim() || '';
    if (!titleText) return;

    const data = await loadCatalog();
    if (!data) {
      renderFlavorDetail(null, titleText);
      return;
    }

    const direct = findDetailFromLabel(titleText, data);
    if (direct) {
      renderFlavorDetail(direct, titleText);
      return;
    }

    const components = splitMixTitle(titleText);
    if (components.length >= 2) {
      renderMixDetail(titleText, components, data);
      return;
    }

    renderFlavorDetail(null, titleText);
  }

  function enhanceCard(card) {
    if (!card || card.dataset.flavorDetailReady === '1') return;
    card.dataset.flavorDetailReady = '1';
    card.classList.add('flavor-detail-enabled');
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.setAttribute('aria-label', `${card.textContent.trim()} の詳細を見る`);

    const hint = document.createElement('span');
    hint.className = 'flavor-detail-hint';
    hint.textContent = 'タップで味・イメージを見る';
    card.appendChild(hint);

    card.addEventListener('click', () => showCardDetail(card));
    card.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        showCardDetail(card);
      }
    });
  }

  function enhanceExistingCards() {
    document.querySelectorAll('.rec-card').forEach(enhanceCard);
  }

  function observeCards() {
    const root = document.getElementById('messages') || document.body;
    const observer = new MutationObserver(() => enhanceExistingCards());
    observer.observe(root, {childList: true, subtree: true});
  }

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeModal();
  });

  injectStyles();
  createModal();
  enhanceExistingCards();
  observeCards();
  loadCatalog();
})();