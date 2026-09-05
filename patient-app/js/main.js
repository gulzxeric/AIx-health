/**
 * main.js - 患者端主应用逻辑
 * 初始化状态机、照片轮播、HUD面板，管理状态切换时的模块生命周期。
 * 所有 API 调用使用 MockAPI 模块。
 */

(function () {
  'use strict';

  var appEl = document.getElementById('app');
  var deviceCodeEl = document.getElementById('device-code');
  var qrCodeEl = document.getElementById('qr-code');
  var photoCarouselEl = document.getElementById('photo-carousel');
  var chatSubtitleEl = document.getElementById('chat-subtitle');
  var chatWaveEl = document.getElementById('chat-wave');
  var soothingOverlayEl = document.getElementById('soothing-overlay');

  var stateMachine = null;
  var photoCarousel = null;
  var hudPanel = null;
  var configPollTimer = null;
  var chatSimTimer = null;
  var waveAnimTimer = null;
  var chatting = false;
  var currentSessionId = null;

  function init() {
    console.log('[Main] 患者端应用启动');
    stateMachine = new StateMachine(STATES.COLD_START);
    hudPanel = new HudPanel({ appContainer: appEl });

    var photos = MockAPI.getPhotos();
    photoCarousel = new PhotoCarousel(photoCarouselEl, photos);

    stateMachine.addEventListener(onStateChange);
    setupColdStart();
    startConfigPolling();

    window.__debug = {
      stateMachine: stateMachine,
      photoCarousel: photoCarousel,
      hudPanel: hudPanel,
      triggerChat: function () { stateMachine.transition('speech_detected'); },
      triggerSoothing: function () { stateMachine.transition('negative_signal'); }
    };
  }

  function onStateChange(prev, next, action) {
    stopStateModules(prev);
    startStateModules(next);
    if (hudPanel && hudPanel.isVisible()) {
      hudPanel.updatePromptInfo('状态: ' + next + ' (动作: ' + action + ')');
    }
  }

  function stopStateModules(state) {
    switch (state) {
      case STATES.STANDBY: if (photoCarousel) photoCarousel.stop(); break;
      case STATES.CHAT: stopChat(); break;
      case STATES.SOOTHING: stopSoothing(); break;
    }
  }

  function startStateModules(state) {
    switch (state) {
      case STATES.COLD_START: setupColdStart(); break;
      case STATES.STANDBY: if (photoCarousel) photoCarousel.start(); break;
      case STATES.CHAT: startChat(); break;
      case STATES.SOOTHING: startSoothing(); break;
    }
  }

  // COLD_START
  function setupColdStart() {
    if (deviceCodeEl) deviceCodeEl.textContent = MockAPI.getDeviceCode();
    if (qrCodeEl) qrCodeEl.innerHTML = generateQRPlaceholder(MockAPI.getDeviceCode());
  }

  function generateQRPlaceholder(code) {
    var size = 160, cells = 11, cs = size / cells;
    var rects = [];
    for (var r = 0; r < cells; r++) {
      for (var c = 0; c < cells; c++) {
        var hash = (code.charCodeAt(r % code.length) * 31 + c * 17) % 3;
        rects.push('<rect x="' + (c*cs) + '" y="' + (r*cs) + '" width="' + (cs-1) + '" height="' + (cs-1) + '" fill="' + (hash===0?'#2c2c2c':'#f5f0e8') + '"/>');
      }
    }
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '"><rect width="' + size + '" height="' + size + '" fill="#fff" rx="8"/>' + rects.join('') +
      '<rect x="2" y="2" width="' + (cs*3) + '" height="' + (cs*3) + '" fill="#2c2c2c" rx="4"/>' +
      '<rect x="' + (size-cs*3-2) + '" y="2" width="' + (cs*3) + '" height="' + (cs*3) + '" fill="#2c2c2c" rx="4"/>' +
      '<rect x="2" y="' + (size-cs*3-2) + '" width="' + (cs*3) + '" height="' + (cs*3) + '" fill="#2c2c2c" rx="4"/></svg>';
  }

  // 配置轮询
  function startConfigPolling() {
    pollConfig();
    configPollTimer = setInterval(pollConfig, 30000);
  }

  function pollConfig() {
    if (stateMachine.getCurrentState() !== STATES.COLD_START) { MockAPI.heartbeat(); return; }
    MockAPI.getConfig().then(function (r) {
      if (r && r.config && r.asset_pack && r.asset_pack.status === 'ready') {
        stateMachine.transition('config_ready');
      }
    }).catch(function (e) { console.warn('[Main] pollConfig error:', e); });
  }

  // CHAT
  function startChat() {
    chatting = true;
    startWaveAnimation();
    simulateChat();
  }

  function stopChat() {
    chatting = false;
    if (chatSimTimer) { clearTimeout(chatSimTimer); chatSimTimer = null; }
    stopWaveAnimation();
    if (currentSessionId) { MockAPI.endSession(currentSessionId); currentSessionId = null; }
  }

  function simulateChat() {
    if (!chatting) return;
    MockAPI.startSession().then(function (r) {
      currentSessionId = r.session_id;
      chatLoop();
    });
  }

  function chatLoop() {
    if (!chatting) return;
    if (chatSubtitleEl) { chatSubtitleEl.textContent = '... 倾听中'; }
    chatSimTimer = setTimeout(function () {
      if (!chatting) return;
      MockAPI.sendChatMessage({ session_id: currentSessionId, asr_text: '(模拟语音)', photo_context: null }).then(function (r) {
        if (!chatting) return;
        if (chatSubtitleEl) { chatSubtitleEl.textContent = '\u300C' + r.reply_text + '\u300D'; }
        if (hudPanel && hudPanel.isVisible()) {
          hudPanel.updatePromptInfo('回复: ' + r.reply_text);
          hudPanel.updateVoiceSource(r.persona + ' / ' + r.voice_source);
        }
        simulateTTSPulse();
        chatSimTimer = setTimeout(function () { if (chatting) chatLoop(); }, 6000 + Math.random() * 2000);
      });
    }, 2000 + Math.random() * 1000);
  }

  function simulateTTSPulse() {
    var av = document.getElementById('chat-avatar');
    if (av) { av.classList.add('tts-active'); setTimeout(function () { av.classList.remove('tts-active'); }, 3000); }
  }

  function triggerChat() { stateMachine.transition('speech_detected'); }
  function triggerSoothing() { stateMachine.transition('negative_signal'); }

  // 声波动画
  function startWaveAnimation() {
    if (!chatWaveEl) return;
    chatWaveEl.innerHTML = '';
    for (var i = 0; i < 12; i++) {
      var b = document.createElement('div');
      b.className = 'wave-bar';
      b.style.cssText = 'display:inline-block;width:4px;height:20px;margin:0 2px;background:#7fdb7f;border-radius:2px;animation:waveAnim 0.8s ease-in-out infinite;animation-delay:' + (i*0.08) + 's;';
      chatWaveEl.appendChild(b);
    }
  }

  function stopWaveAnimation() { if (chatWaveEl) chatWaveEl.innerHTML = ''; }

  // SOOTHING — 超时时间可配置（默认 20 分钟，演示用 15s）
  var SOOTHING_TIMEOUT_MS = 20 * 60 * 1000; // 生产: 20min
  // 检测 URL 参数 ?soothing_timeout=15 可覆盖（单位秒）
  var stMatch = location.search.match(/[?&]soothing_timeout=(\d+)/);
  if (stMatch) SOOTHING_TIMEOUT_MS = parseInt(stMatch[1], 10) * 1000;

  function startSoothing() {
    if (soothingOverlayEl) soothingOverlayEl.classList.add('active');
    var tag = document.getElementById('white-noise-tag');
    if (tag) tag.style.display = 'block';
    setTimeout(function () {
      if (stateMachine.getCurrentState() === STATES.SOOTHING) stateMachine.transition('settled_timeout');
    }, SOOTHING_TIMEOUT_MS);
  }

  function stopSoothing() {
    if (soothingOverlayEl) soothingOverlayEl.classList.remove('active');
    var tag = document.getElementById('white-noise-tag');
    if (tag) tag.style.display = 'none';
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
