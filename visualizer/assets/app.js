/* Light-Router passage visualizer.
 *
 * Static, dependency-free apart from vendored Leaflet. Reads run.json,
 * tracks/*.geojson and wind.json produced by build.py next to this page.
 */
(function () {
  "use strict";

  var MS_PER_KT = 1.94384; // m/s -> knots
  var PLAY_INTERVAL_MS = 700;

  var PALETTE = [
    "#4fc3f7", // unlimited - cyan
    "#81c784", // green
    "#ffd54f", // yellow
    "#ffb74d", // orange
    "#ff8a65", // deep orange
    "#e57373", // red
  ];

  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + ": HTTP " + r.status);
      return r.json();
    });
  }

  function budgetSortKey(name) {
    if (/unlimited/.test(name)) return Infinity;
    var m = name.match(/(\d+)\s*KB/i);
    return m ? parseInt(m[1], 10) : 0;
  }

  function fmt(v, digits, suffix) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    return v.toFixed(digits) + (suffix || "");
  }

  function lerp(a, b, f) { return a + (b - a) * f; }

  function lerpAngle(a, b, f) {
    var d = ((b - a + 540) % 360) - 180;
    return (a + d * f + 360) % 360;
  }

  /* Interpolated boat state at time t from 1h-resolution track points. */
  function Boat(track, color) {
    this.name = track.name;
    this.color = color;
    this.reached = track.reached;
    this.etaHours = track.eta_hours;
    var coords = track.feature.geometry.coordinates;
    var pts = track.feature.points || [];
    this.times = pts.map(function (p) { return p.time_h; });
    this.lat = coords.map(function (c) { return c[1]; });
    this.lon = coords.map(function (c) { return c[0]; });
    this.heading = pts.map(function (p) { return p.heading_deg; });
    this.speed = pts.map(function (p) { return p.speed_kt; });
    this.tws = pts.map(function (p) { return p.tws_kt; });
    this.twa = pts.map(function (p) { return p.twa_deg; });
    this.lastTime = this.times[this.times.length - 1];
    this.visible = true;
  }

  Boat.prototype.stateAt = function (t) {
    var times = this.times;
    if (t <= times[0]) return this.pointState(0, 0);
    if (t >= this.lastTime) {
      var i = times.length - 1;
      return this.pointState(i, 0);
    }
    var lo = 0, hi = times.length - 1;
    while (hi - lo > 1) {
      var mid = (lo + hi) >> 1;
      if (times[mid] <= t) lo = mid; else hi = mid;
    }
    var f = (t - times[lo]) / (times[hi] - times[lo]);
    return {
      lat: lerp(this.lat[lo], this.lat[hi], f),
      lon: lerp(this.lon[lo], this.lon[hi], f),
      heading: lerpAngle(this.heading[lo], this.heading[hi], f),
      speed: lerp(this.speed[lo], this.speed[hi], f),
      tws: lerp(this.tws[lo], this.tws[hi], f),
      twa: lerpAngle(this.twa[lo], this.twa[hi], f),
      finished: false,
    };
  };

  Boat.prototype.pointState = function (i, f) {
    var j = Math.min(i + 1, this.times.length - 1);
    return {
      lat: lerp(this.lat[i], this.lat[j], f),
      lon: lerp(this.lon[i], this.lon[j], f),
      heading: lerpAngle(this.heading[i], this.heading[j], f),
      speed: lerp(this.speed[i], this.speed[j], f),
      tws: lerp(this.tws[i], this.tws[j], f),
      twa: lerpAngle(this.twa[i], this.twa[j], f),
      finished: this.reached && this.times[i] >= this.lastTime - 1e-9,
    };
  };

  function boatIconSvg(color) {
    return '<svg width="22" height="22" viewBox="0 0 22 22" style="transform-origin:11px 11px">' +
      '<path d="M11 1 L17 19 L11 15 L5 19 Z" fill="' + color +
      '" stroke="#0b0f14" stroke-width="1"/></svg>';
  }

  /* Blues-style ramp for the filled speed field (matches the artifacts'
   * contourf underlay: dark blue calm -> bright blue strong). */
  var WIND_MAX_MS = 25;

  function windFill(ms) {
    var t = Math.min(ms / WIND_MAX_MS, 1);
    return [
      Math.round(lerp(30, 90, t)),   // r
      Math.round(lerp(90, 200, t)), // g
      Math.round(lerp(170, 240, t)), // b
      Math.round(lerp(70, 175, t)), // alpha (0.27 -> 0.69)
    ];
  }

  function App() {
    this.boats = [];
    this.frame = 0;
    this.playing = false;
    this.timer = null;
  }

  App.prototype.init = function () {
    var self = this;
    return fetchJson("run.json").then(function (run) {
      self.run = run;
      var trackLoads = run.tracks.map(function (t) {
        return fetchJson(t.file).then(function (feature) {
          t.feature = feature;
          return t;
        });
      });
      var windLoad = run.wind
        ? fetchJson(run.wind.file).catch(function () { return null; })
        : Promise.resolve(null);
      return Promise.all([Promise.all(trackLoads), windLoad]).then(function (r) {
        self.wind = r[1];
        self.setup();
      });
    });
  };

  App.prototype.setup = function () {
    var run = this.run;
    var manifest = run.manifest;

    document.getElementById("run-title").textContent =
      manifest.scenario + " — " + manifest.code_version;
    document.getElementById("run-meta").textContent =
      (manifest.source && (manifest.source.type || manifest.source.truth)) +
      " · " + (manifest.created_at || "");

    // Sort: unlimited first, then descending budget.
    var tracks = run.tracks.slice().sort(function (a, b) {
      return budgetSortKey(b.name) - budgetSortKey(a.name);
    });
    this.boats = tracks.map(function (t, i) {
      return new Boat(t, PALETTE[i % PALETTE.length]);
    });

    this.setupMap();
    this.setupTimeline();
    this.setupPanel();
    this.renderFrame();
  };

  App.prototype.setupMap = function () {
    var self = this;
    var map = L.map("map", { zoomControl: true, attributionControl: true });
    this.map = map;

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    var all = [];
    this.boats.forEach(function (b) {
      for (var i = 0; i < b.lat.length; i++) all.push([b.lat[i], b.lon[i]]);
    });
    if (all.length) map.fitBounds(L.latLngBounds(all).pad(0.08));

    var route = this.run.manifest.route || {};
    if (route.start) {
      L.circleMarker(route.start, { color: "#81c784", radius: 5, fillOpacity: 0.9 })
        .addTo(map).bindTooltip("start");
    }
    if (route.finish) {
      L.circleMarker(route.finish, { color: "#e57373", radius: 5, fillOpacity: 0.9 })
        .addTo(map).bindTooltip("finish");
    }

    this.boats.forEach(function (b) {
      b.trace = L.polyline([], { color: b.color, weight: 2, opacity: 0.85 }).addTo(map);
      b.marker = L.marker([b.lat[0], b.lon[0]], {
        icon: L.divIcon({
          className: "boat-marker",
          html: boatIconSvg(b.color),
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        }),
        keyboard: false,
      }).addTo(map);
      b.tooltip = b.marker.bindTooltip("", {
        className: "boat-tooltip",
        direction: "top",
        offset: [0, -10],
      });
    });

    // Wind rendering: a filled speed field UNDER the traces (like the
    // artifacts' contourf underlay) and quiver arrows above them, both
    // as canvases in custom Leaflet panes so they pan/zoom with the map.
    this.fieldCanvas = this.makeWindPane("windfield", 350);
    this.arrowCanvas = this.makeWindPane("windarrows", 450);
    this.fieldCtx = this.fieldCanvas.getContext("2d");
    this.arrowCtx = this.arrowCanvas.getContext("2d");

    var redraw = function () { self.drawWind(); };
    map.on("move zoom resize viewreset", redraw);
    window.addEventListener("resize", redraw);

    // Re-apply rotation after Leaflet re-creates marker elements.
    map.on("zoomend", function () { self.renderFrame(); });
  };

  /* A canvas inside a custom map pane at the given z-index
   * (tile pane is 200, overlay/traces 400, markers 600). */
  App.prototype.makeWindPane = function (name, zIndex) {
    var pane = this.map.createPane(name);
    pane.style.zIndex = String(zIndex);
    pane.style.pointerEvents = "none";
    var canvas = document.createElement("canvas");
    canvas.style.pointerEvents = "none";
    pane.appendChild(canvas);
    return canvas;
  };

  /* Keep the overlay canvases pinned to the current view. */
  App.prototype.positionWindCanvases = function () {
    var size = this.map.getSize();
    var dpr = window.devicePixelRatio || 1;
    var topLeft = this.map.containerPointToLayerPoint([0, 0]);
    var self = this;
    [this.fieldCanvas, this.arrowCanvas].forEach(function (c) {
      var w = Math.round(size.x * dpr), h = Math.round(size.y * dpr);
      if (c.width !== w || c.height !== h) {
        c.width = w;
        c.height = h;
      }
      c.style.width = size.x + "px";
      c.style.height = size.y + "px";
      L.DomUtil.setPosition(c, topLeft);
    });
  };

  App.prototype.setupTimeline = function () {
    var self = this;
    var maxTrackTime = 0;
    this.boats.forEach(function (b) {
      maxTrackTime = Math.max(maxTrackTime, b.lastTime);
    });

    if (this.wind && this.wind.times_h && this.wind.times_h.length > 1) {
      this.frames = this.wind.times_h.slice();
    } else {
      this.frames = [];
      for (var t = 0; t <= maxTrackTime; t += 6) this.frames.push(t);
    }

    var slider = document.getElementById("timeline");
    slider.max = String(this.frames.length - 1);
    slider.value = "0";
    slider.addEventListener("input", function () {
      self.setFrame(parseInt(slider.value, 10));
    });

    document.getElementById("play").addEventListener("click", function () {
      self.togglePlay();
    });

    this.startDate = null;
    var src = (this.run.manifest.source || {}).start_date;
    if (src) this.startDate = new Date(src + "T00:00:00Z");
  };

  App.prototype.setupPanel = function () {
    var self = this;
    var tbody = document.querySelector("#boat-table tbody");
    this.boats.forEach(function (b) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        '<td><span class="chip" style="background:' + b.color + '"></span></td>' +
        "<td>" + b.name + "</td>" +
        "<td class='c-hdg'></td><td class='c-sog'></td>" +
        "<td class='c-tws'></td><td class='c-twa'></td>";
      tbody.appendChild(tr);
      b.row = tr;
    });

    var toggles = document.getElementById("budget-toggles");
    this.boats.forEach(function (b) {
      var label = document.createElement("label");
      var input = document.createElement("input");
      input.type = "checkbox";
      input.checked = true;
      input.addEventListener("change", function () {
        b.visible = input.checked;
        self.renderFrame();
      });
      label.appendChild(input);
      label.appendChild(document.createTextNode(" " + b.name));
      toggles.appendChild(label);
    });

    var windToggle = document.getElementById("wind-toggle");
    if (!this.wind) {
      windToggle.checked = false;
      windToggle.disabled = true;
      windToggle.parentNode.appendChild(
        document.createTextNode(" (no truth field for this run)"));
      document.getElementById("wind-legend").style.display = "none";
    } else if (this.wind.source === "snapshot") {
      windToggle.parentNode.appendChild(
        document.createTextNode(" (frozen t=0 — no evolving pack)"));
    }
    windToggle.addEventListener("change", function () {
      var show = windToggle.checked ? "" : "none";
      self.fieldCanvas.style.display = show;
      self.arrowCanvas.style.display = show;
      self.drawWind();
    });

    var m = this.run.manifest;
    var route = m.route || {};
    document.getElementById("run-details").innerHTML =
      "scenario: <b>" + m.scenario + "</b><br>" +
      "code: <b>" + m.code_version + "</b> · lib <b>" + (m.light_router_version || "") + "</b><br>" +
      "route: <b>" + (route.start || []).join(", ") + "</b> &rarr; <b>" +
      (route.finish || []).join(", ") + "</b><br>" +
      "staircase: <b>" + (m.staircase || []).map(function (s) {
        return s === null ? "unlimited" : (s >= 1000 ? s / 1000 + " KB" : s + " B");
      }).join(" · ") + "</b><br>" +
      "checksum: <b>" + String(m.data_checksum || "").slice(0, 12) + "</b>";
  };

  App.prototype.setFrame = function (i) {
    this.frame = Math.max(0, Math.min(i, this.frames.length - 1));
    document.getElementById("timeline").value = String(this.frame);
    this.renderFrame();
  };

  App.prototype.togglePlay = function () {
    var self = this;
    this.playing = !this.playing;
    document.getElementById("play").innerHTML = this.playing ? "&#10074;&#10074;" : "&#9654;";
    if (this.playing) {
      this.timer = window.setInterval(function () {
        if (self.frame >= self.frames.length - 1) self.setFrame(0);
        else self.setFrame(self.frame + 1);
      }, PLAY_INTERVAL_MS);
    } else if (this.timer) {
      window.clearInterval(this.timer);
      this.timer = null;
    }
  };

  App.prototype.timeLabel = function (t) {
    if (this.startDate) {
      var d = new Date(this.startDate.getTime() + t * 3600 * 1000);
      var day = Math.floor(t / 24);
      var hh = String(d.getUTCHours()).padStart(2, "0");
      var mm = String(d.getUTCMinutes()).padStart(2, "0");
      return "day " + day + " · " + hh + ":" + mm + " UTC";
    }
    return "t = " + t + " h";
  };

  App.prototype.renderFrame = function () {
    var t = this.frames[this.frame];
    document.getElementById("time-label").textContent = this.timeLabel(t);
    document.getElementById("frame-label").textContent =
      "frame " + (this.frame + 1) + "/" + this.frames.length;

    var self = this;
    this.boats.forEach(function (b) {
      var st = b.stateAt(t);
      b.state = st;

      if (b.visible) {
        var trace = [];
        for (var i = 0; i < b.times.length && b.times[i] <= t + 1e-9; i++) {
          trace.push([b.lat[i], b.lon[i]]);
        }
        trace.push([st.lat, st.lon]);
        b.trace.setLatLngs(trace);
        b.trace.setStyle({ opacity: 0.85 });
      } else {
        b.trace.setLatLngs([]);
      }

      b.marker.setLatLng([st.lat, st.lon]);
      var el = b.marker.getElement();
      if (el) {
        var svg = el.querySelector("svg");
        if (svg) svg.style.transform = "rotate(" + (st.heading || 0) + "deg)";
        el.style.opacity = b.visible ? "1" : "0.25";
      }

      var tip = "<b>" + b.name + "</b> · " + self.timeLabel(t) + "<br>" +
        "hdg " + fmt(st.heading, 0, "°") +
        " · sog " + fmt(st.speed, 1, " kt") + "<br>" +
        "tws " + fmt(st.tws, 1, " kt") +
        " · twa " + fmt(st.twa, 0, "°") +
        (st.finished ? "<br>finished" : "");
      b.tooltip.setTooltipContent(tip);

      b.row.querySelector(".c-hdg").textContent = fmt(st.heading, 0);
      b.row.querySelector(".c-sog").textContent = fmt(st.speed, 1);
      b.row.querySelector(".c-tws").textContent = fmt(st.tws, 1);
      b.row.querySelector(".c-twa").textContent = fmt(st.twa, 0);
      b.row.style.opacity = b.visible ? "1" : "0.4";
    });

    this.drawWind();
  };

  /* Wind arrows: one per grid cell, pointing along the flow, colored by speed. */
  /* Truth wind, artifacts style: a filled, smoothed speed field
   * (contourf-like) under the traces, quiver arrows above them. */
  App.prototype.drawWind = function () {
    if (!this.fieldCanvas || !this.wind) return;
    if (this.fieldCanvas.style.display === "none") return;

    var t = this.frames[this.frame];
    var times = this.wind.times_h;
    var fi = 0;
    for (var i = 0; i < times.length; i++) {
      if (times[i] <= t + 1e-9) fi = i;
    }
    var u = this.wind.u[fi], v = this.wind.v[fi];
    if (!u) return;
    var lats = this.wind.lats, lons = this.wind.lons;
    var nlat = lats.length, nlon = lons.length;

    this.positionWindCanvases();
    var dpr = window.devicePixelRatio || 1;
    var size = this.map.getSize();

    // --- filled speed field: one pixel per grid cell, scaled up with
    //     smoothing so it reads as a continuous contourf-like surface.
    if (!this.fieldImage) {
      this.fieldImage = document.createElement("canvas");
    }
    var fc = this.fieldImage;
    if (fc.width !== nlon || fc.height !== nlat) {
      fc.width = nlon;
      fc.height = nlat;
    }
    var fctx = fc.getContext("2d");
    var img = fctx.createImageData(nlon, nlat);
    for (var r = 0; r < nlat; r++) {
      var row = nlat - 1 - r; // ImageData row 0 is the northernmost
      for (var c = 0; c < nlon; c++) {
        var uu = u[row][c], vv = v[row][c];
        var px = (r * nlon + c) * 4;
        if (uu === null || vv === null) {
          img.data[px + 3] = 0;
          continue;
        }
        var col = windFill(Math.hypot(uu, vv));
        img.data[px] = col[0];
        img.data[px + 1] = col[1];
        img.data[px + 2] = col[2];
        img.data[px + 3] = col[3];
      }
    }
    fctx.putImageData(img, 0, 0);

    var ctx = this.fieldCtx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.x, size.y);
    var tl = this.map.latLngToLayerPoint([lats[nlat - 1], lons[0]]);
    var br = this.map.latLngToLayerPoint([lats[0], lons[nlon - 1]]);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(fc, tl.x, tl.y, br.x - tl.x, br.y - tl.y);

    // --- quiver arrows on top (uniform, like the artifacts' quiver).
    var actx = this.arrowCtx;
    actx.setTransform(dpr, 0, 0, dpr, 0, 0);
    actx.clearRect(0, 0, size.x, size.y);
    actx.strokeStyle = "rgba(255,255,255,0.6)";
    actx.lineWidth = 1.2;
    actx.beginPath();
    for (var r2 = 0; r2 < nlat; r2++) {
      for (var c2 = 0; c2 < nlon; c2++) {
        var u2 = u[r2][c2], v2 = v[r2][c2];
        if (u2 === null || v2 === null) continue;
        var speedKt = Math.hypot(u2, v2) * MS_PER_KT;
        if (speedKt < 1) continue;
        var pt = this.map.latLngToLayerPoint([lats[r2], lons[c2]]);
        if (pt.x < -30 || pt.y < -30 || pt.x > size.x + 30 || pt.y > size.y + 30) continue;

        // Sailor/meteorological convention: arrows point INTO the wind
        // (toward where it comes from), like wind barbs on weather maps.
        var ang = Math.atan2(v2, -u2);
        var len = Math.min(8 + speedKt * 0.8, 24);
        var x1 = pt.x - Math.cos(ang) * len / 2;
        var y1 = pt.y - Math.sin(ang) * len / 2;
        var x2 = pt.x + Math.cos(ang) * len / 2;
        var y2 = pt.y + Math.sin(ang) * len / 2;
        actx.moveTo(x1, y1);
        actx.lineTo(x2, y2);
        var head = 5;
        var a1 = ang + 2.6, a2 = ang - 2.6;
        actx.moveTo(x2, y2);
        actx.lineTo(x2 - Math.cos(a1) * head, y2 - Math.sin(a1) * head);
        actx.moveTo(x2, y2);
        actx.lineTo(x2 - Math.cos(a2) * head, y2 - Math.sin(a2) * head);
      }
    }
    actx.stroke();
  };

  window.addEventListener("DOMContentLoaded", function () {
    var app = new App();
    app.init().catch(function (err) {
      document.getElementById("run-meta").textContent = "failed to load: " + err;
    });
  });
})();
