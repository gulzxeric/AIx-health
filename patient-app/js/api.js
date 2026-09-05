/**
 * API → MockAPI 覆盖层
 * 将 MockAPI 的模拟函数替换为真实后端调用
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

  // 覆盖 MockAPI 的同名函数
  MockAPI.getPhotos = function () {
    // 同步返回接口，但真实 API 是异步的，用缓存做桥接
    if (MockAPI._photosCache) return MockAPI._photosCache;
    _fetch('/photos?patient_id=' + PATIENT_ID).then(function (photos) {
      MockAPI._photosCache = photos;
    }).catch(function () {});
    return [];
  };

  MockAPI.getConfig = function () {
    return _fetch('/patients/config?patient_id=' + PATIENT_ID).then(function (data) {
      // 包装成前端期望的格式 { config, asset_pack }
      return {
        config: data,
        asset_pack: { status: 'ready', photo_urls: [], topic_library: [], prompt_anchors: [] }
      };
    }).catch(function () {
      return null;
    });
  };

  MockAPI.sendChatMessage = function (data) {
    return _fetch('/chat/message', {
      method: 'POST',
      body: JSON.stringify(data),
    }).catch(function () {
      return { reply_text: '抱歉，我现在有点累，晚点再聊吧。', reply_audio_url: null, persona: '老街坊', voice_source: 'default' };
    });
  };

  MockAPI.startSession = function () {
    return _fetch('/chat/session/start', {
      method: 'POST',
      body: JSON.stringify({ patient_id: PATIENT_ID }),
    }).catch(function () {
      return { session_id: 'mock-' + Date.now(), started_at: new Date().toISOString() };
    });
  };

  MockAPI.endSession = function (sessionId) {
    return _fetch('/chat/session/end', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId }),
    }).catch(function () {
      return { session_id: sessionId, duration_seconds: 0, status: 'ended' };
    });
  };

  MockAPI.heartbeat = function () {
    return _fetch('/devices/heartbeat', {
      method: 'POST',
      body: JSON.stringify({ patient_id: PATIENT_ID }),
    }).catch(function () {
      return { status: 'ok', server_time: new Date().toISOString() };
    });
  };

  console.log('[API] 已覆盖 MockAPI，连接后端:', BASE);
})();