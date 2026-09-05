/**
 * PhotoCarousel - 照片轮播模块
 * Ken Burns 视效（缓缩放 + 平移微动）+ 淡入淡出切换
 */

(function (global) {
  'use strict';

  function PhotoCarousel(container, photos) {
    if (!container) throw new Error('[PhotoCarousel] missing container');
    this._container = container;
    this._photos = photos || [];
    this._currentIndex = 0;
    this._timer = null;
    this._running = false;
    this._paused = false;
    this._transitionMs = 800;
    this._interval = 10000;
    this._buildDOM();
  }

  PhotoCarousel.prototype._buildDOM = function () {
    this._container.innerHTML = '';
    this._container.style.cssText = 'position:relative;overflow:hidden;width:100%;height:100%;';
    for (var i = 0; i < 2; i++) {
      var layer = document.createElement('div');
      layer.className = 'carousel-layer';
      layer.style.cssText =
        'position:absolute;top:-5%;left:-5%;width:110%;height:110%;' +
        'background-size:cover;background-position:center;background-repeat:no-repeat;' +
        'transition:opacity ' + this._transitionMs + 'ms ease-in-out;' +
        'opacity:' + (i === 0 ? '1' : '0') + ';z-index:' + (i === 0 ? '2' : '1') + ';';
      this._container.appendChild(layer);
    }
    this._captionEl = document.createElement('div');
    this._captionEl.style.cssText =
      'position:absolute;bottom:30px;left:50%;transform:translateX(-50%);' +
      'color:#fff;font-size:1.2rem;text-shadow:0 2px 8px rgba(0,0,0,0.6);' +
      'z-index:10;opacity:0;transition:opacity 0.5s;pointer-events:none;' +
      'font-family:"Noto Sans SC",sans-serif;';
    this._container.appendChild(this._captionEl);
    this._layers = Array.from(this._container.querySelectorAll('.carousel-layer'));
  };

  PhotoCarousel.prototype._randomKB = function () {
    return { scale: 1.0 + Math.random() * 0.15, originX: (20 + Math.random() * 60) + '%', originY: (20 + Math.random() * 60) + '%' };
  };

  PhotoCarousel.prototype._applyKB = function (el, kb, animate) {
    if (!kb) kb = this._randomKB();
    el.style.transition = animate ? 'transform ' + this._interval + 'ms ease-out' : 'none';
    el.style.transformOrigin = kb.originX + ' ' + kb.originY;
    el.style.transform = 'scale(' + kb.scale + ')';
  };

  PhotoCarousel.prototype._switchTo = function (index) {
    var photos = this._photos;
    if (!photos.length) return;
    index = (index + photos.length) % photos.length;
    var prev = this._currentIndex;
    if (prev === index && this._running) return;
    this._currentIndex = index;
    var photo = photos[index];
    var cur = this._layers[0], nxt = this._layers[1];
    var kb = this._randomKB();
    nxt.style.backgroundImage = 'url("' + photo.url + '")';
    nxt.style.opacity = '0';
    this._applyKB(nxt, kb, false);
    this._preloadNext(index);
    var self = this;
    requestAnimationFrame(function () {
      cur.style.opacity = '0';
      nxt.style.opacity = '1';
      cur.style.zIndex = '1';
      nxt.style.zIndex = '2';
      self._applyKB(cur, self._randomKB(), false);
      if (self._captionEl) {
        self._captionEl.textContent = photo.caption || '';
        self._captionEl.style.opacity = '1';
      }
    });
    this._layers[0] = nxt;
    this._layers[1] = cur;
  };

  PhotoCarousel.prototype._preloadNext = function (i) {
    var photos = this._photos;
    if (!photos.length) return;
    var next = photos[(i + 1) % photos.length];
    if (next && next.url) { var img = new Image(); img.src = next.url; }
  };

  PhotoCarousel.prototype.start = function () {
    if (this._running) return;
    if (!this._photos.length) { console.warn('[PhotoCarousel] no photos'); return; }
    this._running = true;
    this._paused = false;
    this._switchTo(0);
    var self = this;
    this._timer = setInterval(function () {
      if (!self._paused && self._running) self._switchTo((self._currentIndex + 1) % self._photos.length);
    }, this._interval);
  };

  PhotoCarousel.prototype.stop = function () {
    this._running = false; this._paused = false;
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
  };

  PhotoCarousel.prototype.pause = function () { this._paused = true; };
  PhotoCarousel.prototype.resume = function () { this._paused = false; };
  PhotoCarousel.prototype.updatePhotos = function (p) { this._photos = p || []; if (this._running) this._switchTo(0); };
  PhotoCarousel.prototype.getCurrentIndex = function () { return this._currentIndex; };

  global.PhotoCarousel = PhotoCarousel;
})(window);
