/**
 * StateMachine - 患者端状态机
 * ==============================
 * 管理四个状态的流转：COLD_START -> STANDBY -> CHAT -> SOOTHING
 * 所有 UI 切换通过状态驱动，通过 data-state 属性控制显示。
 *
 * 状态图：
 *   COLD_START --(config_ready)--> STANDBY
 *   STANDBY    --(speech_detected / gaze_trigger)--> CHAT
 *   STANDBY    --(negative_signal)--> SOOTHING
 *   CHAT       --(silence_timeout)--> STANDBY
 *   CHAT       --(sunset_trigger)--> SOOTHING
 *   SOOTHING   --(settled_timeout)--> STANDBY
 *   SOOTHING   --(time_window_end)--> STANDBY
 */

(function (global) {
  'use strict';

  var STATES = {
    COLD_START: 'COLD_START',
    STANDBY: 'STANDBY',
    CHAT: 'CHAT',
    SOOTHING: 'SOOTHING'
  };

  var TRANSITIONS = {
    COLD_START: { config_ready: 'STANDBY' },
    STANDBY: { speech_detected: 'CHAT', gaze_trigger: 'CHAT', negative_signal: 'SOOTHING' },
    CHAT: { silence_timeout: 'STANDBY', sunset_trigger: 'SOOTHING' },
    SOOTHING: { settled_timeout: 'STANDBY', time_window_end: 'STANDBY' }
  };

  function StateMachine(initialState) {
    if (initialState === undefined) initialState = STATES.COLD_START;
    this._currentState = initialState;
    this._listeners = [];
    this._syncDOM();
    console.log('[StateMachine] init, state:', this._currentState);
  }

  StateMachine.prototype.getCurrentState = function () { return this._currentState; };

  StateMachine.prototype.transition = function (action) {
    var current = this._currentState;
    var allowed = TRANSITIONS[current];
    if (!allowed || !allowed[action]) {
      console.warn('[StateMachine] invalid transition:', current, action);
      return false;
    }
    var next = allowed[action];
    var prev = current;
    this._currentState = next;
    this._syncDOM();
    this._dispatchEvent(prev, next, action);
    console.log('[StateMachine] ' + prev + ' --(' + action + ')--> ' + next);
    return true;
  };

  StateMachine.prototype.addEventListener = function (fn) { this._listeners.push(fn); };
  StateMachine.prototype.removeEventListener = function (fn) {
    var i = this._listeners.indexOf(fn);
    if (i !== -1) this._listeners.splice(i, 1);
  };

  StateMachine.prototype._syncDOM = function () {
    var el = document.getElementById('app');
    if (el) el.setAttribute('data-state', this._currentState);
  };

  StateMachine.prototype._dispatchEvent = function (prev, next, action) {
    for (var i = 0; i < this._listeners.length; i++) {
      try { this._listeners[i](prev, next, action); } catch (e) { console.error('[StateMachine] listener error:', e); }
    }
  };

  global.STATES = STATES;
  global.StateMachine = StateMachine;
})(window);
