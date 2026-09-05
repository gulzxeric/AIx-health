/**
 * StateMachine - 患者端状态机
 * ==============================
 * 管理四个状态的流转：COLD_START → STANDBY → CHAT → SOOTHING
 * 所有 UI 切换通过状态驱动，通过 data-state 属性控制显示。
 *
 * 状态图：
 *   COLD_START ──(config_ready)──→ STANDBY
 *   STANDBY    ──(speech_detected / gaze_trigger)──→ CHAT
 *   STANDBY    ──(negative_signal)──→ SOOTHING
 *   CHAT       ──(silence_timeout)──→ STANDBY
 *   CHAT       ──(sunset_trigger)──→ SOOTHING
 *   SOOTHING   ──(settled_timeout)──→ STANDBY
 *   SOOTHING   ──(time_window_end)──→ STANDBY
 *
 * @module StateMachine
 */

(function (global) {
  'use strict';

  // ── 状态定义 ──────────────────────────────────────────────────────

  var STATES = {
    COLD_START: 'COLD_START',
    STANDBY: 'STANDBY',
    CHAT: 'CHAT',
    SOOTHING: 'SOOTHING'
  };

  /**
   * 状态转换规则表
   * 格式：当前状态: { 动作: 目标状态 }
   * 非法转换会被忽略并打印警告
   */
  var TRANSITIONS = {
    COLD_START: {
      config_ready: 'STANDBY'
    },
    STANDBY: {
      speech_detected: 'CHAT',
      gaze_trigger: 'CHAT',
      negative_signal: 'SOOTHING'
    },
    CHAT: {
      silence_timeout: 'STANDBY',
      sunset_trigger: 'SOOTHING'
    },
    SOOTHING: {
      settled_timeout: 'STANDBY',
      time_window_end: 'STANDBY'
    }
  };

  /**
   * 状态名称的中文显示
   */
  var STATE_LABELS = {};
  STATE_LABELS[STATES.COLD_START] = '等待绑定';
  STATE_LABELS[STATES.STANDBY] = '轮播待机';
  STATE_LABELS[STATES.CHAT] = '对话中';
  STATE_LABELS[STATES.SOOTHING] = '舒缓模式';

  // ── 状态机类 ──────────────────────────────────────────────────────

  /**
   * @class StateMachine
   * @param {string} initialState - 初始状态，默认 COLD_START
   */
  function StateMachine(initialState) {
    if (initialState === undefined) {
      initialState = STATES.COLD_START;
    }
    /** @private 当前状态 */
    this._currentState = initialState;
    /** @private 监听器列表 */
    this._listeners = [];

    // 初始化立即同步 UI
    this._syncDOM();

    console.log('[StateMachine] 初始化完成，初始状态:', this._currentState);
  }

  /**
   * 获取当前状态
   * @returns {string} 当前状态常量
   */
  StateMachine.prototype.getCurrentState = function () {
    return this._currentState;
  };

  /**
   * 触发状态转换
   * @param {string} action - 动作名称
   * @returns {boolean} 是否转换成功
   *
   * 流程：
   * 1. 查表校验当前状态下该动作是否合法
   * 2. 若合法：更新状态 → 同步 DOM → 派发事件 → 日志
   * 3. 若不合法：打印警告，不操作
   */
  StateMachine.prototype.transition = function (action) {
    var current = this._currentState;
    var allowed = TRANSITIONS[current];

    if (!allowed || !allowed[action]) {
      console.warn(
        '[StateMachine] 非法转换: 当前状态 "' + current +
        '", 动作 "' + action + '" 不被允许'
      );
      return false;
    }

    var nextState = allowed[action];
    var prevState = current;

    console.log(
      '[StateMachine] 转换: ' + STATE_LABELS[prevState] + ' (' + prevState + ')' +
      ' ──(' + action + ')──→ ' + STATE_LABELS[nextState] + ' (' + nextState + ')'
    );

    // 更新状态
    this._currentState = nextState;

    // 更新 DOM data-state
    this._syncDOM();

    // 派发事件给监听器
    this._dispatchEvent(prevState, nextState, action);

    return true;
  };

  /**
   * 注册状态变更监听器
   * @param {Function} listener - 回调 function(prevState, nextState, action)
   */
  StateMachine.prototype.addEventListener = function (listener) {
    if (typeof listener === 'function') {
      this._listeners.push(listener);
    }
  };

  /**
   * 移除监听器
   * @param {Function} listener
   */
  StateMachine.prototype.removeEventListener = function (listener) {
    var idx = this._listeners.indexOf(listener);
    if (idx !== -1) {
      this._listeners.splice(idx, 1);
    }
  };

  /**
   * 将当前同步到 DOM 的 data-state 属性
   * @private
   */
  StateMachine.prototype._syncDOM = function () {
    var appEl = document.getElementById('app');
    if (appEl) {
      appEl.setAttribute('data-state', this._currentState);
    }
  };

  /**
   * 派发事件给所有监听器
   * @private
   * @param {string} prevState
   * @param {string} nextState
   * @param {string} action
   */
  StateMachine.prototype._dispatchEvent = function (prevState, nextState, action) {
    for (var i = 0; i < this._listeners.length; i++) {
      try {
        this._listeners[i](prevState, nextState, action);
      } catch (e) {
        console.error('[StateMachine] 监听器异常:', e);
      }
    }
  };

  // ── 导出 ──────────────────────────────────────────────────────────

  global.STATES = STATES;
  global.StateMachine = StateMachine;

})(window);
