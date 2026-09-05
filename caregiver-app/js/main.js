/**
 * main.js - 家属端前端主应用逻辑
 * 
 * 单页应用，3 Tab 切换，微信风格对话交互
 * 所有 API 调用走 MockAPI 模块
 */

(function () {
  'use strict';

  // ================================================================
  // 应用状态
  // ================================================================
  const AppState = {
    currentTab: 'chat',
    patientId: '58b203df-5424-4f53-b155-82b34f840213',
    patientName: '张伯伯',
    isRecording: false,
    recordingTimer: null,
    messages: [],
    memories: [],
    currentTag: 'all',
    currentDate: new Date(),
    briefCache: {},
    isBound: true,   // 模拟已绑定
    pendingPhoto: null,   // 待发送照片 data URL（组合发送用）
    deviceOnline: true,
    statusPollInterval: null
  };

  var mediaRecorder = null;
  var audioChunks = [];
  var submitPending = false;

  // ================================================================
  // DOM 引用
  // ================================================================
  const DOM = {};

  function cacheDOM() {
    DOM.app = document.getElementById('app');
    DOM.statusDot = document.getElementById('statusDot');
    DOM.patientName = document.getElementById('patientName');
    DOM.syncTime = document.getElementById('syncTime');
    DOM.mainContent = document.getElementById('mainContent');
    DOM.tabChat = document.getElementById('tabChat');
    DOM.tabMemory = document.getElementById('tabMemory');
    DOM.tabBrief = document.getElementById('tabBrief');
    DOM.chatMessages = document.getElementById('chatMessages');
    DOM.chatInput = document.getElementById('chatInput');
    DOM.chatInputArea = document.getElementById('chatInputArea');
    DOM.btnVoice = document.getElementById('btnVoice');
    DOM.btnPhoto = document.getElementById('btnPhoto');
    DOM.btnSend = document.getElementById('btnSend');
    DOM.photoInput = document.getElementById('photoInput');
    DOM.photoComposer = document.getElementById('photoComposer');
    DOM.photoComposerThumb = document.getElementById('photoComposerThumb');
    DOM.photoComposerDesc = document.getElementById('photoComposerDesc');
    DOM.photoComposerCancel = document.getElementById('photoComposerCancel');
    DOM.photoComposerSend = document.getElementById('photoComposerSend');
    DOM.tagFilterBar = document.getElementById('tagFilterBar');
    DOM.memoryList = document.getElementById('memoryList');
    DOM.dateSelector = document.getElementById('dateSelector');
    DOM.vitalityNumber = document.getElementById('vitalityNumber');
    DOM.vitalityStatus = document.getElementById('vitalityStatus');
    DOM.vitalityRingFill = document.getElementById('vitalityRingFill');
    DOM.trendValue = document.getElementById('trendValue');
    DOM.vitalityTrend = document.getElementById('vitalityTrend');
    DOM.topicsList = document.getElementById('topicsList');
    DOM.adviceText = document.getElementById('adviceText');
    DOM.tabBar = document.getElementById('tabBar');
    DOM.toastContainer = document.getElementById('toastContainer');
  }

  // ================================================================
  // 工具函数
  // ================================================================

  /** 格式化时间 */
  function formatTime(date) {
    const d = date || new Date();
    const hours = String(d.getHours()).padStart(2, '0');
    const mins = String(d.getMinutes()).padStart(2, '0');
    return hours + ':' + mins;
  }

  /** 格式化完整时间 */
  function formatDateTime(date) {
    const d = date || new Date();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return month + '-' + day + ' ' + formatTime(d);
  }

  /** 格式化日期 */
  function formatDate(date) {
    const d = date || new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + day;
  }

  /** 获取星期几 */
  function getWeekday(date) {
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    return weekdays[date.getDay()];
  }

  /** 显示 Toast 提示 */
  function showToast(message, duration) {
    duration = duration || 2000;
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    DOM.toastContainer.appendChild(toast);
    setTimeout(function () {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, duration);
  }

  /** 生成唯一 ID */
  function generateId() {
    return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
  }

  // ================================================================
  // Tab 导航
  // ================================================================

  const TabPages = {
    chat: 'tabChat',
    memory: 'tabMemory',
    brief: 'tabBrief'
  };

  function switchTab(tabName) {
    if (tabName === AppState.currentTab) return;
    AppState.currentTab = tabName;

    // 切换页面
    Object.keys(TabPages).forEach(function (key) {
      var page = document.getElementById(TabPages[key]);
      if (key === tabName) {
        page.classList.add('active');
      } else {
        page.classList.remove('active');
      }
    });

    // 切换 Tab 按钮高亮
    var tabItems = DOM.tabBar.querySelectorAll('.tab-item');
    tabItems.forEach(function (item) {
      if (item.dataset.tab === tabName) {
        item.classList.add('active');
        item.setAttribute('aria-selected', 'true');
      } else {
        item.classList.remove('active');
        item.setAttribute('aria-selected', 'false');
      }
    });

    // 触发各模块初始化
    if (tabName === 'memory') {
      loadMemories();
    } else if (tabName === 'brief') {
      loadBrief();
    }
  }

  function initNavigation() {
    var tabItems = DOM.tabBar.querySelectorAll('.tab-item');
    tabItems.forEach(function (item) {
      item.addEventListener('click', function () {
        switchTab(item.dataset.tab);
      });
    });
  }

  // ================================================================
  // 状态栏：设备在线状态轮询
  // ================================================================

  function updateStatusBar(status) {
    var online = status && status.online;
    AppState.deviceOnline = online;

    // 在线状态圆点
    if (online) {
      DOM.statusDot.className = 'status-dot online';
    } else {
      DOM.statusDot.className = 'status-dot offline';
    }

    // 同步时间
    if (status && status.last_heartbeat) {
      var syncDate = new Date(status.last_heartbeat);
      var now = new Date();
      var diffMs = now - syncDate;
      var diffMin = Math.floor(diffMs / 60000);

      var timeText;
      if (diffMin < 1) {
        timeText = '刚刚';
      } else if (diffMin < 60) {
        timeText = diffMin + '分钟前';
      } else {
        timeText = formatTime(syncDate);
      }
      DOM.syncTime.textContent = timeText;
    }
  }

  function startStatusPolling() {
    // 立即查询一次
    MockAPI.getDeviceStatus().then(updateStatusBar);

    // 每 30s 轮询
    AppState.statusPollInterval = setInterval(function () {
      MockAPI.getDeviceStatus().then(updateStatusBar);
    }, 30000);
  }

  // ================================================================
  // 对话流模块
  // ================================================================

  /**
   * 在对话列表底部追加消息
   * @param {Object} msg - { id, type, content, side, time, data }
   */
  function appendMessage(msg) {
    AppState.messages.push(msg);

    var div = document.createElement('div');
    div.className = 'message ' + msg.side;
    div.id = msg.id;

    var bubbleHtml = '';

    // 文本消息
    if (msg.type === 'text') {
      bubbleHtml = '<div class="message-bubble">' + escapeHtml(msg.content) + '</div>';
    }
    // 系统消息（居中提示）
    else if (msg.type === 'system') {
      div.className = 'message message-system';
      bubbleHtml = '<div class="message-bubble">' + escapeHtml(msg.content) + '</div>';
    }
    // 照片消息
    else if (msg.type === 'photo') {
      bubbleHtml = '<div class="message-photo"><img src="' + msg.data.thumbnail + '" alt="照片"></div>';
    }
    // 记忆卡片
    else if (msg.type === 'memory_card') {
      bubbleHtml = renderMemoryCard(msg.data);
    }

    div.innerHTML = bubbleHtml;

    // 时间戳
    var timeEl = document.createElement('span');
    timeEl.className = 'message-time';
    timeEl.textContent = msg.time || formatTime(new Date());
    div.appendChild(timeEl);

    DOM.chatMessages.appendChild(div);

    // 自动滚动到底部
    scrollChatToBottom();
  }

  /** 转义 HTML */
  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /** 渲染记忆卡片 HTML */
  function renderMemoryCard(data) {
    var entities = data.entities || {};
    var confidence = data.confidence || 0;
    var confidencePercent = Math.round(confidence * 100);

    var html = '';
    html += '<div class="message-bubble">';
    html += '  <div class="memory-card">';
    html += '    <div class="memory-card-header">📝 记忆提取</div>';
    html += '    <div class="memory-card-body">';

    // 年代
    if (entities.era) {
      html += '      <div class="memory-card-row"><span class="memory-card-label">年代</span><span class="memory-card-value">' + escapeHtml(entities.era) + '</span></div>';
    }
    // 地点
    if (entities.location && entities.location.length) {
      html += '      <div class="memory-card-row"><span class="memory-card-label">地点</span><span class="memory-card-value">' + escapeHtml(entities.location.join('、')) + '</span></div>';
    }
    // 事件
    if (entities.event) {
      html += '      <div class="memory-card-row"><span class="memory-card-label">事件</span><span class="memory-card-value">' + escapeHtml(entities.event) + '</span></div>';
    }
    // 喜好
    if (entities.preference && entities.preference.length) {
      html += '      <div class="memory-card-row"><span class="memory-card-label">喜好</span><span class="memory-card-value">' + escapeHtml(entities.preference.join('、')) + '</span></div>';
    }
    // 人物
    if (entities.photo_people && entities.photo_people.length) {
      html += '      <div class="memory-card-row"><span class="memory-card-label">人物</span><span class="memory-card-value">' + escapeHtml(entities.photo_people.join('、')) + '</span></div>';
    }

    // 可信度
    var barWidth = confidencePercent;
    html += '      <div class="memory-card-confidence">';
    html += '        <span class="confidence-bar">可信度: <span class="confidence-fill"><span class="confidence-fill-inner" style="width:' + barWidth + '%"></span></span> ' + confidencePercent + '%</span>';
    html += '      </div>';

    html += '    </div>';

    // 操作按钮
    var memoryId = data.id || '';
    html += '    <div class="memory-card-actions">';
    html += '      <button class="btn-confirm" data-action="confirm" data-memory-id="' + memoryId + '">确认</button>';
    html += '      <button class="btn-edit" data-action="edit" data-memory-id="' + memoryId + '">编辑</button>';
    html += '    </div>';

    html += '  </div>';
    html += '</div>';

    return html;
  }

  /** 滚动消息列表到底部 */
  function scrollChatToBottom() {
    setTimeout(function () {
      DOM.chatMessages.scrollTop = DOM.chatMessages.scrollHeight;
    }, 50);
  }

  /** 统一提交记忆入口：文本 / 照片 / 文本+照片 */
  function submitMemoryEntry(opts) {
    var text = (opts.text || '').trim();
    var photoDataUrl = opts.photoDataUrl || null;

    if (!text && !photoDataUrl) return;

    // 入库文本：有描述用描述；纯照片用占位符（后端视觉模型自动识别）
    var rawText = text || '（照片描述）';

    // 追加自己的气泡（照片气泡 + 可选文字气泡，微信式）
    if (photoDataUrl) {
      appendMessage({
        id: generateId(),
        type: 'photo',
        content: '',
        side: 'right',
        time: formatTime(new Date()),
        data: { thumbnail: photoDataUrl }
      });
    }
    if (text) {
      appendMessage({
        id: generateId(),
        type: 'text',
        content: text,
        side: 'right',
        time: formatTime(new Date())
      });
    }

    // 显示"正在处理..."
    var loadingId = 'loading_' + Date.now();
    appendMessage({
      id: loadingId,
      type: 'system',
      content: '正在分析记忆...',
      side: 'left',
      time: ''
    });

    var payload = {
      patient_id: AppState.patientId,
      raw_text: rawText
    };
    if (photoDataUrl) {
      payload.photo_url = photoDataUrl;
    }

    MockAPI.submitMemory(payload).then(function (result) {
      var loadingEl = document.getElementById(loadingId);
      if (loadingEl) {
        loadingEl.remove();
      }

      appendMessage({
        id: generateId(),
        type: 'memory_card',
        content: '',
        side: 'left',
        time: formatTime(new Date()),
        data: result
      });

      showToast('记忆已同步到相框');
    });
  }

  /** 发送文本消息（纯文字路径，保持原行为） */
  function sendTextMessage(text) {
    if (!text || !text.trim()) return;

    DOM.chatInput.value = '';
    DOM.btnSend.disabled = true;

    submitMemoryEntry({ text: text });
  }

  /** 打开照片 composer（选图后调用，不立即发送） */
  function openPhotoComposer(dataUrl) {
    AppState.pendingPhoto = dataUrl;
    DOM.photoComposerThumb.src = dataUrl;
    DOM.photoComposerDesc.value = '';
    DOM.photoComposer.style.display = 'flex';
    DOM.chatInputArea.style.display = 'none';
    DOM.photoComposerDesc.focus();
  }

  /** 关闭照片 composer，恢复普通输入区 */
  function closePhotoComposer() {
    AppState.pendingPhoto = null;
    DOM.photoComposer.style.display = 'none';
    DOM.chatInputArea.style.display = 'flex';
  }

  /** 发送待发照片（带可选描述） */
  function sendPendingPhoto() {
    var dataUrl = AppState.pendingPhoto;
    if (!dataUrl) {
      closePhotoComposer();
      return;
    }
    var desc = DOM.photoComposerDesc.value;
    closePhotoComposer();
    submitMemoryEntry({ text: desc, photoDataUrl: dataUrl });
  }

  /** 开始录音（真实 MediaRecorder；不支持时由 stopRecording 回退模拟） */
  function startRecording() {
    if (AppState.isRecording) return;

    if (!navigator.mediaDevices || !window.MediaRecorder) {
      showToast('当前浏览器不支持录音');
      return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      AppState.isRecording = true;

      DOM.btnVoice.classList.add('recording');
      DOM.btnVoice.textContent = '⏺';

      showToast('录音中... 松开发送');

      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = function (e) {
        if (e.data && e.data.size) audioChunks.push(e.data);
      };
      mediaRecorder.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        if (!submitPending) return;

        var blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        if (blob.size < 2000) {
          showToast('录音太短，请按住说 1 秒以上');
          return;
        }
        showToast('语音识别中...');
        MockAPI.transcribeAudio(blob).then(function (res) {
          var text = ((res && res.text) || '').trim();
          if (!text) {
            showToast('没听清，再试一次');
            return;
          }
          submitMemoryEntry({ text: text });
        }).catch(function () {
          showToast('语音识别不可用');
        });
      };
      mediaRecorder.start();
    }).catch(function () {
      showToast('无法访问麦克风');
    });
  }

  /** 结束录音（submit=true 时提交转写） */
  function stopRecording(submit) {
    if (!AppState.isRecording) return;
    AppState.isRecording = false;

    DOM.btnVoice.classList.remove('recording');
    DOM.btnVoice.textContent = '🎤';

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      submitPending = submit;
      mediaRecorder.stop();
      return;
    }

    // 回退：无 mic 环境（演示）沿用罐头文本
    if (submit) {
      var mockAsrTexts = [
        '我爸以前在广州造船厂上班，每天下班都带我去江边看船',
        '小时候过年最喜欢去外婆家，她做的年糕特别好吃',
        '阿珍是我老伴，我们是在厂里认识的，她唱歌特别好听',
        '退休后喜欢去公园下象棋，老李头每次都输给我'
      ];
      submitMemoryEntry({ text: mockAsrTexts[Math.floor(Math.random() * mockAsrTexts.length)] });
    }
  }

  /** 选择照片 */
  function selectPhoto() {
    DOM.photoInput.click();
  }

  function handlePhotoSelected(event) {
    var file = event.target.files && event.target.files[0];
    if (!file) return;

    var reader = new FileReader();
    reader.onload = function (e) {
      // 进入 composer 预览，不立即发送
      openPhotoComposer(e.target.result);
    };
    reader.readAsDataURL(file);

    // 重置 input 以便重复选择同一文件
    event.target.value = '';
  }

  /** 初始化对话流事件绑定 */
  function initChatModule() {
    // 发送按钮
    DOM.btnSend.addEventListener('click', function () {
      sendTextMessage(DOM.chatInput.value);
    });

    // 回车发送
    DOM.chatInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendTextMessage(DOM.chatInput.value);
      }
    });

    // 输入框内容变化控制发送按钮状态
    DOM.chatInput.addEventListener('input', function () {
      DOM.btnSend.disabled = !DOM.chatInput.value.trim();
    });

    // 语音按钮：按住录音
    DOM.btnVoice.addEventListener('mousedown', function (e) {
      e.preventDefault();
      startRecording();
    });
    DOM.btnVoice.addEventListener('mouseup', function () {
      stopRecording(true);
    });
    DOM.btnVoice.addEventListener('mouseleave', function () {
      stopRecording(false);
    });

    // 触屏事件
    DOM.btnVoice.addEventListener('touchstart', function (e) {
      e.preventDefault();
      startRecording();
    }, { passive: true });
    DOM.btnVoice.addEventListener('touchend', function (e) {
      e.preventDefault();
      stopRecording(true);
    });
    DOM.btnVoice.addEventListener('touchcancel', function () {
      stopRecording(false);
    });

    // 照片按钮
    DOM.btnPhoto.addEventListener('click', selectPhoto);
    DOM.photoInput.addEventListener('change', handlePhotoSelected);

    // 照片 composer：发送 / 取消 / 回车发送
    DOM.photoComposerSend.addEventListener('click', sendPendingPhoto);
    DOM.photoComposerCancel.addEventListener('click', closePhotoComposer);
    DOM.photoComposerDesc.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendPendingPhoto();
      }
    });

    // 记忆卡片操作（事件代理）
    DOM.chatMessages.addEventListener('click', function (e) {
      var target = e.target;
      if (target.tagName === 'BUTTON') {
        handleMemoryCardAction(target);
      }
    });
  }

  /** 处理记忆卡片操作（确认/编辑） */
  function handleMemoryCardAction(button) {
    var action = button.dataset.action;
    var memoryId = button.dataset.memoryId;

    if (action === 'confirm') {
      // 模拟确认：更新记忆状态
      MockAPI.updateMemory(memoryId, { confirmed: true }).then(function () {
        showToast('记忆已确认并同步');
        button.textContent = '✓ 已确认';
        button.disabled = true;
        button.style.opacity = '0.6';
      });
    } else if (action === 'edit') {
      showToast('编辑功能（待实现）');
    }
  }

  // ================================================================
  // 记忆库模块
  // ================================================================

  /** 加载记忆列表 */
  function loadMemories() {
    DOM.memoryList.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><span>加载中...</span></div>';

    MockAPI.getMemories({
      patient_id: AppState.patientId,
      tag: AppState.currentTag
    }).then(function (memories) {
      AppState.memories = memories;
      renderMemoryList(memories);
    });
  }

  /** 渲染记忆卡片列表 */
  function renderMemoryList(memories) {
    if (!memories || memories.length === 0) {
      DOM.memoryList.innerHTML =
        '<div class="empty-state">' +
        '<span class="empty-state-icon">📭</span>' +
        '<span class="empty-state-text">暂无记忆记录</span>' +
        '<span class="empty-state-text" style="font-size:12px;">去"对话流"Tab 记录患者的记忆吧</span>' +
        '</div>';
      return;
    }

    var html = '';
    memories.forEach(function (mem) {
      var entities = mem.entities || {};
      var tags = [];
      if (entities.era) tags.push(entities.era);
      if (entities.location && entities.location.length) tags.push(entities.location[0]);
      if (entities.event) tags.push('事件');
      if (entities.preference && entities.preference.length) tags = tags.concat(entities.preference);

      html += '<div class="memory-lib-card" data-id="' + mem.id + '">';
      // 照片占位
      if (mem.photo_url) {
        html += '<div class="memory-lib-card-photo"><img src="' + mem.photo_url + '" alt="记忆照片"></div>';
      } else {
        html += '<div class="memory-lib-card-photo">🖼️</div>';
      }
      html += '<div class="memory-lib-card-text">' + escapeHtml(mem.raw_text) + '</div>';
      html += '<div class="memory-lib-card-tags">';
      tags.forEach(function (tag) {
        html += '<span class="memory-lib-tag">' + escapeHtml(tag) + '</span>';
      });
      html += '</div>';
      html += '<div class="memory-lib-card-actions">';
      html += '  <button class="btn-edit-card" data-action="lib-edit" data-id="' + mem.id + '">✏️ 编辑</button>';
      html += '  <button class="btn-delete-card" data-action="lib-delete" data-id="' + mem.id + '">🗑️ 删除</button>';
      html += '</div>';
      html += '</div>';
    });

    DOM.memoryList.innerHTML = html;
  }

  /** 初始化记忆库模块 */
  function initMemoryModule() {
    // 标签筛选
    DOM.tagFilterBar.addEventListener('click', function (e) {
      var tagItem = e.target.closest('.tag-item');
      if (!tagItem) return;

      var tag = tagItem.dataset.tag;
      if (tag === AppState.currentTag) return;

      // 更新高亮
      DOM.tagFilterBar.querySelectorAll('.tag-item').forEach(function (item) {
        item.classList.remove('active');
      });
      tagItem.classList.add('active');

      AppState.currentTag = tag;
      loadMemories();
    });

    // 卡片操作（事件代理）
    DOM.memoryList.addEventListener('click', function (e) {
      var btn = e.target.closest('button');
      if (!btn) return;

      var action = btn.dataset.action;
      var id = btn.dataset.id;

      if (action === 'lib-delete') {
        if (confirm('确定删除这条记忆吗？')) {
          MockAPI.deleteMemory(id).then(function () {
            showToast('记忆已删除');
            loadMemories();
          });
        }
      } else if (action === 'lib-edit') {
        showToast('编辑功能（待实现）');
      }
    });
  }

  // ================================================================
  // 每日简报模块
  // ================================================================

  /** 渲染日期选择器（最近 7 天） */
  function renderDateSelector(activeDate) {
    var html = '';
    for (var i = 0; i < 7; i++) {
      var date = new Date();
      date.setDate(date.getDate() - i);
      var dateStr = formatDate(date);
      var weekday = getWeekday(date);
      var day = date.getDate();
      var isActive = formatDate(activeDate) === dateStr;

      html += '<div class="date-item' + (isActive ? ' active' : '') + '" data-date="' + dateStr + '">';
      html += '  <span class="date-weekday">' + weekday + '</span>';
      html += '  <span class="date-day">' + day + '</span>';
      html += '</div>';
    }
    DOM.dateSelector.innerHTML = html;
  }

  /** 加载简报 */
  function loadBrief(date) {
    var targetDate = date || AppState.currentDate;
    AppState.currentDate = targetDate;

    renderDateSelector(targetDate);

    var dateStr = formatDate(targetDate);

    // 检查缓存
    if (AppState.briefCache[dateStr]) {
      renderBrief(AppState.briefCache[dateStr]);
      return;
    }

    // 显示加载状态
    DOM.vitalityNumber.textContent = '--';
    DOM.vitalityStatus.textContent = '加载中...';
    DOM.topicsList.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><span>加载中...</span></div>';
    DOM.adviceText.textContent = '--';

    MockAPI.getBrief(dateStr).then(function (brief) {
      AppState.briefCache[dateStr] = brief;
      renderBrief(brief);
    });
  }

  /** 渲染简报数据 */
  function renderBrief(brief) {
    // 活力指数
    var vitality = brief.vitality_index;
    DOM.vitalityNumber.textContent = vitality;

    // 环形进度条
    var degree = (vitality / 100) * 360;
    DOM.vitalityRingFill.style.background = 'conic-gradient(#4CAF50 ' + degree + 'deg, #e0e0e0 ' + degree + 'deg 360deg)';

    // 状态等级文案
    var statusText = getVitalityStatusText(vitality);
    DOM.vitalityStatus.textContent = statusText;

    // 趋势
    var trend = brief.vitality_trend_pct;
    if (trend > 0) {
      DOM.vitalityTrend.className = 'vitality-trend up';
      DOM.trendValue.innerHTML = '↑ ' + Math.abs(trend) + '%';
    } else if (trend < 0) {
      DOM.vitalityTrend.className = 'vitality-trend down';
      DOM.trendValue.innerHTML = '↓ ' + Math.abs(trend) + '%';
    } else {
      DOM.vitalityTrend.className = 'vitality-trend';
      DOM.trendValue.innerHTML = '— 0%';
    }

    // 高共鸣话题
    var topics = brief.top_topics || [];
    if (topics.length > 0) {
      var topicsHtml = '';
      topics.forEach(function (topic, index) {
        topicsHtml += '<div class="topic-item">';
        topicsHtml += '  <span class="topic-rank">' + (index + 1) + '</span>';
        topicsHtml += '  <div class="topic-info">';
        topicsHtml += '    <div class="topic-name">' + escapeHtml(topic.topic_name) + '</div>';
        topicsHtml += '    <div class="topic-metrics">';
        topicsHtml += '      <span>👁️ ' + topic.gaze_duration + 's</span>';
        topicsHtml += '      <span>💬 ' + topic.dialogue_turns + '轮</span>';
        topicsHtml += '    </div>';
        topicsHtml += '  </div>';
        topicsHtml += '</div>';
      });
      DOM.topicsList.innerHTML = topicsHtml;
    } else {
      DOM.topicsList.innerHTML = '<div class="empty-state"><span class="empty-state-text">暂无数据</span></div>';
    }

    // 沟通建议
    DOM.adviceText.textContent = brief.advice_text || '暂无建议';
  }

  /** 根据活力指数获取状态文案 */
  function getVitalityStatusText(index) {
    if (index >= 80) return '今天精神头很好';
    if (index >= 60) return '今天状态平稳';
    if (index >= 40) return '今天有点疲惫，多陪陪';
    return '建议本周关注状态变化';
  }

  /** 初始化简报模块 */
  function initBriefModule() {
    // 日期选择器事件代理
    DOM.dateSelector.addEventListener('click', function (e) {
      var dateItem = e.target.closest('.date-item');
      if (!dateItem) return;

      var dateStr = dateItem.dataset.date;
      if (dateStr === formatDate(AppState.currentDate)) return;

      // 更新高亮
      DOM.dateSelector.querySelectorAll('.date-item').forEach(function (item) {
        item.classList.remove('active');
      });
      dateItem.classList.add('active');

      var date = new Date(dateStr + 'T00:00:00');
      loadBrief(date);
    });
  }

  // ================================================================
  // PWA Service Worker 注册
  // ================================================================

  function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      // 延迟注册，不阻塞页面加载
      window.addEventListener('load', function () {
        navigator.serviceWorker.register('sw.js').then(function (registration) {
          console.log('[PWA] Service Worker 注册成功:', registration.scope);

          // 检查是否有待处理的推送通知权限
          checkPushPermission(registration);
        }).catch(function (error) {
          console.log('[PWA] Service Worker 注册失败:', error);
        });
      });
    }
  }

  /** 检查并请求推送通知权限 */
  function checkPushPermission(registration) {
    if (!('Notification' in window)) return;
    if (!('PushManager' in window)) return;

    if (Notification.permission === 'granted') {
      subscribePush(registration);
    } else if (Notification.permission === 'default') {
      // 延迟请求，避免刚打开页面就弹权限请求
      setTimeout(function () {
        Notification.requestPermission().then(function (permission) {
          if (permission === 'granted') {
            subscribePush(registration);
          }
        });
      }, 10000);
    }
  }

  /** 订阅推送 */
  function subscribePush(registration) {
    // VAPID 公钥占位（后端生成后填入）
    var vapidPublicKey = '';
    if (!vapidPublicKey) return;

    registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
    }).then(function (subscription) {
      console.log('[PWA] Push 订阅成功:', subscription.endpoint);
      // 将订阅信息发送到后端
      MockAPI.subscribePush(subscription.toJSON());
    }).catch(function (error) {
      console.log('[PWA] Push 订阅失败:', error);
    });
  }

  /** 将 Base64 URL 安全密钥转为 Uint8Array */
  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');
    var rawData = window.atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  // ================================================================
  // 应用初始化
  // ================================================================

  function init() {
    cacheDOM();

    // 设置患者名称
    DOM.patientName.textContent = AppState.patientName;

    // 初始化 Tab 导航
    initNavigation();

    // 初始化对话流
    initChatModule();

    // 初始记忆库
    initMemoryModule();

    // 初始化简报
    initBriefModule();

    // 启动状态栏轮询
    startStatusPolling();

    // 注册 Service Worker
    registerServiceWorker();

    // 如果已绑定，加载简报初始数据
    if (AppState.isBound) {
      loadBrief(new Date());
    }

    console.log('[App] 家属助手初始化完成');
  }

  // ================================================================
  // DOM Ready
  // ================================================================

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
