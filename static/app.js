var state = { year: null, province: null, q_type: null, keyword: '', page: 1, size: 15 };

fetch('/api/filters')
  .then(function(r) { return r.json(); })
  .then(function(d) {
    renderFilterTags('filter-years', d.years, 'year');
    renderFilterTags('filter-provinces', d.provinces, 'province');
    renderFilterTags('filter-types', d.q_types, 'q_type');
    doSearch();
  });

document.getElementById('search-input').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') { state.keyword = this.value.trim(); state.page = 1; doSearch(); }
});
document.getElementById('search-btn').addEventListener('click', function() {
  state.keyword = document.getElementById('search-input').value.trim();
  state.page = 1;
  doSearch();
});

function renderFilterTags(containerId, items, field) {
  var container = document.getElementById(containerId);
  items.forEach(function(item) {
    var tag = document.createElement('span');
    tag.className = 'filter-tag';
    tag.textContent = item.value + ' (' + item.count + ')';
    tag.addEventListener('click', function() {
      var wasActive = tag.classList.contains('active');
      
      // Clear active styling in the same filter section
      container.querySelectorAll('.filter-tag').forEach(function(el) {
        el.classList.remove('active');
      });
      
      if (wasActive) {
        state[field] = null;
      } else {
        state[field] = item.value;
        tag.classList.add('active');
      }
      state.page = 1;
      updateSelectedDisplay();
      doSearch();
    });
    container.appendChild(tag);
  });
}

function updateSelectedDisplay() {
  var summary = document.getElementById('filter-summary');
  var tags = document.getElementById('selected-tags');
  var parts = [];
  if (state.year) parts.push(state.year + '年');
  if (state.province) parts.push(state.province);
  if (state.q_type) parts.push(state.q_type);
  if (parts.length > 0) {
    summary.style.display = 'block';
    tags.textContent = parts.join(' · ');
  } else {
    summary.style.display = 'none';
  }
}

function doSearch() {
  var params = 'page=' + state.page + '&size=' + state.size;
  if (state.keyword) params += '&keyword=' + encodeURIComponent(state.keyword);
  if (state.year) params += '&year=' + state.year;
  if (state.province) params += '&province=' + encodeURIComponent(state.province);
  if (state.q_type) params += '&q_type=' + encodeURIComponent(state.q_type);

  fetch('/api/questions?' + params)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.error) {
        // Handle redirect or error in VIP expired
        if (d.code === 'VIP_REQUIRED') {
          var container = document.getElementById('results-container');
          container.innerHTML = '<div class="empty-state" style="border-color: var(--color-warning-border); background: var(--color-warning-bg);">'
            + '<i data-lucide="alert-circle" style="width: 32px; height: 32px; color: var(--color-warning); margin: 0 auto 12px; display: block;"></i>'
            + '<p style="color: var(--color-warning); font-weight: 600;">需要高级权限</p>'
            + '<p style="font-size: 13px; color: var(--text-secondary); margin-top: 6px;">试用期已过或激活码已过期。请充值激活 VIP 以获得无限试卷搜索特权。</p>'
            + '<a href="/api/vip/page" class="nav-link vip-charge-btn" style="display: inline-flex; margin-top: 14px; padding: 8px 20px;">'
            + '<i data-lucide="credit-card" class="link-icon"></i> 充值激活 VIP'
            + '</a>'
            + '</div>';
          document.getElementById('pagination').innerHTML = '';
          document.getElementById('selected-count').textContent = '0';
          if (window.lucide) window.lucide.createIcons();
          return;
        }
        alert(d.error);
        return;
      }
      renderResults(d);
    });
}

function renderResults(data) {
  var container = document.getElementById('results-container');
  var pagination = document.getElementById('pagination');

  if (!data.questions || data.questions.length === 0) {
    container.innerHTML = '<div class="empty-state">'
      + '<i data-lucide="search-code" style="width: 32px; height: 32px; color: var(--text-muted); margin: 0 auto 12px; display: block;"></i>'
      + '<p>未找到匹配的题目</p>'
      + '</div>';
    pagination.innerHTML = '';
    document.getElementById('selected-count').textContent = '0';
    if (window.lucide) window.lucide.createIcons();
    return;
  }

  document.getElementById('selected-count').textContent = data.total;

  var html = '<div class="result-count">共 ' + data.total + ' 条结果</div>';
  data.questions.forEach(function(q) { html += renderCard(q); });
  container.innerHTML = html;

  var totalPages = Math.ceil(data.total / data.size);
  if (totalPages > 1) {
    var ph = '<div class="pagination-bar"><span>每页</span>';
    ph += '<select onchange="changeSize(this.value)">';
    [15, 30, 50].forEach(function(s) {
      ph += '<option value="' + s + '"' + (state.size === s ? ' selected' : '') + '>' + s + '</option>';
    });
    ph += '</select><span>条</span>';
    ph += '<span class="page-info">共 ' + data.total + ' 条，第 ' + data.page + '/' + totalPages + ' 页</span>';
    ph += '<span class="page-btns">';
    for (var p = 1; p <= totalPages; p++) {
      if (p === data.page) {
        ph += '<span class="page-btn active">' + p + '</span>';
      } else {
        ph += '<span class="page-btn" onclick="goPage(' + p + ')">' + p + '</span>';
      }
    }
    ph += '</span></div>';
    pagination.innerHTML = ph;
  } else {
    pagination.innerHTML = '';
  }

  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderCard(q) {
  var badges = '';
  if (q.year) badges += '<span class="badge badge-year">' + q.year + '年</span>';
  if (q.province) badges += '<span class="badge badge-prov">' + q.province + '</span>';
  if (q.q_type) badges += '<span class="badge badge-qtype">' + q.q_type + '</span>';

  var topicsHtml = '';
  if (q.topics) {
    q.topics.split(/\s+/).filter(Boolean).forEach(function(t) {
      topicsHtml += '<span class="topic-tag">' + escapeHtml(t) + '</span>';
    });
  }

  var stem = escapeHtml(q.stem || '');
  if (stem.length > 200) stem = stem.substring(0, 200) + '...';

  // Subscript molecular tags rendering helper
  stem = formatChemistryFormulas(stem);

  return '<div class="question-card" onclick="showDetail(\'' + q.id + '\')">'
    + '<div class="card-header"><span class="question-num">第' + q.question_num + '题</span><div class="badges">' + badges + '</div></div>'
    + '<div class="card-stem">' + stem + '</div>'
    + (topicsHtml ? '<div class="card-topics">' + topicsHtml + '</div>' : '')
    + '<div class="card-answer" onclick="event.stopPropagation()">'
    + '<span class="answer-toggle" onclick="toggleAnswer(this)" style="cursor:pointer; display:inline-flex; align-items:center; gap:4px; padding: 4px 8px; background: rgba(95,92,255,0.06); border: 1px solid rgba(95,92,255,0.12); border-radius: 4px;">'
    + '<i data-lucide="eye" style="width: 13px; height: 13px; color: var(--color-primary);"></i>'
    + '<span>▼ 查看答案</span>'
    + '</span>'
    + '<span class="answer-text" style="display:none">' + escapeHtml(q.answer || '') + '</span>'
    + '</div>'
    + '</div>';
}

function toggleAnswer(el) {
  var textEl = el.nextElementSibling;
  var iconEl = el.querySelector('i');
  var labelEl = el.querySelector('span');
  if (textEl.style.display === 'none') {
    textEl.style.display = 'block'; 
    labelEl.textContent = '▲ 隐藏答案';
    if (iconEl) {
      iconEl.setAttribute('data-lucide', 'eye-off');
      if (window.lucide) window.lucide.createIcons();
    }
  } else {
    textEl.style.display = 'none'; 
    labelEl.textContent = '▼ 查看答案';
    if (iconEl) {
      iconEl.setAttribute('data-lucide', 'eye');
      if (window.lucide) window.lucide.createIcons();
    }
  }
}

function goPage(p) { state.page = p; doSearch(); window.scrollTo(0, 0); }
function changeSize(s) { state.size = parseInt(s); state.page = 1; doSearch(); }

function showDetail(qId) {
  fetch('/api/question/' + qId)
    .then(function(r) { return r.json(); })
    .then(function(q) {
      var html = '<h2>第' + q.question_num + '题 <small>' + (q.q_type || '') + '</small></h2>';
      html += '<div class="detail-meta">';
      html += '<i data-lucide="calendar" style="width:13px;height:13px;vertical-align:middle;margin-right:4px;"></i>' + q.year + '年 &middot; ';
      html += '<i data-lucide="map-pin" style="width:13px;height:13px;vertical-align:middle;margin-right:4px;"></i>' + q.province + ' &middot; ';
      html += '<i data-lucide="file-text" style="width:13px;height:13px;vertical-align:middle;margin-right:4px;"></i>' + q.paper_type;
      html += '</div>';
      
      var stem = formatChemistryFormulas(escapeHtml(q.stem || ''));
      html += '<div class="detail-stem">' + stem + '</div>';
      
      if (q.options && q.options.length) {
        html += '<div class="detail-options"><ul>';
        q.options.forEach(function(o) {
          for (var k in o) { 
            html += '<li><strong>' + k + '</strong> ' + formatChemistryFormulas(escapeHtml(o[k])) + '</li>'; 
          }
        });
        html += '</ul></div>';
      }
      
      html += '<div class="detail-section detail-section-answer">';
      html += '<h3><i data-lucide="check-circle" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle; margin-right: 4px;"></i> 答案</h3>';
      html += '<p>' + escapeHtml(q.answer || '') + '</p></div>';
      
      if (q.explanation) {
        html += '<div class="detail-section detail-section-explanation">';
        html += '<h3><i data-lucide="book-open" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle; margin-right: 4px;"></i> 解析</h3>';
        html += '<p>' + formatChemistryFormulas(escapeHtml(q.explanation)).replace(/\n/g, '<br>') + '</p></div>';
      }
      
      if (q.topics) {
        var tagsHtml = '';
        q.topics.split(/\s+/).filter(Boolean).forEach(function(t) {
          tagsHtml += '<span class="topic-tag">' + escapeHtml(t) + '</span>';
        });
        html += '<div class="detail-section detail-section-topics">';
        html += '<h3><i data-lucide="tag" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle; margin-right: 4px;"></i> 知识点</h3>';
        html += '<div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:6px;">' + tagsHtml + '</div></div>';
      }
      
      document.getElementById('modal-body').innerHTML = html;
      document.getElementById('detail-modal').style.display = 'flex';
      
      if (window.lucide) {
        window.lucide.createIcons();
      }
    });
}

function closeModal() { document.getElementById('detail-modal').style.display = 'none'; }
document.addEventListener('click', function(e) { if (e.target.id === 'detail-modal') closeModal(); });

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

/* Helper to convert simple chemical signs (e.g. H2O, CO2, SO42-, Fe3+) to nice subscript/superscript markup in templates */
function formatChemistryFormulas(text) {
  if (!text) return '';
  // Subscript for standard chemical patterns (like H2O, C2H5OH, CO2, H2SO4, NH3)
  // Matching elements followed by numbers, but not inside HTML tags.
  // Look for symbols: H, He, Li, Be, B, C, N, O, F, Ne, Na, Mg, Al, Si, P, S, Cl, Ar, K, Ca, Sc, Ti, V, Cr, Mn, Fe, Co, Ni, Cu, Zn, Ga, Ge, As, Se, Br, Kr, Rb, Sr, Y, Zr, Nb, Mo, Tc, Ru, Rh, Pd, Ag, Cd, In, Sn, Sb, Te, I, Xe, Cs, Ba...
  // We can write a regular expression matching common element letters followed by digits:
  // e.g., (H|C|O|N|S|P|F|Cl|Br|I|Na|Mg|Al|Fe|Cu|Zn|Ca|Ag|Ba|K|Si|Mn|Cr|Ni|Pb)(2|3|4|5|6|7|8|9|10|11|12|18)
  var commonElements = '(?:H|He|Li|Be|B|C|N|O|F|Ne|Na|Mg|Al|Si|P|S|Cl|Ar|K|Ca|Sc|Ti|V|Cr|Mn|Fe|Co|Ni|Cu|Zn|Ga|Ge|As|Se|Br|Kr|Ag|Ba|I|Pb)';
  var regex = new RegExp('\\b(' + commonElements + ')(\\d+)\\b', 'g');
  text = text.replace(regex, '$1<sub>$2</sub>');
  
  // Handled double elements like C2H5OH, Ca(OH)2 where the digit isn't necessarily \b.
  // Let's matching elements followed by numbers anywhere except if it's part of HTML tag.
  var regex2 = new RegExp('(' + commonElements + ')(\\d+)(?![^<]*>)', 'g');
  text = text.replace(regex2, '$1<sub>$2</sub>');
  
  // Handle brackets followed by numbers e.g. (OH)2
  text = text.replace(/(\))(\d+)(?![^<]*>)/g, '$1<sub>$2</sub>');
  
  // Handle ionic charges e.g. H+, Fe3+, OH-, SO42-
  // Match a digit + +/-, or just +/- after a letter/subscript
  text = text.replace(/(\b|<sub>\d+<\/sub>)([a-zA-Z]|\))(\d*[+\-])(?![^<]*>)/g, '$1$2<sup>$3</sup>');
  
  return text;
}
