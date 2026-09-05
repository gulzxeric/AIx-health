/**
 * HudPanel - HUD 调试面板模块
 * ==============================
 * 评委调试模式，通过 ?hud=1 URL 参数或 D 键切换。
 * 显示：注视点十字光斑、声学曲线波形、Prompt 意图、音色标识。
 *
 * 设计原则：
 * - 所有内容叠加在相框之上，不干扰主界面布局
 * - 半透明毛玻璃风格，视觉上处于"第二层"
 * - 只在开发/演示阶段使用，生产环境可通过 URL 参数隐藏
 *
 * @module HudPanel
 */

(function (global) {
  'use strict';

  // ── 配置 ──────────────────────────────────────────────────────────

  var PANEL_WIDTH = 320;  // 面板宽度 (px)

  // ── HudPanel 类 ───────────────────────────────────────────────────

  /**
   * @class HudPanel
   * @param {Object} options
   * @param {HTMLElement} options.appContainer - #app 容器
   */
  function HudPanel(options) {
    options = options || {};
    this._appContainer = options.appContainer || document.getElementById('app');

    /** @private 面板是否可见 */
    this._visible = false;
    /** @private 面板 DOM 元素 */
    this._panelEl = null;
    /** @private 注视点十字元素 */
    this._gazeCrosshair = null;
    /** @private 声学 Canvas 元素 */
    this._acousticCanvas = null;
    /** @private 声学 Canvas 上下文 */
    this._acousticCtx = null;

    this._buildDOM();
    this._bindKeys();

    // 检查 URL 参数
    if (this._checkUrlParam()) {
      this.show();
    }
  }

  /**
   * 构建 HUD DOM
   * @private
   */
  HudPanel.prototype._buildDOM = function () {
    // ── 创建面板容器 ──
    var panel = document.createElement('div');
    panel.className = 'hud-panel';
    panel.style.cssText =
      'position:fixed;top:0;right:0;width:' + PANEL_WIDTH + 'px;height:100vh;' +
      'background:rgba(10,10,20,0.75);backdrop-filter:blur(10px);' +
      '-webkit-backdrop-filter:blur(10px);' +
      'border-left:1px solid rgba(255,255,255,0.1);' +
      'color:#e0e0e0;font-family:"Courier New",monospace;font-size:13px;' +
      'z-index:9999;overflow-y:auto;' +
      'transform:translateX(100%);transition:transform 0.3s cubic-bezier(0.4,0,0.2,1);' +
      'padding:20px 16px;box-sizing:border-box;';
    panel.setAttribute('aria-label', 'HUD 调试面板');
    panel.innerHTML = '<div style="font-size:16px;font-weight:bold;margin-bottom:16px;color:#88ccff;border-bottom:1px solid rgba(255,255,255,0.15);padding-bottom:8px;">HUD · 评委模式</div>';
    this._panelEl = panel;
    document.body.appendChild(panel);

    // ── 1. 注视点十字光斑 ──
    var gazeSection = document.createElement('div');
    gazeSection.style.cssText = 'margin-bottom:20px;';
    gazeSection.innerHTML = '<div style="font-size:11px;color:#88ccff;margin-bottom:6px;">◆ 注视点</div>';
    this._panelEl.appendChild(gazeSection);

    var crosshairContainer = document.createElement('div');
    crosshairContainer.style.cssText =
      'position:relative;width:100%;height:120px;background:rgba(0,0,0,0.4);' +
      'border-radius:6px;border:1px solid rgba(255,255,255,0.08);overflow:hidden;';
    this._gazeCrosshair = document.createElement('div');
    this._gazeCrosshair.style.cssText =
      'position:absolute;width:28px;height:28px;top:50%;left:50%;' +
      'transform:translate(-50%,-50%);' +
      'pointer-events:none;transition:all 0.15s ease;';
    // 十字线 + 中心点
    this._gazeCrosshair.innerHTML =
      // 水平线
      '<div style="position:absolute;top:13px;left:0;width:28px;height:2px;background:rgba(255,50,50,0.8);"></div>' +
      // 垂直线
      '<div style="position:absolute;top:0;left:13px;width:2px;height:28px;background:rgba(255,50,50,0.8);"></div>' +
      // 中心点
      '<div style="position:absolute;top:11px;left:11px;width:6px;height:6px;border-radius:50%;background:#ff3333;box-shadow:0 0 6px rgba(255,50,50,0.6);"></div>' +
      // 外圈
      '<div style="position:absolute;top:4px;left:4px;width:20px;height:20px;border-radius:50%;border:1px solid rgba(255,50,50,0.4);"></div>';
    crosshairContainer.appendChild(this._gazeCrosshair);
    this._panelEl.appendChild(crosshairContainer);

    // 坐标显示
    this._gazeCoords = document.createElement('div');
    this._gazeCoords.style.cssText = 'font-size:11px;color:#999;margin-top:4px;text-align:center;';
    this._gazeCoords.textContent = 'x: 0, y: 0';
    this._panelEl.appendChild(this._gazeCoords);

    // ── 2. 声学曲线 ──
    var acousticSection = document.createElement('div');
    acousticSection.style.cssText = 'margin-bottom:20px;';
    acousticSection.innerHTML = '<div style="font-size:11px;color:#88ccff;margin-bottom:6px;">◆ 声学曲线</div>';
    this._panelEl.appendChild(acousticSection);

    this._acousticCanvas = document.createElement('canvas');
    this._acousticCanvas.width = PANEL_WIDTH - 32;
    this._acousticCanvas.height = 80;
    this._acousticCanvas.style.cssText =
      'width:100%;height:80px;background:rgba(0,0,0,0.4);border-radius:6px;' +
      'border:1px solid rgba(255,255,255,0.08);';
    this._acousticCtx = this._acousticCanvas.getContext('2d');
    this._panelEl.appendChild(this._acousticCanvas);

    // ── 3. Prompt意图 ──
    var promptSection = document.createElement('div');
    promptSection.style.cssText = 'margin-bottom:20px;';
    promptSection.innerHTML = '<div style="font-size:11px;color:#88ccff;margin-bottom:6px;">◆ Prompt 意图</div>';
    this._panelEl.appendChild(promptSection);

    this._promptInfo = document.createElement('div');
    this._promptInfo.style.cssText =
      'font-size:12px;color:#ddd;background:rgba(0,0,0,0.3);border-radius:4px;' +
      'padding:8px;line-height:1.5;min-height:30px;word-break:break-all;';
    this._promptInfo.textContent = '等待对话...';
    this._panelEl.appendChild(this._promptInfo);

    // ── 4. 音色标识 ──
    var voiceSection = document.createElement('div');
    voiceSection.style.cssText = 'margin-bottom:20px;';
    voiceSection.innerHTML = '<div style="font-size:11px;color:#88ccff;margin-bottom:6px;">◆ 音色标识</div>';
    this._panelEl.appendChild(voiceSection);

    this._voiceSource = document.createElement('div');
    this._voiceSource.style.cssText =
      'font-size:14px;color:#7fdb7f;background:rgba(0,0,0,0.3);border-radius:4px;' +
      'padding:8px;';
    this._voiceSource.textContent = 'default (默认音色)';
    this._panelEl.appendChild(this._voiceSource);

    // ── 关闭按钮 ──
    var closeBtn = document.createElement('div');
    closeBtn.textContent = '[H] 隐藏';
    closeBtn.style.cssText =
      'position:absolute;top:12px;right:12px;font-size:11px;color:#666;' +
      'cursor:pointer;padding:2px 6px;border-radius:3px;' +
      'border:1px solid rgba(255,255,255,0.1);';
    var self = this;
    closeBtn.addEventListener('click', function () { self.hide(); });
    this._panelEl.appendChild(closeBtn);
  };

  /**
   * 绑定键盘事件
   * @private
   */
  HudPanel.prototype._bindKeys = function () {
    var self = this;
    document.addEventListener('keydown', function (e) {
      // D 键切换 HUD（不区分大小写，且不在输入框中）
      if ((e.key === 'd' || e.key === 'D' || e.key === 'H' || e.key === 'h') &&
          e.target === document.body) {
        // D 键切换
        if (e.key === 'd' || e.key === 'D') {
          self.toggle();
        }
        // H 键隐藏
        if (e.key === 'H' || e.key === 'h') {
          self.hide();
        }
      }
    });
  };

  /**
   * 检查 URL 参数 ?hud=1
   * @returns {boolean}
   * @private
   */
  HudPanel.prototype._checkUrlParam = function () {
    var params = new URLSearchParams(window.location.search);
    return params.get('hud') === '1';
  };

  // ── 公共方法 ──────────────────────────────────────────────────────

  /**
   * 切换显示/隐藏
   */
  HudPanel.prototype.toggle = function () {
    if (this._visible) {
      this.hide();
    } else {
      this.show();
    }
  };

  /**
   * 显示 HUD 面板
   */
  HudPanel.prototype.show = function () {
    this._visible = true;
    this._panelEl.style.transform = 'translateX(0)';
    this._appContainer.style.marginRight = PANEL_WIDTH + 'px';
    console.log('[HUD] 面板已显示');
  };

  /**
   * 隐藏 HUD 面板
   */
  HudPanel.prototype.hide = function () {
    this._visible = false;
    this._panelEl.style.transform = 'translateX(100%)';
    this._appContainer.style.marginRight = '0';
    console.log('[HUD] 面板已隐藏');
  };

  /**
   * 更新注视点十字位置
   * @param {number} x - 归一化 x (0~1)
   * @param {number} y - 归一化 y (0~1)
   */
  HudPanel.prototype.updateGazePoint = function (x, y) {
    if (!this._gazeCrosshair) return;
    // 在迷你视窗中映射到百分比
    var px = (x * 100) + '%';
    var py = (y * 100) + '%';
    this._gazeCrosshair.style.left = px;
    this._gazeCrosshair.style.top = py;
    this._gazeCrosshair.style.transform = 'translate(-50%,-50%)';

    if (this._gazeCoords) {
      this._gazeCoords.textContent = 'x: ' + (x * 100).toFixed(1) + '%, y: ' + (y * 100).toFixed(1) + '%';
    }
  };

  /**
   * 更新声学曲线（绘制简化波形）
   * @param {Array<number>} data - 音频电平数组 (0~1)
   */
  HudPanel.prototype.updateAcousticData = function (data) {
    if (!this._acousticCtx || !this._acousticCanvas) return;

    var ctx = this._acousticCtx;
    var canvas = this._acousticCanvas;
    var w = canvas.width;
    var h = canvas.height;

    // 清除
    ctx.clearRect(0, 0, w, h);

    if (!data || data.length === 0) return;

    // 绘制波形
    ctx.beginPath();
    ctx.strokeStyle = '#7fdb7f';
    ctx.lineWidth = 1.5;

    var step = w / data.length;
    for (var i = 0; i < data.length; i++) {
      var x = i * step;
      var y = h - (data[i] * h * 0.8) - (h * 0.1); // 留边距
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    // 填充底部渐变
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    var gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, 'rgba(127,219,127,0.15)');
    gradient.addColorStop(1, 'rgba(127,219,127,0.0)');
    ctx.fillStyle = gradient;
    ctx.fill();

    // 基准线
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
    ctx.setLineDash([3, 3]);
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
    ctx.setLineDash([]);
  };

  /**
   * 更新 Prompt 意图文本
   * @param {string} text
   */
  HudPanel.prototype.updatePromptInfo = function (text) {
    if (this._promptInfo) {
      this._promptInfo.textContent = text || '等待对话...';
    }
  };

  /**
   * 更新音色标识
   * @param {string} source - 音色来源标识
   */
  HudPanel.prototype.updateVoiceSource = function (source) {
    if (this._voiceSource) {
      this._voiceSource.textContent = source || 'default (默认音色)';
    }
  };

  /**
   * 获取面板可见状态
   * @returns {boolean}
   */
  HudPanel.prototype.isVisible = function () {
    return this._visible;
  };

  // ── 导出 ──────────────────────────────────────────────────────────

  global.HudPanel = HudPanel;

})(window);
