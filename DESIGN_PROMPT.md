# ChaqmoqApp — Admin Panel Redesign Prompt

> Bu faylni Claude'ga yuborganingizda — admin panelingizning **dizayni**ni
> noldan qayta loyihalaydi, **lekin** funksionallik (Python views, URL'lar,
> form names, AJAX call'lar) tegmasdan qoladi.

---

## Promptni qanday ishlatish kerak

**1-variant — bir butun rejim:**
Pastdagi prompt'ni to'liq nusxa olib, Claude Code yoki Claude.ai'ga yuboring.

**2-variant — bosqichma-bosqich:**
Promptni 4 ta bosqichga bo'ling:
- Bosqich 1: **Design system + base.html** (poydevor)
- Bosqich 2: **Dashboard + sidebar + header**
- Bosqich 3: **Jadvallar, formlar, modallar**
- Bosqich 4: **Sahifa-sahifa qolganlari**

Har bosqichdan keyin sinab ko'ring, keyin keyingisiga o'ting.

---

## ✂️ NUSXA OLINADIGAN PROMPT (English — Claude works better in English)

```
You are redesigning the admin/management UI of ChaqmoqApp, a Django SaaS for
learning centers in Uzbekistan. **Visual redesign only.** Do not change
Python views, URL patterns, form field names, AJAX endpoints, model field
names, or JavaScript event handlers. The behavior must remain identical —
clicking the same buttons, submitting the same forms, navigating to the
same routes — but the surface must look like a polished 2026 product.

────────────────────────────────────────────────────────────────────────
PROJECT CONSTRAINTS
────────────────────────────────────────────────────────────────────────
Stack (already installed — use these, don't add new dependencies unless
strictly required):
- Django 5 templates ({% extends %} / {% block %} / {% url %})
- Bootstrap 5 (via static/vendor/bootstrap/css/bootstrap.min.css)
- Bootstrap Icons + FontAwesome 6 (CDN)
- ApexCharts (already loaded for charts)
- Google Font: "Plus Jakarta Sans" (already linked)
- Existing CSS files in static/css/: theme.css, dashboards.css,
  role-theme.css, light-mode-fixes.css, login-premium.css, moliya.css

Multi-tenant: every page must work for any center (don't hard-code names).
Languages: UI is in Uzbek — keep all labels and tooltips Uzbek (don't
translate). Currency: so'm. Number format: humanize.intcomma.

Accessibility:
- WCAG AA contrast (4.5:1 for body text, 3:1 for large)
- All interactive elements must have visible focus rings (keyboard navigation)
- Min tap target 44×44px on mobile
- Respect prefers-reduced-motion
- aria-label on icon-only buttons

Browsers: latest 2 versions of Chrome / Safari / Firefox + iOS Safari 15+.
No IE / no obsolete polyfills.

────────────────────────────────────────────────────────────────────────
DESIGN DIRECTION
────────────────────────────────────────────────────────────────────────
Mood: "Linear × Vercel × Stripe Dashboard" — modern, dense-but-calm,
information-rich, professional. Not flashy, not childish, not gradient-heavy.

Visual rules:
- **Dark mode is the default**, light mode supported via .light-mode class
  on <html> or via @media (prefers-color-scheme: light) — keep both clean
- Soft gradients only on hero/header areas; flat surfaces everywhere else
- 1px borders, low-contrast (rgba white 6–10% in dark, rgba black 6–10% in light)
- Subtle elevation: outline + tiny shadow (max 0 8px 24px rgba(0,0,0,.25))
- 16px base radius for cards, 10px for inputs/buttons, 999px for pills
- Generous whitespace — never cram. 24px section gaps, 16px card padding min
- Typography: Plus Jakarta Sans, 14px body, 28–32px page titles, semibold (600)
  for emphasis, 800–900 only for one hero number per card
- Numbers (money / counts) must use tabular-nums for column alignment

Color tokens (override in :root, document the system):
  --bg-app: #050709
  --bg-surface: rgba(15,20,33,.7)         (cards)
  --bg-surface-hi: rgba(22,28,46,.85)     (popovers/modals)
  --border: rgba(255,255,255,.08)
  --border-hi: rgba(255,255,255,.14)
  --text: #f8fafc
  --text-muted: #94a3b8
  --text-subtle: #64748b
  --accent: #6366f1            (indigo)  — primary actions
  --accent-2: #38bdf8           (sky)     — info / charts
  --success: #22c55e
  --warning: #f59e0b
  --danger:  #ef4444
  --gradient-hero: linear-gradient(135deg, #4f46e5 0%, #6366f1 50%, #8b5cf6 100%)

Light-mode equivalents — generate from same scale (use HSL math or static):
  --bg-app (light): #f8fafc
  --bg-surface (light): #ffffff
  --border (light): rgba(15,23,42,.08)
  --text (light): #0f172a

────────────────────────────────────────────────────────────────────────
HARD-LINE PRESERVATION RULES (DO NOT BREAK ANY OF THESE)
────────────────────────────────────────────────────────────────────────
1. **Every {% url 'name' %} stays.** Don't rename URL names anywhere.
2. **Every <form action="...">, <input name="...">, <select name="...">,
   <button name="...">** — names and values are sacred. CSRF token must remain.
3. **Don't move logic into the frontend.** If a Django view returns a context
   variable (e.g. `teacher_data`, `is_locked`), keep using it.
4. **JS hooks**: any element with `id="..."`, `data-...="..."`, or class
   names referenced by JS files (in static/js/, panel.js, app.js, etc.) —
   keep those exact selectors. Wrap them in new visual chrome rather than
   replacing.
5. **HTMX/AJAX endpoints**: Every `fetch()`, `htmx-get`, `data-href`, or AJAX
   URL must continue to point to the same backend route.
6. **Permissions / role gating**: every {% if user.is_superuser %},
   {% if request.user.role == 'manager' %}, etc. stays exactly as-is.
7. **Pagination links** (`?page=`, `?year=`, `?month=`) — preserve query
   string handling.
8. **Don't introduce new dependencies** without listing them and justifying
   the size impact (e.g. don't add Tailwind alongside Bootstrap).
9. **Tenant features**: many sections are conditionally shown based on
   `center.features` / `center_ui_feature_enabled()`. Preserve all
   `{% if feature_xxx %}` blocks.
10. **Don't delete templates** — modify in place. If you create a new
    component template, add it under `templates/components/` and include
    via `{% include %}`.

────────────────────────────────────────────────────────────────────────
SCOPE — WHICH SCREENS TO REDESIGN
────────────────────────────────────────────────────────────────────────
ALL admin / staff-facing pages reachable after login. In particular:

**Layout / chrome (highest impact, redesign first):**
- templates/base.html — root layout (header, sidebar, content area, footer)
- templates/partials/sidebar*.html, partials/header*.html (if exist)
- Bottom navigation on mobile (≤768px) — sticky, 5-icon nav

**Dashboards:**
- core/templates/core/dashboard*.html
- accounts/templates/accounts/superadmin_dashboard.html
- chaqmoq/templates/director_dashboard*.html
- billing/templates/billing/dashboard*.html

**Education (largest area):**
- education/templates/education/group_list.html, group_detail.html,
  group_form.html
- attendance pages (group_month_attendance.html, daily attendance)
- teacher_salary_list.html, teacher_groups.html, teacher_salary_summary.html
- enrollment, exam, certificate templates

**Finance:**
- billing/templates/billing/* (subscriptions, invoices, payments)
- moliya/* (income, expense)

**Settings & SuperAdmin:**
- accounts/templates/accounts/center_edit.html (feature toggles —
  redesign as toggle cards grid)
- center create / list / picker pages

**Auth:**
- login, register, password reset (already has login-premium.css — modernize)

**State pages:**
- 404, 429, no_permission, empty states

────────────────────────────────────────────────────────────────────────
COMPONENT LIBRARY TO BUILD (consistent across all pages)
────────────────────────────────────────────────────────────────────────
Define each as a reusable {% include %} partial in templates/components/
or via CSS classes. Document one example for each:

1. **Top app bar** — fixed, 56px tall, has: logo, center switcher, search,
   notifications, theme toggle, user menu. On scroll: subtle blur backdrop.
2. **Sidebar** — collapsible to icons (60px) ↔ expanded (260px). Active
   route gets accent border-left + tinted bg. Section headers (small,
   uppercase, muted).
3. **Mobile bottom nav** — only shown <768px, 5 icon buttons (home,
   groups, attendance, finance, more).
4. **Page header** — title, breadcrumbs, action buttons row. Sticky on
   scroll if page is long.
5. **Stat card** — label (small, muted, uppercase), big number,
   delta/sparkline, optional icon. Multiple sizes (xs/sm/md/lg).
6. **Data table** — header sticky, rows hover-highlight, zebra optional,
   right-aligned numbers, sortable columns (chevron icon), pagination
   below. Empty state inside.
7. **Form** — labels above inputs, helper text below, error states
   (red border + message), success states (green check), file/audio/image
   inputs with previews. Multi-step form variant.
8. **Modal** — backdrop blur, centered card, close X, footer with primary
   + ghost actions.
9. **Toast / alert** — top-right slide-in, 4 variants (info/success/warn/error),
   auto-dismiss option.
10. **Empty state** — illustration / large icon, title, sub, primary CTA.
11. **Skeleton loader** — for tables and cards while data loads.
12. **Filter bar** — chip pills + dropdowns + search input, "Clear all"
    button, active filter count badge.
13. **Tag / badge** — small pill, 6 color variants matching tokens.
14. **Avatar** — circle, initial fallback, status dot (online/idle/offline).
15. **Toggle switch** — smooth animation, locked state for plan-gated
    features, hover preview.
16. **Tabs** — underlined active, ghost variant, vertical variant
    (for settings pages).
17. **Segmented control** — used for time range selectors (Today / Week /
    Month / Year).
18. **Drawer** — slides in from right, 90vw on mobile, 480px on desktop.

────────────────────────────────────────────────────────────────────────
INTERACTION DETAILS (these matter — they make it feel premium)
────────────────────────────────────────────────────────────────────────
- All buttons: 150ms transform + opacity transition. Pressed state =
  scale(0.97). Hover = bg-tint + slight border-hi.
- Inputs: focus = 2px accent ring + slight scale on label.
- Cards: hover = border-hi + 0 8px 24px rgba(0,0,0,.25) lift, no scale.
- Page transitions: fade + 8px y-translate on view change (use
  view-transition-name where supported, fallback graceful).
- Loading: skeleton, never spinners except inside buttons during submit.
- Charts: animate on load (ApexCharts has built-in animations — just
  configure colors to match tokens).
- Number changes: count-up animation for hero stats on dashboard.
- Empty states: friendly copy, never "No data". e.g. "Hali davomat
  olinmagan — birinchi darsdan boshlang" + CTA button.

────────────────────────────────────────────────────────────────────────
DARK MODE / LIGHT MODE
────────────────────────────────────────────────────────────────────────
- Both modes must be production-quality, not just inverted colors.
- Light mode: warm whites, no pure black text (use #0f172a), shadows
  visible (not lost on white).
- Theme toggle in top bar — persist to localStorage and respect system
  preference on first visit.
- All charts re-render with new palette on toggle (ApexCharts theme).
- Existing light-mode-fixes.css overrides — extend it, don't fight it.

────────────────────────────────────────────────────────────────────────
RESPONSIVE BREAKPOINTS
────────────────────────────────────────────────────────────────────────
- ≤480px: phone portrait — single column, bottom nav, drawer for sidebar
- 481–768px: large phone / small tablet — 2-column where it fits
- 769–1024px: tablet — sidebar collapsed by default, 2–3 column grid
- 1025–1440px: laptop — full sidebar, 3–4 column grid
- ≥1441px: desktop — max content width 1400px, centered, 4–6 column grid

Mobile-first CSS — base styles work on phone, scale up via min-width
media queries.

────────────────────────────────────────────────────────────────────────
DELIVERABLES (per phase / per session)
────────────────────────────────────────────────────────────────────────
1. **One CSS file** (or amended theme.css) with the design tokens at the
   top, then component classes. Heavily commented sections.
2. **Modified Django templates** — minimal HTML changes, focus on classes
   and structure. Keep template inheritance.
3. **No new JS** unless strictly necessary for interactions. If added,
   vanilla only (no jQuery, no React).
4. **A 'design changelog' note** at the bottom of theme.css listing what
   was redesigned in this session.

For each modified template, leave a one-line comment at top:
`{# Redesigned 2026-MM-DD: layout chrome, kept all form names + URLs #}`

────────────────────────────────────────────────────────────────────────
QUALITY BAR (self-check before finishing)
────────────────────────────────────────────────────────────────────────
Walk through each page yourself and verify:
☐ All Django form fields render and submit (don't drop {{ form.x }})
☐ All {% url %} links work (no renamed URL names)
☐ All AJAX/htmx endpoints unchanged
☐ Mobile (375px) and Desktop (1440px) both look intentional
☐ Light mode looks intentional, not broken
☐ All buttons reachable by keyboard (Tab order natural)
☐ No layout shift (CLS) on load — set sizes for images/charts
☐ Font weights consistent with the type scale
☐ Color contrast WCAG AA confirmed for text on any background
☐ Active nav item visually distinguishable
☐ Empty states are friendly (Uzbek copy)
☐ Permission checks ({% if user.role %}) untouched
☐ Multi-tenant: no center name hardcoded

If you change anything that risks breaking behavior, flag it explicitly
and ask before committing.

────────────────────────────────────────────────────────────────────────
INSPIRATION (reference quality bar — don't copy literally)
────────────────────────────────────────────────────────────────────────
- linear.app — for dense data tables and command palette feel
- vercel.com/dashboard — for cards, charts, dark theme polish
- stripe.com/dashboard — for finance tables and form clarity
- attio.com — for sidebar + content layout
- pieces.app — for file/asset management views

Avoid: Material Design 3 looks (too "Google"), heavy gradients on every
element, neumorphism, rainbow accents, animated backgrounds.

────────────────────────────────────────────────────────────────────────
START HERE
────────────────────────────────────────────────────────────────────────
1. Read templates/base.html, static/css/theme.css, static/css/dashboards.css
   to understand the current foundation.
2. Audit the 5 most-visited admin pages (likely: dashboard, group list,
   teacher_salary_list, group_detail, settings).
3. Propose the design tokens and 2 component examples (button, card)
   first — get my approval — then expand.
4. Phase by phase, commit one phase at a time. Report what you changed
   and what you intentionally left alone.

If you encounter a template using `{% block %}` you don't recognize,
keep all blocks intact and only restyle within them. If a template has
inline CSS that contradicts the new tokens, replace it with token
references. Inline styles for one-off positioning (top: 12px) are okay.
```

---

## 🎯 Promptni qisqartirilgan versiyasi (agar uzun versiyaga vaqt kam bo'lsa)

```
Redesign the entire admin UI of my Django + Bootstrap 5 SaaS (ChaqmoqApp,
o'quv markazlar boshqaruvi) — visual only, don't break any view, URL,
form name, or JS hook. Stack: Bootstrap 5, Plus Jakarta Sans,
Bootstrap Icons + FA6, ApexCharts. Dark mode default, light mode supported.

Direction: "Linear × Vercel × Stripe" — clean, dense, professional.
Tokens in static/css/theme.css. Components: top bar, sidebar, mobile
bottom nav, stat cards, data tables, forms, modals, toasts. Mobile-first.
WCAG AA. Tabular numbers for money. Uzbek labels untouched.

Hard rules:
1. Every {% url %}, form name="...", {% if user.role %} stays
2. Every JS data-attribute / id stays
3. Tenant features ({% if feature_x %}) preserved
4. No new deps

Start by reading base.html and theme.css. Propose tokens + 2 components,
get approval, then redesign phase by phase: chrome → dashboards →
education → finance → settings → auth. After each phase report exactly
what changed.
```

---

## Foydalanish bo'yicha tavsiyalar

1. **Branch yarating:** `git checkout -b ui-redesign-2026` — bu juda muhim, dizayn buzilsa qaytarib olasiz
2. **Backup oling:** `git add -A && git commit -m "before redesign"` 
3. **Promptni Claude'ga yuboring:**
   - Claude Code: `/Users/amirxon/Desktop/ChaqmoqApp` ichida turib promptni yuboring
   - Yoki Claude.ai web: zip qilib yuboring va promptni qo'shing
4. **Bosqichma-bosqich:** har Claude tugatgandan keyin sinab ko'ring (login, dashboard, group list, attendance) — keyin keyingi bosqichga o'ting
5. **Har commit'dan keyin:** `python manage.py runserver` da o'zingiz tekshirib, screenshot oling — bir narsa buzilsa darrov sezasiz

## Oddiy buzilish testlari (Claude tugatgandan keyin)
```bash
# 1. URL'lar
python manage.py shell -c "from django.urls import reverse; reverse('education:teacher_salary_list')"

# 2. Templates compile bo'ladimi
python manage.py validate_templates 2>&1 | grep -i error

# 3. Dev server boot bo'ladimi
python manage.py runserver --noreload
```

## Dizayn sifatini baholash (subjective — siz qarang)
- 🟢 Mukammal: Linear/Vercel'ga o'xshaydi, dense lekin oson o'qiladi
- 🟡 O'rtacha: chiroyli lekin "shablonga o'xshash"
- 🔴 Yomon: rangsiz, tushunarsiz yoki funksional buzilgan

Promptni `/Users/amirxon/Desktop/ChaqmoqApp/DESIGN_PROMPT.md` faylida saqladim — har safar Claude'ga yuborganda mana shu faylni yuborsangiz bo'ladi. Sinab ko'ring va natija qanday bo'lganini aytib bering — keyin yanada yaxshilashingiz mumkin.