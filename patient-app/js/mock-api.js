/**
 * MockAPI - 模拟后端 API 层
 * ===========================
 * 用于纯前端演示和开发阶段。
 * 后续接入真实后端时，只需按相同接口签名替换此模块。
 *
 * @module MockAPI
 */

const MockAPI = (function () {
  'use strict';

  // ── 模拟数据 ──────────────────────────────────────────────────────

  /** 设备码 */
  const DEVICE_CODE = 'ABC123';

  /** 占位照片列表 - 使用 CSS 渐变模拟老照片风格 */
  const PHOTO_PLACEHOLDERS = [
    {
      id: 'photo-1',
      url: 'data:image/svg+xml,' + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">' +
        '<defs><linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">' +
        '<stop offset="0%" style="stop-color:#8B7355;stop-opacity:1" />' +
        '<stop offset="50%" style="stop-color:#C4A882;stop-opacity:1" />' +
        '<stop offset="100%" style="stop-color:#A0845C;stop-opacity:1" />' +
        '</linearGradient></defs>' +
        '<rect width="800" height="600" fill="url(#g1)"/>' +
        '<circle cx="350" cy="200" r="60" fill="#D2B48C" opacity="0.8"/>' +
        '<circle cx="450" cy="210" r="55" fill="#D2B48C" opacity="0.8"/>' +
        '<rect x="250" y="300" width="100" height="120" rx="5" fill="#A0522D" opacity="0.6"/>' +
        '<rect x="420" y="310" width="80" height="110" rx="5" fill="#8B4513" opacity="0.5"/>' +
        '<text x="400" y="500" text-anchor="middle" font-size="24" fill="#F5DEB3" font-family="serif">1985年·全家福</text>' +
        '</svg>'
      ),
      caption: '1985年·全家福',
      era: '1980s'
    },
    {
      id: 'photo-2',
      url: 'data:image/svg+xml,' + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">' +
        '<defs><linearGradient id="g2" x1="0%" y1="0%" x2="100%" y2="100%">' +
        '<stop offset="0%" style="stop-color:#6B8E7B;stop-opacity:1" />' +
        '<stop offset="50%" style="stop-color:#8FBC8F;stop-opacity:1" />' +
        '<stop offset="100%" style="stop-color:#5F9EA0;stop-opacity:1" />' +
        '</linearGradient></defs>' +
        '<rect width="800" height="600" fill="url(#g2)"/>' +
        '<rect x="200" y="250" width="120" height="80" rx="3" fill="#DEB887" opacity="0.7"/>' +
        '<rect x="450" y="230" width="130" height="90" rx="3" fill="#DEB887" opacity="0.7"/>' +
        '<circle cx="300" cy="150" r="30" fill="#FFD700" opacity="0.5"/>' +
        '<text x="400" y="500" text-anchor="middle" font-size="24" fill="#F0FFF0" font-family="serif">厂门口·老工友</text>' +
        '</svg>'
      ),
      caption: '厂门口·老工友',
      era: '1980s'
    },
    {
      id: 'photo-3',
      url: 'data:image/svg+xml,' + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">' +
        '<defs><linearGradient id="g3" x1="0%" y1="0%" x2="100%" y2="100%">' +
        '<stop offset="0%" style="stop-color:#B8860B;stop-opacity:1" />' +
        '<stop offset="50%" style="stop-color:#DAA520;stop-opacity:1" />' +
        '<stop offset="100%" style="stop-color:#CD853F;stop-opacity:1" />' +
        '</linearGradient></defs>' +
        '<rect width="800" height="600" fill="url(#g3)"/>' +
        '<circle cx="400" cy="180" r="70" fill="#FFE4B5" opacity="0.6"/>' +
        '<rect x="300" y="310" width="80" height="100" rx="5" fill="#B22222" opacity="0.5"/>' +
        '<rect x="420" y="320" width="70" height="90" rx="5" fill="#B22222" opacity="0.4"/>' +
        '<text x="400" y="520" text-anchor="middle" font-size="24" fill="#FFF8DC" font-family="serif">结婚照·1978</text>' +
        '</svg>'
      ),
      caption: '结婚照·1978',
      era: '1970s'
    },
    {
      id: 'photo-4',
      url: 'data:image/svg+xml,' + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">' +
        '<defs><linearGradient id="g4" x1="0%" y1="0%" x2="100%" y2="100%">' +
        '<stop offset="0%" style="stop-color:#708090;stop-opacity:1" />' +
        '<stop offset="50%" style="stop-color:#A9A9A9;stop-opacity:1" />' +
        '<stop offset="100%" style="stop-color:#778899;stop-opacity:1" />' +
        '</linearGradient></defs>' +
        '<rect width="800" height="600" fill="url(#g4)"/>' +
        '<rect x="180" y="200" width="160" height="100" rx="4" fill="#696969" opacity="0.6"/>' +
        '<rect x="460" y="220" width="140" height="80" rx="4" fill="#696969" opacity="0.5"/>' +
        '<text x="400" y="500" text-anchor="middle" font-size="24" fill="#E0E0E0" font-family="serif">供销社·1982</text>' +
        '</svg>'
      ),
      caption: '供销社·1982',
      era: '1980s'
    },
    {
      id: 'photo-5',
      url: 'data:image/svg+xml,' + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">' +
        '<defs><linearGradient id="g5" x1="0%" y1="0%" x2="100%" y2="100%">' +
        '<stop offset="0%" style="stop-color:#2F4F4F;stop-opacity:1" />' +
        '<stop offset="50%" style="stop-color:#556B2F;stop-opacity:1" />' +
        '<stop offset="100%" style="stop-color:#6B8E23;stop-opacity:1" />' +
        '</linearGradient></defs>' +
        '<rect width="800" height="600" fill="url(#g5)"/>' +
        '<circle cx="200" cy="150" r="40" fill="#FFD700" opacity="0.6"/>' +
        '<polygon points="400,200 300,400 500,400" fill="#228B22" opacity="0.5"/>' +
        '<rect x="520" y="300" width="60" height="80" rx="3" fill="#8B4513" opacity="0.5"/>' +
        '<text x="400" y="520" text-anchor="middle" font-size="24" fill="#F5FFFA" font-family="serif">下乡·知青点</text>' +
        '</svg>'
      ),
      caption: '下乡·知青点',
      era: '1970s'
    }
  ];

  /** 模拟配置 */
  const MOCK_CONFIG = {
    config: {
      era: '1980s',
      language: 'zh-CN',
      persona_name: '强叔'
    },
    asset_pack: {
      status: 'ready',
      photo_urls: PHOTO_PLACEHOLDERS.map(p => p.url)
    }
  };

  // ── 公共 API ──────────────────────────────────────────────────────

  return {

    /**
     * 获取设备码
     * @returns {string} 6 位设备码
     */
    getDeviceCode: function () {
      return DEVICE_CODE;
    },

    /**
     * 获取患者配置 + 资产包
     * 对应 GET /api/v1/patients/config
     * @returns {Promise<Object>} { config, asset_pack }
     */
    getConfig: function () {
      return new Promise(function (resolve) {
        setTimeout(function () {
          resolve(MOCK_CONFIG);
        }, 300); // 模拟网络延迟
      });
    },

    /**
     * 获取照片列表
     * 对应 GET /api/v1/photos
     * @returns {Promise<Array>} 照片数组 [{ id, url, caption, era }]
     */
    getPhotos: function () {
      return new Promise(function (resolve) {
        setTimeout(function () {
          resolve(PHOTO_PLACEHOLDERS);
        }, 200);
      });
    },

    /**
     * 发送对话消息
     * 对应 POST /api/v1/chat/message
     * @param {Object} data - { session_id, asr_text, photo_context }
     * @returns {Promise<Object>} { reply_text, reply_audio_url, persona, voice_source }
     */
    sendChatMessage: function (data) {
      return new Promise(function (resolve) {
        setTimeout(function () {
          // 模拟不同的回复
          var replies = [
            '今天天气不错啊，要不要出去走走？',
            '我记得你最爱吃糖葫芦了。',
            '那年厂里分房子，咱们抽到了三楼。',
            '阿珍昨天还念叨你来着。',
            '咱老街坊啊，就爱听你讲故事。'
          ];
          var idx = Math.floor(Math.random() * replies.length);
          resolve({
            reply_text: replies[idx],
            reply_audio_url: null,
            persona: '老街坊',
            voice_source: 'default'
          });
        }, 500 + Math.random() * 500);
      });
    },

    /**
     * 心跳
     * 对应 POST /api/v1/devices/heartbeat
     * @returns {Promise<Object>} { status: 'ok' }
     */
    heartbeat: function () {
      return new Promise(function (resolve) {
        resolve({ status: 'ok' });
      });
    },

    /**
     * 开始对话 session
     * 对应 POST /api/v1/chat/session/start
     * @returns {Promise<Object>} { session_id }
     */
    startSession: function () {
      return new Promise(function (resolve) {
        setTimeout(function () {
          resolve({ session_id: 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 8) });
        }, 200);
      });
    },

    /**
     * 结束对话 session
     * 对应 POST /api/v1/chat/session/end
     * @param {string} sessionId
     * @returns {Promise<Object>} { status: 'ok' }
     */
    endSession: function (sessionId) {
      return new Promise(function (resolve) {
        setTimeout(function () {
          resolve({ status: 'ok' });
        }, 100);
      });
    }
  };
})();

// 导出（浏览器环境作为全局变量）
window.MockAPI = MockAPI;
