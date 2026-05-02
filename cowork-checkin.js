/* ============================================================
 * 配搭打卡互動 (cowork-checkin.js)
 * - 全頁一個下拉 + 一個按鈕
 * - 寫入 Supabase cowork_checkins
 * - 排行榜 + 卡片狀態渲染
 * - 30 秒輪詢，看別人打卡
 * ============================================================ */

(function () {
  'use strict';

  // ====== 設定 ======
  const SUPABASE_URL = 'https://hiytxefiylgsjehzxglw.supabase.co';
  const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpeXR4ZWZpeWxnc2plaHp4Z2x3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTcyMzEsImV4cCI6MjA5MzEzMzIzMX0.Q3ll5Kav_yxad_GpksNE70SPluRj8NJl67Eu9-hygsw';
  const STORAGE_KEY = 'cowork_checkin_user';
  const POLL_INTERVAL_MS = 30000; // 30 秒輪詢

  const ZONE_LABELS = {
    y1: '青一', y2: '青二', y3: '青三',
    hs1: '高一', hs2: '高二', hs3: '高三',
    ms1: '國一', ms2: '國二',
  };

  // ====== 從 update_dashboard.py 注入的全域 ======
  const week = window.COWORK_CURRENT_WEEK || '';
  const membersByZone = window.COWORK_MEMBERS || {};

  // 反查表：name -> zone
  const nameToZone = {};
  for (const [zone, names] of Object.entries(membersByZone)) {
    for (const name of names) nameToZone[name] = zone;
  }

  // ====== 狀態 ======
  let supabase = null;
  let checkins = [];
  let selectedName = localStorage.getItem(STORAGE_KEY) || '';
  let pollTimer = null;

  // ====== 工具 ======
  function pad(n) { return String(n).padStart(2, '0'); }

  function fmtTime(iso) {
    const t = new Date(iso);
    return `${pad(t.getMonth() + 1)}/${pad(t.getDate())} ${pad(t.getHours())}:${pad(t.getMinutes())}`;
  }

  function fmtTimeShort(iso) {
    const t = new Date(iso);
    return `${pad(t.getHours())}:${pad(t.getMinutes())}`;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  // ====== UI 渲染 ======
  function renderBar() {
    const $bar = document.getElementById('checkin-bar');
    if (!$bar) return;

    const myCheckin = checkins.find((c) => c.member_name === selectedName);

    let optionsHtml = '<option value="">— 選擇您的姓名 —</option>';
    for (const [zone, names] of Object.entries(membersByZone)) {
      const label = ZONE_LABELS[zone] || zone;
      optionsHtml += `<optgroup label="${escapeHtml(label)}">`;
      for (const name of names) {
        const sel = name === selectedName ? ' selected' : '';
        optionsHtml += `<option value="${escapeHtml(name)}"${sel}>${escapeHtml(name)}</option>`;
      }
      optionsHtml += '</optgroup>';
    }

    let btnHtml;
    if (!selectedName) {
      btnHtml = '<button disabled>請先選擇姓名</button>';
    } else if (myCheckin) {
      btnHtml = `<button class="btn-done" disabled>✅ 已於 ${fmtTime(myCheckin.checked_at)} 完成</button>`;
    } else {
      btnHtml = '<button id="ck-btn">✋ 我點完本週</button>';
    }

    $bar.innerHTML = `
      <span class="ck-label">我是</span>
      <select id="ck-select" aria-label="選擇您的姓名">${optionsHtml}</select>
      ${btnHtml}
      <div class="ck-msg" id="ck-msg"></div>
    `;

    document.getElementById('ck-select').addEventListener('change', (e) => {
      selectedName = e.target.value;
      if (selectedName) {
        localStorage.setItem(STORAGE_KEY, selectedName);
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
      renderBar();
    });

    const btn = document.getElementById('ck-btn');
    if (btn) btn.addEventListener('click', handleCheckin);
  }

  function renderLeaderboard() {
    const $lb = document.getElementById('leaderboard');
    if (!$lb) return;

    const totalAll = Object.values(membersByZone).reduce((s, arr) => s + arr.length, 0);
    const done = [...checkins].sort((a, b) =>
      new Date(a.checked_at) - new Date(b.checked_at)
    );

    let html = `<div class="lb-title">🏆 本週完成排行榜 <span class="lb-stat">${done.length} / ${totalAll}</span></div>`;

    if (done.length === 0) {
      html += '<div class="lb-empty">還沒有人打卡，搶頭香！</div>';
    } else {
      html += '<div class="lb-list">';
      done.forEach((c, i) => {
        let medal, cls;
        if (i === 0) { medal = '🥇'; cls = 'medal-gold'; }
        else if (i === 1) { medal = '🥈'; cls = 'medal-silver'; }
        else if (i === 2) { medal = '🥉'; cls = 'medal-bronze'; }
        else { medal = `${i + 1}.`; cls = ''; }

        const zoneLabel = ZONE_LABELS[c.zone] || c.zone;
        html += `<span class="lb-item ${cls}">${medal} ${fmtTimeShort(c.checked_at)} ${escapeHtml(c.member_name)}（${escapeHtml(zoneLabel)}）</span>`;
      });
      html += '</div>';
    }

    $lb.innerHTML = html;
  }

  function renderCards() {
    const doneMap = {};
    for (const c of checkins) doneMap[c.member_name] = c.checked_at;

    document.querySelectorAll('.cm[data-name]').forEach((card) => {
      const name = card.dataset.name;
      let status = card.querySelector('.cm-checkin');
      if (!status) {
        status = document.createElement('div');
        status.className = 'cm-checkin';
        card.appendChild(status);
      }

      if (doneMap[name]) {
        status.className = 'cm-checkin done';
        status.textContent = `✅ ${fmtTime(doneMap[name])} 已點完`;
        card.classList.add('cm-done');
      } else {
        status.className = 'cm-checkin pending';
        status.textContent = '⏳ 待點名';
        card.classList.remove('cm-done');
      }
    });
  }

  function renderAll() {
    renderBar();
    renderLeaderboard();
    renderCards();
  }

  function showMsg(text, type) {
    const el = document.getElementById('ck-msg');
    if (!el) return;
    el.textContent = text;
    el.className = 'ck-msg ' + (type || '');
    if (type === 'success') {
      setTimeout(() => {
        el.textContent = '';
        el.className = 'ck-msg';
      }, 4000);
    }
  }

  // ====== 動作 ======
  async function handleCheckin() {
    if (!selectedName) return;
    const zone = nameToZone[selectedName];
    if (!zone) {
      showMsg('找不到您的小區，請聯絡管理員', 'error');
      return;
    }

    const btn = document.getElementById('ck-btn');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '送出中...';
    }

    const { data, error } = await supabase
      .from('cowork_checkins')
      .insert({ week, zone, member_name: selectedName })
      .select()
      .single();

    if (error) {
      // 23505 = unique_violation（已經打過卡了）
      if (error.code === '23505') {
        showMsg('您本週已經打過卡了', 'error');
        await loadCheckins();
        renderAll();
      } else {
        showMsg(`打卡失敗：${error.message}`, 'error');
        if (btn) {
          btn.disabled = false;
          btn.textContent = '✋ 我點完本週';
        }
      }
      return;
    }

    showMsg('🎉 打卡成功！', 'success');
    checkins.push(data);
    checkins.sort((a, b) => new Date(a.checked_at) - new Date(b.checked_at));
    renderAll();
  }

  async function loadCheckins() {
    const { data, error } = await supabase
      .from('cowork_checkins')
      .select('*')
      .eq('week', week)
      .order('checked_at', { ascending: true });

    if (error) {
      console.error('[cowork-checkin] load failed:', error);
      return;
    }
    checkins = data || [];
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      // 分頁不可見時跳過，省資源
      if (document.hidden) return;
      const before = checkins.length;
      await loadCheckins();
      // 只有資料數量變動才重渲染（避免無謂的 DOM 改動）
      if (checkins.length !== before) renderAll();
    }, POLL_INTERVAL_MS);
  }

  // ====== 啟動 ======
  async function init() {
    if (!week) {
      console.warn('[cowork-checkin] COWORK_CURRENT_WEEK 未設定，停用打卡功能');
      return;
    }
    if (!window.supabase) {
      console.error('[cowork-checkin] supabase-js 未載入');
      return;
    }

    supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

    await loadCheckins();
    renderAll();
    startPolling();
  }

  // 等 DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
