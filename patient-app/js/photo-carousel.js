/**
 * PhotoCarousel - 照片轮播模块
 * ==============================
 * 在 STANDBY 状态下运行，实现 Ken Burns 视效（缓缩放 + 平移微动）
 * 以及淡入淡出的照片切换逻辑。
 *
 * @module PhotoCarousel
 */

(function (global) {
  'use strict';

  /**
   * PhotoCarousel 类
   * @param {HTMLElement} container - 轮播容器 DOM 元素
   * @param {Array} photos - 照片数组 [{ id, url, caption }]
   */
  function PhotoCarousel(container, photos) {
    if (!container) {
      throw new Error('[PhotoCarousel] 缺少容器元素');
    }

    /** @private 容器元素 */
    this._container = container;
    /** @private 照片列表 */
    this._photos = photos || [];
    /** @private 当前索引 */
    this._currentIndex = 0;
    /** @private 定时器句柄 */
    this._timer = null;
    /** @private 是否正在运行 */
    this._running = false;
    /** @private 是否暂停 */
    this._paused = false;
    /** @private 过渡持续时间 (ms) */
    this._transitionDuration = 800;
    /** @private 轮播间隔 (ms) */
    this._interval = 10000;

    // 初始化 DOM 结构
    this._buildDOM();
  }

  /**
   * 构建轮播 DOM 结构
   * 创建两个 img slot 用于实现 cross-fade 切换
   * @private
   */
  PhotoCarousel.prototype._buildDOM = function () {
    // 清空容器
    this._container.innerHTML = '';
    this._container.style.position = 'relative';
    this._container.style.overflow = 'hidden';
    this._container.style.width = '100%';
    this._container.style.height = '100%';

    // 创建两个图层（current / next）用于淡入淡出
    for (var i = 0; i < 2; i++) {
      var layer = document.createElement('div');
      layer.className = 'carousel-layer';
      layer.style.cssText =
        'position:absolute;top:0;left:0;width:100%;height:100%;' +
        'background-size:cover;background-position:center;' +
        'background-repeat:no-repeat;' +
        'transition:opacity ' + this._transitionDuration + 'ms ease-in-out;' +
        'opacity:' + (i === 0 ? '1' : '0') + ';' +
        'z-index:' + (i === 0 ? '2' : '1') + ';';
      this._container.appendChild(layer);
    }

    // 照片标题
    this._captionEl = document.createElement('div');
    this._captionEl.className = 'carousel-caption';
    this._captionEl.style.cssText =
      'position:absolute;bottom:30px;left:50%;transform:translateX(-50%);' +
      'color:#fff;font-size:1.2rem;text-shadow:0 2px 8px rgba(0,0,0,0.6);' +
      'z-index:10;font-family:"Noto Sans SC",sans-serif;' +
      'opacity:0;transition:opacity 0.5s ease;' +
      'pointer-events:none;';
    this._container.appendChild(this._captionEl);

    /** @private 图层元素引用 */
    this._layers = this._container.querySelectorAll('.carousel-layer');
  };

  /**
   * 生成随机 Ken Burns 起始偏移
   * @returns {Object} { scale, originX, originY }
   * @private
   */
  PhotoCarousel.prototype._randomKenBurns = function () {
    // 缩放 1.0→1.15 之间随机起始
    return {
      scale: 1.0 + Math.random() * 0.15,
      // 随机偏移起始点（百分比）
      originX: (20 + Math.random() * 60) + '%',
      originY: (20 + Math.random() * 60) + '%'
    };
  };

  /**
   * 应用 Ken Burns 动画到元素
   * @param {HTMLElement} el
   * @param {Object} kb - { scale, originX, originY }
   * @param {boolean} animate - 是否带动画过渡
   * @private
   */
  PhotoCarousel.prototype._applyKenBurns = function (el, kb, animate) {
    if (!kb) {
      kb = this._randomKenBurns();
    }
    var dur = this._interval;
    var timing = 'transform ' + dur + 'ms ease-out';

    el.style.transition = animate ? timing : 'none';
    el.style.transformOrigin = kb.originX + ' ' + kb.originY;
    el.style.transform = 'scale(' + kb.scale + ')';
  };

  /**
   * 切换照片
   * @param {number} index - 目标照片索引
   * @private
   */
  PhotoCarousel.prototype._switchTo = function (index) {
    var photos = this._photos;
    if (!photos || photos.length === 0) return;

    // 防止越界
    index = index % photos.length;
    if (index < 0) index = photos.length - 1;

    var prevIndex = this._currentIndex;
    this._currentIndex = index;

    var photo = photos[index];
    var prevPhoto = photos[prevIndex];

    // current 层（z-index:2）：当前显示的照片 → 淡出
    // next 层（z-index:1）：下一张照片 → 淡入，然后提升 z-index
    var currentLayer = this._layers[0];
    var nextLayer = this._layers[1];

    // 如果索引没变，不操作
    if (prevIndex === index && this._running) return;

    // 设置下一张照片的背景
    var kb = this._randomKenBurns();
    nextLayer.style.backgroundImage = 'url("' + photo.url + '")';
    nextLayer.style.opacity = '0';
    this._applyKenBurns(nextLayer, kb, false);

    // 预加载下一张（索引+1）
    this._preloadNext(index);

    // 强制回流后开始动画
    var self = this;
    requestAnimationFrame(function () {
      // 当前层淡出
      currentLayer.style.opacity = '0';
      // 下一层淡入
      nextLayer.style.opacity = '1';

      // 交换 z-index
      currentLayer.style.zIndex = '1';
      nextLayer.style.zIndex = '2';

      // 对当前层（刚淡出的那张）应用 Ken Burns 重置
      // 下一层已经设置了 Ken Burns，开始动画
      self._applyKenBurns(currentLayer, self._randomKenBurns(), false);

      // 更新标题
      if (self._captionEl) {
        self._captionEl.textContent = photo.caption || '';
        self._captionEl.style.opacity = '1';
      }
    });

    // 切换图层引用，让 currentLayer 始终指向"最上层"（刚淡入的）
    this._layers[0] = nextLayer;
    this._layers[1] = currentLayer;
  };

  /**
   * 预加载下一张照片（索引+1）
   * @param {number} currentIndex
   * @private
   */
  PhotoCarousel.prototype._preloadNext = function (currentIndex) {
    var photos = this._photos;
    if (!photos || photos.length === 0) return;

    var nextIdx = (currentIndex + 1) % photos.length;
    var nextPhoto = photos[nextIdx];
    if (nextPhoto && nextPhoto.url) {
      var img = new Image();
      img.src = nextPhoto.url;
    }
  };

  /**
   * 开始轮播
   */
  PhotoCarousel.prototype.start = function () {
    if (this._running) return;
    if (!this._photos || this._photos.length === 0) {
      console.warn('[PhotoCarousel] 无照片可轮播');
      return;
    }

    this._running = true;
    this._paused = false;

    // 显示第一张照片
    this._switchTo(0);

    // 启动定时器
    var self = this;
    this._timer = setInterval(function () {
      if (!self._paused && self._running) {
        self._switchTo((self._currentIndex + 1) % self._photos.length);
      }
    }, this._interval);

    console.log('[PhotoCarousel] 轮播已启动，间隔 ' + this._interval + 'ms');
  };

  /**
   * 停止轮播
   */
  PhotoCarousel.prototype.stop = function () {
    this._running = false;
    this._paused = false;
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
    console.log('[PhotoCarousel] 轮播已停止');
  };

  /**
   * 暂停（暂停动画计时器）
   */
  PhotoCarousel.prototype.pause = function () {
    this._paused = true;
  };

  /**
   * 继续
   */
  PhotoCarousel.prototype.resume = function () {
    this._paused = false;
  };

  /**
   * 更新照片列表（热替换）
   * @param {Array} photos
   */
  PhotoCarousel.prototype.updatePhotos = function (photos) {
    this._photos = photos || [];
    if (this._running) {
      this._switchTo(0);
    }
  };

  /**
   * 获取当前索引
   * @returns {number}
   */
  PhotoCarousel.prototype.getCurrentIndex = function () {
    return this._currentIndex;
  };

  /**
   * 获取当前照片对象
   * @returns {Object|null} { id, url|object_url, persona_name, ... }
   */
  PhotoCarousel.prototype.getCurrentPhoto = function () {
    if (!this._photos || this._photos.length === 0) return null;
    return this._photos[this._currentIndex] || null;
  };

  // ── 导出 ──────────────────────────────────────────────────────────

  global.PhotoCarousel = PhotoCarousel;

})(window);
