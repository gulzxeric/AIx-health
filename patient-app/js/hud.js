/**
 * HudPanel - HUD 调试面板模块
 * 评委调试模式，通过 ?hud=1 URL 参数或 D 键切换。
 * 显示：注视点十字光斑、声学曲线、Prompt 意图、音色标识。
 */

(function (global) {
  'use strict';

  var PW = 320;

  function HudPanel(opts) {
    opts = opts || {};
    this._app = opts.appContainer || document.getElementById('app');
    this._visible = false;
    this._panelEl = null;
    this._gazeCrosshair = null;
    this._acousticCanvas = null;
    this._acousticCtx = null;
    this._buildDOM();
    this._bindKeys();
    if (this._checkUrlParam()) this.show();
  }

  HudPanel.prototype._buildDOM = function () {
    var p = document.createElement('div');
    p.className = 'hud-panel';
    p.style.cssText =
      'position:fixed;top:0;right:0;width:' + PW + 'px;height:100vh;' +
      'background:rgba(10,10,20,0.75);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);' +
      'border-left:1px solid rgba(255,255,255,0.1);color:#e0e0e0;font-family:"Courier New",monospace;' +
      'font-size:13px;z-index:9999;overflow-y:auto;' +
      'transform:translateX(100%);transition:transform 0.3s cubic-bezier(0.4,0,0.2,1);' +
      'padding:20px 16px;box-sizing:border-box;';
    p.setAttribute('aria-label','HUD');
    p.innerHTML = '<div style="font-size:16px;font-weight:bold;margin-bottom:16px;color:#88ccff;border-bottom:1px solid rgba(255,255,255,0.15);padding-bottom:8px;">HUD · 评委模式</div>';
    this._panelEl = p;
    document.body.appendChild(p);

    // 1. 注视点
    var gs = document.createElement('div');
    gs.style.cssText = 'margin-bottom:20px;';
    gs.innerHTML = '<div style="font-size:11px;color:#88ccff;margin-bottom:6px;">◆ 注视点</div>';
    p.appendChild(gs);
    var cc = document.createElement('div');
    cc.style.cssText = 'position:relative;width:100%;height:120px;background:rgba(0,0,0,0.4);border-radius:6px;border:1px solid rgba(255,255,255,0.08);overflow:hidden;';
    this._gazeCrosshair = document.createElement('div');
    this._gazeCrosshair.style.cssText = 'position:absolute;width:28px;height:28px;top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;transition:all 0.15s ease;';
    this._gazeCrosshair.innerHTML =
      '<div style="position:absolute;top:13px;left:0;width:28px;height:2px;background:rgba(255,50,50,0.8);"></div>' +
      '<div style="position:absolute;top:0;left:13px;width:2px;height:28px;background:rgba(255,50,50,0.8);"></div>' +
      '<div style="position:absolute;top:11px;left:11px;width:6px;height:6px;border-radius:50%;background:#ff3333;box-shadow:0 0 6px rgba(255,50,50,0.6);"></div>' +
      '<div style="position:absolute;top:4px;left:4px;width:20px;height:20px;border-radius:50%;border:1px solid rgba(255,50,50,0.4);"></div>';
    cc.appendChild(this._gazeCrosshair);
    p.appendChild(cc);
    this._gazeCoords = document.createElement('div');
    this._gazeCoords.style.cssText = 'font-size:11px;color:#999;margin-top:4px;text-align:center;';
    this._gazeCoords.textContent = 'x: 0, y: 0';
    p.appendChild(this._gazeCoords);

    // 2. 声学曲线
    var acs = document.createElement('div');
    acs.style.cssText = 'margin-bottom:20px;';
    acs.innerHTML = '<div style="font-size:11px;color:#88ccff;margin-bottom:6px;">◆ 声学曲线</div>';
    p.appendChild(acs);
    this._acousticCanvas = document.createElement('canvas');
    this._acousticCanvas.width = PW - 32;
    this._acousticCanvas.height = 80;
    this._acousticCanvas.style.cssText = 'width:100%;height:80px;background:rgba(0,0,0,0.4);border-radius:6px;border:1px solid rgba(255,255,255,0.08);';
    this._acousticCtx = this._acousticCanvas.getContext('2d');
    p.appendChild(this._acousticCanvas);

    // 3. Prompt 意图
    var ps = document.createElement('div');
    ps.style.cssText = 'margin-bottom:20px;';
    ps.innerHTML = '<div style="font-size:11px;color:#88ccff;margin-bottom:6px;">◆ Prompt 意图</div>';
    p.appendChild(ps);
    this._promptInfo = document.createElement('div');
    this._promptInfo.style.cssText = 'font-size:12px;color:#ddd;background:rgba(0,0,0,0.3);border-radius:4px;padding:8px;line-height:1.5;min-height:30px;word-break:break-all;';
    this._promptInfo.textContent = '等待对话...';
    p.appendChild(this._promptInfo);

    // 4. 音色标识
    var vs = document.createElement('div');
    vs.style.cssText = 'margin-bottom:20px;';
    vs.innerHTML = '<div style="font-size:11px;color:#88ccff;margin-bottom:6px;">◆ 音色标识</div>';
    p.appendChild(vs);
    this._voiceSource = document.createElement('div');
    this._voiceSource.style.cssText = 'font-size:14px;color:#7fdb7f;background:rgba(0,0,0,0.3);border-radius:4px;padding:8px;';
    this._voiceSource.textContent = 'default (默认音色)';
    p.appendChild(this._voiceSource);

    // 关闭按钮
    var btn = document.createElement('div');
    btn.textContent = '[H] 隐藏';
    btn.style.cssText = 'position:absolute;top:12px;right:12px;font-size:11px;color:#666;cursor:pointer;padding:2px 6px;border-radius:3px;border:1px solid rgba(255,255,255,0.1);';
    var self = this;
    btn.addEventListener('click', function () { self.hide(); });
    p.appendChild(btn);
  };

  HudPanel.prototype._bindKeys = function () {
    var self = this;
    document.addEventListener('keydown', function (e) {
      if ((e.key === 'd' || e.key === 'D') && e.target === document.body) self.toggle();
      if ((e.key === 'H' || e.key === 'h') && e.target === document.body) self.hide();
    });
  };

  HudPanel.prototype._checkUrlParam = function () {
    return new URLSearchParams(window.location.search).get('hud') === '1';
  };

  HudPanel.prototype.toggle = function () { this._visible ? this.hide() : this.show(); };

  HudPanel.prototype.show = function () {
    this._visible = true;
    this._panelEl.style.transform = 'translateX(0)';
    this._app.style.marginRight = PW + 'px';
  };

  HudPanel.prototype.hide = function () {
    this._visible = false;
    this._panelEl.style.transform = 'translateX(100%)';
    this._app.style.marginRight = '0';
  };

  HudPanel.prototype.updateGazePoint = function (x, y) {
    if (!this._gazeCrosshair) return;
    this._gazeCrosshair.style.left = (x * 100) + '%';
    this._gazeCrosshair.style.top = (y * 100) + '%';
    this._gazeCrosshair.style.transform = 'translate(-50%,-50%)';
    if (this._gazeCoords) this._gazeCoords.textContent = 'x: ' + (x * 100).toFixed(1) + '%, y: ' + (y * 100).toFixed(1) + '%';
  };

  HudPanel.prototype.updateAcousticData = function (data) {
    var ctx = this._acousticCtx, cv = this._acousticCanvas;
    if (!ctx || !cv || !data || !data.length) return;
    var w = cv.width, h = cv.height;
    ctx.clearRect(0, 0, w, h);
    ctx.beginPath();
    ctx.strokeStyle = '#7fdb7f';
    ctx.lineWidth = 1.5;
    var step = w / data.length;
    for (var i = 0; i < data.length; i++) {
      var x = i * step, y = h - (data[i] * h * 0.8) - (h * 0.1);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
    var g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, 'rgba(127,219,127,0.15)');
    g.addColorStop(1, 'rgba(127,219,127,0.0)');
    ctx.fillStyle = g; ctx.fill();
    ctx.beginPath(); ctx.strokeStyle = 'rgba(255,255,255,0.1)'; ctx.setLineDash([3,3]);
    ctx.moveTo(0, h/2); ctx.lineTo(w, h/2); ctx.stroke(); ctx.setLineDash([]);
  };

  HudPanel.prototype.updatePromptInfo = function (t) { if (this._promptInfo) this._promptInfo.textContent = t || '等待对话...'; };
  HudPanel.prototype.updateVoiceSource = function (s) { if (this._voiceSource) this._voiceSource.textContent = s || 'default (默认音色)'; };
  HudPanel.prototype.isVisible = function () { return this._visible; };

  global.HudPanel = HudPanel;
})(window);
