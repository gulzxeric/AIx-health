/**
 * main.js - 患者端主应用逻辑
 * ==============================
 * 初始化状态机、照片轮播、HUD面板，管理状态切换时的模块生命周期。
 * 所有 API 调用使用 MockAPI 模块，后续可替换为真实后端。
 *
 * 启动流程：
 * 1. DOMContentLoaded → 初始化所有模块
 * 2. 状态机初始化为 COLD_START
 * 3. 显示设备码，开始配置轮询
 * 4. 配置就绪 → 状态转换 STANDBY → 启动轮播
 *
 * @module Main
 */

(function () {
  'use strict';

  // ── DOM 引用 ──────────────────────────────────────────────────────

  var appEl = document.getElementById('app');
  var deviceCodeEl = document.getElementById('device-code');
  var qrCodeEl = document.getElementById('qr-code');
  var photoCarouselEl = document.getElementById('photo-carousel');
  var chatAvatarEl = document.getElementById('chat-avatar');
  var chatSubtitleEl = document.getElementById('chat-subtitle');
  var chatWaveEl = document.getElementById('chat-wave');
  var soothingOverlayEl = document.getElementById('soothing-overlay');

  // ── 全局实例 ──────────────────────────────────────────────────────

  /** @type {StateMachine} */
  var stateMachine = null;

  /** @type {PhotoCarousel} */
  var photoCarousel = null;

  /** @type {HudPanel} */
  var hudPanel = null;

  /** @type {number} 配置轮询定时器 */
  var configPollTimer = null;

  /** @type {number} 对话模拟定时器 */
  var chatSimTimer = null;

  /** @type {number} 声波动画定时器 */
  var waveAnimTimer = null;

  /** @type {boolean} 是否在对话模拟中 */
  var chatting = false;

  /** @type {string} 当前 session ID */
  var currentSessionId = null;

  // ── 初始化 ────────────────────────────────────────────────────────

  /**
   * 应用启动入口
   */
  function init() {
    console.log('[Main] 患者端应用启动');

    // 1. 初始化状态机
    stateMachine = new StateMachine(STATES.COLD_START);

    // 2. 初始化 HUD
    hudPanel = new HudPanel({ appContainer: appEl });

    // 3. 初始化照片轮播（暂不启动）
    var photos = MockAPI.getPhotos();
    photoCarousel = new PhotoCarousel(photoCarouselEl, photos);

    // 4. 注册状态监听器
    stateMachine.addEventListener(onStateChange);

    // 5. COLD_START 初始化
    setupColdStart();

    // 6. 启动配置轮询
    startConfigPolling();

    // 7. 模拟对话触发（演示用，绑定到 window 方便调试）
    window.__debug = {
      stateMachine: stateMachine,
      photoCarousel: photoCarousel,
      hudPanel: hudPanel,
      triggerChat: triggerChat,
      triggerSoothing: triggerSoothing
    };

    console.log('[Main] 初始化完成，当前状态:', stateMachine.getCurrentState());
  }

  // ── 状态切换处理 ──────────────────────────────────────────────────

  /**
   * 状态切换回调
   * @param {string} prevState
   * @param {string} nextState
   * @param {string} action
   */
  function onStateChange(prevState, nextState, action) {
    console.log('[Main] 状态切换: ' + prevState + ' → ' + nextState + ' (动作: ' + action + ')');

    // 停止上一个状态的所有活动
    stopStateModules(prevState);
    // 启动新状态的活动
    startStateModules(nextState);

    // 更新 HUD 状态信息
    if (hudPanel && hudPanel.isVisible()) {
      hudPanel.updatePromptInfo('状态: ' + nextState + ' (动作: ' + action + ')');
    }
  }

  /**
   * 停止指定状态的模块
   * @param {string} state
   */
  function stopStateModules(state) {
    switch (state) {
      case STATES.STANDBY:
        if (photoCarousel) photoCarousel.stop();
        break;
      case STATES.CHAT:
        stopChat();
        break;
      case STATES.SOOTHING:
        stopSoothing();
        break;
      case STATES.COLD_START:
      default:
        break;
    }
  }

  /**
   * 启动指定状态的模块
   * @param {string} state
   */
  function startStateModules(state) {
    switch (state) {
      case STATES.COLD_START:
        setupColdStart();
        break;
      case STATES.STANDBY:
        if (photoCarousel) photoCarousel.start();
        break;
      case STATES.CHAT:
        startChat();
        break;
      case STATES.SOOTHING:
        startSoothing();
        break;
    }
  }

  // ── COLD_START ────────────────────────────────────────────────────

  /**
   * 冷启动：显示设备码和二维码占位
   */
  function setupColdStart() {
    // 显示设备码
    if (deviceCodeEl) {
      deviceCodeEl.textContent = MockAPI.getDeviceCode();
    }
    // 生成简单的二维码占位（使用 CSS 格子图案）
    if (qrCodeEl) {
      qrCodeEl.innerHTML = generateQRPlaceholder(MockAPI.getDeviceCode());
    }
    console.log('[Main] COLD_START: 设备码 ' + MockAPI.getDeviceCode());
  }

  /**
   * 生成二维码占位 SVG
   * @param {string} code
   * @returns {string} SVG 字符串
   */
  function generateQRPlaceholder(code) {
    var size = 160;
    var cells = 11;
    var cellSize = size / cells;

    // 生成简单的类二维码图案
    var rects = [];
    for (var row = 0; row < cells; row++) {
      for (var col = 0; col < cells; col++) {
        // 基于设备码的简单伪随机
        var hash = (code.charCodeAt(row % code.length) * 31 + col * 17) % 3;
        var fill = hash === 0 ? '#2c2c2c' : '#f5f0e8';
        rects.push(
          '<rect x="' + (col * cellSize) + '" y="' + (row * cellSize) +
          '" width="' + (cellSize - 1) + '" height="' + (cellSize - 1) + '" fill="' + fill + '"/>'
        );
      }
    }

    return (
      '<svg xmlns="http://www.w3.org/2000/svg" width="' + size + '" height="' + size + '" viewBox="0 0 ' + size + ' ' + size + '">' +
      '<rect width="' + size + '" height="' + size + '" fill="#fff" rx="8"/>' +
      rects.join('') +
      '<rect x="2" y="2" width="' + (cellSize * 3) + '" height="' + (cellSize * 3) + '" fill="#2c2c2c" rx="4"/>' +
      '<rect x="' + (size - cellSize * 3 - 2) + '" y="2" width="' + (cellSize * 3) + '" height="' + (cellSize * 3) + '" fill="#2c2c2c" rx="4"/>' +
      '<rect x="2" y="' + (size - cellSize * 3 - 2) + '" width="' + (cellSize * 3) + '" height="' + (cellSize * 3) + '" fill="#2c2c2c" rx="4"/>' +
      '</svg>'
    );
  }

  // ── 配置轮询 ──────────────────────────────────────────────────────

  /**
   * 启动配置轮询（每 30s）
   * 模拟 GET /api/v1/patients/config
   */
  function startConfigPolling() {
    // 首次立即检查
    pollConfig();

    // 每 30s 轮询
    configPollTimer = setInterval(pollConfig, 30000);
  }

  /**
   * 轮询配置
   */
  function pollConfig() {
    if (stateMachine.getCurrentState() !== STATES.COLD_START) {
      // 已离开 COLD_START，停止轮询
      // 但保持心跳
      MockAPI.heartbeat();
      return;
    }

    MockAPI.getConfig().then(function (result) {
      if (result && result.config && result.asset_pack && result.asset_pack.status === 'ready') {
        console.log('[Main] 配置就绪，准备进入 STANDBY');
        // 模拟 "配置就绪" 转换
        stateMachine.transition('config_ready');
      }
    }).catch(function (err) {
      console.warn('[Main] 配置轮询失败:', err);
    });
  }

  // ── CHAT 对话模块 ────────────────────────────────────────────────

  /**
   * 启动对话模式
   */
  function startChat() {
    chatting = true;

    // 设置数字人形象（L1 插画风格占位）
    if (chatAvatarEl) {
      chatAvatarEl.style.backgroundImage =
        'radial-gradient(circle at 35% 35%, #f0d8b8, #d4a574 60%, #b8845a 100%)';
    }

    // 开始声波动画
    startWaveAnimation();

    // 模拟对话交互
    simulateChat();
  }

  /**
   * 停止对话模式
   */
  function stopChat() {
    chatting = false;
    if (chatSimTimer) {
      clearTimeout(chatSimTimer);
      chatSimTimer = null;
    }
    stopWaveAnimation();

    // 结束 session
    if (currentSessionId) {
      MockAPI.endSession(currentSessionId);
      currentSessionId = null;
    }
  }

  /**
   * 模拟对话交互
   */
  function simulateChat() {
    if (!chatting) return;

    // 开始 session
    MockAPI.startSession().then(function (result) {
      currentSessionId = result.session_id;

      // 模拟多轮对话
      chatLoop();
    });
  }

  /**
   * 对话循环（模拟）
   */
  function chatLoop() {
    if (!chatting) return;

    // 显示"听"状态
    if (chatSubtitleEl) {
      chatSubtitleEl.textContent = '... 倾听中';
      chatSubtitleEl.className = 'listening';
    }

    // 模拟 2-3s 后回复
    chatSimTimer = setTimeout(function () {
      if (!chatting) return;

      MockAPI.sendChatMessage({
        session_id: currentSessionId,
        asr_text: '(模拟语音输入)',
        photo_context: null
      }).then(function (result) {
        if (!chatting) return;

        // 显示回复文字（大字幕）
        if (chatSubtitleEl) {
          chatSubtitleEl.textContent = '「' + result.reply_text + '」';
          chatSubtitleEl.className = 'speaking';
        }

        // 更新 HUD
        if (hudPanel && hudPanel.isVisible()) {
          hudPanel.updatePromptInfo('回复: ' + result.reply_text);
          hudPanel.updateVoiceSource(result.persona + ' / ' + result.voice_source);
        }

        // 模拟 TTS 播报脉冲
        simulateTTSPulse();

        // 6-8s 后下一轮
        chatSimTimer = setTimeout(function () {
          if (chatting) {
            chatLoop();
          }
        }, 6000 + Math.random() * 2000);
      });
    }, 2000 + Math.random() * 1000);
  }

  /**
   * 模拟 TTS 播报时的视觉脉冲
   */
  function simulateTTSPulse() {
    if (chatAvatarEl) {
      chatAvatarEl.classList.add('tts-active');
      setTimeout(function () {
        chatAvatarEl.classList.remove('tts-active');
      }, 3000);
    }
  }

  /**
   * 手动触发对话（演示用）
   */
  function triggerChat() {
    stateMachine.transition('speech_detected');
  }

  /**
   * 手动触发舒缓（演示用）
   */
  function triggerSoothing() {
    stateMachine.transition('negative_signal');
  }

  // ── 声波动画 ──────────────────────────────────────────────────────

  /**
   * 启动声波动画（CSS 条形波动）
   */
  function startWaveAnimation() {
    if (!chatWaveEl) return;

    // 清空并创建声波条
    chatWaveEl.innerHTML = '';
    var bars = 12;
    for (var i = 0; i < bars; i++) {
      var bar = document.createElement('div');
      bar.className = 'wave-bar';
      bar.style.cssText =
        'display:inline-block;width:4px;height:20px;margin:0 2px;' +
        'background:#7fdb7f;border-radius:2px;' +
        'animation:waveAnim 0.8s ease-in-out infinite;' +
        'animation-delay:' + (i * 0.08) + 's;';
      chatWaveEl.appendChild(bar);
    }
  }

  /**
   * 停止声波动画
   */
  function stopWaveAnimation() {
    if (chatWaveEl) {
      chatWaveEl.innerHTML = '';
    }
  }

  // ── SOOTHING 舒缓模式 ────────────────────────────────────────────

  /**
   * 启动舒缓模式
   */
  function startSoothing() {
    if (soothingOverlayEl) {
      soothingOverlayEl.classList.add('active');
    }

    // 显示白噪音标识
    var noiseTag = document.getElementById('white-noise-tag');
    if (noiseTag) {
      noiseTag.style.display = 'block';
    }

    // 模拟 20 分钟后回到 STANDBY（演示时缩短为 10s）
    console.log('[Main] 舒缓模式已启动，模拟 10s 后回到 STANDBY');
    setTimeout(function () {
      if (stateMachine.getCurrentState() === STATES.SOOTHING) {
        stateMachine.transition('settled_timeout');
      }
    }, 10000);
  }

  /**
   * 停止舒缓模式
   */
  function stopSoothing() {
    if (soothingOverlayEl) {
      soothingOverlayEl.classList.remove('active');
    }
    var noiseTag = document.getElementById('white-noise-tag');
    if (noiseTag) {
      noiseTag.style.display = 'none';
    }
  }

  // ── 启动 ──────────────────────────────────────────────────────────

  // DOM 就绪后启动
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
