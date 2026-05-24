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
      if (state[field] === item.value) {
        state[field] = null;
      } else {
        state[field] = item.value;
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
      if (d.error) { alert(d.error); return; }
      renderResults(d);
    });
}

function renderResults(data) {
  var container = document.getElementById('results-container');
  var pagination = document.getElementById('pagination');

  if (!data.questions || data.questions.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>未找到匹配的题目</p></div>';
    pagination.innerHTML = '';
    document.getElementById('selected-count').textContent = '0';
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
}

function renderCard(q) {
  var badges = '';
  if (q.year) badges += '<span class="badge badge-year">' + q.year + '</span>';
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

  return '<div class="question-card" onclick="showDetail(\'' + q.id + '\')">'
    + '<div class="card-header"><span class="question-num">第' + q.question_num + '题</span><div class="badges">' + badges + '</div></div>'
    + '<div class="card-stem">' + stem + '</div>'
    + (topicsHtml ? '<div class="card-topics">' + topicsHtml + '</div>' : '')
    + '<div class="card-answer" onclick="event.stopPropagation()"><span class="answer-toggle" onclick="toggleAnswer(this)">▼ 查看答案</span><span class="answer-text" style="display:none">' + escapeHtml(q.answer || '') + '</span></div>'
    + '</div>';
}

function toggleAnswer(el) {
  var textEl = el.nextElementSibling;
  if (textEl.style.display === 'none') {
    textEl.style.display = 'inline'; el.textContent = '▲ 隐藏答案';
  } else {
    textEl.style.display = 'none'; el.textContent = '▼ 查看答案';
  }
}

function goPage(p) { state.page = p; doSearch(); window.scrollTo(0, 0); }
function changeSize(s) { state.size = parseInt(s); state.page = 1; doSearch(); }

function showDetail(qId) {
  fetch('/api/question/' + qId)
    .then(function(r) { return r.json(); })
    .then(function(q) {
      var html = '<h2>第' + q.question_num + '题 <small>' + (q.q_type || '') + '</small></h2>';
      html += '<div class="detail-meta">' + q.year + '年 ' + q.province + ' ' + q.paper_type + '</div>';
      html += '<div class="detail-stem">' + escapeHtml(q.stem || '') + '</div>';
      if (q.options && q.options.length) {
        html += '<div class="detail-options"><ul>';
        q.options.forEach(function(o) {
          for (var k in o) { html += '<li><strong>' + k + '.</strong> ' + escapeHtml(o[k]) + '</li>'; }
        });
        html += '</ul></div>';
      }
      html += '<div class="detail-section"><h3>答案</h3><p>' + escapeHtml(q.answer || '') + '</p></div>';
      if (q.explanation) html += '<div class="detail-section"><h3>解析</h3><p>' + escapeHtml(q.explanation) + '</p></div>';
      if (q.topics) html += '<div class="detail-section"><h3>知识点</h3><p>' + escapeHtml(q.topics) + '</p></div>';
      document.getElementById('modal-body').innerHTML = html;
      document.getElementById('detail-modal').style.display = 'flex';
    });
}

function closeModal() { document.getElementById('detail-modal').style.display = 'none'; }
document.addEventListener('click', function(e) { if (e.target.id === 'detail-modal') closeModal(); });

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
