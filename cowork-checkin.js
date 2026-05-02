/* ============================================================
 * 配搭打卡互動 (cowork-checkin.js)
 *
 * 競賽窗口（台灣時間）：
 *   開始：每週日 11:30
 *   結束：週一 23:00
 *   循環：每週一次
 *
 * 功能：
 * - 競賽中：可打卡（含確認）+ 可撤回 + 即時排行榜 + 倒數結束
 * - 休息期：禁止操作 + 顯示上週最終排行榜 + 倒數下次開始
 * - 30 秒輪詢，看別人的動作
 * ============================================================ */

(function () {
  'use strict';

  // ====== Supabase 設定 ======
  const SUPABASE_URL = 'https://hiytxefiylgsjehzxglw.supabase.co';
  const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhpeXR4ZWZpeWxnc2plaHp4Z2x3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc1NTcyMzEsImV4cCI6MjA5MzEzMzIzMX0.Q3ll5Kav_yxad_GpksNE70SPluRj8NJl67Eu9-hygsw';
  const STORAGE_KEY = 'cowork_checkin_user';

  // ====== 競賽窗口設定（台灣時間 UTC+8） ======
  const TW_OFFSET_MS = 8 * 3600000;
  const HOUR_MS = 3600000;
  const DAY_MS = 86400000;
  // 開始：週日 11:30 → 結束：週一 23:00（共 35.5 小時）
  const COMP_START_HOUR = 11;
  const COMP_START_MIN = 30;
  const COMP_DURATION_HOURS = 35.5;

  const POLL_INTERVAL_MS = 30000;     // 別人打卡：30 秒輪詢一次
  const TICK_INTERVAL_MS = 1000;      // 倒數 + 狀態切換：每秒檢查

  const ZONE_LABELS = {
    y1: '青一', y2: '青二', y3: '青三',
    hs1: '高一', hs2: '高二', hs3: '高三',
    ms1: '國一', ms2: '國二',
  };

  // ====== 從 update_dashboard.py 注入 ======
  const dataWeekLabel = window.COWORK_CURRENT_WEEK || '';   // 例 '4月第四週'
  const membersByZone = window.COWORK_MEMBERS || {};

  const nameToZone = {};
  for (const [zone, names] of Object.entries(membersByZone)) {
    for (const name of names) nameToZone[name] = zone;
  }

  // ====== 狀態 ======
  let supabase = null;
  let checkins = [];
  let selectedName = localStorage.getItem(STORAGE_KEY) || '';
  let competitionState = null;
  let pollTimer = null;
  let tickTimer = null;
  let lastLoadedWeekKey = null;

  // ====== 工具：時間 ======
  function pad(n) { return String(n).padStart(2, '0'); }

  // 把 epoch 轉成「假裝是 UTC 的台灣時間」Date 物件，
  // 之後讀 getUTCXxx() 等於讀台灣本地時刻
  function epochToTw(epoch) { return new Date(epoch + TW_OFFSET_MS); }

  // 反向：台灣時間「假裝是 UTC 的毫秒數」→ 真實 epoch
  function twToEpoch(twMs) { return twMs - TW_OFFSET_MS; }

  function ymdOfTwDate(twDate) {
    return `${twDate.getUTCFullYear()}-${pad(twDate.getUTCMonth() + 1)}-${pad(twDate.getUTCDate())}`;
  }

  // 把 ISO 字串顯示成台灣時間 M/D HH:MM
  function fmtTime(iso) {
    const tw = epochToTw(new Date(iso).getTime());
    return `${pad(tw.getUTCMonth() + 1)}/${pad(tw.getUTCDate())} ${pad(tw.getUTCHours())}:${pad(tw.getUTCMinutes())}`;
  }

  function fmtTimeShort(iso) {
    const tw = epochToTw(new Date(iso).getTime());
    return `${pad(tw.getUTCHours())}:${pad(tw.getUTCMinutes())}`;
  }

  function fmtDateRange(weekKey) {
    // weekKey = 'YYYY-MM-DD' (週日)
    // 顯示 'M/D - M/D'（週日 ~ 週一）
    const [y, m, d] = weekKey.split('-').map(Number);
    const sunDate = new Date(Date.UTC(y, m - 1, d));
    const monDate = new Date(sunDate.getTime() + DAY_MS);
    return `${pad(sunDate.getUTCMonth() + 1)}/${pad(sunDate.getUTCDate())} - ${pad(monDate.getUTCMonth() + 1)}/${pad(monDate.getUTCDate())}`;
  }

  function fmtCountdown(ms) {
    if (ms < 0) ms = 0;
    const totalSec = Math.floor(ms / 1000);
    const days = Math.floor(totalSec / 86400);
    const hours = Math.floor((totalSec % 86400) / 3600);
    const mins = Math.floor((totalSec % 3600) / 60);
    const secs = totalSec % 60;
    if (days > 0) return `${days} 天 ${hours} 小時 ${mins} 分`;
    if (hours > 0) return `${hours}:${pad(mins)}:${pad(secs)}`;
    return `${pad(mins)}:${pad(secs)}`;
  }

  // ====== 競賽狀態判定 ======
  function getCompetitionState(now = Date.now()) {
    const tw = epochToTw(now);
    const day = tw.getUTCDay();          // 0 = 週日

    // 本週日 00:00（台灣）對應的「假 UTC 物件」
    const thisSunMidnightTw = new Date(tw.getTime());
    thisSunMidnightTw.setUTCHours(0, 0, 0, 0);
    thisSunMidnightTw.setUTCDate(thisSunMidnightTw.getUTCDate() - day);

    // 本週日 11:30 → 真實 epoch
    const thisSundayStart = twToEpoch(thisSunMidnightTw.getTime() + (COMP_START_HOUR + COMP_START_MIN / 60) * HOUR_MS);
    // 本週一 23:00 = 週日 00:00 + 47h
    const thisCompEnd = twToEpoch(thisSunMidnightTw.getTime() + 47 * HOUR_MS);

    if (now >= thisSundayStart && now <= thisCompEnd) {
      return {
        state: 'ACTIVE',
        weekKey: ymdOfTwDate(thisSunMidnightTw),
        startsAt: new Date(thisSundayStart),
        endsAt: new Date(thisCompEnd),
      };
    }

    // INACTIVE：找上一輪 + 下一輪
    let lastSunMidnightTw, nextStartEpoch;
    if (now < thisSundayStart) {
      // 還沒到本週日 11:30 → 上一輪是上週日
      lastSunMidnightTw = new Date(thisSunMidnightTw.getTime() - 7 * DAY_MS);
      nextStartEpoch = thisSundayStart;
    } else {
      // 已過本週一 23:00 → 上一輪就是本週日
      lastSunMidnightTw = thisSunMidnightTw;
      nextStartEpoch = thisSundayStart + 7 * DAY_MS;
    }

    return {
      state: 'INACTIVE',
      lastWeekKey: ymdOfTwDate(lastSunMidnightTw),
      nextStart: new Date(nextStartEpoch),
    };
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  // ====== 渲染 ======
  function renderBar() {
    const $bar = document.getElementById('checkin-bar');
    if (!$bar) return;
    $bar.classList.toggle('inactive', competitionState.state === 'INACTIVE');

    if (competitionState.state === 'INACTIVE') {
      const cd = competitionState.nextStart.getTime() - Date.now();
      $bar.innerHTML = `
        <span class="ck-label">🔒 競賽休息中</span>
        <span class="ck-countdown" id="ck-countdown">🏁 距下次開始 ${escapeHtml(fmtCountdown(cd))}</span>
        <div class="ck-msg" id="ck-msg">下次競賽：${escapeHtml(weekdayLabel(competitionState.nextStart))} 11:30</div>
      `;
      return;
    }

    // ACTIVE
    const myCheckin = checkins.find((c) => c.member_name === selectedName);
    const cd = competitionState.endsAt.getTime() - Date.now();
    const cdClass = cd < 60 * 60 * 1000 ? 'ck-countdown urgent' : 'ck-countdown';

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

    let actionHtml;
    if (!selectedName) {
      actionHtml = '<button disabled>請先選擇姓名</button>';
    } else if (myCheckin) {
      actionHtml = `
        <button class="btn-done" disabled>✅ 已於 ${escapeHtml(fmtTime(myCheckin.checked_at))} 完成</button>
        <button id="ck-undo-btn" title="撤回打卡">↶ 撤回</button>
      `;
    } else {
      actionHtml = '<button id="ck-btn">✋ 我點完本週</button>';
    }

    $bar.innerHTML = `
      <span class="ck-label">我是</span>
      <select id="ck-select" aria-label="選擇您的姓名">${optionsHtml}</select>
      ${actionHtml}
      <span class="${cdClass}" id="ck-countdown">⏱️ 競賽剩 ${escapeHtml(fmtCountdown(cd))}</span>
      <div class="ck-msg" id="ck-msg"></div>
    `;

    document.getElementById('ck-select').addEventListener('change', (e) => {
      selectedName = e.target.value;
      if (selectedName) localStorage.setItem(STORAGE_KEY, selectedName);
      else localStorage.removeItem(STORAGE_KEY);
      renderBar();
    });

    const btn = document.getElementById('ck-btn');
    if (btn) btn.addEventListener('click', handleCheckin);
    const undoBtn = document.getElementById('ck-undo-btn');
    if (undoBtn) undoBtn.addEventListener('click', handleUndo);
  }

  function weekdayLabel(d) {
    const tw = epochToTw(d.getTime());
    const days = ['日', '一', '二', '三', '四', '五', '六'];
    return `週${days[tw.getUTCDay()]}`;
  }

  function renderLeaderboard() {
    const $lb = document.getElementById('leaderboard');
    if (!$lb) return;

    const totalAll = Object.values(membersByZone).reduce((s, arr) => s + arr.length, 0);
    const done = [...checkins].sort((a, b) =>
      new Date(a.checked_at) - new Date(b.checked_at)
    );

    let title;
    if (competitionState.state === 'ACTIVE') {
      title = `🏆 本週競賽排行榜 (${escapeHtml(fmtDateRange(competitionState.weekKey))})`;
    } else {
      title = `🏁 上週最終排行榜 (${escapeHtml(fmtDateRange(competitionState.lastWeekKey))})`;
    }

    let html = `<div class="lb-title">${title} <span class="lb-stat">${done.length} / ${totalAll}</span></div>`;

    if (done.length === 0) {
      html += '<div class="lb-empty">';
      html += competitionState.state === 'ACTIVE' ? '還沒有人打卡，搶頭香！' : '上週沒有人打卡';
      html += '</div>';
    } else {
      html += '<div class="lb-list">';
      done.forEach((c, i) => {
        let medal, cls;
        if (i === 0) { medal = '🥇'; cls = 'medal-gold'; }
        else if (i === 1) { medal = '🥈'; cls = 'medal-silver'; }
        else if (i === 2) { medal = '🥉'; cls = 'medal-bronze'; }
        else { medal = `${i + 1}.`; cls = ''; }

        const zoneLabel = ZONE_LABELS[c.zone] || c.zone;
        html += `<span class="lb-item ${cls}">${medal} ${escapeHtml(fmtTimeShort(c.checked_at))} ${escapeHtml(c.member_name)}（${escapeHtml(zoneLabel)}）</span>`;
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
        status.textContent = competitionState.state === 'ACTIVE' ? '⏳ 待點名' : '— 未打卡';
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
        const e2 = document.getElementById('ck-msg');
        if (e2) { e2.textContent = ''; e2.className = 'ck-msg'; }
      }, 4000);
    }
  }

  function updateCountdownText() {
    const $cd = document.getElementById('ck-countdown');
    if (!$cd) return;
    if (competitionState.state === 'ACTIVE') {
      const cd = competitionState.endsAt.getTime() - Date.now();
      $cd.textContent = `⏱️ 競賽剩 ${fmtCountdown(cd)}`;
      $cd.classList.toggle('urgent', cd < 60 * 60 * 1000);
    } else {
      const cd = competitionState.nextStart.getTime() - Date.now();
      $cd.textContent = `🏁 距下次開始 ${fmtCountdown(cd)}`;
    }
  }

  // ====== 動作 ======
  async function handleCheckin() {
    if (!selectedName) return;
    if (competitionState.state !== 'ACTIVE') {
      showMsg('競賽尚未開始或已結束', 'error');
      return;
    }
    const zone = nameToZone[selectedName];
    if (!zone) {
      showMsg('找不到您的小區，請聯絡管理員', 'error');
      return;
    }

    if (!confirm(`確定以「${selectedName}」的身分打卡嗎？\n\n打卡後可以撤回，但只能在競賽進行中。`)) {
      return;
    }

    const btn = document.getElementById('ck-btn');
    if (btn) {
      btn.disabled = true;
      btn.textContent = '送出中...';
    }

    const { data, error } = await supabase
      .from('cowork_checkins')
      .insert({ week: competitionState.weekKey, zone, member_name: selectedName })
      .select()
      .single();

    if (error) {
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

  async function handleUndo() {
    if (!selectedName) return;
    if (competitionState.state !== 'ACTIVE') {
      showMsg('競賽已結束，無法撤回', 'error');
      return;
    }

    const myCheckin = checkins.find((c) => c.member_name === selectedName);
    if (!myCheckin) {
      showMsg('找不到打卡紀錄', 'error');
      return;
    }

    if (!confirm(`確定撤回「${selectedName}」的打卡嗎？\n\n撤回後可以重新打卡，但完成時間會重新計算。`)) {
      return;
    }

    const undoBtn = document.getElementById('ck-undo-btn');
    if (undoBtn) {
      undoBtn.disabled = true;
      undoBtn.textContent = '撤回中...';
    }

    const { error } = await supabase
      .from('cowork_checkins')
      .delete()
      .eq('id', myCheckin.id);

    if (error) {
      showMsg(`撤回失敗：${error.message}`, 'error');
      if (undoBtn) {
        undoBtn.disabled = false;
        undoBtn.textContent = '↶ 撤回';
      }
      return;
    }

    showMsg('已撤回打卡', 'success');
    checkins = checkins.filter((c) => c.id !== myCheckin.id);
    renderAll();
  }

  async function loadCheckins() {
    const targetWeek = competitionState.state === 'ACTIVE'
      ? competitionState.weekKey
      : competitionState.lastWeekKey;

    const { data, error } = await supabase
      .from('cowork_checkins')
      .select('*')
      .eq('week', targetWeek)
      .order('checked_at', { ascending: true });

    if (error) {
      console.error('[cowork-checkin] load failed:', error);
      return;
    }
    checkins = data || [];
    lastLoadedWeekKey = targetWeek;
  }

  // 每秒：更新倒數 + 偵測狀態切換
  function startTick() {
    if (tickTimer) clearInterval(tickTimer);
    tickTimer = setInterval(async () => {
      const newState = getCompetitionState();
      const targetWeek = newState.state === 'ACTIVE' ? newState.weekKey : newState.lastWeekKey;
      const stateChanged = newState.state !== competitionState.state || targetWeek !== lastLoadedWeekKey;

      if (stateChanged) {
        competitionState = newState;
        await loadCheckins();
        renderAll();
      } else {
        competitionState = newState;
        updateCountdownText();
      }
    }, TICK_INTERVAL_MS);
  }

  // 每 30 秒：拉一次最新打卡列表（看別人）
  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      if (document.hidden) return;
      const before = checkins.length;
      await loadCheckins();
      if (checkins.length !== before) renderAll();
    }, POLL_INTERVAL_MS);
  }

  // ====== 啟動 ======
  async function init() {
    if (!window.supabase) {
      console.error('[cowork-checkin] supabase-js 未載入');
      return;
    }

    supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    competitionState = getCompetitionState();

    await loadCheckins();
    renderAll();
    startTick();
    startPolling();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
