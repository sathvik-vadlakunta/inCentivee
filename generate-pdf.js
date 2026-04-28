#!/usr/bin/env node
/**
 * Generate a branded PracticeRank PDF report from audit JSON.
 * Uses the system Chrome via CDP (no puppeteer needed).
 */

const fs = require('fs');
const { execSync } = require('child_process');
const http = require('http');
const path = require('path');

const inputFile = process.argv[2] || 'hilltop-report.json';
const report = JSON.parse(fs.readFileSync(inputFile, 'utf8'));

const nameSlug = (report.practice_name || 'practice').toLowerCase().replace(/\s+/g, '-');
const outputFile = path.resolve(__dirname, `practicerank-report-${nameSlug}.pdf`);

function statusColor(s) {
  return { critical: '#ef4444', needs_work: '#f59e0b', good: '#22c55e', excellent: '#06b6d4' }[s] || '#888';
}
function statusLabel(s) {
  return { critical: 'Critical', needs_work: 'Needs Work', good: 'Good', excellent: 'Excellent' }[s] || s;
}
function scoreColor(sc) {
  if (sc >= 81) return '#22c55e';
  if (sc >= 61) return '#06b6d4';
  if (sc >= 31) return '#f59e0b';
  return '#ef4444';
}
function visIcon(v) {
  if (v === 'yes') return '<span style="color:#22c55e;font-weight:700;">&#10003; Visible</span>';
  if (v === 'partial') return '<span style="color:#f59e0b;font-weight:700;">&#9680; Partial</span>';
  return '<span style="color:#ef4444;font-weight:700;">&#10007; Not Visible</span>';
}

const CAT_NAMES = {
  gbp: 'Google Business Profile',
  ai_readiness: 'AI Search Readiness',
  reviews: 'Review Strength',
  local_seo: 'Local SEO',
  content: 'Content & On-Page SEO',
  technical: 'Technical SEO',
};

let catsHtml = '';
for (const [key, label] of Object.entries(CAT_NAMES)) {
  const cat = (report.categories || {})[key] || {};
  const sc = cat.score || 0;
  const st = cat.status || '';
  const findings = (cat.findings || []).map(f => `<li style="margin-bottom:6px;color:#334155;font-size:13px;line-height:1.5;">${f}</li>`).join('');

  let extra = '';
  if (key === 'reviews') {
    extra = `
    <div style="display:flex;gap:24px;margin-top:12px;">
      <div style="background:#f1f5f9;padding:10px 18px;border-radius:8px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#0f172a;">${cat.count || '?'}</div>
        <div style="font-size:11px;color:#64748b;">Your Reviews</div>
      </div>
      <div style="background:#f1f5f9;padding:10px 18px;border-radius:8px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#ef4444;">${cat.competitor_reviews || '?'}</div>
        <div style="font-size:11px;color:#64748b;">${cat.competitor_name || 'Competitor'}</div>
      </div>
      <div style="background:#f1f5f9;padding:10px 18px;border-radius:8px;text-align:center;">
        <div style="font-size:24px;font-weight:700;color:#0f172a;">${cat.rating || '?'}</div>
        <div style="font-size:11px;color:#64748b;">Your Rating</div>
      </div>
    </div>`;
  }

  catsHtml += `
  <div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-bottom:16px;break-inside:avoid;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <h3 style="margin:0;font-size:16px;color:#0f172a;">${label}</h3>
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="background:${statusColor(st)};color:#fff;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;">${statusLabel(st)}</span>
        <span style="font-size:24px;font-weight:800;color:${scoreColor(sc)};">${sc}</span>
      </div>
    </div>
    <ul style="padding-left:18px;margin:0;">${findings}</ul>
    ${extra}
  </div>`;
}

let aiRows = '';
for (const [platform, data] of Object.entries(report.ai_visibility || {})) {
  aiRows += `
  <tr>
    <td style="padding:10px 14px;font-weight:600;text-transform:capitalize;border-bottom:1px solid #e2e8f0;">${platform}</td>
    <td style="padding:10px 14px;border-bottom:1px solid #e2e8f0;">${visIcon(data.visible)}</td>
    <td style="padding:10px 14px;color:#475569;font-size:13px;border-bottom:1px solid #e2e8f0;">${data.reason || ''}</td>
  </tr>`;
}

let actionsHtml = '';
(report.priority_actions || []).forEach((a, i) => {
  const ic = a.impact === 'high' ? '#ef4444' : '#f59e0b';
  actionsHtml += `
  <div style="display:flex;gap:14px;align-items:flex-start;margin-bottom:14px;break-inside:avoid;">
    <div style="min-width:36px;height:36px;background:#6366f1;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;">${i + 1}</div>
    <div style="flex:1;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap;">
        <strong style="font-size:14px;color:#0f172a;">${a.title || ''}</strong>
        <span style="background:${ic};color:#fff;padding:2px 8px;border-radius:12px;font-size:10px;font-weight:600;">${(a.impact || '').toUpperCase()}</span>
        <span style="color:#6366f1;font-weight:700;font-size:13px;">${a.est_patients_mo || ''} patients/mo</span>
      </div>
      <p style="margin:0;color:#475569;font-size:13px;line-height:1.5;">${a.description || ''}</p>
    </div>
  </div>`;
});

const proj = report.projections || {};

const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 36px 44px; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; color: #0f172a; line-height: 1.6; margin: 0; padding: 0; }
  table { border-spacing: 0; }
</style>
</head>
<body>

<!-- Header -->
<div style="display:flex;justify-content:space-between;align-items:center;padding-bottom:16px;border-bottom:3px solid #6366f1;margin-bottom:24px;">
  <div>
    <div style="font-size:28px;font-weight:800;color:#6366f1;">PracticeRank</div>
    <div style="font-size:12px;color:#64748b;margin-top:2px;">AI-Powered Dental Marketing Intelligence</div>
  </div>
  <div style="text-align:right;">
    <div style="font-size:11px;color:#64748b;">SEO & AI Search Audit Report</div>
    <div style="font-size:14px;font-weight:600;color:#0f172a;">${report.practice_name || ''}</div>
    <div style="font-size:12px;color:#64748b;">${report.city || ''}, ${report.state || ''}</div>
  </div>
</div>

<!-- Score Hero -->
<div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:16px;padding:28px;color:#fff;text-align:center;margin-bottom:20px;">
  <div style="font-size:60px;font-weight:900;line-height:1;">${report.overall_score || ''}</div>
  <div style="font-size:13px;opacity:0.8;margin-top:4px;">out of 100</div>
  <div style="display:inline-block;margin-top:10px;background:rgba(255,255,255,0.2);padding:5px 18px;border-radius:20px;font-size:18px;font-weight:700;">Grade: ${report.grade || ''}</div>
  <p style="margin:14px auto 0;max-width:540px;font-size:13px;line-height:1.6;opacity:0.9;">${report.executive_summary || ''}</p>
</div>

<!-- Revenue Lost -->
<div style="background:#fef2f2;border:2px solid #fca5a5;border-radius:12px;padding:16px;text-align:center;margin-bottom:24px;">
  <div style="font-size:11px;color:#ef4444;font-weight:600;text-transform:uppercase;letter-spacing:1px;">Estimated Revenue Lost Annually</div>
  <div style="font-size:30px;font-weight:900;color:#ef4444;margin-top:4px;">${report.revenue_lost_annually || ''}</div>
  <div style="font-size:11px;color:#64748b;margin-top:4px;">Based on patient lifetime value of ${report.patient_lifetime_value || ''}</div>
</div>

<!-- Category Scores -->
<h2 style="font-size:17px;color:#0f172a;margin-bottom:14px;">Category Breakdown</h2>
${catsHtml}

<!-- AI Visibility -->
<div style="break-before:page;"></div>
<h2 style="font-size:17px;color:#0f172a;margin-bottom:14px;">AI Platform Visibility</h2>
<p style="font-size:12px;color:#64748b;margin-top:-8px;margin-bottom:12px;">40%+ of patients now use AI assistants to find dentists. Here's whether they'd find you.</p>
<table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-radius:12px;margin-bottom:24px;">
  <thead>
    <tr style="background:#f8fafc;">
      <th style="padding:10px 14px;text-align:left;font-size:11px;color:#64748b;border-bottom:2px solid #e2e8f0;width:120px;">Platform</th>
      <th style="padding:10px 14px;text-align:left;font-size:11px;color:#64748b;border-bottom:2px solid #e2e8f0;width:120px;">Status</th>
      <th style="padding:10px 14px;text-align:left;font-size:11px;color:#64748b;border-bottom:2px solid #e2e8f0;">Details</th>
    </tr>
  </thead>
  <tbody>${aiRows}</tbody>
</table>

<!-- CTA 1 -->
<div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:12px;padding:22px;color:#fff;text-align:center;margin-bottom:24px;">
  <div style="font-size:17px;font-weight:700;">Your practice is invisible to AI search.</div>
  <div style="font-size:13px;opacity:0.85;margin-top:6px;">40%+ of patients now ask ChatGPT, Gemini, and other AI assistants for dentist recommendations — and they'll never hear about you.</div>
  <a href="https://calendly.com/ethan-practicerank" style="margin-top:12px;display:inline-block;background:#fff;color:#6366f1;padding:9px 24px;border-radius:8px;font-weight:700;font-size:13px;text-decoration:none;">Book a Free Strategy Call &rarr; calendly.com/ethan-practicerank</a>
</div>

<!-- Priority Actions -->
<h2 style="font-size:17px;color:#0f172a;margin-bottom:14px;">Top 5 Priority Actions</h2>
${actionsHtml}

<!-- Growth Projections -->
<h2 style="font-size:17px;color:#0f172a;margin-top:24px;margin-bottom:14px;">Growth Projections</h2>
<div style="display:flex;gap:10px;margin-bottom:24px;">
  <div style="flex:1;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px;text-align:center;">
    <div style="font-size:10px;color:#64748b;font-weight:600;">TODAY</div>
    <div style="font-size:26px;font-weight:800;color:#ef4444;margin-top:6px;">${proj.current_inquiries_mo || ''}</div>
    <div style="font-size:10px;color:#64748b;">inquiries/mo</div>
  </div>
  <div style="flex:1;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px;text-align:center;">
    <div style="font-size:10px;color:#64748b;font-weight:600;">3 MONTHS</div>
    <div style="font-size:26px;font-weight:800;color:#f59e0b;margin-top:6px;">${proj.month_3 || ''}</div>
    <div style="font-size:10px;color:#64748b;">inquiries/mo</div>
  </div>
  <div style="flex:1;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px;text-align:center;">
    <div style="font-size:10px;color:#64748b;font-weight:600;">6 MONTHS</div>
    <div style="font-size:26px;font-weight:800;color:#22c55e;margin-top:6px;">${proj.month_6 || ''}</div>
    <div style="font-size:10px;color:#64748b;">inquiries/mo</div>
  </div>
  <div style="flex:1;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px;text-align:center;">
    <div style="font-size:10px;color:#64748b;font-weight:600;">12 MONTHS</div>
    <div style="font-size:26px;font-weight:800;color:#6366f1;margin-top:6px;">${proj.month_12 || ''}</div>
    <div style="font-size:10px;color:#64748b;">inquiries/mo</div>
  </div>
</div>

<!-- Final CTA -->
<div style="background:#0f172a;border-radius:12px;padding:24px;color:#fff;text-align:center;margin-top:16px;">
  <div style="font-size:13px;color:#f59e0b;font-weight:600;">You're leaving ${report.revenue_lost_annually || ''} on the table every year.</div>
  <div style="font-size:20px;font-weight:800;margin-top:6px;">Ready to start getting the patients you deserve?</div>
  <div style="margin-top:10px;font-size:12px;color:#94a3b8;">Schedule a free 30-minute strategy call. We'll walk through your report and show you exactly how to fix it.</div>
  <a href="https://calendly.com/ethan-practicerank" style="margin-top:14px;display:inline-block;background:#6366f1;color:#fff;padding:10px 28px;border-radius:8px;font-weight:700;font-size:14px;text-decoration:none;">Book Your Strategy Call &rarr; calendly.com/ethan-practicerank</a>
</div>

<div style="text-align:center;margin-top:20px;padding-top:14px;border-top:1px solid #e2e8f0;">
  <span style="font-size:10px;color:#94a3b8;">PracticeRank &mdash; AI-Powered Dental Marketing | practicerank.ai | kdoherty@practicerank.ai</span>
</div>

</body>
</html>`;

// Write HTML to temp file, then use Chrome headless to print to PDF
const tmpHtml = path.resolve(__dirname, '.tmp-report.html');
fs.writeFileSync(tmpHtml, html);

// Find Chrome
const chromePaths = [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
];
let chromePath = null;
for (const p of chromePaths) {
  if (fs.existsSync(p)) { chromePath = p; break; }
}
if (!chromePath) {
  console.error('No Chrome-based browser found. Install Google Chrome.');
  process.exit(1);
}

try {
  execSync(`"${chromePath}" --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="${outputFile}" "file://${tmpHtml}"`, {
    stdio: 'pipe',
    timeout: 30000,
  });
  console.log(`PDF saved: ${outputFile}`);
} catch (err) {
  // Chrome headless sometimes writes to stderr even on success
  if (fs.existsSync(outputFile) && fs.statSync(outputFile).size > 0) {
    console.log(`PDF saved: ${outputFile}`);
  } else {
    console.error('Failed to generate PDF:', err.stderr?.toString() || err.message);
    process.exit(1);
  }
} finally {
  fs.unlinkSync(tmpHtml);
}
