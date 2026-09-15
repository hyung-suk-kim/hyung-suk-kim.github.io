const state = {
  publications: [],
  peerReviews: [],
  query: '',
  year: 'all'
};

const ORCID_ID = '0000-0002-9155-1144';
const THEME_KEY = 'hsk-theme';
const THEME_ORDER = ['system', 'light', 'dark'];
const $ = (s) => document.querySelector(s);

function esc(s = '') {
  return String(s).replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
}

function highlightMe(authors = []) {
  if (!authors.length) return '';
  return authors.map(a => {
    const isMe = /hyung\s*-?\s*suk\s+kim/i.test(a);
    return `<span class="${isMe ? 'me' : ''}">${esc(a)}</span>`;
  }).join(', ');
}

function doiURL(doi) {
  return doi ? `https://doi.org/${doi}` : '';
}

function workURL(p) {
  return p.url || doiURL(p.doi) || `https://orcid.org/${ORCID_ID}`;
}

function formatSyncDate(raw) {
  if (!raw) return '';
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${String(d.getUTCDate()).padStart(2, '0')} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

function formatReviewYear(item) {
  return item.completion_year ? String(item.completion_year) : '—';
}

function resolveTheme(pref) {
  if (pref === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return pref;
}

function applyTheme(pref, persist = true) {
  const resolved = resolveTheme(pref);
  document.documentElement.dataset.themePreference = pref;
  document.documentElement.dataset.theme = resolved;
  if (persist) localStorage.setItem(THEME_KEY, pref);

  const iconMap = { system: '◐', light: '☼', dark: '☾' };
  const labelMap = { system: 'System', light: 'Light', dark: 'Dark' };
  if ($('#themeIcon')) $('#themeIcon').textContent = iconMap[pref];
  if ($('#themeLabel')) $('#themeLabel').textContent = labelMap[pref];

  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', resolved === 'dark' ? '#090a0d' : '#f5f1ed');
}

function cycleTheme() {
  const current = document.documentElement.dataset.themePreference || 'system';
  const idx = THEME_ORDER.indexOf(current);
  applyTheme(THEME_ORDER[(idx + 1) % THEME_ORDER.length]);
}

function featuredCard(p, i) {
  return `<a class="featured-item featured-accent-${(i % 4) + 1}" href="${esc(workURL(p))}" target="_blank" rel="noreferrer">
    <div class="featured-journal"><span>${esc(p.journal || p.type || 'Research output')}</span><span>${esc(p.year || '')}</span></div>
    <h3>${esc(p.title)}</h3>
    <div class="featured-bottom"><span>${esc((p.authors || []).slice(0, 4).join(', '))}${(p.authors || []).length > 4 ? ' et al.' : ''}</span><strong>View work ↗</strong></div>
  </a>`;
}

function pubRow(p) {
  const doi = p.doi ? `<a href="${esc(doiURL(p.doi))}" target="_blank" rel="noreferrer">DOI ↗</a>` : '';
  const orcid = p.put_code ? `<a href="https://orcid.org/${ORCID_ID}" target="_blank" rel="noreferrer">ORCID ↗</a>` : '';
  return `<article class="pub-item">
    <div class="pub-year">${esc(p.year || '—')}</div>
    <div>
      <h3 class="pub-title"><a href="${esc(workURL(p))}" target="_blank" rel="noreferrer">${esc(p.title)}</a></h3>
      <div class="pub-authors">${highlightMe(p.authors || [])}</div>
      <div class="pub-meta">${esc(p.journal || p.type || '')}${p.doi ? ` · ${esc(p.doi)}` : ''}</div>
    </div>
    <div class="pub-actions">${doi}${orcid}</div>
  </article>`;
}

function peerReviewItemCard(item) {
  const link = item.url || `https://orcid.org/${ORCID_ID}`;
  const label = item.reviewer_role ? item.reviewer_role.replace(/_/g, ' ') : (item.review_type || 'review');
  const source = item.source_name ? `<span class="service-note">Verified via ${esc(item.source_name)}</span>` : '';
  return `<article class="service-item review-row">
    <div class="review-year">${esc(formatReviewYear(item))}</div>
    <div class="review-detail">
      <p>${esc(label.charAt(0).toUpperCase() + label.slice(1))}</p>
      ${source}
    </div>
    <a class="review-link" href="${esc(link)}" target="_blank" rel="noreferrer">View ↗</a>
  </article>`;
}

function renderPublications() {
  const q = state.query.trim().toLowerCase();
  const filtered = state.publications.filter(p => {
    const hay = [p.title, p.journal, p.doi, ...(p.authors || [])].join(' ').toLowerCase();
    return (!q || hay.includes(q)) && (state.year === 'all' || String(p.year) === state.year);
  });
  $('#publicationList').innerHTML = filtered.map(pubRow).join('');
  $('#emptyState').hidden = filtered.length !== 0;
}

function populateYears() {
  const years = [...new Set(state.publications.map(p => p.year).filter(Boolean))].sort((a, b) => b - a);
  $('#yearFilter').innerHTML = '<option value="all">All years</option>' + years.map(y => `<option value="${y}">${y}</option>`).join('');
}

function updateStats(pubMeta = {}, peerMeta = {}) {
  const years = state.publications.map(p => Number(p.year)).filter(Boolean);
  $('#pubCount').textContent = state.publications.length || '0';
  $('#reviewCount').textContent = state.peerReviews.length || '0';
  $('#latestYear').textContent = years.length ? Math.max(...years) : '—';
  $('#yearSpan').textContent = years.length ? `${Math.min(...years)}–${Math.max(...years)}` : '—';

  const syncDates = [pubMeta.last_synced, peerMeta.last_synced].filter(Boolean).sort().reverse();
  if (syncDates.length) {
    const txt = `Last synced · ${formatSyncDate(syncDates[0])}`;
    $('#lastUpdated').textContent = txt;
    $('#syncText').textContent = txt;
  }
}

function renderPeerReviews() {
  const list = $('#peerReviewList');
  const empty = $('#peerReviewEmpty');
  if (!state.peerReviews.length) {
    list.innerHTML = '';
    empty.hidden = false;
    $('#peerReviewSummary').textContent = 'No verified public ORCID peer-review records are currently available.';
    return;
  }

  empty.hidden = true;
  const grouped = new Map();
  state.peerReviews.forEach(item => {
    const key = item.outlet || item.group_id || 'Peer review';
    const arr = grouped.get(key) || [];
    arr.push(item);
    grouped.set(key, arr);
  });

  const summary = [...grouped.entries()]
    .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
    .slice(0, 4)
    .map(([name, arr]) => `${name} (${arr.length})`)
    .join(' · ');

  $('#peerReviewSummary').textContent = `${state.peerReviews.length} verified review record${state.peerReviews.length > 1 ? 's' : ''}${summary ? ` · ${summary}` : ''}`;

  list.innerHTML = [...grouped.entries()]
    .sort((a, b) => {
      const ay = Math.max(...a[1].map(x => Number(x.completion_year) || 0));
      const by = Math.max(...b[1].map(x => Number(x.completion_year) || 0));
      return by - ay || b[1].length - a[1].length || a[0].localeCompare(b[0]);
    })
    .map(([name, arr], i) => {
      const latest = arr.slice().sort((a, b) => (Number(b.completion_year) || 0) - (Number(a.completion_year) || 0))[0];
      return `<article class="service-item grouped-service-item service-accent-${(i % 4) + 1}">
        <div class="service-item-top">
          <div>
            <h4>${esc(name)}</h4>
            <p>${arr.length} review${arr.length > 1 ? 's' : ''}${latest && latest.completion_year ? ` · latest ${esc(formatReviewYear(latest))}` : ''}</p>
          </div>
          <span class="count-pill">${arr.length}</span>
        </div>
        <div class="sub-item-list">
          ${arr.slice().sort((a, b) => (Number(b.completion_year) || 0) - (Number(a.completion_year) || 0) || (Number(b.completion_month) || 0) - (Number(a.completion_month) || 0)).map(peerReviewItemCard).join('')}
        </div>
      </article>`;
    }).join('');
}

async function loadJSON(path, fallback) {
  try {
    const res = await fetch(path, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn(`Failed to load ${path}`, err);
    return fallback;
  }
}

async function init() {
  $('#copyrightYear').textContent = new Date().getFullYear();
  applyTheme(localStorage.getItem(THEME_KEY) || 'system', false);

  $('#themeToggle').addEventListener('click', cycleTheme);
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if ((document.documentElement.dataset.themePreference || 'system') === 'system') {
      applyTheme('system', false);
    }
  });

  const [pubData, peerData] = await Promise.all([
    loadJSON('data/publications.json', { publications: [], meta: {} }),
    loadJSON('data/peer_reviews.json', { peer_reviews: [], meta: {} })
  ]);

  state.publications = (pubData.publications || []).sort((a, b) => (Number(b.year) || 0) - (Number(a.year) || 0) || (b.title || '').localeCompare(a.title || ''));
  state.peerReviews = (peerData.peer_reviews || []).sort((a, b) => (Number(b.completion_year) || 0) - (Number(a.completion_year) || 0) || (Number(b.completion_month) || 0) - (Number(a.completion_month) || 0));

  const featured = state.publications.filter(p => p.featured).slice(0, 4);
  $('#featuredList').innerHTML = (featured.length ? featured : state.publications.slice(0, 4)).map(featuredCard).join('');
  $('#featuredWrap').hidden = state.publications.length === 0;

  if (!state.publications.length) {
    $('#publicationList').innerHTML = '<p class="empty-state">Publication data could not be loaded. Run the ORCID sync workflow once.</p>';
  } else {
    populateYears();
    renderPublications();
  }

  updateStats(pubData.meta || {}, peerData.meta || {});
  renderPeerReviews();

  $('#searchInput').addEventListener('input', e => {
    state.query = e.target.value;
    renderPublications();
  });
  $('#yearFilter').addEventListener('change', e => {
    state.year = e.target.value;
    renderPublications();
  });
}

init();
