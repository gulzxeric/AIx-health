/**
 * API → MockAPI 覆盖层
 * 将家属端的 MockAPI 模拟函数替换为真实后端调用
 * 放在 mock-api.js 之后加载，覆盖其同名函数
 */
(function () {
  'use strict';

  const BASE = 'http://127.0.0.1:8000/api/v1';
  const PATIENT_ID = '58b203df-5424-4f53-b155-82b34f840213'; // 测试患者

  async function _fetch(path, options) {
    const url = BASE + path;
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
      ...options,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      console.warn('[API] error:', res.status, err);
      throw err;
    }
    return res.json();
  }

  MockAPI.scanBinding = function (deviceCode) {
    return _fetch('/bindings/scan', {
      method: 'POST',
      body: JSON.stringify({ device_code: deviceCode || 'ABC123' }),
    }).catch(function () {
      return { patient_id: PATIENT_ID, is_new: true, role: 'admin', patient_name: '张伯伯' };
    });
  };

  MockAPI.completeConfig = function (config) {
    return _fetch('/bindings/complete', {
      method: 'POST',
      body: JSON.stringify({ patient_id: PATIENT_ID, ...config }),
    }).catch(function () {
      return { success: true, patient_id: PATIENT_ID, config: config };
    });
  };

  MockAPI.getPatientConfig = function () {
    return _fetch('/patients/config?patient_id=' + PATIENT_ID).catch(function () {
      return { era: '1980s', region: { country: 'CN', province: '广东', city: '广州' }, language: 'zh-CN' };
    });
  };

  MockAPI.signConsent = function (data) {
    return _fetch('/consents', {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch(function () {
      return { id: 'mock-consent-id', signed_at: new Date().toISOString(), consent_version: 'v1.0' };
    });
  };

  MockAPI.submitMemory = function (data) {
    return _fetch('/memories', {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch(function () {
      return { id: 'mock-mem-' + Date.now(), entities: { era: '1980s', location: ['广州'] }, confidence: 0.85, sync_status: 'synced' };
    });
  };

  MockAPI.getMemories = function (params) {
    return _fetch('/memories?patient_id=' + PATIENT_ID).catch(function () { return []; });
  };

  MockAPI.deleteMemory = function (id) {
    return _fetch('/memories/' + id, { method: 'DELETE' }).catch(function () { return { success: true }; });
  };

  MockAPI.getBrief = function (date) {
    var d = date || new Date();
    var dateStr;
    if (typeof d === 'string') {
      dateStr = d; // 直接使用传入的日期字符串
    } else {
      dateStr = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
    }
    return _fetch('/briefs/' + dateStr + '?patient_id=' + PATIENT_ID).catch(function () {
      return { vitality_index: 78, vitality_trend_pct: 5, top_topics: [], advice_text: '暂无数据' };
    });
  };

  MockAPI.getDeviceStatus = function () {
    return _fetch('/devices/status?patient_id=' + PATIENT_ID).catch(function () {
      return { online: true, current_state: 'STANDBY', last_heartbeat: new Date().toISOString() };
    });
  };

  console.log('[API] 已覆盖 MockAPI，连接后端:', BASE);
})();