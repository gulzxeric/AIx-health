/**
 * VoiceManager - 麦克风 VAD + 切句录音
 * ==============================
 * 常驻监听：音量 RMS 检测说话开始/结束，静音 0.7s 切句产出音频 blob。
 * 播放 TTS 期间 suspend() 暂停检测（防自听回声）。
 *
 * @module VoiceManager
 */
(function (global) {
  'use strict';

  var RMS_START = 0.045;      // 判定开始说话的音量阈值
  var RMS_STOP = 0.015;       // 判定停止说话的音量阈值
  var SILENCE_MS = 700;       // 静音多久判定一句话结束
  var MIN_UTTERANCE_MS = 400; // 过短视为噪声丢弃

  function VoiceManager() {
    this.available = false;
    this._ctx = null;
    this._stream = null;
    this._analyser = null;
    this._meterTimer = null;
    this._suspended = false;
    this._recorder = null;
    this._chunks = [];
    this._utteranceStart = 0;
    this._speechActive = false;
    this._silenceSince = 0;
    this.onSpeechStart = null; // 说话开始（用于 STANDBY->CHAT 触发）
    this.onUtterance = null;   // function(blob) 一句话结束
  }

  /** 初始化麦克风与分析器，resolve(true/false) */
  VoiceManager.prototype.init = function () {
    var self = this;
    if (!navigator.mediaDevices || !window.MediaRecorder ||
        !window.AudioContext) {
      return Promise.resolve(false);
    }
    return navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      self._stream = stream;
      var Ctx = window.AudioContext || window.webkitAudioContext;
      self._ctx = new Ctx();
      if (self._ctx.state === 'suspended') {
        self._ctx.resume();
        self._watchGestureResume();
      }
      var source = self._ctx.createMediaStreamSource(stream);
      self._analyser = self._ctx.createAnalyser();
      self._analyser.fftSize = 1024;
      source.connect(self._analyser);
      self.available = true;
      self._startMeter();
      return true;
    }).catch(function (err) {
      console.warn('[Voice] 麦克风不可用:', err);
      return false;
    });
  };

  /**
   * 手势兜底恢复 AudioContext：
   * 无用户手势时 Chrome 以 suspended 态创建 context（mic 授权≠页面手势），
   * analyser 无数据会导致 VAD 恒哑。监听任一 click/keydown/touchstart，
   * 若 context 仍 suspended 则 resume()，恢复成功后移除全部监听。
   */
  VoiceManager.prototype._watchGestureResume = function () {
    var self = this;
    var events = ['click', 'keydown', 'touchstart'];
    var handler = function () {
      if (!self._ctx || self._ctx.state !== 'suspended') {
        detach();
        return;
      }
      self._ctx.resume().then(function () {
        detach();
      }, function () {
        /* 恢复失败：保留监听，等待下一次手势 */
      });
    };
    var detach = function () {
      for (var i = 0; i < events.length; i++) {
        document.removeEventListener(events[i], handler);
      }
    };
    for (var i = 0; i < events.length; i++) {
      document.addEventListener(events[i], handler);
    }
  };

  VoiceManager.prototype._startMeter = function () {
    var self = this;
    var buf = new Uint8Array(this._analyser.fftSize);
    this._meterTimer = setInterval(function () {
      if (!self._analyser || self._suspended) return;

      self._analyser.getByteTimeDomainData(buf);
      var sum = 0;
      for (var i = 0; i < buf.length; i++) {
        var v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      var rms = Math.sqrt(sum / buf.length);
      var now = Date.now();

      if (!self._speechActive) {
        if (rms >= RMS_START) {
          self._speechActive = true;
          self._utteranceStart = now;
          self._beginRecording();
          if (typeof self.onSpeechStart === 'function') self.onSpeechStart();
        }
      } else {
        if (rms < RMS_STOP) {
          if (!self._silenceSince) self._silenceSince = now;
          if (now - self._silenceSince >= SILENCE_MS) {
            self._speechActive = false;
            self._silenceSince = 0;
            self._finishRecording(now - self._utteranceStart);
          }
        } else {
          self._silenceSince = 0;
        }
      }
    }, 100);
  };

  VoiceManager.prototype._beginRecording = function () {
    var self = this;
    try {
      this._chunks = [];
      this._recorder = new MediaRecorder(this._stream);
      this._recorder.ondataavailable = function (e) {
        if (e.data && e.data.size) self._chunks.push(e.data);
      };
      this._recorder.start();
    } catch (e) {
      console.warn('[Voice] 录音启动失败:', e);
    }
  };

  VoiceManager.prototype._finishRecording = function (durationMs) {
    var self = this;
    var rec = this._recorder;
    if (!rec || rec.state === 'inactive') return;

    if (durationMs < MIN_UTTERANCE_MS) {
      try { rec.stop(); } catch (e) { /* ignore */ }
      this._chunks = [];
      return;
    }
    rec.onstop = function () {
      var blob = new Blob(self._chunks, { type: rec.mimeType || 'audio/webm' });
      if (blob.size > 0 && typeof self.onUtterance === 'function') {
        self.onUtterance(blob);
      }
    };
    try { rec.stop(); } catch (e) { /* ignore */ }
  };

  /**
   * 丢弃当前未完成的录音：
   * 转写/播报等待期用户插话时，VAD 已开始录音但该段为残句，
   * 置空 onstop（不产出 blob）后 stop()，防止 recorder 永久录音泄漏。
   * 正常路径 _finishRecording 已自行处理 onstop 且 stop 后 state 为 inactive，此处为 no-op。
   */
  VoiceManager.prototype._killRecorder = function () {
    var rec = this._recorder;
    if (rec && rec.state !== 'inactive') {
      rec.onstop = null;
      try { rec.stop(); } catch (e) { /* ignore */ }
    }
  };

  /** 播放 TTS 期间暂停检测（并清理可能已开始的残段录音） */
  VoiceManager.prototype.suspend = function () {
    this._suspended = true;
    this._killRecorder();
  };

  /** 播放完恢复（重置状态防误触发，并清理残留录音器） */
  VoiceManager.prototype.resume = function () {
    this._suspended = false;
    this._silenceSince = 0;
    this._speechActive = false;
    this._killRecorder();
  };

  global.VoiceManager = VoiceManager;

})(window);
