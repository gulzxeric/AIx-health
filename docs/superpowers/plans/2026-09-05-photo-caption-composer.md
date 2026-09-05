# 家属端「图片+文字描述」组合发送 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** caregiver-app 对话流选图后进入「预览+描述」composer，与文字一起作为一条记忆提交。

**Architecture:** 纯前端改造（微信式组合发送）。后端 `POST /memories` 已支持 `raw_text + photo_url(data URL)` 同传，零后端改动；描述为空时仍发占位 `（照片描述）` 走现有视觉自动识别。

**Tech Stack:** 原生 HTML/CSS/JS（无构建、ES5 风格：`var`/`function`，2 空格缩进），MockAPI 覆盖层模式。

**Spec:** `docs/superpowers/specs/2026-09-05-fix-photo-caption-voice-design.md` 第 3.1 节（A）。

## Global Constraints

- 工作目录：仓库根 `AIx-health/`（分支 `fix/photo-caption-voice`）。
- 前端无测试框架：验证用「手动浏览器验证」步骤（本计划写明精确操作与预期），不做自动化测试。
- JS 一律 ES5 风格（`var`、`function`），与 caregiver-app 现有代码一致；CSS 追加到 `caregiver-app/css/caregiver.css` 末尾。
- 提交信息风格：`fix:/feat:/docs:` 前缀 + 中文摘要。

---

### Task 1: 图片组合发送 composer（UI + 逻辑）

**Files:**
- Modify: `caregiver-app/index.html`（chat-container 内、`#chatInputArea` 之前插入 composer 标记）
- Modify: `caregiver-app/js/main.js`（`AppState`、`cacheDOM`、统一提交函数、composer 事件）
- Modify: `caregiver-app/css/caregiver.css`（文件末尾追加 composer 样式）

**Interfaces:**
- Consumes: `MockAPI.submitMemory({patient_id, raw_text, photo_url})`（已存在，caregiver-app/js/api.js:60）；`appendMessage` / `renderMemoryCard` / `showToast`（main.js 已存在）。
- Produces: `submitMemoryEntry({ text, photoDataUrl })` —— 后续语音录记忆任务（voice-system 计划 Task 9）将复用它提交纯文本记忆；`AppState.pendingPhoto`（data URL 或 null）。

- [ ] **Step 1: index.html 添加 composer 标记**

在 `caregiver-app/index.html` 的 `chat-container` 内、`<!-- 输入区 -->` 注释的 `<div class="chat-input-area" id="chatInputArea">` 之前插入：

```html
          <!-- 照片组合发送面板（选图后出现，替换普通输入区） -->
          <div class="photo-composer" id="photoComposer" style="display:none">
            <img id="photoComposerThumb" class="photo-composer-thumb" alt="待发送照片">
            <input id="photoComposerDesc" class="photo-composer-desc" type="text"
                   placeholder="补充这张照片的描述（可留空）" autocomplete="off">
            <button id="photoComposerCancel" class="photo-composer-cancel" title="移除照片">✕</button>
            <button id="photoComposerSend" class="chat-send-btn" title="发送">➤</button>
          </div>
```

- [ ] **Step 2: caregiver.css 末尾追加样式**

```css
/* ============================================================
   照片组合发送面板（photo composer）
   ============================================================ */
.photo-composer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-top: 1px solid #e0e0e0;
}

.photo-composer-thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.photo-composer-desc {
  flex: 1;
  min-width: 0;
  border: none;
  border-radius: 18px;
  padding: 10px 14px;
  font-size: 14px;
  outline: none;
  background: #fff;
}

.photo-composer-cancel {
  border: none;
  background: transparent;
  font-size: 16px;
  color: #999;
  cursor: pointer;
  padding: 6px;
  flex-shrink: 0;
}

.photo-composer-cancel:active {
  color: #666;
}
```

- [ ] **Step 3: main.js — AppState 与 DOM 缓存**

`AppState` 对象内（`isBound: true,` 之后）加一行：

```js
    pendingPhoto: null,   // 待发送照片 data URL（组合发送用）
```

`cacheDOM()` 内（`DOM.photoInput = ...` 之后）追加：

```js
    DOM.photoComposer = document.getElementById('photoComposer');
    DOM.photoComposerThumb = document.getElementById('photoComposerThumb');
    DOM.photoComposerDesc = document.getElementById('photoComposerDesc');
    DOM.photoComposerCancel = document.getElementById('photoComposerCancel');
    DOM.photoComposerSend = document.getElementById('photoComposerSend');
```

- [ ] **Step 4: main.js — 统一提交函数 + composer 开关**

在 `sendTextMessage` 函数**之前**插入以下三个新函数（并整体替换旧 `sendTextMessage`、旧 `handlePhotoSelected`）：

```js
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
```

替换旧 `handlePhotoSelected`（原 432-474 行，立即提交的那段）为：

```js
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
```

- [ ] **Step 5: main.js — initChatModule 绑定 composer 事件**

`initChatModule()` 内（`DOM.photoInput.addEventListener('change', handlePhotoSelected);` 之后）追加：

```js
    // 照片 composer：发送 / 取消 / 回车发送
    DOM.photoComposerSend.addEventListener('click', sendPendingPhoto);
    DOM.photoComposerCancel.addEventListener('click', closePhotoComposer);
    DOM.photoComposerDesc.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendPendingPhoto();
      }
    });
```

- [ ] **Step 6: 手动验证（浏览器，无后端也可）**

1. 用浏览器打开 `caregiver-app/index.html`（或 Live Server）。
2. 点 📷 选一张图 → 预期：输入区被替换为 composer（缩略图 + 描述框 + ✕ + ➤），**没有**立即出现照片气泡/记忆卡片。
3. 输入「这是阿珍和我在厂门口的合影」按回车 → 预期：出现照片气泡 + 文字气泡 + 「正在分析记忆...」+ 记忆卡片（mock 模式下实体来自 mock）。
4. 再次选图 → 点 ✕ → 预期：composer 关闭、普通输入区恢复、未发送任何消息。
5. 选图后不输描述直接 ➤ → 预期：发送占位「（照片描述）」的记忆（真实后端时由视觉模型生成描述）。
6. 纯文字输入回车 → 预期：与改造前一致（文字气泡 + 记忆卡片）。
7. F12 控制台无报错。

- [ ] **Step 7: Commit**

```bash
git add caregiver-app/index.html caregiver-app/js/main.js caregiver-app/css/caregiver.css
git commit -m "fix: 家属端选图后进入composer预览，支持图片+文字描述组合发送"
```
