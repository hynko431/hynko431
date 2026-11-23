(() => {
  "use strict";

  const DEG = Math.PI / 180;
  const YAW_MIN = 10;
  const YAW_MAX = 72;
  const YAW_DEFAULT = 20;
  const PITCH_MIN = 18;
  const PITCH_MAX = 55;
  const PITCH_DEFAULT = 32;
  const ZOOM_MIN = 0.7;
  const ZOOM_MAX = 1.8;
  const ZOOM_DEFAULT = 1.0;

  const state = {
    profile: null,
    telemetry: null,
    yaw: YAW_DEFAULT,
    pitch: PITCH_DEFAULT,
    zoom: ZOOM_DEFAULT,
    activeTier: "all",
    hoveredIdx: -1,
    focusedIdx: -1,
    hitBars: [],
    dayGrid: new Map(),
    nWeeks: 53,
    maxCount: 1,
    dragging: false,
    lastX: 0,
    lastY: 0,
  };

  const lightMql = window.matchMedia("(prefers-color-scheme: light)");
  const dateFmt = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });

  function isSafeUrl(url) {
    return typeof url === "string" && (url.startsWith("https://") || url.startsWith("mailto:"));
  }

  function clamp(val, min, max) {
    return Math.min(max, Math.max(min, val));
  }

  function currentMode() {
    return lightMql.matches ? "light" : "dark";
  }

  function barHeight(count, maxCount) {
    if (count <= 0) return 3.0;
    const linearPart = Math.min(count, 16) * 2.45;
    if (count <= 16) return 6.0 + linearPart;
    const boost = (Math.log1p(count - 16) / Math.log1p(Math.max(maxCount - 16, 1))) * 64.0;
    return 6.0 + linearPart + boost;
  }

  function pointInQuad(px, py, quad) {
    let inside = false;
    for (let i = 0, j = quad.length - 1; i < quad.length; j = i++) {
      const xi = quad[i][0];
      const yi = quad[i][1];
      const xj = quad[j][0];
      const yj = quad[j][1];
      const intersect = (yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi + 1e-12) + xi;
      if (intersect) inside = !inside;
    }
    return inside;
  }

  function formatUpdatedDate(isoStr) {
    if (typeof isoStr !== "string" || !isoStr.trim()) return null;
    const ms = Date.parse(isoStr);
    if (!Number.isFinite(ms)) return null;
    return `Updated ${dateFmt.format(new Date(ms))}`;
  }

  function applySkylinePalette() {
    if (!state.telemetry || !state.telemetry.theme_palettes) return;
    const pal = state.telemetry.theme_palettes[currentMode()];
    const skylineEl = document.getElementById("skyline");
    if (!pal || !skylineEl) return;
    skylineEl.style.setProperty("--skyline-eyebrow", pal.eyebrow);
    skylineEl.style.setProperty("--skyline-accent", pal.accent);
    skylineEl.style.setProperty("--skyline-bg0", pal.bg0);
    skylineEl.style.setProperty("--skyline-bg1", pal.bg1);
  }

  function setTooltip(text) {
    const el = document.getElementById("skyline-tooltip");
    if (el) el.textContent = text;
  }

  function renderSkyline() {
    const canvas = document.getElementById("skyline-canvas");
    if (!canvas || !state.telemetry) return;
    const rect = canvas.getBoundingClientRect();
    const cssW = Math.max(1, Math.floor(rect.width));
    const cssH = Math.max(1, Math.floor(rect.height));
    if (cssW < 20 || cssH < 20) return;

    const dpr = Math.max(1, window.devicePixelRatio || 1);
    if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const pal = state.telemetry.theme_palettes[currentMode()];
    const days = state.telemetry.calendar_days;
    const nWeeks = state.nWeeks;
    const yaw0 = YAW_DEFAULT * DEG;
    const pitch0 = PITCH_DEFAULT * DEG;
    const yaw = state.yaw * DEG;
    const pitch = state.pitch * DEG;

    const centerW = (nWeeks - 1) / 2;
    const baseScale = Math.min(
      (cssW * 0.84) / (nWeeks * Math.cos(yaw0) + 7 * Math.sin(yaw0)),
      (cssH * 0.62) /
        (nWeeks * Math.sin(yaw0) * Math.sin(pitch0) +
          7 * Math.cos(yaw0) * Math.sin(pitch0) +
          (112 / 16.5) * Math.cos(pitch0))
    );
    const scale = baseScale * state.zoom;
    const cx = cssW * 0.5;
    const cy = cssH * 0.60;

    const wx = scale * Math.cos(yaw);
    const wy = scale * Math.sin(yaw) * Math.sin(pitch);
    const dx = -scale * Math.sin(yaw);
    const dy = scale * Math.cos(yaw) * Math.sin(pitch);
    const zScale = (scale / 16.5) * Math.cos(pitch);

    function proj(w, d, z) {
      const u = w - centerW;
      const v = d - 3.5;
      return [cx + u * wx + v * dx, cy + u * wy + v * dy - z * zScale];
    }

    // Background gradient
    const grad = ctx.createLinearGradient(0, 0, cssW, cssH);
    grad.addColorStop(0, pal.bg0);
    grad.addColorStop(1, pal.bg1);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, cssW, cssH);

    // Base plinth slab
    const pad = 0.65;
    const pBack = proj(-pad, -pad, 0);
    const pRight = proj(nWeeks + pad, -pad, 0);
    const pFront = proj(nWeeks + pad, 7 + pad, 0);
    const pLeft = proj(-pad, 7 + pad, 0);
    const plinthDrop = 10 * (scale / 16.5);
    const pbLeft = [pLeft[0], pLeft[1] + plinthDrop];
    const pbFront = [pFront[0], pFront[1] + plinthDrop];
    const pbRight = [pRight[0], pRight[1] + plinthDrop];

    function fillPoly(pts, fill, stroke, lineWidth) {
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      for (let i = 1; i < pts.length; i += 1) {
        ctx.lineTo(pts[i][0], pts[i][1]);
      }
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = lineWidth || 0.7;
        ctx.stroke();
      }
    }

    fillPoly([pLeft, pFront, pbFront, pbLeft], pal.plinth_left, pal.plinth_stroke, 0.8);
    fillPoly([pFront, pRight, pbRight, pbFront], pal.plinth_right, pal.plinth_stroke, 0.8);
    fillPoly([pBack, pRight, pFront, pLeft], pal.plinth_top, pal.plinth_stroke, 0.9);

    // Draw all bars strictly back-to-front (week asc, dow asc) and store 3 visible face quads
    const s = 0.80;
    const margin = (1.0 - s) * 0.5;
    const hitBars = [];

    for (let i = 0; i < days.length; i += 1) {
      const day = days[i];
      const w0 = day.week + margin;
      const d0 = day.dow + margin;
      const h = barHeight(day.count, state.maxCount);
      const cols = pal.levels[String(day.level)] || pal.levels["0"];
      const isActive = i === state.hoveredIdx || i === state.focusedIdx;

      const b0 = proj(w0, d0, 0);
      const b1 = proj(w0 + s, d0, 0);
      const b2 = proj(w0 + s, d0 + s, 0);
      const b3 = proj(w0, d0 + s, 0);
      const t0 = proj(w0, d0, h);
      const t1 = proj(w0 + s, d0, h);
      const t2 = proj(w0 + s, d0 + s, h);
      const t3 = proj(w0, d0 + s, h);

      const leftQuad = [t3, t2, b2, b3];
      const rightQuad = [t2, t1, b1, b2];
      const topQuad = [t0, t1, t2, t3];

      fillPoly(leftQuad, cols[1], null, 0);
      fillPoly(rightQuad, cols[2], null, 0);
      fillPoly(
        topQuad,
        isActive ? pal.peak_cap : cols[0],
        isActive ? pal.title : cols[3],
        isActive ? 1.4 : 0.55
      );

      hitBars.push({ idx: i, day, quads: [topQuad, leftQuad, rightQuad] });
    }

    state.hitBars = hitBars;
  }

  function announceDay(idx) {
    if (!state.telemetry || idx < 0 || idx >= state.telemetry.calendar_days.length) return;
    const day = state.telemetry.calendar_days[idx];
    const noun = day.count === 1 ? "contribution" : "contributions";
    setTooltip(`${day.date}: ${day.count} ${noun} (week ${day.week + 1})`);
  }

  function renderHeaderAndKpis() {
    const p = state.profile;
    const t = state.telemetry;
    const nameEl = document.getElementById("header-name");
    const roleEl = document.getElementById("header-role");
    const eyebrowEl = document.getElementById("skyline-eyebrow");
    if (nameEl) nameEl.textContent = p.name;
    if (roleEl) roleEl.textContent = p.role_headline;
    if (eyebrowEl) {
      const themeTag = t.active_theme && t.active_theme !== "baseline" ? ` · ${t.active_theme.replace("_", " ").toUpperCase()} THEME` : "";
      eyebrowEl.textContent = `3D CONTRIBUTION SKYLINE · @${t.username}${themeTag}`;
    }

    const totalEl = document.getElementById("kpi-total");
    const activeEl = document.getElementById("kpi-active");
    const bestEl = document.getElementById("kpi-best");
    const currentEl = document.getElementById("kpi-current");
    if (totalEl) totalEl.textContent = Number(t.stats.total).toLocaleString("en-US");
    if (activeEl) activeEl.textContent = String(t.stats.active_days);
    if (bestEl) bestEl.textContent = `${t.stats.best_streak}d`;
    if (currentEl) currentEl.textContent = `${t.stats.current_streak}d`;
  }

  function renderStackFilters() {
    const container = document.getElementById("stack-filters");
    if (!container || !state.profile) return;
    container.replaceChildren();

    const tiers = [{ id: "all", index: "ALL", label: "All Projects" }, ...state.profile.tech_stack_tiers];
    for (const tier of tiers) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tier-btn";
      btn.dataset.tierId = tier.id;
      btn.setAttribute("aria-pressed", tier.id === state.activeTier ? "true" : "false");
      btn.textContent = tier.id === "all" ? tier.label : `${tier.index} · ${tier.label}`;
      btn.addEventListener("click", () => {
        state.activeTier = tier.id;
        renderStackFilters();
        renderProjects();
      });
      container.appendChild(btn);
    }
  }

  function makePictureIcon(slug, name) {
    const pic = document.createElement("picture");
    pic.className = "project-icon";

    const srcDark = document.createElement("source");
    srcDark.media = "(prefers-color-scheme: dark)";
    srcDark.srcset = `./assets/icons/${slug}-dark.svg`;

    const srcLight = document.createElement("source");
    srcLight.media = "(prefers-color-scheme: light)";
    srcLight.srcset = `./assets/icons/${slug}-light.svg`;

    const img = document.createElement("img");
    img.src = `./assets/icons/${slug}-light.svg`;
    img.width = 48;
    img.height = 48;
    img.alt = `${name} icon`;

    pic.append(srcDark, srcLight, img);
    return pic;
  }

  function renderProjects() {
    const grid = document.getElementById("projects-grid");
    const statusEl = document.getElementById("projects-filter-status");
    if (!grid || !state.profile || !state.telemetry) return;
    grid.replaceChildren();

    const filtered = state.profile.projects.filter(
      (proj) => state.activeTier === "all" || (Array.isArray(proj.tier_ids) && proj.tier_ids.includes(state.activeTier))
    );

    if (statusEl) {
      if (state.activeTier === "all") {
        statusEl.textContent = `Showing all ${filtered.length} featured projects.`;
      } else {
        const tierObj = state.profile.tech_stack_tiers.find((t) => t.id === state.activeTier);
        const label = tierObj ? tierObj.label : state.activeTier;
        statusEl.textContent = `Showing ${filtered.length} project(s) matching ${label}.`;
      }
    }

    const repos = state.telemetry.repositories || {};
    for (const proj of filtered) {
      const card = document.createElement("article");
      card.className = "project-card";

      const body = document.createElement("div");
      body.className = "project-body";

      const h3 = document.createElement("h3");
      h3.className = "project-title";
      h3.textContent = proj.name;

      const cat = document.createElement("p");
      cat.className = "project-category";
      cat.textContent = proj.category;

      const sum = document.createElement("p");
      sum.className = "project-summary";
      sum.textContent = proj.summary;

      const tagRow = document.createElement("div");
      tagRow.className = "tag-row";
      for (const tech of proj.stack) {
        const span = document.createElement("span");
        span.className = "tag";
        span.textContent = tech;
        tagRow.appendChild(span);
      }

      const repoMeta = repos[proj.repo] || {};
      const metaRow = document.createElement("div");
      metaRow.className = "meta-row";
      if (typeof repoMeta.primary_language === "string" && repoMeta.primary_language.trim()) {
        const lang = document.createElement("span");
        lang.className = "meta-pill";
        lang.textContent = repoMeta.primary_language;
        metaRow.appendChild(lang);
      }
      const updatedText = formatUpdatedDate(repoMeta.pushed_at);
      if (updatedText) {
        const upd = document.createElement("span");
        upd.className = "meta-pill";
        upd.textContent = updatedText;
        metaRow.appendChild(upd);
      }
      if (repoMeta.display_stars === true && Number.isFinite(repoMeta.stars)) {
        const stars = document.createElement("span");
        stars.className = "meta-pill";
        stars.textContent = `★ ${repoMeta.stars}`;
        metaRow.appendChild(stars);
      }

      const linkRow = document.createElement("div");
      linkRow.className = "link-row";
      const linkDefs = [
        ["Code", proj.links && proj.links.code],
        ["Docs", proj.links && proj.links.docs],
        ["Live", proj.links && proj.links.live],
      ];
      for (const [label, href] of linkDefs) {
        if (!isSafeUrl(href)) continue;
        const a = document.createElement("a");
        a.href = href;
        a.rel = "noopener noreferrer";
        a.textContent = label;
        linkRow.appendChild(a);
      }

      body.append(h3, cat, sum, tagRow);
      if (metaRow.childElementCount > 0) body.appendChild(metaRow);
      body.appendChild(linkRow);
      card.append(makePictureIcon(proj.slug, proj.name), body);
      grid.appendChild(card);
    }
  }

  function wireCanvasInteractions() {
    const canvas = document.getElementById("skyline-canvas");
    if (!canvas) return;

    canvas.addEventListener("pointerdown", (ev) => {
      state.dragging = true;
      state.lastX = ev.clientX;
      state.lastY = ev.clientY;
      canvas.setPointerCapture(ev.pointerId);
    });

    canvas.addEventListener("pointerup", (ev) => {
      state.dragging = false;
      if (canvas.hasPointerCapture(ev.pointerId)) {
        canvas.releasePointerCapture(ev.pointerId);
      }
    });

    canvas.addEventListener("pointerleave", () => {
      state.dragging = false;
      if (state.hoveredIdx !== -1) {
        state.hoveredIdx = -1;
        renderSkyline();
      }
    });

    canvas.addEventListener("pointermove", (ev) => {
      const rect = canvas.getBoundingClientRect();
      if (state.dragging) {
        const dx = ev.clientX - state.lastX;
        const dy = ev.clientY - state.lastY;
        state.lastX = ev.clientX;
        state.lastY = ev.clientY;
        state.yaw = clamp(state.yaw + dx * 0.3, YAW_MIN, YAW_MAX);
        state.pitch = clamp(state.pitch + dy * 0.25, PITCH_MIN, PITCH_MAX);
        renderSkyline();
        return;
      }

      const px = ev.clientX - rect.left;
      const py = ev.clientY - rect.top;
      let hit = -1;
      for (let i = state.hitBars.length - 1; i >= 0; i -= 1) {
        const entry = state.hitBars[i];
        if (entry.quads.some((q) => pointInQuad(px, py, q))) {
          hit = entry.idx;
          break;
        }
      }
      if (hit !== state.hoveredIdx) {
        state.hoveredIdx = hit;
        renderSkyline();
        if (hit !== -1) {
          announceDay(hit);
        }
      }
    });

    canvas.addEventListener(
      "wheel",
      (ev) => {
        ev.preventDefault();
        const delta = ev.deltaY < 0 ? 0.1 : -0.1;
        state.zoom = clamp(state.zoom + delta, ZOOM_MIN, ZOOM_MAX);
        renderSkyline();
      },
      { passive: false }
    );

    canvas.addEventListener("keydown", (ev) => {
      if (ev.shiftKey) {
        if (ev.key === "ArrowLeft") state.yaw = clamp(state.yaw - 5, YAW_MIN, YAW_MAX);
        else if (ev.key === "ArrowRight") state.yaw = clamp(state.yaw + 5, YAW_MIN, YAW_MAX);
        else if (ev.key === "ArrowUp") state.pitch = clamp(state.pitch + 5, PITCH_MIN, PITCH_MAX);
        else if (ev.key === "ArrowDown") state.pitch = clamp(state.pitch - 5, PITCH_MIN, PITCH_MAX);
        else return;
        ev.preventDefault();
        renderSkyline();
        return;
      }

      if (ev.key === "+" || ev.key === "=") {
        ev.preventDefault();
        state.zoom = clamp(state.zoom + 0.15, ZOOM_MIN, ZOOM_MAX);
        renderSkyline();
        return;
      }
      if (ev.key === "-") {
        ev.preventDefault();
        state.zoom = clamp(state.zoom - 0.15, ZOOM_MIN, ZOOM_MAX);
        renderSkyline();
        return;
      }
      if (ev.key === "0") {
        ev.preventDefault();
        state.yaw = YAW_DEFAULT;
        state.pitch = PITCH_DEFAULT;
        state.zoom = ZOOM_DEFAULT;
        renderSkyline();
        return;
      }

      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(ev.key)) return;
      ev.preventDefault();
      const days = state.telemetry.calendar_days;
      if (!days.length) return;
      if (state.focusedIdx === -1) {
        state.focusedIdx = days.length - 1;
      } else {
        const cur = days[state.focusedIdx];
        let targetWeek = cur.week;
        let targetDow = cur.dow;
        if (ev.key === "ArrowLeft") targetWeek = Math.max(0, cur.week - 1);
        else if (ev.key === "ArrowRight") targetWeek = Math.min(state.nWeeks - 1, cur.week + 1);
        else if (ev.key === "ArrowUp") targetDow = Math.max(0, cur.dow - 1);
        else if (ev.key === "ArrowDown") targetDow = Math.min(6, cur.dow + 1);
        const found = state.dayGrid.get(`${targetWeek}:${targetDow}`);
        if (found !== undefined) {
          state.focusedIdx = found;
        }
      }
      renderSkyline();
      announceDay(state.focusedIdx);
    });

    const toolbar = document.querySelector(".skyline-controls");
    if (toolbar) {
      toolbar.addEventListener("click", (ev) => {
        const btn = ev.target.closest("button[data-action]");
        if (!btn) return;
        const action = btn.dataset.action;
        if (action === "yaw-dec") state.yaw = clamp(state.yaw - 5, YAW_MIN, YAW_MAX);
        else if (action === "yaw-inc") state.yaw = clamp(state.yaw + 5, YAW_MIN, YAW_MAX);
        else if (action === "pitch-dec") state.pitch = clamp(state.pitch - 5, PITCH_MIN, PITCH_MAX);
        else if (action === "pitch-inc") state.pitch = clamp(state.pitch + 5, PITCH_MIN, PITCH_MAX);
        else if (action === "zoom-out") state.zoom = clamp(state.zoom - 0.15, ZOOM_MIN, ZOOM_MAX);
        else if (action === "zoom-in") state.zoom = clamp(state.zoom + 0.15, ZOOM_MIN, ZOOM_MAX);
        else if (action === "reset") {
          state.yaw = YAW_DEFAULT;
          state.pitch = PITCH_DEFAULT;
          state.zoom = ZOOM_DEFAULT;
        }
        renderSkyline();
      });
    }

    if (typeof ResizeObserver === "function") {
      const ro = new ResizeObserver(() => renderSkyline());
      ro.observe(canvas);
    }
  }

  async function init() {
    try {
      const [profileResp, telemetryResp] = await Promise.all([
        fetch("./profile.json"),
        fetch("./telemetry.json"),
      ]);
      if (!profileResp.ok || !telemetryResp.ok) {
        throw new Error(`HTTP error loading explorer data (${profileResp.status}/${telemetryResp.status})`);
      }
      const [profile, telemetry] = await Promise.all([profileResp.json(), telemetryResp.json()]);
      if (!profile || !Array.isArray(profile.projects) || !telemetry || !Array.isArray(telemetry.calendar_days)) {
        throw new Error("Invalid explorer data schema");
      }

      state.profile = profile;
      state.telemetry = telemetry;
      state.nWeeks = Math.max(...telemetry.calendar_days.map((d) => d.week)) + 1;
      state.maxCount = Math.max(1, ...telemetry.calendar_days.map((d) => d.count));
      state.dayGrid = new Map();
      telemetry.calendar_days.forEach((d, idx) => state.dayGrid.set(`${d.week}:${d.dow}`, idx));

      applySkylinePalette();
      renderHeaderAndKpis();
      renderStackFilters();
      renderProjects();

      const skylineEl = document.getElementById("skyline");
      if (skylineEl) skylineEl.classList.add("is-interactive");
      wireCanvasInteractions();
      renderSkyline();
      setTooltip("Hover or press arrow keys on the 3D skyline to inspect daily contributions.");

      lightMql.addEventListener("change", () => {
        applySkylinePalette();
        renderSkyline();
      });
    } catch (err) {
      setTooltip(`Unable to load interactive telemetry (${err.message}). Showing static skyline fallback.`);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
