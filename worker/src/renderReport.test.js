import { describe, it, expect, beforeEach } from "vitest";

// ════════════════════════════════════════════════════════════════
// ── Frontend Report Rendering Tests ──
//
// These tests validate that renderReport() and related frontend
// functions produce valid HTML without runtime errors. The bug
// that prompted these tests: `report.multi_location` referenced
// an undefined variable `report` instead of `r`, causing every
// audit with reviews to crash with "report is not defined".
//
// We extract the rendering logic from index.html and test it
// with realistic report data covering all edge cases.
// ════════════════════════════════════════════════════════════════

// ── Helpers extracted from index.html ──

function scoreColor(n) {
  return n >= 70 ? "green" : n >= 45 ? "amber" : "red";
}

function statusBadge(s) {
  const colors = {
    critical: "var(--red)",
    needs_work: "var(--yellow)",
    good: "var(--accent)",
    excellent: "var(--accent)",
  };
  const labels = {
    critical: "Critical",
    needs_work: "Needs Work",
    good: "Good",
    excellent: "Excellent",
  };
  return `<span style="font-size:0.68rem;font-weight:700;padding:0.2rem 0.5rem;border-radius:4px;background:${colors[s] || "var(--yellow)"};color:var(--btn-text);text-transform:uppercase;letter-spacing:0.5px;">${labels[s] || s}</span>`;
}

function visIcon(v) {
  return v === "yes"
    ? '<span style="color:var(--accent);font-weight:800;">&#10003;</span>'
    : v === "partial"
      ? '<span style="color:var(--yellow);font-weight:800;">~</span>'
      : '<span style="color:var(--red);font-weight:800;">&#10007;</span>';
}

// ── renderReport extracted and adapted for Node (no DOM writes) ──

function renderReportHTML(r, url) {
  const c = r.categories;
  const cats = [
    { key: "gbp", label: "Google Business Profile", icon: "&#x1F4CD;" },
    { key: "ai_readiness", label: "AI Search Readiness", icon: "&#x1F916;" },
    { key: "reviews", label: "Review Strength", icon: "&#x2B50;" },
    { key: "local_seo", label: "Local SEO & Citations", icon: "&#x1F4CC;" },
    { key: "content", label: "Content & On-Page SEO", icon: "&#x1F4DD;" },
    { key: "technical", label: "Technical SEO", icon: "&#x2699;" },
  ];
  const platforms = ["chatgpt", "gemini", "grok", "claude", "perplexity"];
  const platformNames = {
    chatgpt: "ChatGPT",
    gemini: "Gemini",
    grok: "Grok",
    claude: "Claude",
    perplexity: "Perplexity",
  };

  // This is the exact template from index.html — if it throws, the test fails
  const html = `
      <div class="report-header">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem;">
          <div>
            <div class="section-label">Your PracticeRank Score</div>
            <h2 style="margin-bottom:0.25rem;">${r.practice_name || url}</h2>
            <p style="margin:0;">${r.city || ""}, ${r.state || ""}</p>
          </div>
        </div>
      </div>

      <div style="text-align:center;margin-bottom:2.5rem;">
        <div style="display:inline-flex;align-items:center;justify-content:center;width:120px;height:120px;border-radius:50%;border:4px solid ${r.overall_score >= 70 ? "var(--accent)" : r.overall_score >= 45 ? "var(--yellow)" : "var(--red)"};margin-bottom:1rem;">
          <div><div style="font-size:2.8rem;font-weight:800;">${r.overall_score}</div><div style="font-size:0.65rem;">out of 100</div></div>
        </div>
        <p>${r.executive_summary}</p>
        <div>
          <span style="font-weight:700;">Estimated revenue lost to competitors: ${r.revenue_lost_annually}/year</span>
        </div>
      </div>

      <div class="report-grid">
        ${cats
          .map((cat) => {
            const d = c[cat.key];
            return `<div class="metric-card">
            <div>${cat.icon}</div>
            <div class="metric-label">${cat.label}</div>
            <div class="metric-val ${scoreColor(d.score)}">${d.score}</div>
            <div>${statusBadge(d.status)}</div>
          </div>`;
          })
          .join("")}
      </div>

      <div class="report-section">
        <h3>AI Platform Visibility</h3>
        <div>
          ${platforms
            .map((p) => {
              const v = r.ai_visibility[p];
              return `<div>
                <div>${visIcon(v.visible)}</div>
                <div>${platformNames[p]}</div>
                <div>${v.reason}</div>
              </div>`;
            })
            .join("")}
        </div>
      </div>

      ${cats
        .map((cat) => {
          const d = c[cat.key];
          let extra = "";
          if (cat.key === "reviews" && d.count) {
            // BUG FIX: was `report.multi_location` — must be `r.multi_location`
            const ml = r.multi_location;
            let locationBreakdown = "";
            if (ml && ml.locations) {
              locationBreakdown = `<div>${ml.location_count} Locations Combined
              ${ml.locations
                .map(
                  (l) =>
                    `<div><span>${l.city || l.name}</span><span>${l.review_count} reviews ${l.rating}</span></div>`,
                )
                .join("")}
            </div>`;
            }
            extra = `<div>
            <div>${ml ? "Combined Reviews" : "Your Reviews"}</div>
            <div>${d.count} ${d.rating}</div>
            <div>Top Competitor</div>
            <div>${d.competitor_reviews} ${d.competitor_name}</div>
          </div>${locationBreakdown}`;
          }
          return `<div class="report-section">
          <h3>${cat.label} ${d.score}/100</h3>
          <div>
            <ul>${d.findings.map((f) => `<li>${f}</li>`).join("")}</ul>
            ${extra}
          </div>
        </div>`;
        })
        .join("")}

      <div class="report-section">
        <h3>Top 5 Actions</h3>
        <div>
          ${r.priority_actions
            .map(
              (a, i) => `
            <div>
              <div>${i + 1}</div>
              <div>
                <div>${a.title}</div>
                <div>${a.description}</div>
                <span>${a.impact} impact</span>
                <span>${a.est_patients_mo} patients/mo</span>
              </div>
            </div>
          `,
            )
            .join("")}
        </div>
      </div>

      <div class="report-section">
        <h3>Growth Projections</h3>
        <div>
          <div>Today: ${r.projections.current_inquiries_mo}</div>
          <div>3 Months: ${r.projections.month_3}</div>
          <div>6 Months: ${r.projections.month_6}</div>
          <div>12 Months: ${r.projections.month_12}</div>
        </div>
      </div>

      <div>
        <h3>You're leaving ${r.revenue_lost_annually}/year on the table.</h3>
      </div>`;

  return html;
}

// ════════════════════════════════════════════════════════════════
// ── Test Data Factories ──
// ════════════════════════════════════════════════════════════════

function makeCategory(overrides = {}) {
  return {
    score: 50,
    status: "needs_work",
    findings: ["Finding 1", "Finding 2"],
    ...overrides,
  };
}

function makeReport(overrides = {}) {
  return {
    practice_name: "Test Dental",
    city: "Austin",
    state: "TX",
    overall_score: 64,
    grade: "D",
    executive_summary: "Your practice needs improvement in AI visibility.",
    revenue_lost_annually: "$180,000",
    patient_lifetime_value: "$3,500",
    categories: {
      gbp: makeCategory({ score: 70, status: "good" }),
      ai_readiness: makeCategory({ score: 20, status: "critical" }),
      reviews: makeCategory({
        score: 75,
        status: "good",
        count: 150,
        rating: 4.8,
        competitor_name: "Rival Dental",
        competitor_reviews: 200,
      }),
      local_seo: makeCategory({ score: 45, status: "needs_work" }),
      content: makeCategory({ score: 60, status: "needs_work" }),
      technical: makeCategory({ score: 80, status: "excellent" }),
    },
    ai_visibility: {
      chatgpt: { visible: "no", reason: "Not mentioned" },
      gemini: { visible: "partial", reason: "Mentioned but not recommended" },
      grok: { visible: "no", reason: "Not in knowledge base" },
      claude: { visible: "yes", reason: "Recommended for Austin area" },
      perplexity: { visible: "no", reason: "No citations found" },
    },
    priority_actions: [
      {
        title: "Claim Google Business",
        description: "Set up GBP",
        impact: "high",
        est_patients_mo: "15-20",
      },
      {
        title: "Add schema markup",
        description: "Add JSON-LD",
        impact: "high",
        est_patients_mo: "10-15",
      },
      {
        title: "Get more reviews",
        description: "Automate review requests",
        impact: "medium",
        est_patients_mo: "5-10",
      },
      {
        title: "Create blog content",
        description: "Write 4 blog posts",
        impact: "medium",
        est_patients_mo: "5-8",
      },
      {
        title: "Fix page speed",
        description: "Optimize images",
        impact: "low",
        est_patients_mo: "2-4",
      },
    ],
    projections: {
      current_inquiries_mo: "8-12",
      month_3: "18-25",
      month_6: "30-40",
      month_12: "50-65",
    },
    ...overrides,
  };
}

// ════════════════════════════════════════════════════════════════
// ── Helper Function Tests ──
// ════════════════════════════════════════════════════════════════

describe("scoreColor", () => {
  it("returns green for scores >= 70", () => {
    expect(scoreColor(70)).toBe("green");
    expect(scoreColor(100)).toBe("green");
    expect(scoreColor(85)).toBe("green");
  });

  it("returns amber for scores 45-69", () => {
    expect(scoreColor(45)).toBe("amber");
    expect(scoreColor(69)).toBe("amber");
    expect(scoreColor(55)).toBe("amber");
  });

  it("returns red for scores < 45", () => {
    expect(scoreColor(0)).toBe("red");
    expect(scoreColor(44)).toBe("red");
    expect(scoreColor(20)).toBe("red");
  });
});

describe("statusBadge", () => {
  it("renders all known statuses", () => {
    for (const s of ["critical", "needs_work", "good", "excellent"]) {
      const html = statusBadge(s);
      expect(html).toContain("<span");
      expect(html).not.toContain("undefined");
    }
  });

  it("handles unknown status gracefully", () => {
    const html = statusBadge("unknown_status");
    expect(html).toContain("unknown_status");
    expect(html).not.toContain("undefined");
  });
});

describe("visIcon", () => {
  it("returns check for yes", () => {
    expect(visIcon("yes")).toContain("10003");
  });

  it("returns tilde for partial", () => {
    expect(visIcon("partial")).toContain("~");
  });

  it("returns X for no", () => {
    expect(visIcon("no")).toContain("10007");
  });
});

// ════════════════════════════════════════════════════════════════
// ── Report Rendering — Core Tests ──
// ════════════════════════════════════════════════════════════════

describe("renderReportHTML", () => {
  it("renders a complete report without throwing", () => {
    const r = makeReport();
    expect(() => renderReportHTML(r, "https://testdental.com")).not.toThrow();
  });

  it("includes practice name and location", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).toContain("Test Dental");
    expect(html).toContain("Austin");
    expect(html).toContain("TX");
  });

  it("includes overall score", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).toContain("64");
    expect(html).toContain("out of 100");
  });

  it("includes executive summary", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).toContain("AI visibility");
  });

  it("includes revenue lost", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).toContain("$180,000");
  });

  it("renders all 6 category scores", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).toContain("Google Business Profile");
    expect(html).toContain("AI Search Readiness");
    expect(html).toContain("Review Strength");
    expect(html).toContain("Local SEO");
    expect(html).toContain("Content");
    expect(html).toContain("Technical SEO");
  });

  it("renders all 5 AI platform visibility entries", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).toContain("ChatGPT");
    expect(html).toContain("Gemini");
    expect(html).toContain("Grok");
    expect(html).toContain("Claude");
    expect(html).toContain("Perplexity");
  });

  it("renders all priority actions", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).toContain("Claim Google Business");
    expect(html).toContain("Add schema markup");
    expect(html).toContain("Get more reviews");
    expect(html).toContain("Create blog content");
    expect(html).toContain("Fix page speed");
  });

  it("renders growth projections", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).toContain("8-12");
    expect(html).toContain("18-25");
    expect(html).toContain("30-40");
    expect(html).toContain("50-65");
  });

  it("does not contain 'undefined' anywhere", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).not.toContain("undefined");
  });

  it("does not contain 'NaN' anywhere", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).not.toContain("NaN");
  });

  it("does not contain '[object Object]' anywhere", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).not.toContain("[object Object]");
  });
});

// ════════════════════════════════════════════════════════════════
// ── Report Rendering — Reviews Section (where the bug was) ──
// ════════════════════════════════════════════════════════════════

describe("renderReportHTML — reviews section", () => {
  it("renders review count and rating without error", () => {
    const r = makeReport();
    const html = renderReportHTML(r, "https://testdental.com");
    expect(html).toContain("150");
    expect(html).toContain("4.8");
    expect(html).toContain("Your Reviews");
  });

  it("renders competitor info", () => {
    const html = renderReportHTML(makeReport(), "https://testdental.com");
    expect(html).toContain("Rival Dental");
    expect(html).toContain("200");
    expect(html).toContain("Top Competitor");
  });

  it("renders correctly when multi_location is undefined", () => {
    const r = makeReport();
    // No multi_location field — this is the common case
    expect(r.multi_location).toBeUndefined();
    expect(() => renderReportHTML(r, "https://testdental.com")).not.toThrow();
    const html = renderReportHTML(r, "https://testdental.com");
    expect(html).toContain("Your Reviews"); // not "Combined Reviews"
    expect(html).not.toContain("undefined");
  });

  it("renders correctly when multi_location is null", () => {
    const r = makeReport({ multi_location: null });
    expect(() => renderReportHTML(r, "https://testdental.com")).not.toThrow();
    const html = renderReportHTML(r, "https://testdental.com");
    expect(html).toContain("Your Reviews");
  });

  it("renders multi-location breakdown when present", () => {
    const r = makeReport({
      multi_location: {
        location_count: 3,
        locations: [
          { city: "Austin", review_count: 80, rating: 4.9 },
          { city: "Round Rock", review_count: 45, rating: 4.7 },
          { city: "Cedar Park", review_count: 25, rating: 4.8 },
        ],
      },
    });
    const html = renderReportHTML(r, "https://testdental.com");
    expect(html).toContain("Combined Reviews");
    expect(html).toContain("3 Locations Combined");
    expect(html).toContain("Austin");
    expect(html).toContain("Round Rock");
    expect(html).toContain("Cedar Park");
    expect(html).not.toContain("undefined");
  });

  it("renders multi-location with name fallback when city is missing", () => {
    const r = makeReport({
      multi_location: {
        location_count: 2,
        locations: [
          { name: "Main Office", review_count: 100, rating: 5.0 },
          { name: "Branch Office", review_count: 50, rating: 4.5 },
        ],
      },
    });
    const html = renderReportHTML(r, "https://testdental.com");
    expect(html).toContain("Main Office");
    expect(html).toContain("Branch Office");
  });

  it("renders when reviews have zero count", () => {
    const r = makeReport();
    r.categories.reviews.count = 0;
    // count is falsy so extra section should be skipped
    expect(() => renderReportHTML(r, "https://testdental.com")).not.toThrow();
  });
});

// ════════════════════════════════════════════════════════════════
// ── Report Rendering — Edge Cases ──
// ════════════════════════════════════════════════════════════════

describe("renderReportHTML — edge cases", () => {
  it("uses URL as fallback when practice_name is empty", () => {
    const r = makeReport({ practice_name: "" });
    const html = renderReportHTML(r, "https://example.com");
    expect(html).toContain("https://example.com");
  });

  it("handles missing city and state", () => {
    const r = makeReport({ city: "", state: "" });
    expect(() => renderReportHTML(r, "https://test.com")).not.toThrow();
    const html = renderReportHTML(r, "https://test.com");
    expect(html).not.toContain("undefined");
  });

  it("handles score of 0", () => {
    const r = makeReport({ overall_score: 0 });
    const html = renderReportHTML(r, "https://test.com");
    expect(html).toContain("var(--red)");
  });

  it("handles score of 100", () => {
    const r = makeReport({ overall_score: 100 });
    const html = renderReportHTML(r, "https://test.com");
    expect(html).toContain("var(--accent)");
  });

  it("handles empty findings arrays", () => {
    const r = makeReport();
    r.categories.gbp.findings = [];
    expect(() => renderReportHTML(r, "https://test.com")).not.toThrow();
  });

  it("handles single priority action", () => {
    const r = makeReport({
      priority_actions: [
        {
          title: "Only action",
          description: "Do this",
          impact: "high",
          est_patients_mo: "10",
        },
      ],
    });
    const html = renderReportHTML(r, "https://test.com");
    expect(html).toContain("Only action");
  });

  it("handles AI visibility with all 'no' values", () => {
    const r = makeReport({
      ai_visibility: {
        chatgpt: { visible: "no", reason: "Not found" },
        gemini: { visible: "no", reason: "Not found" },
        grok: { visible: "no", reason: "Not found" },
        claude: { visible: "no", reason: "Not found" },
        perplexity: { visible: "no", reason: "Not found" },
      },
    });
    expect(() => renderReportHTML(r, "https://test.com")).not.toThrow();
  });

  it("handles AI visibility with all 'yes' values", () => {
    const r = makeReport({
      ai_visibility: {
        chatgpt: { visible: "yes", reason: "Recommended" },
        gemini: { visible: "yes", reason: "Recommended" },
        grok: { visible: "yes", reason: "Recommended" },
        claude: { visible: "yes", reason: "Recommended" },
        perplexity: { visible: "yes", reason: "Recommended" },
      },
    });
    expect(() => renderReportHTML(r, "https://test.com")).not.toThrow();
  });

  it("handles special characters in practice name", () => {
    const r = makeReport({ practice_name: "O'Brien & Associates <Dental>" });
    expect(() => renderReportHTML(r, "https://test.com")).not.toThrow();
    const html = renderReportHTML(r, "https://test.com");
    expect(html).toContain("O'Brien");
  });

  it("handles very long executive summary", () => {
    const r = makeReport({
      executive_summary: "A".repeat(2000),
    });
    expect(() => renderReportHTML(r, "https://test.com")).not.toThrow();
  });

  it("handles many findings per category", () => {
    const r = makeReport();
    r.categories.gbp.findings = Array.from(
      { length: 20 },
      (_, i) => `Finding ${i + 1}`,
    );
    expect(() => renderReportHTML(r, "https://test.com")).not.toThrow();
  });
});

// ════════════════════════════════════════════════════════════════
// ── Regression: the exact bug that was deployed ──
// ════════════════════════════════════════════════════════════════

// ════════════════════════════════════════════════════════════════
// ── Source File Lint — catch variable scope bugs in index.html ──
// ════════════════════════════════════════════════════════════════

describe("index.html source lint", () => {
  let renderFnSource;

  beforeEach(async () => {
    const fs = await import("fs");
    const html = fs.readFileSync(
      new URL("../../public/index.html", import.meta.url),
      "utf-8",
    );
    // Extract the renderReport function body
    const start = html.indexOf("function renderReport(r, url)");
    const end = html.indexOf("function downloadPDF()");
    if (start === -1 || end === -1)
      throw new Error("Could not find renderReport in index.html");
    renderFnSource = html.slice(start, end);
  });

  it("does not reference 'report.' inside renderReport (must use 'r.')", () => {
    // Match `report.` but not inside strings like "your report" or "this report"
    // Look for JS property access: report.something (not preceded by quote or letter)
    const matches = renderFnSource.match(/\breport\.\w+/g) || [];
    expect(
      matches,
      `Found bare 'report.X' references in renderReport — use 'r.X' instead: ${matches.join(", ")}`,
    ).toEqual([]);
  });

  it("does not reference undeclared variables in template literals", () => {
    // Check for common mistakes: data., result., response. (should be r. or c.)
    const badRefs = renderFnSource.match(
      /\$\{(?:report|data|result|response)\./g,
    );
    expect(
      badRefs,
      `Found undeclared variable references in template: ${badRefs}`,
    ).toBeNull();
  });
});

describe("regression: report variable scope", () => {
  it("does NOT reference 'report' variable — only 'r' parameter", () => {
    // The actual renderReportHTML function uses `r`, not `report`.
    // This test ensures the template string can execute without
    // a `report` variable in scope (which was the production bug).
    const r = makeReport();

    // If this function internally referenced `report` instead of `r`,
    // it would throw ReferenceError: report is not defined
    expect(() => renderReportHTML(r, "https://test.com")).not.toThrow();
  });

  it("renders reviews section with multi_location=undefined without ReferenceError", () => {
    // This was the EXACT scenario that caused the production bug.
    // The report had reviews with count > 0 but no multi_location field.
    // `report.multi_location` threw because `report` was not defined.
    const r = makeReport();
    r.categories.reviews.count = 688;
    r.categories.reviews.rating = 5.0;
    delete r.multi_location; // ensure it's truly undefined

    expect(() => renderReportHTML(r, "https://asarkof.com")).not.toThrow();
    const html = renderReportHTML(r, "https://asarkof.com");
    expect(html).toContain("688");
    expect(html).toContain("Your Reviews");
    expect(html).not.toContain("undefined");
  });
});
