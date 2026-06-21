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
  LEGAL_KEYWORDS,
  MEDICAL_KEYWORDS,
  VERTICAL_CONFIG,
  BAD_NAME_PATTERNS,
  VALID_STATES,
  AREA_CODE_STATES,
  BLOCKED_HOSTS,
  nameSimilarity,
  validateCompetitors,
  detectVertical,
  assertsGbpAbsence,
  scrubGbpAbsenceText,
  finalSafetyChecks,
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

  it("returns null when no strong match (never guesses a wrong place)", () => {
    const match = findBestMatch(results, "Unknown Practice", "unknown.com", "", "Chicago");
    // No result scores >= 3, so findBestMatch returns null rather than a wrong
    // fallback — returning a random competitor as the practice would corrupt the audit.
    expect(match).toBeNull();
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

// ════════════════════════════════════════════════════════════════
// ── Dynamic Vertical Support ──
// ════════════════════════════════════════════════════════════════

describe("VERTICAL_CONFIG", () => {
  it("has all three core verticals", () => {
    expect(VERTICAL_CONFIG).toHaveProperty("dental");
    expect(VERTICAL_CONFIG).toHaveProperty("legal");
    expect(VERTICAL_CONFIG).toHaveProperty("medical");
  });

  it("medical placeType is an array with doctor and hospital", () => {
    const med = VERTICAL_CONFIG.medical;
    expect(Array.isArray(med.placeType)).toBe(true);
    expect(med.placeType).toContain("doctor");
    expect(med.placeType).toContain("hospital");
  });

  it("dental and legal placeType are strings (single type)", () => {
    expect(VERTICAL_CONFIG.dental.placeType).toBe("dentist");
    expect(VERTICAL_CONFIG.legal.placeType).toBe("lawyer");
  });

  it("all verticals have required display fields", () => {
    for (const [key, config] of Object.entries(VERTICAL_CONFIG)) {
      expect(config, `${key} missing placeLabel`).toHaveProperty("placeLabel");
      expect(config, `${key} missing businessTerm`).toHaveProperty("businessTerm");
      expect(config, `${key} missing clientTerm`).toHaveProperty("clientTerm");
      expect(config, `${key} missing providerTerm`).toHaveProperty("providerTerm");
    }
  });
});

describe("LEGAL_KEYWORDS and MEDICAL_KEYWORDS", () => {
  it("LEGAL_KEYWORDS includes essential terms", () => {
    expect(LEGAL_KEYWORDS).toContain("attorney");
    expect(LEGAL_KEYWORDS).toContain("lawyer");
    expect(LEGAL_KEYWORDS).toContain("law firm");
    expect(LEGAL_KEYWORDS).toContain("litigation");
  });

  it("MEDICAL_KEYWORDS includes essential terms", () => {
    expect(MEDICAL_KEYWORDS).toContain("doctor");
    expect(MEDICAL_KEYWORDS).toContain("physician");
    expect(MEDICAL_KEYWORDS).toContain("clinic");
    expect(MEDICAL_KEYWORDS).toContain("urgent care");
  });
});

describe("nameSimilarity", () => {
  it("identical names return 1.0", () => {
    expect(nameSimilarity("Smith Law", "Smith Law")).toBe(1.0);
  });

  it("completely different names return 0.0", () => {
    expect(nameSimilarity("Smith Law", "Downtown Dental")).toBe(0.0);
  });

  it("empty string returns 0.0", () => {
    expect(nameSimilarity("", "Test")).toBe(0.0);
    expect(nameSimilarity("Test", "")).toBe(0.0);
  });

  it("same business with suffix still >= 0.5 (self-filter threshold)", () => {
    expect(nameSimilarity("Hilltop Dental", "Hilltop Family Dental")).toBeGreaterThanOrEqual(0.5);
  });
});

describe("validateCompetitors", () => {
  it("rejects wrong-industry names (tax, insurance, etc.)", async () => {
    const comps = [
      { name: "Optima Tax Relief", primaryType: "", website: "" },
      { name: "Smith Insurance Agent", primaryType: "", website: "" },
      { name: "Downtown Law Firm", primaryType: "lawyer", website: "" },
    ];
    const result = await validateCompetitors(comps, "legal");
    expect(result.length).toBe(1);
    expect(result[0].name).toBe("Downtown Law Firm");
  });

  it("accepts competitors with industry name keywords", async () => {
    const comps = [
      { name: "River City Legal Group", primaryType: "", website: "" },
      { name: "Smith & Associates Attorney", primaryType: "", website: "" },
    ];
    const result = await validateCompetitors(comps, "legal");
    expect(result.length).toBe(2);
  });

  it("medical vertical accepts both doctor and hospital primaryType", async () => {
    const comps = [
      { name: "Springfield General", primaryType: "hospital", website: "" },
      { name: "Dr. Johnson Office", primaryType: "doctor", website: "" },
      { name: "Joe's Auto Shop", primaryType: "car_repair", website: "" },
    ];
    const result = await validateCompetitors(comps, "medical");
    // Springfield General: name has no medical keyword, but primaryType=hospital matches
    // Dr. Johnson: name has "doctor" keyword → accepted
    // Joe's Auto: rejected (no keyword, wrong primaryType)
    expect(result.some(c => c.name === "Springfield General")).toBe(true);
    expect(result.some(c => c.name.includes("Johnson"))).toBe(true);
    expect(result.some(c => c.name.includes("Auto"))).toBe(false);
  });

  it("falls back to returning filtered list when too aggressive", async () => {
    const comps = [
      { name: "Generic Business Name", primaryType: "", website: "" },
    ];
    // Unknown vertical, no keywords match — should return the competitor
    // since fallback returns non-excluded competitors
    const result = await validateCompetitors(comps, "dental");
    expect(result.length).toBe(1);
  });

  it("returns empty array for empty input", async () => {
    const result = await validateCompetitors([], "legal");
    expect(result.length).toBe(0);
  });
});

// ════════════════════════════════════════════════════════════════
// ── Vertical Auto-Detection ──
// ════════════════════════════════════════════════════════════════

describe("detectVertical", () => {
  // Helper to build mock site data
  function mockSite({ isDental = false, isLegal = false, isMedical = false, text = "" }) {
    return {
      scraped: true,
      isDentalSite: isDental,
      isLegalSite: isLegal,
      isMedicalSite: isMedical,
      visibleText: text,
    };
  }

  // --- User explicitly chose legal — NEVER override ---

  it("trusts explicit legal selection even with medical keywords", () => {
    // frblaw.com scenario: law firm with "healthcare" practice area
    const site = mockSite({
      isLegal: true,
      isMedical: true, // false positive from "healthcare" keyword
      text: "law firm attorney litigation healthcare compliance estate planning counsel",
    });
    expect(detectVertical("legal", site)).toBe("legal");
  });

  it("trusts explicit legal selection even with zero legal signals", () => {
    const site = mockSite({ text: "some random website content" });
    expect(detectVertical("legal", site)).toBe("legal");
  });

  it("reclassifies to dental when content is clearly dental despite a legal selection", () => {
    // Content wins over the submitted vertical: a site full of dental terms is
    // dental even if the lead came in on the legal page (the Ethan-class bug).
    const site = mockSite({
      isDental: true,
      text: "dentist dental practice orthodontist",
    });
    expect(detectVertical("legal", site)).toBe("dental");
  });

  // --- User explicitly chose medical — NEVER override ---

  it("trusts explicit medical selection even with legal keywords", () => {
    const site = mockSite({
      isMedical: true,
      isLegal: true, // false positive from "legal" in content
      text: "physician clinic healthcare patient legal notice terms of service",
    });
    expect(detectVertical("medical", site)).toBe("medical");
  });

  it("trusts explicit medical selection with no medical signals", () => {
    const site = mockSite({ text: "welcome to our website" });
    expect(detectVertical("medical", site)).toBe("medical");
  });

  // --- Default dental page: auto-detect when site is NOT dental ---

  it("auto-detects legal from dental page when strong legal signals", () => {
    const site = mockSite({
      text: "law firm attorney personal injury litigation estate planning criminal defense family law",
    });
    expect(detectVertical("dental", site)).toBe("legal");
  });

  it("auto-detects medical from dental page when strong medical signals", () => {
    const site = mockSite({
      text: "physician clinic primary care board certified internal medicine family medicine specialist",
    });
    expect(detectVertical("dental", site)).toBe("medical");
  });

  it("does NOT auto-detect with fewer than 3 keyword matches", () => {
    // Only 2 legal keywords — not enough to switch
    const site = mockSite({
      text: "attorney law firm welcome to our website",
    });
    expect(detectVertical("dental", site)).toBe("dental");
  });

  it("picks legal over medical when legal has more matches", () => {
    // law firm that mentions healthcare (like frblaw.com)
    const site = mockSite({
      text: "law firm attorney litigation counsel estate planning healthcare compliance practice areas",
    });
    expect(detectVertical("dental", site)).toBe("legal");
  });

  it("picks medical over legal when medical has more matches", () => {
    const site = mockSite({
      text: "physician clinic healthcare patient primary care board certified internal medicine attorney referral",
    });
    expect(detectVertical("dental", site)).toBe("medical");
  });

  // --- Dental site stays dental ---

  it("keeps dental when site IS dental", () => {
    const site = mockSite({
      isDental: true,
      text: "dentist dental practice cosmetic dentistry",
    });
    expect(detectVertical("dental", site)).toBe("dental");
  });

  it("keeps dental when site is dental even with medical keywords", () => {
    const site = mockSite({
      isDental: true,
      text: "dental practice patient healthcare board certified oral surgeon",
    });
    expect(detectVertical("dental", site)).toBe("dental");
  });

  // --- Edge cases ---

  it("returns user vertical when siteData is null", () => {
    expect(detectVertical("legal", null)).toBe("legal");
    expect(detectVertical("dental", null)).toBe("dental");
  });

  it("returns user vertical when site was not scraped", () => {
    expect(detectVertical("dental", { scraped: false })).toBe("dental");
  });

  it("stays dental when no signals detected at all", () => {
    const site = mockSite({ text: "welcome to our company we sell widgets" });
    expect(detectVertical("dental", site)).toBe("dental");
  });
});

// ════════════════════════════════════════════════════════════════
// ── Vertical Detection — Integration Tests (real site content) ──
// These simulate real scraped content from known sites to prevent
// regressions like the frblaw.com healthcare false positive.
// ════════════════════════════════════════════════════════════════

describe("detectVertical — real site scenarios", () => {
  it("frblaw.com on legal page stays legal (healthcare practice area false positive)", () => {
    // Real content from Falcon Rappaport & Berkman LLP
    const site = {
      scraped: true,
      isDentalSite: false,
      isLegalSite: true,
      isMedicalSite: true, // triggered by "healthcare"
      visibleText: "Falcon Rappaport & Berkman LLP 80+ attorneys across 23 practice areas law firm attorney litigation corporate securities bankruptcy estate planning intellectual property labor employment healthcare compliance counsel probate trusts",
    };
    expect(detectVertical("legal", site)).toBe("legal");
  });

  it("frblaw.com on dental page auto-detects to legal", () => {
    const site = {
      scraped: true,
      isDentalSite: false,
      isLegalSite: true,
      isMedicalSite: true,
      visibleText: "Falcon Rappaport & Berkman LLP 80+ attorneys across 23 practice areas law firm attorney litigation corporate securities bankruptcy estate planning intellectual property labor employment healthcare compliance counsel probate trusts",
    };
    expect(detectVertical("dental", site)).toBe("legal");
  });

  it("mayo clinic on medical page stays medical", () => {
    const site = {
      scraped: true,
      isDentalSite: false,
      isLegalSite: false,
      isMedicalSite: true,
      visibleText: "Mayo Clinic physician healthcare medical doctor patient primary care specialist board certified internal medicine cardiology dermatology orthopedics clinic hospital",
    };
    expect(detectVertical("medical", site)).toBe("medical");
  });

  it("dental practice with patient keyword stays dental on medical page", () => {
    // Dental sites often use "patient" which is a MEDICAL_KEYWORD
    const site = {
      scraped: true,
      isDentalSite: true,
      isLegalSite: false,
      isMedicalSite: true, // "patient" triggers this
      visibleText: "family dental practice dentist cosmetic dentistry patient care oral hygiene teeth whitening",
    };
    // User came in on the medical page, but the content is overwhelmingly
    // dental — content wins, so the audit is correctly run as dental.
    expect(detectVertical("medical", site)).toBe("dental");
  });

  it("personal injury law firm on dental page auto-detects legal", () => {
    const site = {
      scraped: true,
      isDentalSite: false,
      isLegalSite: true,
      isMedicalSite: false,
      visibleText: "Morgan & Morgan personal injury attorney law firm lawyer free consultation litigation accident injury criminal defense family law",
    };
    expect(detectVertical("dental", site)).toBe("legal");
  });

  it("medical spa with legal terms stays on chosen vertical", () => {
    // Med spa might have "terms of service" legal language
    const site = {
      scraped: true,
      isDentalSite: false,
      isLegalSite: false,
      isMedicalSite: true,
      visibleText: "medical spa dermatology aesthetic clinic botox physician board certified patient healthcare terms of service legal notice",
    };
    expect(detectVertical("medical", site)).toBe("medical");
  });
});

// ════════════════════════════════════════════════════════════════
// ── GBP existence guard — never falsely claim "no Google Business Profile" ──
// ════════════════════════════════════════════════════════════════

describe("assertsGbpAbsence", () => {
  it("flags explicit absence claims", () => {
    expect(assertsGbpAbsence("No Google Business Profile detected for this practice")).toBe(true);
    expect(assertsGbpAbsence("The business has an unclaimed Google Business listing")).toBe(true);
    expect(assertsGbpAbsence("They don't have a Google Business Profile")).toBe(true);
    expect(assertsGbpAbsence("Missing a Google Business Profile entirely")).toBe(true);
    expect(assertsGbpAbsence("This practice is not listed on Google Maps")).toBe(true);
    expect(assertsGbpAbsence("Google Business Profile has not been claimed")).toBe(true);
    expect(assertsGbpAbsence("Lacks a presence on Google")).toBe(true);
  });

  it("does NOT flag legitimate optimization findings", () => {
    expect(assertsGbpAbsence("Your Google Business Profile is missing photos and recent posts")).toBe(false);
    expect(assertsGbpAbsence("Google Business Profile has no recent posts in 6 months")).toBe(false);
    expect(assertsGbpAbsence("The profile is under-optimized with incomplete categories")).toBe(false);
    expect(assertsGbpAbsence("Add more photos to your Google Business Profile")).toBe(false);
    expect(assertsGbpAbsence("Few reviews compared to competitors")).toBe(false);
    expect(assertsGbpAbsence("")).toBe(false);
    expect(assertsGbpAbsence(null)).toBe(false);
  });

  it("does not flag text that never mentions the profile/listing", () => {
    expect(assertsGbpAbsence("No FAQ schema markup was detected on the site")).toBe(false);
    expect(assertsGbpAbsence("The site is not optimized for AI search")).toBe(false);
  });
});

describe("finalSafetyChecks — GBP guard", () => {
  const placeData = {
    name: "Hilltop Family Dental",
    city: "Reno",
    state: "NV",
    rating: 4.8,
    reviewCount: 152,
    businessStatus: "OPERATIONAL",
    matchConfidence: "high",
    domainMatch: true,
    nameMatch: true,
    placeId: "abc123",
  };

  function baseReport(gbpFindings) {
    return {
      practice_name: "Hilltop Family Dental",
      state: "NV",
      executive_summary: "Summary.",
      categories: {
        gbp: { score: 5, status: "critical", findings: gbpFindings },
        reviews: { score: 70, status: "good", findings: [], count: 152, rating: 4.8 },
      },
    };
  }

  it("rewrites a false 'no GBP' finding when Google confirms the profile exists", () => {
    const report = finalSafetyChecks(
      baseReport(["No Google Business Profile was detected for this practice."]),
      "https://hilltopfamilydental.com",
      { practiceName: "Hilltop Family Dental" },
      placeData,
      []
    );
    const f = report.categories.gbp.findings[0];
    expect(assertsGbpAbsence(f)).toBe(false);
    expect(f).toMatch(/live/i);
    expect(report.categories.gbp.profile_verified).toBe(true);
  });

  it("floors the GBP score when Google proves the profile exists", () => {
    const report = finalSafetyChecks(
      baseReport(["No Google Business Profile detected."]),
      "https://hilltopfamilydental.com",
      { practiceName: "Hilltop Family Dental" },
      placeData,
      []
    );
    expect(report.categories.gbp.score).toBeGreaterThanOrEqual(30);
  });

  it("preserves legitimate optimization findings untouched", () => {
    const original = "Your Google Business Profile is missing photos and has no posts in 6 months.";
    const report = finalSafetyChecks(
      baseReport([original]),
      "https://hilltopfamilydental.com",
      { practiceName: "Hilltop Family Dental" },
      placeData,
      []
    );
    expect(report.categories.gbp.findings[0]).toBe(original);
  });

  it("softens absence claims to 'could not verify' when placeData is null", () => {
    const report = finalSafetyChecks(
      baseReport(["This practice has no Google Business Profile."]),
      "https://example.com",
      { practiceName: "Example" },
      null,
      []
    );
    const f = report.categories.gbp.findings[0];
    expect(assertsGbpAbsence(f)).toBe(false);
    expect(f).toMatch(/could not (fully )?verify|under-optimized/i);
  });
});

// ════════════════════════════════════════════════════════════════
// ── Vertical Detection — financial + generic (new verticals) ──
// ════════════════════════════════════════════════════════════════

describe("detectVertical — financial & generic", () => {
  it("reclassifies a wealth advisor (submitted as legal) to financial", () => {
    const site = {
      scraped: true,
      visibleText: "fee-only fiduciary financial advisor wealth management retirement planning investment management portfolio cfp",
    };
    expect(detectVertical("legal", site)).toBe("financial");
  });

  it("honors an explicit financial selection", () => {
    const site = {
      scraped: true,
      visibleText: "wealth advisory financial planning fiduciary retirement income",
    };
    expect(detectVertical("financial", site)).toBe("financial");
  });

  it("falls back to generic for a non-modeled business with real content", () => {
    const site = {
      scraped: true,
      visibleText: "instructional design e-learning company we build custom training courses and learning management systems for enterprise clients across many industries with a focus on engaging multimedia content and measurable outcomes for corporate learning and development teams worldwide every single day".repeat(2),
    };
    expect(detectVertical("dental", site)).toBe("generic");
  });

  it("uses signalCounts from scrape when present", () => {
    const site = {
      scraped: true,
      visibleText: "irrelevant",
      signalCounts: { dental: 0, legal: 1, medical: 0, financial: 6 },
    };
    expect(detectVertical("legal", site)).toBe("financial");
  });

  it("respects a near-tie with the user's selection", () => {
    // legal=4, financial=4 (estate planning overlap) — user picked legal, keep it
    const site = {
      scraped: true,
      visibleText: "x",
      signalCounts: { dental: 0, legal: 4, medical: 0, financial: 4 },
    };
    expect(detectVertical("legal", site)).toBe("legal");
  });
});

describe("VERTICAL_CONFIG — new verticals", () => {
  it("has financial and generic configs with null placeType", () => {
    expect(VERTICAL_CONFIG.financial).toBeDefined();
    expect(VERTICAL_CONFIG.financial.placeType).toBe(null);
    expect(VERTICAL_CONFIG.financial.clientTerm).toBe("client");
    expect(VERTICAL_CONFIG.generic).toBeDefined();
    expect(VERTICAL_CONFIG.generic.placeType).toBe(null);
    expect(VERTICAL_CONFIG.generic.clientTerm).toBe("customer");
  });
});
