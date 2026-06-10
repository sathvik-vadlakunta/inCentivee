# Dashboard UI Redesign — Sidebar Navigation + Modern Facelift

## Goal
Replace the current top-nav tab layout with a sidebar-based navigation system. Modernize the visual design with clean typography, consistent spacing, and a professional dark/light theme.

---

## 1. Sidebar Navigation Structure

### Layout
```
+--------+--------------------------------------------------+
| LOGO   |  Header Bar (customer name, date range, actions) |
|--------|--------------------------------------------------|
| NAV    |                                                  |
|        |  Main Content Area                               |
| Home   |                                                  |
| Cust.  |                                                  |
|  ├ Oak |                                                  |
|  ├ Sojo|                                                  |
|  └ Down|                                                  |
| Board  |                                                  |
| Reports|                                                  |
| Settings|                                                 |
|        |                                                  |
|--------|                                                  |
| v1.0   |                                                  |
+--------+--------------------------------------------------+
```

### Sidebar Sections
```
Dashboard (home icon)
  → Overview / stats across all customers

Customers (users icon)
  → Customer list (collapsible)
  → Click customer → sub-nav appears:
    ├ Overview
    ├ SEO & GEO
    │  ├ Checklist
    │  ├ Overview
    │  ├ Rankings
    │  ├ Traffic
    │  ├ Audit
    │  ├ Backlinks
    │  └ Integrations
    ├ AI Mentions
    ├ Content
    └ Settings

Board (kanban icon)
  → Kanban pipeline view

Reports (chart icon)
  → Cross-customer reporting

Settings (gear icon)
  → Global settings, API keys, team
```

### Sidebar Behavior
- **Collapsible**: Toggle to icon-only mode (64px → 16px padding icons)
- **Active state**: Highlighted background on current page
- **Sub-menus**: Expand/collapse with chevron animation
- **Mobile**: Slides in as overlay from left
- **Persistent**: Stays visible across all pages (not re-rendered per page)

---

## 2. Design System

### Colors
```css
:root {
  /* Primary */
  --primary: #2563eb;        /* Blue 600 */
  --primary-hover: #1d4ed8;  /* Blue 700 */
  --primary-light: #dbeafe;  /* Blue 100 */

  /* Neutrals */
  --bg-page: #f8fafc;        /* Slate 50 */
  --bg-card: #ffffff;
  --bg-sidebar: #0f172a;     /* Slate 900 */
  --text-primary: #0f172a;   /* Slate 900 */
  --text-secondary: #64748b; /* Slate 500 */
  --text-sidebar: #cbd5e1;   /* Slate 300 */
  --border: #e2e8f0;         /* Slate 200 */

  /* Status */
  --success: #16a34a;        /* Green 600 */
  --warning: #d97706;        /* Amber 600 */
  --danger: #dc2626;         /* Red 600 */
  --info: #0891b2;           /* Cyan 600 */

  /* Spacing scale */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;

  /* Typography */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
}
```

### Card Component
```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: var(--space-6);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.card-header {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-4);
}
```

### Metric Card
```html
<div class="metric-card">
  <div class="metric-label">Clicks</div>
  <div class="metric-value">350</div>
  <div class="metric-change positive">+12% ▲</div>
</div>
```

### Tables
- Alternating row backgrounds (subtle)
- Sticky headers on scroll
- Sort indicators on column headers
- Compact padding for data-dense tables

### Buttons
```css
.btn { padding: 0.5rem 1rem; border-radius: 0.5rem; font-weight: 500; }
.btn-primary { background: var(--primary); color: white; }
.btn-secondary { background: var(--bg-page); border: 1px solid var(--border); }
.btn-ghost { background: transparent; color: var(--text-secondary); }
.btn-sm { padding: 0.25rem 0.75rem; font-size: 0.875rem; }
```

---

## 3. Page Layouts

### Dashboard Home
```
+--------------------------------------------------+
| Welcome back, Jon            May 26, 2026        |
+--------------------------------------------------+
| [3] Active    [1] Setup    [0] Attention          |
| Customers     Customers    Customers              |
+--------------------------------------------------+
| Recent Activity                                   |
| • Oakridge audit completed — Score: 72           |
| • Sojo keywords updated — 30 tracked            |
| • Downtown Dental added to pipeline              |
+--------------------------------------------------+
| Quick Stats                                       |
| Total Clicks: 1,200 | Avg Health: 68 | ...       |
+--------------------------------------------------+
```

### Customer Detail
```
+--------------------------------------------------+
| ← Customers    Oakridge Dental Smiles            |
|                oakridgedentalsmiles.com           |
+--------------------------------------------------+
| [Overview] [SEO] [AI Mentions] [Content] [Settings]|
+--------------------------------------------------+
| (sub-tab content based on selection)              |
+--------------------------------------------------+
```

The top-level customer tabs stay as horizontal tabs within the content area. SEO sub-tabs (Checklist, Rankings, Traffic, etc.) also stay horizontal but are nested under the SEO section.

### Board
- Keep existing kanban layout
- Update card styling to match new design system
- Add health score badges per plan spec

---

## 4. Responsive Breakpoints

```css
/* Mobile: sidebar hidden, hamburger menu */
@media (max-width: 768px) {
  .sidebar { transform: translateX(-100%); position: fixed; z-index: 50; }
  .sidebar.open { transform: translateX(0); }
  .main-content { margin-left: 0; }
}

/* Tablet: collapsed sidebar (icons only) */
@media (min-width: 769px) and (max-width: 1024px) {
  .sidebar { width: 64px; }
  .sidebar .nav-label { display: none; }
  .main-content { margin-left: 64px; }
}

/* Desktop: full sidebar */
@media (min-width: 1025px) {
  .sidebar { width: 240px; }
  .main-content { margin-left: 240px; }
}
```

---

## 5. Implementation Approach

### Phase 1: Base Layout (do with Tier 1)
1. Create `base.html` template with sidebar + content area
2. Move navigation from top tabs to sidebar
3. Apply design system CSS variables
4. Update card/table/button styles
5. All existing pages extend `base.html`

### Phase 2: Polish (do with Tier 2)
1. Add Inter font via Google Fonts
2. Smooth transitions on sidebar collapse
3. Active state highlighting
4. Mobile hamburger menu
5. Breadcrumb navigation

### Phase 3: Advanced (do with Tier 3)
1. Dark mode toggle
2. Notification badge in sidebar
3. Quick-search (Cmd+K) overlay
4. Customizable dashboard widgets

---

## Files to Modify

- `dashboard/templates/base.html` — NEW base template with sidebar
- `dashboard/templates/index.html` — Extend base, dashboard home content
- `dashboard/templates/customer_detail.html` — Extend base, move tabs to content area
- `dashboard/templates/board.html` — Extend base, kanban in content area
- `dashboard/static/css/style.css` — NEW or replace existing styles
- `dashboard/app.py` — Add dashboard home route with aggregate stats

## Verification

- [ ] Sidebar shows on all pages with correct navigation
- [ ] Active page highlighted in sidebar
- [ ] Customer sub-navigation works (expand/collapse)
- [ ] Mobile: sidebar hidden, hamburger menu works
- [ ] Tablet: icon-only sidebar
- [ ] All existing functionality preserved after layout change
- [ ] Design system colors/typography applied consistently
