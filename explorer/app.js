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

  const STACK_YAW_MIN = 20;
  const STACK_YAW_MAX = 70;
  const STACK_YAW_DEFAULT = 45;
  const STACK_PITCH_MIN = 16;
  const STACK_PITCH_MAX = 42;
  const STACK_PITCH_DEFAULT = 25;

  const STACK_THEMES = {
    dark: {
      bg0: "#0D1117",
      bg1: "#111827",
      cardBg: "#161B22",
      cardBorder: "#30363D",
      pillBg: "#0D1117",
      title: "#F0F6FC",
      muted: "#8B949E",
      spine: "#30363D",
      shadow: "#000000",
      tiers: {
        "01": { accent: "#58A6FF", top: "#132641", left: "#13477F", right: "#0D325B", grid: "#1F4D80" },
        "02": { accent: "#818CF8", top: "#1C1F42", left: "#393E8A", right: "#292D68", grid: "#43499E" },
        "03": { accent: "#34D399", top: "#0F2D27", left: "#156352", right: "#0F483B", grid: "#1B7A65" },
        "04": { accent: "#F59E0B", top: "#2E210C", left: "#754E0C", right: "#553809", grid: "#8A5C10" },
      },
    },
    light: {
      bg0: "#FFFFFF",
      bg1: "#F4F7FB",
      cardBg: "#FFFFFF",
      cardBorder: "#D0D7DE",
      pillBg: "#F4F7FB",
      title: "#1F2328",
      muted: "#57606A",
      spine: "#CBD5E1",
      shadow: "#1F2937",
      tiers: {
        "01": { accent: "#0969DA", top: "#EAF3FF", left: "#B7D6FB", right: "#8ABBF7", grid: "#C2DCFB" },
        "02": { accent: "#4F46E5", top: "#EEF0FF", left: "#C4CBFD", right: "#9FA9FA", grid: "#CFD4FE" },
        "03": { accent: "#047857", top: "#E8F8F2", left: "#A7E5CD", right: "#79D6B3", grid: "#BBEBD8" },
        "04": { accent: "#B45309", top: "#FEF5E6", left: "#FBD69A", right: "#F7BE63", grid: "#FDE0B0" },
      },
    },
  };

  const state = {
    profile: null,
    telemetry: null,
    yaw: YAW_DEFAULT,
    pitch: PITCH_DEFAULT,
    zoom: ZOOM_DEFAULT,
    activeTier: "all",
    hoveredIdx: -1,
    focusedIdx: -1,
    selectedIdx: -1,
    todayIdx: -1,
    hitBars: [],
    dayGrid: new Map(),
    nWeeks: 53,
    maxCount: 1,
    dragging: false,
    dragMoved: false,
    lastX: 0,
    lastY: 0,
    // Interactive 3D Tech Stack camera & selection state
    stackYaw: STACK_YAW_DEFAULT,
    stackPitch: STACK_PITCH_DEFAULT,
    stackExploded: false,
    stackHoverTier: null,
    stackHitTargets: [],
    stackDragging: false,
    stackDragMoved: false,
    stackLastX: 0,
    stackLastY: 0,
  };

  const lightMql = window.matchMedia("(prefers-color-scheme: light)");
  const dateFmt = new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
  const monthFmt = new Intl.DateTimeFormat("en-US", {
    month: "short",
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

  function formatIsoDate(isoStr) {
    if (typeof isoStr !== "string" || !isoStr.trim()) return isoStr || "";
    const ms = Date.parse(isoStr.length === 10 ? `${isoStr}T00:00:00Z` : isoStr);
    if (!Number.isFinite(ms)) return isoStr;
    return dateFmt.format(new Date(ms));
  }

  function formatUpdatedDate(isoStr) {
    if (typeof isoStr !== "string" || !isoStr.trim()) return null;
    const ms = Date.parse(isoStr);
    if (!Number.isFinite(ms)) return null;
    return `Updated ${dateFmt.format(new Date(ms))}`;
  }

  function wrapItems(items, maxChars) {
    const sep = " · ";
    const lines = [];
    let current = "";
    for (const item of items) {
      const cand = current ? `${current}${sep}${item}` : item;
      if (current && cand.length > maxChars) {
        lines.push(current);
        current = item;
      } else {
        current = cand;
      }
    }
    if (current) lines.push(current);
    return lines.slice(0, 2);
  }

  function fillPoly(ctx, pts, fill, stroke, lineWidth) {
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i += 1) {
      ctx.lineTo(pts[i][0], pts[i][1]);
    }
    ctx.closePath();
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = lineWidth || 0.7;
      ctx.stroke();
    }
  }

  function fillRoundRect(ctx, x, y, w, h, r, fill, stroke, lineWidth) {
    const rad = Math.min(r, w * 0.5, h * 0.5);
    ctx.beginPath();
    ctx.moveTo(x + rad, y);
    ctx.arcTo(x + w, y, x + w, y + h, rad);
    ctx.arcTo(x + w, y + h, x, y + h, rad);
    ctx.arcTo(x, y + h, x, y, rad);
    ctx.arcTo(x, y, x + w, y, rad);
    ctx.closePath();
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = lineWidth || 1;
      ctx.stroke();
    }
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
    renderLegend(pal);
  }

  function renderLegend(pal) {
    const el = document.getElementById("skyline-legend");
    if (!el || !pal || !pal.levels) return;
    el.replaceChildren();
    const less = document.createElement("span");
    less.textContent = "Less";
    el.appendChild(less);
    for (let lvl = 0; lvl <= 4; lvl += 1) {
      const sw = document.createElement("span");
      sw.className = "legend-swatch";
      sw.style.setProperty("background-color", pal.levels[String(lvl)][0]);
      sw.style.setProperty("border-color", pal.levels[String(lvl)][3]);
      el.appendChild(sw);
    }
    const more = document.createElement("span");
    more.textContent = "More";
    el.appendChild(more);
  }

  function setTooltip(text) {
    const el = document.getElementById("skyline-tooltip");
    if (el) el.textContent = text;
  }

  function setStackStatus(text) {
    const el = document.getElementById("stack-status");
    if (el) el.textContent = text;
  }

  function formatProjectDetail(proj) {
    const parts = [];
    if (proj.commits > 0) parts.push(`${proj.commits} ${proj.commits === 1 ? "commit" : "commits"}`);
    if (proj.prs > 0) parts.push(`${proj.prs} ${proj.prs === 1 ? "PR" : "PRs"}`);
    return parts.length ? `${proj.repo} · ${parts.join(", ")}` : proj.repo;
  }

  function announceDay(idx, prefix) {
    const el = document.getElementById("skyline-tooltip");
    if (!el || !state.telemetry || idx < 0 || idx >= state.telemetry.calendar_days.length) return;
    const day = state.telemetry.calendar_days[idx];
    const noun = day.count === 1 ? "contribution" : "contributions";
    const lead = prefix ? `${prefix} · ` : idx === state.todayIdx ? "We are here (Today) · " : "";

    el.replaceChildren();
    const summarySpan = document.createElement("span");
    summarySpan.textContent = `${lead}${formatIsoDate(day.date)} (${day.date}): ${day.count} ${noun} · week ${day.week + 1}`;
    el.appendChild(summarySpan);

    const projects = Array.isArray(day.projects) ? day.projects : [];
    if (projects.length > 0) {
      for (const proj of projects) {
        const label = formatProjectDetail(proj);
        if (!proj.is_private && isSafeUrl(proj.url)) {
          const a = document.createElement("a");
          a.className = "tooltip-repo-chip";
          a.href = proj.url;
          a.rel = "noopener noreferrer";
          a.textContent = label;
          el.appendChild(a);
        } else {
          const chip = document.createElement("span");
          chip.className = "tooltip-repo-chip is-private";
          chip.textContent = label;
          el.appendChild(chip);
        }
      }
    } else if (day.count > 0) {
      const chip = document.createElement("span");
      chip.className = "tooltip-repo-chip is-private";
      chip.textContent = "Private / review activity";
      el.appendChild(chip);
    }
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
      (cssW * 0.80) / (nWeeks * Math.cos(yaw0) + 7 * Math.sin(yaw0)),
      (cssH * 0.56) /
        (nWeeks * Math.sin(yaw0) * Math.sin(pitch0) +
          7 * Math.cos(yaw0) * Math.sin(pitch0) +
          (112 / 16.5) * Math.cos(pitch0))
    );
    const scale = baseScale * state.zoom;
    const cx = cssW * 0.5;
    const cy = cssH * 0.62;

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

    fillPoly(ctx, [pLeft, pFront, pbFront, pbLeft], pal.plinth_left, pal.plinth_stroke, 0.8);
    fillPoly(ctx, [pFront, pRight, pbRight, pbFront], pal.plinth_right, pal.plinth_stroke, 0.8);
    fillPoly(ctx, [pBack, pRight, pFront, pLeft], pal.plinth_top, pal.plinth_stroke, 0.9);

    // Draw all bars back-to-front (week asc, dow asc) and store 3 visible face quads
    const s = 0.80;
    const margin = (1.0 - s) * 0.5;
    const hitBars = [];
    let todayTopCenter = null;
    let todayRing = null;
    const inspectIdx = state.hoveredIdx !== -1 ? state.hoveredIdx : state.selectedIdx !== -1 ? state.selectedIdx : state.focusedIdx;
    let inspectTopCenter = null;

    for (let i = 0; i < days.length; i += 1) {
      const day = days[i];
      const w0 = day.week + margin;
      const d0 = day.dow + margin;
      const h = barHeight(day.count, state.maxCount);
      const cols = pal.levels[String(day.level)] || pal.levels["0"];
      const isToday = i === state.todayIdx;
      const isActive = i === state.hoveredIdx || i === state.focusedIdx || i === state.selectedIdx;

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

      fillPoly(ctx, leftQuad, cols[1], null, 0);
      fillPoly(ctx, rightQuad, cols[2], null, 0);
      fillPoly(
        ctx,
        topQuad,
        isActive ? pal.peak_cap : cols[0],
        isActive ? pal.title : isToday ? pal.accent : cols[3],
        isActive ? 1.5 : isToday ? 1.35 : 0.55
      );

      const topCenter = [(t0[0] + t2[0]) * 0.5, (t0[1] + t2[1]) * 0.5];
      if (isToday) {
        todayTopCenter = topCenter;
        const padR = 0.28;
        todayRing = [
          proj(w0 - padR, d0 - padR, h),
          proj(w0 + s + padR, d0 - padR, h),
          proj(w0 + s + padR, d0 + s + padR, h),
          proj(w0 - padR, d0 + s + padR, h),
        ];
      }
      if (i === inspectIdx) {
        inspectTopCenter = topCenter;
      }

      hitBars.push({ idx: i, day, topCenter, quads: [topQuad, leftQuad, rightQuad] });
    }

    // 3D-projected Month & Weekday plinth labels
    if (cssW >= 420) {
      ctx.font = '10px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
      ctx.fillStyle = pal.axis_text;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const seenMonths = new Set();
      let lastLabelWeek = -4;
      for (const day of days) {
        if (day.dow === 0) {
          const ym = day.date.slice(0, 7);
          if (!seenMonths.has(ym) && day.week - lastLabelWeek >= 3) {
            seenMonths.add(ym);
            lastLabelWeek = day.week;
            const mp = proj(day.week + 0.5, 8.8, -plinthDrop * 0.5);
            const label = monthFmt.format(new Date(`${day.date}T00:00:00Z`));
            ctx.fillText(label, mp[0], mp[1]);
          }
        }
      }

      ctx.textAlign = "right";
      for (const [dowIdx, lbl] of [
        [1, "Mon"],
        [3, "Wed"],
        [5, "Fri"],
      ]) {
        const lp = proj(-1.8, dowIdx + 0.5, 0);
        ctx.fillText(lbl, lp[0], lp[1]);
      }
    }

    // Glowing "WE ARE HERE · TODAY" 3D beacon pin anchored to Today's bar
    const showingHoverCard = inspectIdx >= 0 && inspectTopCenter !== null;
    const hoveringToday = showingHoverCard && inspectIdx === state.todayIdx;

    if (todayTopCenter && state.todayIdx >= 0 && !hoveringToday) {
      const todayDay = days[state.todayIdx];
      const [tx, ty] = todayTopCenter;
      ctx.save();
      if (showingHoverCard) ctx.globalAlpha = 0.34;
      if (todayRing) {
        fillPoly(ctx, todayRing, null, pal.accent, 1.3);
      }

      const compact = cssW < 520;
      const pinW = compact ? 168 : 204;
      const pinH = 38;
      const pinX = clamp(tx - pinW * 0.58, 12, cssW - pinW - 12);
      const pinY = clamp(ty - 118, 14, cssH - pinH - 12);
      const anchorX = clamp(tx, pinX + 14, pinX + pinW - 14);

      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = pal.accent;
      ctx.lineWidth = 1.25;
      ctx.beginPath();
      ctx.moveTo(anchorX, pinY + pinH);
      ctx.lineTo(tx, ty);
      ctx.stroke();
      ctx.restore();

      ctx.beginPath();
      ctx.arc(tx, ty, 6, 0, Math.PI * 2);
      ctx.strokeStyle = pal.accent;
      ctx.lineWidth = 1.1;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(tx, ty, 3.1, 0, Math.PI * 2);
      ctx.fillStyle = pal.accent;
      ctx.fill();

      fillRoundRect(ctx, pinX, pinY, pinW, pinH, 8, pal.hud_bg, pal.accent, 1.2);
      ctx.beginPath();
      ctx.arc(pinX + 13, pinY + 13, 3, 0, Math.PI * 2);
      ctx.fillStyle = pal.accent;
      ctx.fill();

      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.font = '700 9.5px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
      ctx.fillStyle = pal.accent;
      ctx.fillText("WE ARE HERE · TODAY", pinX + 22, pinY + 13.5);

      const noun = todayDay.count === 1 ? "commit" : "commits";
      const valText = compact
        ? `${formatIsoDate(todayDay.date)} · ${todayDay.count}`
        : `${formatIsoDate(todayDay.date)} · ${todayDay.count} ${noun}`;
      ctx.font = '600 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif';
      ctx.fillStyle = pal.title;
      ctx.fillText(valText, pinX + 13, pinY + 27.5);
      ctx.restore();
    }

    // Floating On-Canvas Hover/Inspect Card showing exact commits & projects worked on that date
    if (showingHoverCard) {
      const day = days[inspectIdx];
      const [hx, hy] = inspectTopCenter;
      const projects = Array.isArray(day.projects) ? day.projects.slice(0, 4) : [];
      const noun = day.count === 1 ? "contribution" : "contributions";
      const headerLead = hoveringToday ? "WE ARE HERE · TODAY · " : "";
      const headerText = `${headerLead}${formatIsoDate(day.date)}`;
      const subText = `${day.count} ${noun} · Week ${day.week + 1}`;

      const projectLines = [];
      if (projects.length > 0) {
        for (const p of projects) {
          projectLines.push({
            text: formatProjectDetail(p),
            isPrivate: Boolean(p.is_private),
          });
        }
      } else if (day.count > 0) {
        projectLines.push({ text: "Private / review activity", isPrivate: true });
      } else {
        projectLines.push({ text: "No recorded commits on this date", isPrivate: true });
      }

      ctx.font = '700 10px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
      let maxTextW = ctx.measureText(headerText).width + 18;
      ctx.font = '600 11.5px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif';
      maxTextW = Math.max(maxTextW, ctx.measureText(subText).width + 10);
      ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
      for (const row of projectLines) {
        maxTextW = Math.max(maxTextW, ctx.measureText(row.text).width + 20);
      }

      const cardW = clamp(Math.ceil(maxTextW + 24), 216, Math.min(360, cssW - 24));
      const cardH = 44 + projectLines.length * 17 + 8;
      const cardX = clamp(hx - cardW * 0.5, 12, cssW - cardW - 12);
      let cardY = hy - cardH - 26;
      if (cardY < 12) {
        cardY = clamp(hy + 22, 12, cssH - cardH - 12);
      }
      const anchorX = clamp(hx, cardX + 16, cardX + cardW - 16);
      const anchorY = cardY < hy ? cardY + cardH : cardY;

      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = pal.accent;
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.moveTo(anchorX, anchorY);
      ctx.lineTo(hx, hy);
      ctx.stroke();
      ctx.restore();

      ctx.beginPath();
      ctx.arc(hx, hy, 5.8, 0, Math.PI * 2);
      ctx.strokeStyle = pal.accent;
      ctx.lineWidth = 1.3;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(hx, hy, 2.8, 0, Math.PI * 2);
      ctx.fillStyle = pal.peak_cap;
      ctx.fill();

      fillRoundRect(ctx, cardX, cardY, cardW, cardH, 10, pal.hud_bg, pal.accent, 1.3);
      ctx.beginPath();
      ctx.arc(cardX + 14, cardY + 15, 3, 0, Math.PI * 2);
      ctx.fillStyle = pal.accent;
      ctx.fill();

      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.font = '700 10px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
      ctx.fillStyle = pal.accent;
      ctx.fillText(headerText, cardX + 23, cardY + 15);

      ctx.font = '600 11.5px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif';
      ctx.fillStyle = pal.title;
      ctx.fillText(subText, cardX + 13, cardY + 32);

      // Subtle divider above project breakdown
      ctx.beginPath();
      ctx.moveTo(cardX + 12, cardY + 42);
      ctx.lineTo(cardX + cardW - 12, cardY + 42);
      ctx.strokeStyle = pal.hud_border;
      ctx.lineWidth = 0.9;
      ctx.stroke();

      ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
      projectLines.forEach((row, idx) => {
        const ry = cardY + 54 + idx * 17;
        ctx.beginPath();
        ctx.arc(cardX + 16, ry, 2.4, 0, Math.PI * 2);
        ctx.fillStyle = row.isPrivate ? pal.muted : pal.accent;
        ctx.fill();
        ctx.fillStyle = row.isPrivate ? pal.muted : pal.title;
        let label = row.text;
        while (label.length > 10 && ctx.measureText(label).width > cardW - 36) {
          label = `${label.slice(0, -2)}…`;
        }
        ctx.fillText(label, cardX + 25, ry);
      });
    }

    state.hitBars = hitBars;
  }

  function renderStackCanvas() {
    const canvas = document.getElementById("stack-canvas");
    if (!canvas || !state.profile) return;
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

    const theme = STACK_THEMES[currentMode()];
    const tiers = state.profile.tech_stack_tiers;
    const wide = cssW >= 740;

    // Background gradient
    const grad = ctx.createLinearGradient(0, 0, cssW, cssH);
    grad.addColorStop(0, theme.bg0);
    grad.addColorStop(1, theme.bg1);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, cssW, cssH);

    // Subtle dot grid
    ctx.fillStyle = theme.spine;
    ctx.globalAlpha = 0.25;
    for (let gx = 20; gx < cssW; gx += 28) {
      for (let gy = 20; gy < cssH; gy += 28) {
        ctx.fillRect(gx, gy, 1.5, 1.5);
      }
    }
    ctx.globalAlpha = 1;

    // 3D orthographic projection for floating isometric architectural slabs
    const yaw = state.stackYaw * DEG;
    const pitch = state.stackPitch * DEG;
    const slabHalf = wide ? Math.min(96, cssW * 0.092) : Math.min(84, cssW * 0.25);
    const slabThick = wide ? 15 : 13;
    const spacing = state.stackExploded ? (wide ? 88 : 72) : (wide ? 76 : 62);

    const centerX = wide ? Math.min(225, cssW * 0.21) : cssW * 0.5;
    const topY = wide ? (state.stackExploded ? 68 : 84) : (state.stackExploded ? 56 : 68);

    function projSlab(x, y, z, baseCenterY) {
      const rx = x * Math.cos(yaw) - y * Math.sin(yaw);
      const ry = (x * Math.sin(yaw) + y * Math.cos(yaw)) * Math.sin(pitch);
      return [centerX + rx, baseCenterY + ry - z];
    }

    const tierCy = tiers.map((_, i) => topY + i * spacing);

    // Floor shadow beneath tier 04
    const shadowCy = tierCy[tiers.length - 1] + slabThick + 12;
    const shPts = [
      projSlab(-slabHalf * 1.04, -slabHalf * 1.04, 0, shadowCy),
      projSlab(slabHalf * 1.04, -slabHalf * 1.04, 0, shadowCy),
      projSlab(slabHalf * 1.04, slabHalf * 1.04, 0, shadowCy),
      projSlab(-slabHalf * 1.04, slabHalf * 1.04, 0, shadowCy),
    ];
    ctx.save();
    ctx.globalAlpha = currentMode() === "dark" ? 0.35 : 0.09;
    fillPoly(ctx, shPts, theme.shadow, null, 0);
    ctx.restore();

    // Dashed architectural vertical spine connecting layers
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = theme.spine;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(centerX, tierCy[0]);
    ctx.lineTo(centerX, tierCy[tiers.length - 1] + slabThick);
    ctx.stroke();
    ctx.restore();

    const hitTargets = [];

    // Draw slabs bottom-to-top (04 -> 01) for authentic 3D occlusion
    for (let i = tiers.length - 1; i >= 0; i -= 1) {
      const tier = tiers[i];
      const tStyle = theme.tiers[tier.index] || theme.tiers["01"];
      const isSelected = state.activeTier === tier.id;
      const isHovered = state.stackHoverTier === tier.id;
      const isDimmed = state.activeTier !== "all" && !isSelected && !isHovered;
      const liftZ = isSelected ? 12 : isHovered ? 7 : 0;
      const cy = tierCy[i];

      const p0 = projSlab(-slabHalf, -slabHalf, liftZ, cy);
      const p1 = projSlab(slabHalf, -slabHalf, liftZ, cy);
      const p2 = projSlab(slabHalf, slabHalf, liftZ, cy);
      const p3 = projSlab(-slabHalf, slabHalf, liftZ, cy);

      const b1 = [p1[0], p1[1] + slabThick];
      const b2 = [p2[0], p2[1] + slabThick];
      const b3 = [p3[0], p3[1] + slabThick];

      const leftFace = [p3, p2, b2, b3];
      const rightFace = [p2, p1, b1, b2];
      const topFace = [p0, p1, p2, p3];

      ctx.save();
      if (isDimmed) ctx.globalAlpha = 0.45;

      fillPoly(ctx, leftFace, tStyle.left, tStyle.accent, isSelected || isHovered ? 1.3 : 0.85);
      fillPoly(ctx, rightFace, tStyle.right, tStyle.accent, isSelected || isHovered ? 1.3 : 0.85);
      fillPoly(ctx, topFace, tStyle.top, tStyle.accent, isSelected ? 2.0 : isHovered ? 1.6 : 1.15);

      // Etched 3x3 isometric surface grid
      ctx.strokeStyle = tStyle.grid;
      ctx.lineWidth = 0.7;
      for (const f of [-0.45, 0, 0.45]) {
        const gA = projSlab(-slabHalf, slabHalf * f, liftZ, cy);
        const gB = projSlab(slabHalf, slabHalf * f, liftZ, cy);
        ctx.beginPath();
        ctx.moveTo(gA[0], gA[1]);
        ctx.lineTo(gB[0], gB[1]);
        ctx.stroke();

        const gC = projSlab(slabHalf * f, -slabHalf, liftZ, cy);
        const gD = projSlab(slabHalf * f, slabHalf, liftZ, cy);
        ctx.beginPath();
        ctx.moveTo(gC[0], gC[1]);
        ctx.lineTo(gD[0], gD[1]);
        ctx.stroke();
      }

      // Layer badge positioned cleanly on the exposed front quadrant of every slab (L01-L04 all visible)
      const badgeCenter = projSlab(0, slabHalf * 0.34, liftZ, cy);
      const bw = 44;
      const bh = 22;
      fillRoundRect(
        ctx,
        badgeCenter[0] - bw * 0.5,
        badgeCenter[1] - bh * 0.5,
        bw,
        bh,
        6,
        theme.pillBg,
        tStyle.accent,
        isSelected ? 1.5 : 1.1
      );
      ctx.font = '700 11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
      ctx.fillStyle = tStyle.accent;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`L${tier.index}`, badgeCenter[0], badgeCenter[1] + 0.5);

      // Right-hand callout cards + leader lines on wide viewports
      let cardQuad = null;
      if (wide) {
        const cardX = Math.max(centerX + slabHalf * 1.48 + 26, cssW * 0.41);
        const cardW = cssW - cardX - 24;
        const cardH = 62;
        const cardY = cy - cardH * 0.5 - liftZ * 0.4;

        // Rightmost corner of slab for crisp leader line
        const rightCorner = p1[0] >= p2[0] ? p1 : p2;
        ctx.save();
        ctx.setLineDash([3, 3]);
        ctx.strokeStyle = tStyle.accent;
        ctx.lineWidth = isSelected || isHovered ? 1.5 : 1.05;
        ctx.beginPath();
        ctx.moveTo(rightCorner[0] + 4, rightCorner[1]);
        ctx.lineTo(cardX, cardY + cardH * 0.5);
        ctx.stroke();
        ctx.restore();

        ctx.beginPath();
        ctx.arc(cardX, cardY + cardH * 0.5, 3, 0, Math.PI * 2);
        ctx.fillStyle = tStyle.accent;
        ctx.fill();

        fillRoundRect(
          ctx,
          cardX,
          cardY,
          cardW,
          cardH,
          10,
          theme.cardBg,
          isSelected || isHovered ? tStyle.accent : theme.cardBorder,
          isSelected ? 1.6 : 1.0
        );
        fillRoundRect(ctx, cardX, cardY, 5, cardH, 2.5, tStyle.accent, null, 0);

        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        ctx.font = '700 13px -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif';
        ctx.fillStyle = tStyle.accent;
        ctx.fillText(`${tier.index} · ${tier.label}`, cardX + 18, cardY + 20);

        const maxChars = Math.max(36, Math.floor((cardW - 36) / 6.8));
        const wrapped = wrapItems(tier.items, maxChars);
        ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
        ctx.fillStyle = theme.title;
        if (wrapped.length === 1) {
          ctx.fillText(wrapped[0], cardX + 18, cardY + 43);
        } else {
          ctx.fillText(wrapped[0], cardX + 18, cardY + 38);
          ctx.fillText(wrapped[1], cardX + 18, cardY + 52);
        }

        cardQuad = [
          [cardX, cardY],
          [cardX + cardW, cardY],
          [cardX + cardW, cardY + cardH],
          [cardX, cardY + cardH],
        ];
      }

      ctx.restore();

      const quads = cardQuad ? [topFace, leftFace, rightFace, cardQuad] : [topFace, leftFace, rightFace];
      hitTargets.push({ tier, quads });
    }

    // Hint label on compact viewports
    if (!wide) {
      ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
      ctx.fillStyle = theme.muted;
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.fillText("Tap any 3D layer slab (L01–L04) to filter projects", cssW * 0.5, cssH - 10);
    }

    state.stackHitTargets = hitTargets;
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

  function selectTier(tierId) {
    state.activeTier = tierId;
    renderStackFilters();
    renderStackCanvas();
    renderProjects();
    if (tierId === "all") {
      setStackStatus("Showing all 4 architecture layers — click any 3D slab (01–04) to filter projects.");
    } else {
      const tierObj = state.profile.tech_stack_tiers.find((t) => t.id === tierId);
      if (tierObj) {
        setStackStatus(`Selected Layer ${tierObj.index} · ${tierObj.label}: ${tierObj.items.join(" · ")}`);
      }
    }
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
      btn.addEventListener("click", () => selectTier(tier.id));
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

  function hitTestSkyline(px, py) {
    for (let i = state.hitBars.length - 1; i >= 0; i -= 1) {
      const entry = state.hitBars[i];
      if (entry.quads.some((q) => pointInQuad(px, py, q))) {
        return entry.idx;
      }
    }
    return -1;
  }

  function wireCanvasInteractions() {
    const canvas = document.getElementById("skyline-canvas");
    if (!canvas) return;

    canvas.addEventListener("pointerdown", (ev) => {
      state.dragging = true;
      state.dragMoved = false;
      state.lastX = ev.clientX;
      state.lastY = ev.clientY;
      canvas.setPointerCapture(ev.pointerId);
    });

    canvas.addEventListener("pointerup", (ev) => {
      const wasClick = !state.dragMoved;
      state.dragging = false;
      if (canvas.hasPointerCapture(ev.pointerId)) {
        canvas.releasePointerCapture(ev.pointerId);
      }
      if (wasClick) {
        const rect = canvas.getBoundingClientRect();
        const hit = hitTestSkyline(ev.clientX - rect.left, ev.clientY - rect.top);
        if (hit !== -1) {
          state.selectedIdx = hit;
          renderSkyline();
          announceDay(hit, hit === state.todayIdx ? "We are here (Today)" : "Pinned");
        }
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
        if (Math.abs(dx) > 2 || Math.abs(dy) > 2) state.dragMoved = true;
        state.lastX = ev.clientX;
        state.lastY = ev.clientY;
        state.yaw = clamp(state.yaw + dx * 0.3, YAW_MIN, YAW_MAX);
        state.pitch = clamp(state.pitch + dy * 0.25, PITCH_MIN, PITCH_MAX);
        renderSkyline();
        return;
      }

      const hit = hitTestSkyline(ev.clientX - rect.left, ev.clientY - rect.top);
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
      if (ev.key === "t" || ev.key === "T") {
        ev.preventDefault();
        state.focusedIdx = state.todayIdx;
        state.selectedIdx = state.todayIdx;
        renderSkyline();
        announceDay(state.todayIdx, "We are here (Today)");
        return;
      }
      if (ev.key === "0") {
        ev.preventDefault();
        state.yaw = YAW_DEFAULT;
        state.pitch = PITCH_DEFAULT;
        state.zoom = ZOOM_DEFAULT;
        state.selectedIdx = -1;
        renderSkyline();
        return;
      }

      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(ev.key)) return;
      ev.preventDefault();
      const days = state.telemetry.calendar_days;
      if (!days.length) return;
      if (state.focusedIdx === -1) {
        state.focusedIdx = state.todayIdx >= 0 ? state.todayIdx : days.length - 1;
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
        if (action === "today") {
          state.yaw = YAW_DEFAULT;
          state.pitch = PITCH_DEFAULT;
          state.zoom = 1.15;
          state.selectedIdx = state.todayIdx;
          state.focusedIdx = state.todayIdx;
          renderSkyline();
          announceDay(state.todayIdx, "We are here (Today)");
          return;
        }
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
          state.selectedIdx = -1;
        }
        renderSkyline();
      });
    }

    if (typeof ResizeObserver === "function") {
      const ro = new ResizeObserver(() => renderSkyline());
      ro.observe(canvas);
    }
  }

  function hitTestStack(px, py) {
    // Hit targets were appended bottom-to-top (04 -> 01); walk reverse (01 -> 04)
    for (let i = state.stackHitTargets.length - 1; i >= 0; i -= 1) {
      const entry = state.stackHitTargets[i];
      if (entry.quads.some((q) => pointInQuad(px, py, q))) {
        return entry.tier;
      }
    }
    return null;
  }

  function wireStackInteractions() {
    const canvas = document.getElementById("stack-canvas");
    if (!canvas) return;

    canvas.addEventListener("pointerdown", (ev) => {
      state.stackDragging = true;
      state.stackDragMoved = false;
      state.stackLastX = ev.clientX;
      state.stackLastY = ev.clientY;
      canvas.setPointerCapture(ev.pointerId);
    });

    canvas.addEventListener("pointerup", (ev) => {
      const wasClick = !state.stackDragMoved;
      state.stackDragging = false;
      if (canvas.hasPointerCapture(ev.pointerId)) {
        canvas.releasePointerCapture(ev.pointerId);
      }
      if (wasClick) {
        const rect = canvas.getBoundingClientRect();
        const hitTier = hitTestStack(ev.clientX - rect.left, ev.clientY - rect.top);
        if (hitTier) {
          selectTier(state.activeTier === hitTier.id ? "all" : hitTier.id);
        }
      }
    });

    canvas.addEventListener("pointerleave", () => {
      state.stackDragging = false;
      if (state.stackHoverTier !== null) {
        state.stackHoverTier = null;
        canvas.style.removeProperty("cursor");
        renderStackCanvas();
      }
    });

    canvas.addEventListener("pointermove", (ev) => {
      const rect = canvas.getBoundingClientRect();
      if (state.stackDragging) {
        const dx = ev.clientX - state.stackLastX;
        const dy = ev.clientY - state.stackLastY;
        if (Math.abs(dx) > 2 || Math.abs(dy) > 2) state.stackDragMoved = true;
        state.stackLastX = ev.clientX;
        state.stackLastY = ev.clientY;
        state.stackYaw = clamp(state.stackYaw + dx * 0.3, STACK_YAW_MIN, STACK_YAW_MAX);
        state.stackPitch = clamp(state.stackPitch + dy * 0.25, STACK_PITCH_MIN, STACK_PITCH_MAX);
        renderStackCanvas();
        return;
      }

      const hitTier = hitTestStack(ev.clientX - rect.left, ev.clientY - rect.top);
      const nextId = hitTier ? hitTier.id : null;
      if (nextId !== state.stackHoverTier) {
        state.stackHoverTier = nextId;
        canvas.style.setProperty("cursor", hitTier ? "pointer" : "grab");
        renderStackCanvas();
        if (hitTier) {
          setStackStatus(`Layer ${hitTier.index} · ${hitTier.label} (${hitTier.items.length} technologies) — click to filter projects.`);
        }
      }
    });

    canvas.addEventListener("keydown", (ev) => {
      const tiers = state.profile ? state.profile.tech_stack_tiers : [];
      if (!tiers.length) return;
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        const curIdx = tiers.findIndex((t) => t.id === state.activeTier);
        let nextIdx = 0;
        if (curIdx === -1) {
          nextIdx = ev.key === "ArrowDown" ? 0 : tiers.length - 1;
        } else {
          nextIdx = (curIdx + (ev.key === "ArrowDown" ? 1 : -1) + tiers.length) % tiers.length;
        }
        selectTier(tiers[nextIdx].id);
        return;
      }
      if (ev.key === "Escape" || ev.key === "0") {
        ev.preventDefault();
        selectTier("all");
        return;
      }
      if (ev.key === "e" || ev.key === "E") {
        ev.preventDefault();
        toggleStackExplode();
      }
    });

    function toggleStackExplode() {
      state.stackExploded = !state.stackExploded;
      const btn = document.querySelector('[data-stack-action="explode"]');
      if (btn) btn.setAttribute("aria-pressed", state.stackExploded ? "true" : "false");
      renderStackCanvas();
    }

    const toolbar = document.querySelector(".stack-controls");
    if (toolbar) {
      toolbar.addEventListener("click", (ev) => {
        const btn = ev.target.closest("button[data-stack-action]");
        if (!btn) return;
        const action = btn.dataset.stackAction;
        if (action === "explode") {
          toggleStackExplode();
        } else if (action === "reset") {
          state.stackYaw = STACK_YAW_DEFAULT;
          state.stackPitch = STACK_PITCH_DEFAULT;
          state.stackExploded = false;
          const expBtn = document.querySelector('[data-stack-action="explode"]');
          if (expBtn) expBtn.setAttribute("aria-pressed", "false");
          selectTier("all");
        }
      });
    }

    if (typeof ResizeObserver === "function") {
      const ro = new ResizeObserver(() => renderStackCanvas());
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
      let latestIdx = -1;
      let latestDate = "";
      telemetry.calendar_days.forEach((d, idx) => {
        state.dayGrid.set(`${d.week}:${d.dow}`, idx);
        if (d.date >= latestDate) {
          latestDate = d.date;
          latestIdx = idx;
        }
      });
      const exactTodayIdx = telemetry.today_date
        ? telemetry.calendar_days.findIndex((d) => d.date === telemetry.today_date)
        : -1;
      state.todayIdx = exactTodayIdx >= 0 ? exactTodayIdx : latestIdx;

      applySkylinePalette();
      renderHeaderAndKpis();
      renderStackFilters();
      renderProjects();

      const skylineEl = document.getElementById("skyline");
      if (skylineEl) skylineEl.classList.add("is-interactive");
      const stackEl = document.getElementById("stack");
      if (stackEl) stackEl.classList.add("is-interactive");

      wireCanvasInteractions();
      wireStackInteractions();
      renderSkyline();
      renderStackCanvas();

      if (state.todayIdx >= 0) {
        announceDay(state.todayIdx, "We are here (Today)");
      } else {
        setTooltip("Hover or press arrow keys on the 3D skyline to inspect daily contributions.");
      }

      lightMql.addEventListener("change", () => {
        applySkylinePalette();
        renderSkyline();
        renderStackCanvas();
      });
    } catch (err) {
      setTooltip(`Unable to load interactive telemetry (${err.message}). Showing static skyline fallback.`);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
