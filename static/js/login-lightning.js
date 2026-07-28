/* =====================================================================
   ChaqmoqApp — login foni: interaktiv chaqmoq animatsiyasi
   ---------------------------------------------------------------------
   • Sichqoncha ortidan yumshoq brend nuri (aura) yuradi.
   • Uchqunlar (sparks) sekin suzadi, kursorga yaqinlashganda tortiladi
     va yorqinlashadi.
   • Vaqti-vaqti bilan yuqoridan CHAQMOQ uradi — nishoni kursor atrofi.
     Tez harakat qilsangiz, chaqmoq tezroq uradi.
   • Kunduz/tun rejimi uchun alohida palitra.

   Ishlash (performance) qoidalari:
   • DPR 2 bilan cheklangan, uchqunlar soni ekran yuzasiga qarab.
   • Tab ko'rinmasa yoki oyna fokusdan chiqsa — animatsiya to'xtaydi.
   • prefers-reduced-motion: reduce → harakat yo'q, faqat tinch nur.
   ===================================================================== */
(function () {
    'use strict';

    const canvas = document.getElementById('authFx');
    const page = document.getElementById('authPage');
    if (!canvas || !page || !canvas.getContext) {
        return;
    }

    const ctx = canvas.getContext('2d', { alpha: true });
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    let W = 0;
    let H = 0;
    let dpr = 1;
    let raf = 0;
    let lastTs = 0;

    // Sichqoncha: tx/ty — nishon, x/y — yumshoq (lerp qilingan) holat.
    const pointer = { x: 0, y: 0, tx: 0, ty: 0, speed: 0, moved: false };

    let sparks = [];
    let bolts = [];
    let flash = 0;
    let boltTimer = 0;

    const PALETTE = {
        night: {
            composite: 'lighter',
            aura: ['rgba(251, 191, 36, 0.26)', 'rgba(251, 191, 36, 0.07)', 'rgba(251, 191, 36, 0)'],
            spark: '251, 191, 36',
            sparkAlpha: 0.55,
            filament: '253, 224, 71',
            filamentAlpha: 0.6,
            boltGlow: 'rgba(251, 191, 36, 0.55)',
            boltCore: 'rgba(255, 251, 235, 0.95)',
            boltWidth: 2.6,
            flash: 'rgba(251, 191, 36, 0.05)'
        },
        day: {
            composite: 'source-over',
            aura: ['rgba(245, 158, 11, 0.30)', 'rgba(245, 158, 11, 0.10)', 'rgba(245, 158, 11, 0)'],
            spark: '202, 106, 8',
            sparkAlpha: 0.5,
            filament: '217, 119, 6',
            filamentAlpha: 0.5,
            boltGlow: 'rgba(245, 158, 11, 0.45)',
            boltCore: 'rgba(180, 83, 9, 0.85)',
            boltWidth: 2.2,
            flash: 'rgba(245, 158, 11, 0.045)'
        }
    };

    function palette() {
        return page.classList.contains('theme-night') ? PALETTE.night : PALETTE.day;
    }

    /* Uchqun nuri oldindan bir marta chiziladi.
       Har kadrda `shadowBlur` ishlatish canvas'ni juda sekinlashtiradi —
       o'rniga tayyor tasvirni drawImage bilan qo'yamiz (o'nlab marta tez). */
    const SPRITE_SIZE = 64;
    const sprites = {};

    function glowSprite(rgb) {
        if (sprites[rgb]) {
            return sprites[rgb];
        }
        const c = document.createElement('canvas');
        c.width = SPRITE_SIZE;
        c.height = SPRITE_SIZE;
        const g = c.getContext('2d');
        const half = SPRITE_SIZE / 2;
        const grad = g.createRadialGradient(half, half, 0, half, half, half);
        grad.addColorStop(0, 'rgba(' + rgb + ', 1)');
        grad.addColorStop(0.18, 'rgba(' + rgb + ', 0.85)');
        grad.addColorStop(0.45, 'rgba(' + rgb + ', 0.22)');
        grad.addColorStop(1, 'rgba(' + rgb + ', 0)');
        g.fillStyle = grad;
        g.fillRect(0, 0, SPRITE_SIZE, SPRITE_SIZE);
        sprites[rgb] = c;
        return c;
    }

    /* ── O'lcham ─────────────────────────────────────────────────── */

    function sparkCount() {
        if (!W || !H) {
            return 24;
        }
        const byArea = Math.round((W * H) / 26000);
        const cap = W < 640 ? 26 : 60;
        return Math.max(16, Math.min(byArea, cap));
    }

    function seedSparks() {
        const n = sparkCount();
        sparks = [];
        for (let i = 0; i < n; i++) {
            sparks.push({
                x: Math.random() * W,
                y: Math.random() * H,
                vx: (Math.random() - 0.5) * 0.13,
                vy: (Math.random() - 0.5) * 0.13,
                r: 0.8 + Math.random() * 1.8,
                phase: Math.random() * Math.PI * 2,
                pulse: 0.5 + Math.random() * 0.9
            });
        }
    }

    function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = canvas.clientWidth || window.innerWidth;
        H = canvas.clientHeight || window.innerHeight;
        canvas.width = Math.round(W * dpr);
        canvas.height = Math.round(H * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        seedSparks();
        if (!pointer.moved) {
            pointer.tx = pointer.x = W / 2;
            pointer.ty = pointer.y = H * 0.34;
        }
    }

    /* ── Chaqmoq geometriyasi (midpoint displacement) ─────────────── */

    function boltPath(x1, y1, x2, y2, displace, minStep) {
        const pts = [];

        function walk(ax, ay, bx, by, d) {
            if (d < minStep) {
                pts.push({ x: bx, y: by });
                return;
            }
            const mx = (ax + bx) / 2;
            const my = (ay + by) / 2;
            const dx = bx - ax;
            const dy = by - ay;
            const len = Math.hypot(dx, dy) || 1;
            // Segmentga perpendikulyar yo'nalishda tasodifiy siljish
            const nx = -dy / len;
            const ny = dx / len;
            const off = (Math.random() - 0.5) * d;
            const cx = mx + nx * off;
            const cy = my + ny * off;
            walk(ax, ay, cx, cy, d / 2);
            walk(cx, cy, bx, by, d / 2);
        }

        pts.push({ x: x1, y: y1 });
        walk(x1, y1, x2, y2, displace);
        return pts;
    }

    function spawnBolt(targetX, targetY, opts) {
        const o = opts || {};
        const startX = targetX + (Math.random() - 0.5) * W * 0.5;
        const startY = -20;
        const main = boltPath(startX, startY, targetX, targetY, Math.min(W, H) * 0.18, 9);

        const branches = [];
        const branchCount = 1 + Math.floor(Math.random() * 3);
        for (let i = 0; i < branchCount; i++) {
            const anchor = main[Math.floor(main.length * (0.25 + Math.random() * 0.55))];
            if (!anchor) {
                continue;
            }
            const len = 40 + Math.random() * 110;
            const ang = (Math.random() - 0.5) * 1.6 + Math.PI / 2;
            branches.push(boltPath(
                anchor.x,
                anchor.y,
                anchor.x + Math.cos(ang) * len * (Math.random() < 0.5 ? -1 : 1),
                anchor.y + Math.sin(ang) * len,
                34,
                7
            ));
        }

        bolts.push({
            main: main,
            branches: branches,
            life: 1,
            decay: o.fast ? 0.075 : 0.045,
            scale: o.scale || 1
        });

        flash = Math.min(1, flash + (o.fast ? 0.35 : 0.55));
        if (bolts.length > 4) {
            bolts.shift();
        }
    }

    function strokePath(pts, width, color, glow, alpha) {
        if (pts.length < 2) {
            return;
        }
        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        for (let i = 1; i < pts.length; i++) {
            ctx.lineTo(pts[i].x, pts[i].y);
        }
        ctx.lineWidth = width;
        ctx.strokeStyle = color;
        ctx.shadowColor = color;
        ctx.shadowBlur = glow;
        ctx.globalAlpha = alpha;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.stroke();
    }

    /* ── Chizish ─────────────────────────────────────────────────── */

    function drawAura(p) {
        const radius = Math.max(200, Math.min(W, H) * 0.44);
        const g = ctx.createRadialGradient(pointer.x, pointer.y, 0, pointer.x, pointer.y, radius);
        g.addColorStop(0, p.aura[0]);
        g.addColorStop(0.45, p.aura[1]);
        g.addColorStop(1, p.aura[2]);
        ctx.globalAlpha = 1;
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(pointer.x, pointer.y, radius, 0, Math.PI * 2);
        ctx.fill();
    }

    /* Kursordan yaqin uchqunlarga elektr ipchalari — sichqoncha
       harakati darrov sezilib turishi uchun. */
    function drawFilaments(p, near) {
        if (!near.length) {
            return;
        }
        ctx.lineCap = 'round';
        for (let i = 0; i < near.length; i++) {
            const n = near[i];
            const alpha = n.force * p.filamentAlpha;
            if (alpha < 0.02) {
                continue;
            }
            const dx = n.s.x - pointer.x;
            const dy = n.s.y - pointer.y;
            const nx = -dy;
            const ny = dx;
            const jitter = 7 + n.force * 9;

            ctx.beginPath();
            ctx.moveTo(pointer.x, pointer.y);
            // Uch bo'g'inli sinsiq ip — har kadrda biroz o'zgaradi (chirsillash)
            for (let k = 1; k <= 3; k++) {
                const f = k / 4;
                const off = (Math.random() - 0.5) * jitter * (1 - Math.abs(f - 0.5) * 1.4);
                ctx.lineTo(
                    pointer.x + dx * f + nx * off / 60,
                    pointer.y + dy * f + ny * off / 60
                );
            }
            ctx.lineTo(n.s.x, n.s.y);

            ctx.strokeStyle = 'rgba(' + p.filament + ', 1)';
            ctx.shadowColor = 'rgba(' + p.filament + ', 0.9)';
            ctx.shadowBlur = 8;
            ctx.lineWidth = 0.7 + n.force * 0.9;
            ctx.globalAlpha = alpha;
            ctx.stroke();
        }
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1;
    }

    function drawSparks(p, dt, t) {
        const pullRadius = 190;
        const near = [];
        const sprite = glowSprite(p.spark);
        for (let i = 0; i < sparks.length; i++) {
            const s = sparks[i];

            s.x += s.vx * dt;
            s.y += s.vy * dt;

            // Kursorga yumshoq tortilish
            const dx = pointer.x - s.x;
            const dy = pointer.y - s.y;
            const dist = Math.hypot(dx, dy);
            let boost = 0;
            if (dist < pullRadius && dist > 0.001) {
                const force = (1 - dist / pullRadius);
                s.x += (dx / dist) * force * 0.55 * dt;
                s.y += (dy / dist) * force * 0.55 * dt;
                boost = force * 0.7;
                if (near.length < 9) {
                    near.push({ s: s, force: force });
                }
            }

            // Chetdan chiqsa — qarama-qarshi tomondan qaytadi
            if (s.x < -10) { s.x = W + 10; }
            if (s.x > W + 10) { s.x = -10; }
            if (s.y < -10) { s.y = H + 10; }
            if (s.y > H + 10) { s.y = -10; }

            const twinkle = 0.55 + 0.45 * Math.sin(t * 0.0016 * s.pulse + s.phase);
            const alpha = Math.min(1, (p.sparkAlpha * twinkle) + boost);
            // Nur diametri: yadro radiusidan ~7 barobar kattaroq
            const size = s.r * (1 + boost * 0.9) * 7;

            ctx.globalAlpha = alpha;
            ctx.drawImage(sprite, s.x - size / 2, s.y - size / 2, size, size);
        }
        ctx.globalAlpha = 1;
        drawFilaments(p, near);
    }

    function drawBolts(p) {
        for (let i = bolts.length - 1; i >= 0; i--) {
            const b = bolts[i];
            const a = Math.max(0, b.life);
            // Ikki qatlam: keng xira nur + ingichka yorqin o'zak
            strokePath(b.main, p.boltWidth * 2.6 * b.scale, p.boltGlow, 26, a * 0.32);
            strokePath(b.main, p.boltWidth * b.scale, p.boltCore, 16, a * 0.92);
            for (let j = 0; j < b.branches.length; j++) {
                strokePath(b.branches[j], p.boltWidth * 0.7 * b.scale, p.boltCore, 10, a * 0.5);
            }
        }
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1;
    }

    /* ── Asosiy tsikl ────────────────────────────────────────────── */

    function frame(ts) {
        raf = requestAnimationFrame(frame);

        if (!lastTs) {
            lastTs = ts;
        }
        // dt — 60fps ga normallashtirilgan qadam (sakrashlarni cheklaymiz)
        const dt = Math.min((ts - lastTs) / 16.666, 3);
        lastTs = ts;

        const p = palette();

        ctx.clearRect(0, 0, W, H);
        ctx.globalCompositeOperation = p.composite;

        // Kursorni yumshoq kuzatish
        const px = pointer.x;
        const py = pointer.y;
        pointer.x += (pointer.tx - pointer.x) * Math.min(1, 0.075 * dt);
        pointer.y += (pointer.ty - pointer.y) * Math.min(1, 0.075 * dt);
        pointer.speed = Math.hypot(pointer.x - px, pointer.y - py);

        drawAura(p);
        drawSparks(p, dt, ts);

        // Chaqmoq: doimiy interval + tez harakatda qo'shimcha zarba
        boltTimer -= dt;
        if (boltTimer <= 0) {
            spawnBolt(
                pointer.x + (Math.random() - 0.5) * 160,
                pointer.y + (Math.random() - 0.5) * 120,
                {}
            );
            // ~2.8–6.5 soniya
            boltTimer = 170 + Math.random() * 220;
        }
        if (pointer.speed > 11 && Math.random() < 0.05) {
            spawnBolt(pointer.tx, pointer.ty, { fast: true, scale: 0.7 });
            boltTimer = Math.max(boltTimer, 60);
        }

        for (let i = bolts.length - 1; i >= 0; i--) {
            bolts[i].life -= bolts[i].decay * dt;
            if (bolts[i].life <= 0) {
                bolts.splice(i, 1);
            }
        }
        drawBolts(p);

        if (flash > 0.001) {
            ctx.globalAlpha = flash;
            ctx.fillStyle = p.flash;
            ctx.fillRect(0, 0, W, H);
            flash -= 0.06 * dt;
        } else {
            flash = 0;
        }

        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = 'source-over';
    }

    function drawStatic() {
        // reduced-motion: harakatsiz, faqat yumshoq brend nuri
        const p = palette();
        ctx.clearRect(0, 0, W, H);
        ctx.globalCompositeOperation = p.composite;
        pointer.x = W / 2;
        pointer.y = H * 0.3;
        drawAura(p);
        ctx.globalCompositeOperation = 'source-over';
    }

    function start() {
        if (raf || reduceMotion.matches) {
            return;
        }
        lastTs = 0;
        raf = requestAnimationFrame(frame);
    }

    function stop() {
        if (raf) {
            cancelAnimationFrame(raf);
            raf = 0;
        }
    }

    /* ── Hodisalar ───────────────────────────────────────────────── */

    let resizeTimer = 0;
    window.addEventListener('resize', function () {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function () {
            resize();
            if (reduceMotion.matches) {
                drawStatic();
            }
        }, 150);
    });

    window.addEventListener('pointermove', function (e) {
        const rect = canvas.getBoundingClientRect();
        pointer.tx = e.clientX - rect.left;
        pointer.ty = e.clientY - rect.top;
        pointer.moved = true;
    }, { passive: true });

    // Sensorli ekranda ham ishlasin
    window.addEventListener('touchmove', function (e) {
        if (!e.touches || !e.touches.length) {
            return;
        }
        const rect = canvas.getBoundingClientRect();
        pointer.tx = e.touches[0].clientX - rect.left;
        pointer.ty = e.touches[0].clientY - rect.top;
        pointer.moved = true;
    }, { passive: true });

    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            stop();
        } else {
            start();
        }
    });

    if (typeof reduceMotion.addEventListener === 'function') {
        reduceMotion.addEventListener('change', function () {
            if (reduceMotion.matches) {
                stop();
                drawStatic();
            } else {
                start();
            }
        });
    }

    resize();
    if (reduceMotion.matches) {
        drawStatic();
    } else {
        start();
    }
})();
