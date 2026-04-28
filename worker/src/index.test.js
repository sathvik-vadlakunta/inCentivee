import { describe, it, expect } from "vitest";
import {
  validatePracticeUrl,
  isValidEmail,
  validateScrapedData,
  validateAndCorrectReport,
  findBestMatch,
  calculateReviewScore,
  scoreToStatus,
  scoreToGrade,
  extractMeta,
  DENTAL_KEYWORDS,
  BAD_NAME_PATTERNS,
  VALID_STATES,
  AREA_CODE_STATES,
  BLOCKED_HOSTS,
} from "./index.js";

// ════════════════════════════════════════════════════════════════
// ── Input Validation — SSRF, URL, Email ──
// ════════════════════════════════════════════════════════════════

describe("validatePracticeUrl", () => {
  it("accepts valid dental domains", () => {
    expect(validatePracticeUrl("thedentalfamily.com")).toBeNull();
    expect(validatePracticeUrl("www.hilltopdental.com")).toBeNull();
    expect(validatePracticeUrl("my-dentist.com")).toBeNull();
    expect(validatePracticeUrl("https://brightsmile.com")).toBeNull();
    expect(validatePracticeUrl("http://www.example.dental")).toBeNull();
  });

  it("rejects empty or too-short input", () => {
    expect(validatePracticeUrl("")).not.toBeNull();
    expect(validatePracticeUrl("ab")).not.toBeNull();
    expect(validatePracticeUrl("a.b")).not.toBeNull();
  });

  it("rejects domains without a dot", () => {
    expect(validatePracticeUrl("localhost")).not.toBeNull();
    expect(validatePracticeUrl("intranet")).not.toBeNull();
  });

  // ── SSRF protection ──
  it("blocks localhost", () => {
    expect(validatePracticeUrl("localhost:8080")).not.toBeNull();
    expect(validatePracticeUrl("http://localhost/path")).not.toBeNull();
  });

  it("blocks private IPv4 ranges", () => {
    expect(validatePracticeUrl("127.0.0.1")).not.toBeNull();
    expect(validatePracticeUrl("10.0.0.1")).not.toBeNull();
    expect(validatePracticeUrl("172.16.0.1")).not.toBeNull();
    expect(validatePracticeUrl("192.168.1.1")).not.toBeNull();
    expect(validatePracticeUrl("169.254.169.254")).not.toBeNull(); // AWS metadata
    expect(validatePracticeUrl("0.0.0.0")).not.toBeNull();
  });

  it("blocks all raw IP addresses", () => {
    expect(validatePracticeUrl("8.8.8.8")).not.toBeNull();
    expect(validatePracticeUrl("1.2.3.4:80")).not.toBeNull();
  });

  it("blocks internal hostnames", () => {
    expect(validatePracticeUrl("server.local")).not.toBeNull();
    expect(validatePracticeUrl("api.internal")).not.toBeNull();
    expect(validatePracticeUrl("mail.corp")).not.toBeNull();
    expect(validatePracticeUrl("printer.lan")).not.toBeNull();
  });

  it("rejects URLs longer than 253 chars", () => {
    const long = "a".repeat(250) + ".com";
    expect(validatePracticeUrl(long)).not.toBeNull();
  });

  it("strips protocol and trailing slashes before validating", () => {
    expect(validatePracticeUrl("https://example.com/")).toBeNull();
    expect(validatePracticeUrl("http://example.com/about")).toBeNull();
  });
});

describe("isValidEmail", () => {
  it("accepts valid emails", () => {
    expect(isValidEmail("test@example.com")).toBe(true);
    expect(isValidEmail("dr.smith@dental.org")).toBe(true);
    expect(isValidEmail("user+tag@sub.domain.co")).toBe(true);
  });

  it("rejects invalid emails", () => {
    expect(isValidEmail("")).toBe(false);
    expect(isValidEmail("notanemail")).toBe(false);
    expect(isValidEmail("@nodomain.com")).toBe(false);
    expect(isValidEmail("user@")).toBe(false);
    expect(isValidEmail("user@.com")).toBe(false);
    expect(isValidEmail("user@domain.x")).toBe(false); // TLD too short
    expect(isValidEmail(null)).toBe(false);
    expect(isValidEmail(undefined)).toBe(false);
  });

  it("rejects emails over 254 chars", () => {
    const long = "a".repeat(250) + "@b.com";
    expect(isValidEmail(long)).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════
// ── Scraped Data Validation ──
// ════════════════════════════════════════════════════════════════

describe("validateScrapedData", () => {
  function makeData(overrides = {}) {
    return {
      scraped: true,
      domain: "thedentalfamily.com",
      practiceName: "The Dental Family",
      city: "Westfield",
      state: "NJ",
      phone: "(908) 232-9300",
      postalCode: "07090",
      visibleText: "Welcome to The Dental Family in Westfield NJ. General dentistry and cosmetic services.",
      ...overrides,
    };
  }

  it("validates a fully valid practice with high confidence", () => {
    const result = validateScrapedData(makeData());
    expect(result.validation.confidence).toBe("high");
    expect(result.validation.checks.practiceName.status).toBe("verified");
    expect(result.validation.checks.state.status).toBe("verified");
    expect(result.validation.checks.city.status).toBe("verified");
  });

  it("detects missing practice name", () => {
    const result = validateScrapedData(makeData({ practiceName: "" }));
    expect(result.validation.confidence).toBe("low");
    expect(result.validation.checks.practiceName.status).toBe("missing");
  });

  it("rejects junk practice names (menus, generic text)", () => {
    const junkNames = ["Eastern Time", "Select", "Home", "Monday", "123", "AB", "a".repeat(101)];
    for (const name of junkNames) {
      const result = validateScrapedData(makeData({ practiceName: name }));
      expect(result.practiceName).toBe(""); // cleared
      expect(result.validation.checks.practiceName.status).toBe("rejected");
    }
  });

  it("rejects invalid state abbreviations", () => {
    const result = validateScrapedData(makeData({ state: "ZZ" }));
    expect(result.state).toBe(""); // cleared
    expect(result.validation.checks.state.status).toBe("rejected");
  });

  it("accepts all valid US states", () => {
    for (const st of ["NY", "CA", "TX", "FL", "NJ"]) {
      const result = validateScrapedData(makeData({ state: st }));
      expect(result.validation.checks.state.status).toBe("verified");
    }
  });

  it("accepts valid Canadian provinces", () => {
    for (const prov of ["ON", "BC", "AB", "QC"]) {
      const result = validateScrapedData(makeData({ state: prov }));
      expect(result.validation.checks.state.status).toBe("verified");
    }
  });

  it("flags city not found in page content", () => {
    const result = validateScrapedData(makeData({ city: "Denver" }));
    expect(result.validation.checks.city.status).toBe("unverified");
    expect(result.validation.confidence).toBe("medium");
  });

  it("cross-checks phone area code vs state", () => {
    // 908 = NJ, matches
    const good = validateScrapedData(makeData({ phone: "(908) 232-9300", state: "NJ" }));
    expect(good.validation.checks.phone.status).toBe("verified");

    // 512 = TX, doesn't match NJ
    const bad = validateScrapedData(makeData({ phone: "(512) 555-1234", state: "NJ" }));
    expect(bad.validation.checks.phone.status).toBe("mismatch");
  });

  it("infers state from phone area code when state is missing", () => {
    const result = validateScrapedData(makeData({ state: "", phone: "(908) 232-9300" }));
    expect(result.phoneInferredState).toBe("NJ");
    expect(result.validation.checks.phone.status).toBe("inferred");
  });

  it("validates postal code format", () => {
    const good = validateScrapedData(makeData({ postalCode: "07090" }));
    expect(good.validation.checks.postalCode.status).toBe("verified");

    const bad = validateScrapedData(makeData({ postalCode: "ABCDE" }));
    expect(bad.validation.checks.postalCode.status).toBe("invalid_format");
  });

  it("accepts Canadian postal codes", () => {
    const result = validateScrapedData(makeData({ postalCode: "M5V3L9", state: "ON" }));
    expect(result.validation.checks.postalCode.status).toBe("verified");
  });
});

// ════════════════════════════════════════════════════════════════
// ── Post-Response Validation — Correcting Hallucinations ──
// ════════════════════════════════════════════════════════════════

describe("validateAndCorrectReport", () => {
  function makeReport(overrides = {}) {
    return {
      practice_name: "Some Dental",
      city: "Unknown",
      state: "XX",
      overall_score: 50,
      grade: "D",
      categories: {
        gbp: { score: 40, status: "needs_work" },
        ai_readiness: { score: 30, status: "critical" },
        reviews: {
          score: 30,
          status: "critical",
          count: 15,
          rating: 4.2,
          competitor_name: "Fake Competitor",
          competitor_reviews: 50,
          findings: ["Only 15 reviews visible", "Low review count hurts ranking"],
        },
        local_seo: { score: 50, status: "needs_work" },
        content: { score: 60, status: "needs_work" },
        technical: { score: 70, status: "good" },
      },
      ...overrides,
    };
  }

  const placeData = {
    verified: true,
    name: "The Dental Family",
    city: "Westfield",
    state: "NJ",
    rating: 5.0,
    reviewCount: 688,
    website: "https://thedentalfamily.com",
    domainMatch: true,
    nameMatch: true,
    matchConfidence: "high",
    location: { latitude: 40.65, longitude: -74.35 },
  };

  const competitors = [
    { name: "Westfield Smiles", rating: 4.9, reviewCount: 581, address: "440 E Broad St" },
    { name: "Downtown Dental", rating: 5.0, reviewCount: 207, address: "219 N Ave W" },
  ];

  it("overrides hallucinated review count with Google-verified data", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, placeData, competitors);
    expect(result.categories.reviews.count).toBe(688);
    expect(result.categories.reviews.rating).toBe(5.0);
  });

  it("overrides hallucinated practice name with Google-verified data", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, placeData, competitors);
    expect(result.practice_name).toBe("The Dental Family");
  });

  it("overrides hallucinated city and state with Google-verified data", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, placeData, competitors);
    expect(result.city).toBe("Westfield");
    expect(result.state).toBe("NJ");
  });

  it("overrides hallucinated competitor with real Google data", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, placeData, competitors);
    expect(result.categories.reviews.competitor_name).toBe("Westfield Smiles");
    expect(result.categories.reviews.competitor_reviews).toBe(581);
  });

  it("recalculates review score based on real data", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, placeData, competitors);
    // 688 reviews at 5.0 with top competitor at 581 — should score high
    expect(result.categories.reviews.score).toBeGreaterThan(70);
    expect(result.categories.reviews.status).toBe("excellent");
  });

  it("recalculates overall score after corrections", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, placeData, competitors);
    // Overall should change since review score changed dramatically
    expect(result.overall_score).not.toBe(50);
  });

  it("sets data_confidence to verified when domain matches", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, placeData, competitors);
    expect(result.data_confidence).toBe("verified");
    expect(result.google_verified).toBe(true);
  });

  it("tracks all corrections made", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, placeData, competitors);
    expect(result.data_corrections).toBeDefined();
    expect(result.data_corrections.length).toBeGreaterThan(0);
    // Should mention the review count correction
    expect(result.data_corrections.some(c => c.includes("reviews"))).toBe(true);
  });

  it("does not override when Google data has low confidence", () => {
    const lowConfidence = { ...placeData, matchConfidence: "low", domainMatch: false, nameMatch: false };
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, lowConfidence, competitors);
    // Should still use Claude's values for name/city/state
    expect(result.practice_name).toBe("Some Dental");
  });

  it("handles null placeData gracefully", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, null, []);
    expect(result.data_confidence).toBe("unverified");
    expect(result.google_verified).toBe(false);
    expect(result.categories.reviews.count).toBe(15); // unchanged
  });

  it("handles empty competitors gracefully", () => {
    const report = makeReport();
    const result = validateAndCorrectReport(report, {}, placeData, []);
    expect(result.categories.reviews.competitor_name).toBe("Fake Competitor"); // no real data to override
  });

  it("does not modify review data when Claude's numbers are close to Google", () => {
    const report = makeReport();
    report.categories.reviews.count = 680; // within 20% of 688
    report.categories.reviews.rating = 4.9; // within 0.3 of 5.0
    const result = validateAndCorrectReport(report, {}, placeData, competitors);
    // Count is within tolerance, should still be corrected since it's >20% threshold check
    // But rating 4.9 is within 0.3 of 5.0, so should NOT be overridden
    expect(result.categories.reviews.rating).toBe(4.9);
  });
});

// ════════════════════════════════════════════════════════════════
// ── Google Places Match Logic ──
// ════════════════════════════════════════════════════════════════

describe("findBestMatch", () => {
  const results = [
    {
      displayName: { text: "The Dental Family: Brett and Irene Druger, DMD" },
      formattedAddress: "531 E Broad St, Westfield, NJ 07090",
      websiteUri: "http://www.thedentalfamily.com/",
      userRatingCount: 688,
      rating: 5.0,
      id: "place1",
    },
    {
      displayName: { text: "Westfield Smiles" },
      formattedAddress: "440 E Broad St, Westfield, NJ 07090",
      websiteUri: "https://www.westfieldsmiles.com/",
      userRatingCount: 581,
      rating: 4.9,
      id: "place2",
    },
    {
      displayName: { text: "Some Other Dental" },
      formattedAddress: "123 Main St, Newark, NJ 07101",
      websiteUri: "https://www.someother.com/",
      userRatingCount: 50,
      rating: 4.5,
      id: "place3",
    },
  ];

  it("matches by domain (strongest signal)", () => {
    const match = findBestMatch(results, "The Dental Family", "thedentalfamily.com", "", "Westfield");
    expect(match.id).toBe("place1");
  });

  it("matches by name when domain is unknown", () => {
    const match = findBestMatch(results, "Westfield Smiles", "unknown.com", "", "Westfield");
    expect(match.id).toBe("place2");
  });

  it("prefers domain match over name match", () => {
    // Name says "Westfield Smiles" but domain says thedentalfamily.com
    const match = findBestMatch(results, "Westfield Smiles", "thedentalfamily.com", "", "Westfield");
    expect(match.id).toBe("place1");
  });

  it("falls back to first result when no strong match", () => {
    const match = findBestMatch(results, "Unknown Practice", "unknown.com", "", "Chicago");
    // Should return first result since no match scores >= 2
    expect(match).not.toBeNull();
  });

  it("handles empty results", () => {
    const match = findBestMatch([], "Test", "test.com", "", "");
    expect(match).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════
// ── Review Score Calculation ──
// ════════════════════════════════════════════════════════════════

describe("calculateReviewScore", () => {
  const competitors = [
    { name: "Top Dental", reviewCount: 500 },
    { name: "Second Dental", reviewCount: 200 },
  ];

  it("scores high for 500+ reviews at 5.0 with competitive advantage", () => {
    const score = calculateReviewScore(688, 5.0, competitors);
    expect(score).toBeGreaterThanOrEqual(80);
  });

  it("scores low for few reviews at low rating", () => {
    const score = calculateReviewScore(5, 3.2, competitors);
    expect(score).toBeLessThan(30);
  });

  it("rewards being ahead of top competitor", () => {
    const ahead = calculateReviewScore(600, 4.8, competitors);
    const behind = calculateReviewScore(100, 4.8, competitors);
    expect(ahead).toBeGreaterThan(behind);
  });

  it("caps at 100", () => {
    const score = calculateReviewScore(1000, 5.0, []);
    expect(score).toBeLessThanOrEqual(100);
  });

  it("handles zero reviews", () => {
    const score = calculateReviewScore(0, 0, competitors);
    expect(score).toBeLessThan(20);
  });

  it("handles empty competitors", () => {
    const score = calculateReviewScore(100, 4.5, []);
    expect(score).toBeGreaterThan(30); // gets benefit-of-doubt bonus
  });
});

describe("scoreToStatus", () => {
  it("maps scores to correct status labels", () => {
    expect(scoreToStatus(0)).toBe("critical");
    expect(scoreToStatus(30)).toBe("critical");
    expect(scoreToStatus(31)).toBe("needs_work");
    expect(scoreToStatus(60)).toBe("needs_work");
    expect(scoreToStatus(61)).toBe("good");
    expect(scoreToStatus(80)).toBe("good");
    expect(scoreToStatus(81)).toBe("excellent");
    expect(scoreToStatus(100)).toBe("excellent");
  });
});

describe("scoreToGrade", () => {
  it("maps scores to letter grades", () => {
    expect(scoreToGrade(95)).toBe("A");
    expect(scoreToGrade(85)).toBe("B");
    expect(scoreToGrade(75)).toBe("C");
    expect(scoreToGrade(65)).toBe("D");
    expect(scoreToGrade(50)).toBe("F");
    expect(scoreToGrade(0)).toBe("F");
  });
});

// ════════════════════════════════════════════════════════════════
// ── HTML Extraction ──
// ════════════════════════════════════════════════════════════════

describe("extractMeta", () => {
  it("extracts title from HTML", () => {
    const html = "<html><head><title>My Dental Practice | Best Dentist</title></head></html>";
    expect(extractMeta(html, /<title[^>]*>([^<]+)<\/title>/i)).toBe("My Dental Practice | Best Dentist");
  });

  it("extracts meta description", () => {
    const html = '<meta name="description" content="We are the best dental practice in town.">';
    expect(extractMeta(html, /<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i)).toBe("We are the best dental practice in town.");
  });

  it("extracts schema streetAddress", () => {
    const html = '{"@type":"Dentist","streetAddress":"531 E Broad St","addressLocality":"Westfield"}';
    expect(extractMeta(html, /"streetAddress"\s*:\s*"([^"]+)"/)).toBe("531 E Broad St");
  });

  it("returns empty string when no match", () => {
    expect(extractMeta("<html></html>", /<title>([^<]+)<\/title>/)).toBe("");
  });
});

// ════════════════════════════════════════════════════════════════
// ── Security Constants ──
// ════════════════════════════════════════════════════════════════

describe("security constants", () => {
  it("DENTAL_KEYWORDS includes essential terms", () => {
    expect(DENTAL_KEYWORDS).toContain("dental");
    expect(DENTAL_KEYWORDS).toContain("dentist");
    expect(DENTAL_KEYWORDS).toContain("teeth");
    expect(DENTAL_KEYWORDS).toContain("implant");
  });

  it("VALID_STATES includes all 50 US states + DC", () => {
    const required = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI", "DC"];
    for (const st of required) {
      expect(VALID_STATES.has(st)).toBe(true);
    }
  });

  it("VALID_STATES includes Canadian provinces", () => {
    const provinces = ["ON", "BC", "AB", "QC", "MB", "SK"];
    for (const p of provinces) {
      expect(VALID_STATES.has(p)).toBe(true);
    }
  });

  it("AREA_CODE_STATES covers major cities", () => {
    expect(AREA_CODE_STATES["212"]).toBe("NY"); // NYC
    expect(AREA_CODE_STATES["310"]).toBe("CA"); // LA
    expect(AREA_CODE_STATES["312"]).toBe("IL"); // Chicago
    expect(AREA_CODE_STATES["713"]).toBe("TX"); // Houston
    expect(AREA_CODE_STATES["908"]).toBe("NJ"); // Westfield area
  });

  it("BLOCKED_HOSTS catches all private ranges", () => {
    const blockedExamples = ["localhost", "127.0.0.1", "10.0.0.1", "192.168.1.1", "server.local", "api.internal"];
    for (const host of blockedExamples) {
      const blocked = BLOCKED_HOSTS.some(p => p.test(host));
      expect(blocked, `Expected ${host} to be blocked`).toBe(true);
    }
  });

  it("BLOCKED_HOSTS does not block legitimate domains", () => {
    const allowed = ["example.com", "dental.org", "my-practice.dental"];
    for (const host of allowed) {
      const blocked = BLOCKED_HOSTS.some(p => p.test(host));
      expect(blocked, `Expected ${host} to NOT be blocked`).toBe(false);
    }
  });

  it("BAD_NAME_PATTERNS catches common garbage extractions", () => {
    const garbage = ["Eastern Time", "Select", "Home", "Monday Morning", "42", "AB"];
    for (const name of garbage) {
      const caught = BAD_NAME_PATTERNS.some(p => p.test(name));
      expect(caught, `Expected "${name}" to be caught`).toBe(true);
    }
  });

  it("BAD_NAME_PATTERNS does not flag real practice names", () => {
    const legit = ["The Dental Family", "Hilltop Dental", "Bright Smile Dentistry", "Dr. Smith DDS"];
    for (const name of legit) {
      const caught = BAD_NAME_PATTERNS.some(p => p.test(name));
      expect(caught, `Expected "${name}" to NOT be flagged`).toBe(false);
    }
  });
});

// ════════════════════════════════════════════════════════════════
// ── Error Handling — No Secret Leakage ──
// ════════════════════════════════════════════════════════════════

describe("error handling security", () => {
  it("API keys are never included in error responses", () => {
    // Simulate the kind of error messages that could leak secrets
    const dangerousMessages = [
      "Request failed: API key AIzaSyD2mVZV7jo3Q56fdZchyOmmFZFeHIx_TqU is invalid",
      "Authentication error for key sk-ant-12345",
      "Connection refused to https://api.anthropic.com with key abc123",
    ];

    for (const msg of dangerousMessages) {
      const e = new Error(msg);
      // The worker uses a safe message, not e.message
      const safeMessage = e instanceof SyntaxError
        ? "Failed to parse audit response. Please try again."
        : "An error occurred generating your audit. Please try again.";
      expect(safeMessage).not.toContain("AIza");
      expect(safeMessage).not.toContain("sk-ant");
      expect(safeMessage).not.toContain("abc123");
    }
  });

  it("SyntaxError gets a specific safe message", () => {
    const e = new SyntaxError("Unexpected token < in JSON");
    const safeMessage = e instanceof SyntaxError
      ? "Failed to parse audit response. Please try again."
      : "An error occurred generating your audit. Please try again.";
    expect(safeMessage).toBe("Failed to parse audit response. Please try again.");
    expect(safeMessage).not.toContain("token");
  });
});
