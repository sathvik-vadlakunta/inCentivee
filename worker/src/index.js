export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(env) });
    }

    const url = new URL(request.url);

    // GET /leads — view captured leads (auth via Authorization header or query param fallback)
    if (url.pathname === "/leads" && request.method === "GET") {
      const authHeader = request.headers.get("Authorization") || "";
      const bearerToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";
      const queryKey = url.searchParams.get("key") || "";
      if (!env.LEADS_SECRET || (bearerToken !== env.LEADS_SECRET && queryKey !== env.LEADS_SECRET)) {
        return new Response(JSON.stringify({ error: "Unauthorized" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }

      // Optional: filter by customer domain
      const filterDomain = url.searchParams.get("domain") || "";

      const list = await env.LEADS.list();
      const leads = [];
      for (const key of list.keys) {
        const val = await env.LEADS.get(key.name, "json");
        if (val) {
          if (filterDomain && val.practiceUrl && !val.practiceUrl.includes(filterDomain)) {
            continue;
          }
          leads.push(val);
        }
      }
      leads.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      return new Response(JSON.stringify(leads, null, 2), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // GET /stats/:domain — llms.txt hit counts (auth required)
    const statsMatch = url.pathname.match(/^\/stats\/(.+)$/);
    if (statsMatch && request.method === "GET") {
      const authHeader = request.headers.get("Authorization") || "";
      const bearerToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";
      if (!env.LEADS_SECRET || bearerToken !== env.LEADS_SECRET) {
        return new Response(JSON.stringify({ error: "Unauthorized" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }

      const domain = statsMatch[1];
      const today = new Date().toISOString().split("T")[0];
      const totalHits = parseInt(await env.LEADS.get(`hits:${domain}:total`) || "0");
      const todayHits = parseInt(await env.LEADS.get(`hits:${domain}:${today}`) || "0");

      // Get per-agent breakdowns
      const agents = ["chatgpt", "claude", "perplexity", "google", "bing", "apple"];
      const agentStats = {};
      for (const agent of agents) {
        const agentTotal = parseInt(await env.LEADS.get(`hits:${domain}:agent:${agent}:total`) || "0");
        const agentToday = parseInt(await env.LEADS.get(`hits:${domain}:agent:${agent}:${today}`) || "0");
        if (agentTotal > 0 || agentToday > 0) {
          agentStats[agent] = { total: agentTotal, today: agentToday };
        }
      }

      // Get last 7 days of daily hits
      const dailyHistory = [];
      for (let i = 0; i < 7; i++) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        const dateStr = d.toISOString().split("T")[0];
        const dayHits = parseInt(await env.LEADS.get(`hits:${domain}:${dateStr}`) || "0");
        dailyHistory.push({ date: dateStr, hits: dayHits });
      }

      return new Response(JSON.stringify({
        domain,
        total_hits: totalHits,
        today_hits: todayHits,
        date: today,
        by_agent: agentStats,
        daily_history: dailyHistory,
      }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // Track llms.txt hits — intercept requests from GEO_FILES KV worker
    if ((url.pathname === "/track-hit") && request.method === "POST") {
      try {
        const { domain, path, userAgent } = await request.json();
        if (domain && path) {
          const today = new Date().toISOString().split("T")[0];
          const totalKey = `hits:${domain}:total`;
          const dailyKey = `hits:${domain}:${today}`;

          const totalHits = parseInt(await env.LEADS.get(totalKey) || "0") + 1;
          const dailyHits = parseInt(await env.LEADS.get(dailyKey) || "0") + 1;

          await env.LEADS.put(totalKey, String(totalHits));
          await env.LEADS.put(dailyKey, String(dailyHits), { expirationTtl: 90 * 86400 });

          // Track by AI user-agent
          const agent = classifyUserAgent(userAgent || "");
          if (agent !== "other") {
            const agentTotalKey = `hits:${domain}:agent:${agent}:total`;
            const agentDailyKey = `hits:${domain}:agent:${agent}:${today}`;
            const agentTotal = parseInt(await env.LEADS.get(agentTotalKey) || "0") + 1;
            const agentDaily = parseInt(await env.LEADS.get(agentDailyKey) || "0") + 1;
            await env.LEADS.put(agentTotalKey, String(agentTotal));
            await env.LEADS.put(agentDailyKey, String(agentDaily), { expirationTtl: 90 * 86400 });
          }

          return new Response(JSON.stringify({ ok: true }), {
            headers: { "Content-Type": "application/json" },
          });
        }
      } catch (e) {
        // Silently fail — don't block the request
      }
      return new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // GET /geo/:domain/llms.txt or /geo/:domain/llms-full.txt — serve generated files from KV
    const geoMatch = url.pathname.match(/^\/geo\/([^/]+)\/(llms\.txt|llms-full\.txt|robots\.txt)$/);
    if (geoMatch && request.method === "GET") {
      const domain = geoMatch[1];
      const filename = geoMatch[2];
      const kvKey = `geo:${domain}:${filename}`;
      const content = await env.LEADS.get(kvKey);
      if (content) {
        // Track hit for llms.txt files
        if (filename.startsWith("llms")) {
          const userAgent = request.headers.get("User-Agent") || "";
          try {
            await fetch(new URL("/track-hit", url.origin), {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ domain, path: `/${filename}`, userAgent }),
            });
          } catch (_) { /* don't block response */ }
        }
        return new Response(content, {
          headers: {
            "Content-Type": "text/plain; charset=utf-8",
            "Cache-Control": "public, max-age=86400",
            "X-Generated-By": "PracticeRank GEO Agent",
            "Access-Control-Allow-Origin": "*",
          },
        });
      }
      return new Response("Not found", { status: 404, headers: { "Content-Type": "text/plain" } });
    }

    // PUT /geo/:domain/:filename — upload generated files to KV (auth required)
    const geoPutMatch = url.pathname.match(/^\/geo\/([^/]+)\/(llms\.txt|llms-full\.txt|robots\.txt)$/);
    if (geoPutMatch && request.method === "PUT") {
      const authHeader = request.headers.get("Authorization") || "";
      const bearerToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";
      if (!env.LEADS_SECRET || bearerToken !== env.LEADS_SECRET) {
        return new Response(JSON.stringify({ error: "Unauthorized" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }
      const domain = geoPutMatch[1];
      const filename = geoPutMatch[2];
      const kvKey = `geo:${domain}:${filename}`;
      const content = await request.text();
      await env.LEADS.put(kvKey, content);
      return new Response(JSON.stringify({ ok: true, key: kvKey }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.pathname !== "/audit" || request.method !== "POST") {
      return new Response(JSON.stringify({ error: "Not found" }), {
        status: 404,
        headers: { ...corsHeaders(env), "Content-Type": "application/json" },
      });
    }

    try {
      const body = await request.json();
      const { practiceUrl, email, name, phone } = body;

      if (!practiceUrl || !email) {
        return new Response(
          JSON.stringify({ error: "practiceUrl and email are required" }),
          { status: 400, headers: { ...corsHeaders(env), "Content-Type": "application/json" } }
        );
      }

      // ── Input validation ──
      const urlError = validatePracticeUrl(practiceUrl);
      if (urlError) {
        return new Response(
          JSON.stringify({ error: urlError }),
          { status: 400, headers: { ...corsHeaders(env), "Content-Type": "application/json" } }
        );
      }
      if (!isValidEmail(email)) {
        return new Response(
          JSON.stringify({ error: "Please enter a valid email address." }),
          { status: 400, headers: { ...corsHeaders(env), "Content-Type": "application/json" } }
        );
      }

      // ── Step 1: Scrape the actual website to get real practice info ──
      const siteData = await scrapePracticeSite(practiceUrl);

      // ── Step 1b: Reject non-dental websites ──
      if (siteData.scraped && !siteData.isDentalSite) {
        return new Response(
          JSON.stringify({ error: "This doesn't appear to be a dental practice website. PracticeRank audits are designed specifically for dental practices." }),
          { status: 400, headers: { ...corsHeaders(env), "Content-Type": "application/json" } }
        );
      }

      // ── Step 2: Fetch VERIFIED data from Google Places API ──
      let placeData = null;
      let competitors = [];
      if (env.GOOGLE_PLACES_API_KEY) {
        placeData = await fetchGooglePlaceData(
          siteData.practiceName,
          siteData.city,
          siteData.state,
          siteData.domain,
          siteData.phone,
          env.GOOGLE_PLACES_API_KEY
        );

        // If Google found the place, search for additional locations + competitors
        if (placeData && placeData.location) {
          const lat = placeData.location.latitude || placeData.location.lat;
          const lng = placeData.location.longitude || placeData.location.lng;

          // Search for other locations of the same practice
          const otherLocations = await fetchOtherLocations(
            siteData.practiceName,
            siteData.domain,
            placeData,
            env.GOOGLE_PLACES_API_KEY
          );
          if (otherLocations.length > 0) {
            placeData.locations = [
              { name: placeData.name, address: placeData.address, city: placeData.city, state: placeData.state, rating: placeData.rating, reviewCount: placeData.reviewCount, placeId: placeData.placeId },
              ...otherLocations,
            ];
            // Aggregate: combined review count, weighted average rating
            const totalReviews = placeData.locations.reduce((sum, l) => sum + l.reviewCount, 0);
            const weightedRating = placeData.locations.reduce((sum, l) => sum + l.rating * l.reviewCount, 0) / totalReviews;
            placeData.combinedReviewCount = totalReviews;
            placeData.combinedRating = Math.round(weightedRating * 10) / 10;
            placeData.isMultiLocation = true;
          }

          competitors = await fetchNearbyCompetitors(
            lat,
            lng,
            placeData.name,
            env.GOOGLE_PLACES_API_KEY
          );
        }
      }

      // ── Step 3: Build prompt with real scraped + verified data ──
      const prompt = buildAuditPrompt(practiceUrl, siteData, placeData, competitors);

      // ── Step 4: Call Claude with the real data ──
      const anthropicRes = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": env.ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 2500,
          messages: [{ role: "user", content: prompt }],
        }),
      });

      const data = await anthropicRes.json();

      if (data.error) {
        return new Response(JSON.stringify({ error: data.error.message }), {
          status: 502,
          headers: { ...corsHeaders(env), "Content-Type": "application/json" },
        });
      }

      const raw = data.content.map((b) => b.text || "").join("");
      const cleaned = raw.replace(/```json|```/g, "").trim();
      let report = JSON.parse(cleaned);

      // ── Step 5: Post-validate — override Claude's guesses with verified data ──
      report = validateAndCorrectReport(report, siteData, placeData, competitors);

      // Save lead to KV with per-domain prefix for customer isolation
      const domainSlug = practiceUrl.replace(/^https?:\/\//, "").replace(/[^a-z0-9]/gi, "_").toLowerCase();
      const leadId = `lead_${domainSlug}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const lead = {
        id: leadId,
        timestamp: new Date().toISOString(),
        name: name || "Not provided",
        email,
        phone: phone || "Not provided",
        practiceUrl,
        domain: domainSlug,
        score: report.overall_score,
        grade: report.grade,
        practice_name: report.practice_name,
        city: report.city,
        state: report.state,
        revenue_lost: report.revenue_lost_annually,
        executive_summary: report.executive_summary,
        data_confidence: report.data_confidence,
      };
      await env.LEADS.put(leadId, JSON.stringify(lead));

      // Send email notifications (non-blocking — don't fail the audit if email fails)
      if (env.RESEND_API_KEY) {
        try {
          await sendAuditEmails(env, report, email, name, practiceUrl);
        } catch (emailErr) {
          console.error("Email send failed:", emailErr.message);
        }
      }

      return new Response(JSON.stringify(report), {
        headers: { ...corsHeaders(env), "Content-Type": "application/json" },
      });
    } catch (e) {
      // Never leak internal error details to the client
      console.error("Audit error:", e.message);
      const safeMessage = e instanceof SyntaxError
        ? "Failed to parse audit response. Please try again."
        : "An error occurred generating your audit. Please try again.";
      return new Response(JSON.stringify({ error: safeMessage }), {
        status: 500,
        headers: { ...corsHeaders(env), "Content-Type": "application/json" },
      });
    }
  },
};

// ════════════════════════════════════════════════════════════════
// ── Google Places API — Verified Business Data ──
// ════════════════════════════════════════════════════════════════

async function fetchGooglePlaceData(practiceName, city, state, domain, phone, apiKey) {
  try {
    // Strategy: try multiple search queries to find the right place
    const queries = [];

    // Best query: name + city + state + "dentist"
    if (practiceName && city && state) {
      queries.push(`${practiceName} dentist ${city} ${state}`);
    }
    // Fallback: name + "dentist"
    if (practiceName) {
      queries.push(`${practiceName} dentist`);
    }
    // Fallback: domain-based search
    const domainName = domain.replace(/^www\./, "").replace(/\.(com|net|org|dental|dentist)$/i, "").replace(/[-_]/g, " ");
    queries.push(`${domainName} dentist ${city || ""} ${state || ""}`.trim());

    const FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.rating,places.userRatingCount,places.websiteUri,places.location,places.businessStatus,places.addressComponents";

    let bestPlace = null;

    for (const query of queries) {
      const res = await fetch("https://places.googleapis.com/v1/places:searchText", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Goog-Api-Key": apiKey,
          "X-Goog-FieldMask": FIELD_MASK,
        },
        body: JSON.stringify({
          textQuery: query,
          includedType: "dentist",
          maxResultCount: 5,
        }),
      });
      const data = await res.json();

      if (data.places && data.places.length > 0) {
        bestPlace = findBestMatch(data.places, practiceName, domain, phone, city);
        if (bestPlace) break;
      }
    }

    if (!bestPlace) return null;

    const place = bestPlace;

    // Parse address components
    const addressParts = {};
    for (const comp of place.addressComponents || []) {
      const types = comp.types || [];
      if (types.includes("locality")) addressParts.city = comp.longText || comp.shortText;
      if (types.includes("administrative_area_level_1")) addressParts.state = comp.shortText;
      if (types.includes("postal_code")) addressParts.zip = comp.longText || comp.shortText;
    }

    // Verify this is actually the right business by checking domain match
    const placeWebsite = (place.websiteUri || "").replace(/^https?:\/\//, "").replace(/\/+$/, "").replace(/^www\./, "");
    const inputDomain = domain.replace(/^www\./, "");
    const domainMatch = placeWebsite && inputDomain &&
      (placeWebsite.includes(inputDomain) || inputDomain.includes(placeWebsite));

    // Check name similarity
    const placeName = place.displayName?.text || "";
    const nameMatch = practiceName && placeName &&
      (placeName.toLowerCase().includes(practiceName.toLowerCase().slice(0, 10)) ||
       practiceName.toLowerCase().includes(placeName.toLowerCase().slice(0, 10)));

    return {
      verified: true,
      name: placeName,
      address: place.formattedAddress || "",
      city: addressParts.city || "",
      state: addressParts.state || "",
      zip: addressParts.zip || "",
      phone: place.nationalPhoneNumber || "",
      rating: place.rating || 0,
      reviewCount: place.userRatingCount || 0,
      website: place.websiteUri || "",
      location: place.location || null,
      businessStatus: place.businessStatus || "",
      placeId: place.id,
      domainMatch,
      nameMatch: !!nameMatch,
      matchConfidence: domainMatch ? "high" : nameMatch ? "medium" : "low",
    };
  } catch (e) {
    console.error("Google Places API error:", e.message);
    return null;
  }
}

async function fetchOtherLocations(practiceName, domain, primaryPlace, apiKey) {
  // Search for other locations of the same practice by name (without city filter)
  if (!practiceName) return [];

  try {
    const FIELD_MASK = "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.websiteUri,places.addressComponents";

    const res = await fetch("https://places.googleapis.com/v1/places:searchText", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": apiKey,
        "X-Goog-FieldMask": FIELD_MASK,
      },
      body: JSON.stringify({
        textQuery: `${practiceName} dentist`,
        includedType: "dentist",
        maxResultCount: 10,
      }),
    });
    const data = await res.json();

    if (!data.places || data.places.length === 0) return [];

    const inputDomain = (domain || "").replace(/^www\./, "").toLowerCase();
    const primaryId = primaryPlace.placeId;
    const locations = [];

    for (const place of data.places) {
      // Skip the primary location we already found
      if (place.id === primaryId) continue;

      // Check if this is the same business (domain match or strong name match)
      const placeWebsite = (place.websiteUri || "").replace(/^https?:\/\//, "").replace(/\/+$/, "").replace(/^www\./, "").toLowerCase();
      const placeName = (place.displayName?.text || "").toLowerCase();
      const primaryName = (primaryPlace.name || "").toLowerCase();

      const domainMatch = inputDomain && placeWebsite && (placeWebsite.includes(inputDomain) || inputDomain.includes(placeWebsite));
      // Strong name match: names share significant overlap (not just a few chars)
      const nameMatch = primaryName.length > 5 && placeName.length > 5 &&
        (placeName.includes(primaryName) || primaryName.includes(placeName) ||
         placeName.replace(/\s+(dental|dentistry|dds|dmd)\s*/gi, "").trim() === primaryName.replace(/\s+(dental|dentistry|dds|dmd)\s*/gi, "").trim());

      if (!domainMatch && !nameMatch) continue;

      // Parse city from address components
      let city = "";
      for (const comp of place.addressComponents || []) {
        if ((comp.types || []).includes("locality")) {
          city = comp.longText || comp.shortText || "";
        }
      }

      locations.push({
        name: place.displayName?.text || "",
        address: place.formattedAddress || "",
        city,
        state: "",
        rating: place.rating || 0,
        reviewCount: place.userRatingCount || 0,
        placeId: place.id,
      });
    }

    return locations;
  } catch (e) {
    console.error("Multi-location search error:", e.message);
    return [];
  }
}

function findBestMatch(results, practiceName, domain, phone, city) {
  const inputDomain = (domain || "").replace(/^www\./, "").toLowerCase();
  const inputName = (practiceName || "").toLowerCase();
  const inputPhone = (phone || "").replace(/\D/g, "");
  const inputCity = (city || "").toLowerCase();

  let bestScore = -1;
  let bestResult = null;

  for (const r of results) {
    let score = 0;
    const rName = (r.displayName?.text || "").toLowerCase();

    // Name contains our name or vice versa
    if (inputName && rName && (rName.includes(inputName.slice(0, 10)) || inputName.includes(rName.slice(0, 10)))) {
      score += 3;
    }

    // Domain match (strongest signal)
    const rWebsite = (r.websiteUri || "").replace(/^https?:\/\//, "").replace(/\/+$/, "").replace(/^www\./, "").toLowerCase();
    if (inputDomain && rWebsite && (rWebsite.includes(inputDomain) || inputDomain.includes(rWebsite))) {
      score += 5;
    }

    // City match
    const rAddr = (r.formattedAddress || "").toLowerCase();
    if (inputCity && rAddr.includes(inputCity)) {
      score += 2;
    }

    // Has reviews (more likely to be a real match)
    if ((r.userRatingCount || 0) > 10) {
      score += 1;
    }

    if (score > bestScore) {
      bestScore = score;
      bestResult = r;
    }
  }

  return bestScore >= 2 ? bestResult : (results[0] || null);
}

async function fetchNearbyCompetitors(lat, lng, practiceName, apiKey) {
  try {
    // Search for dentists within ~8km (5 miles) using Places API (New)
    const res = await fetch("https://places.googleapis.com/v1/places:searchNearby", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": apiKey,
        "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount,places.formattedAddress",
      },
      body: JSON.stringify({
        includedTypes: ["dentist"],
        maxResultCount: 20,
        locationRestriction: {
          circle: {
            center: { latitude: lat, longitude: lng },
            radius: 8000.0,
          },
        },
      }),
    });
    const data = await res.json();

    if (!data.places || data.places.length === 0) return [];

    // Filter out the practice itself + sort by review count
    const pName = (practiceName || "").toLowerCase();
    const competitors = data.places
      .filter(r => {
        const rName = (r.displayName?.text || "").toLowerCase();
        return !(rName.includes(pName.slice(0, 10)) || pName.includes(rName.slice(0, 10)));
      })
      .map(r => ({
        name: r.displayName?.text || "",
        rating: r.rating || 0,
        reviewCount: r.userRatingCount || 0,
        address: r.formattedAddress || "",
        placeId: r.id,
      }))
      .sort((a, b) => b.reviewCount - a.reviewCount)
      .slice(0, 10);

    return competitors;
  } catch (e) {
    console.error("Competitor search error:", e.message);
    return [];
  }
}

// ════════════════════════════════════════════════════════════════
// ── Post-Response Validation — Fix hallucinated data ──
// ════════════════════════════════════════════════════════════════

function validateAndCorrectReport(report, siteData, placeData, competitors) {
  const corrections = [];

  // ── Override with Google-verified practice info ──
  if (placeData && placeData.matchConfidence !== "low") {
    // Fix practice name
    if (placeData.name && placeData.nameMatch) {
      if (report.practice_name !== placeData.name) {
        corrections.push(`practice_name: "${report.practice_name}" → "${placeData.name}" (Google verified)`);
        report.practice_name = placeData.name;
      }
    }

    // Fix city
    if (placeData.city) {
      if (report.city !== placeData.city) {
        corrections.push(`city: "${report.city}" → "${placeData.city}" (Google verified)`);
        report.city = placeData.city;
      }
    }

    // Fix state
    if (placeData.state) {
      if (report.state !== placeData.state) {
        corrections.push(`state: "${report.state}" → "${placeData.state}" (Google verified)`);
        report.state = placeData.state;
      }
    }

    // Fix review count and rating — this is the big one
    // For multi-location practices, use combined totals
    if (placeData.reviewCount > 0) {
      const claudeCount = report.categories?.reviews?.count || 0;
      const claudeRating = report.categories?.reviews?.rating || 0;
      const realCount = placeData.isMultiLocation ? placeData.combinedReviewCount : placeData.reviewCount;
      const realRating = placeData.isMultiLocation ? placeData.combinedRating : placeData.rating;

      // If Claude's numbers are more than 20% off, override
      if (Math.abs(claudeCount - realCount) > realCount * 0.2 || claudeCount === 0) {
        corrections.push(`reviews.count: ${claudeCount} → ${realCount} (Google verified)`);
        report.categories.reviews.count = realCount;
      }
      if (Math.abs(claudeRating - realRating) > 0.3 || claudeRating === 0) {
        corrections.push(`reviews.rating: ${claudeRating} → ${realRating} (Google verified)`);
        report.categories.reviews.rating = realRating;
      }

      // Recalculate review score based on real data
      report.categories.reviews.score = calculateReviewScore(realCount, realRating, competitors);
      report.categories.reviews.status = scoreToStatus(report.categories.reviews.score);

      // Fix findings across ALL categories if they mentioned wrong review count
      const fixReviewCount = (f) => f.replace(/\b\d+\s*reviews?\b/gi, (match) => {
        const num = parseInt(match);
        if (num !== realCount && num < 1000) {
          return `${realCount} reviews`;
        }
        return match;
      });
      for (const cat of Object.values(report.categories)) {
        if (Array.isArray(cat.findings)) {
          cat.findings = cat.findings.map(fixReviewCount);
        }
      }
    }
  }

  // ── Override competitor data with real Google data ──
  if (competitors.length > 0) {
    const topCompetitor = competitors[0];
    const claudeCompName = report.categories?.reviews?.competitor_name || "";
    const claudeCompReviews = report.categories?.reviews?.competitor_reviews || 0;

    // Always use real competitor data
    if (topCompetitor.reviewCount > 0) {
      if (claudeCompName !== topCompetitor.name || Math.abs(claudeCompReviews - topCompetitor.reviewCount) > topCompetitor.reviewCount * 0.2) {
        corrections.push(`competitor: "${claudeCompName}" (${claudeCompReviews}) → "${topCompetitor.name}" (${topCompetitor.reviewCount}) (Google verified)`);
        report.categories.reviews.competitor_name = topCompetitor.name;
        report.categories.reviews.competitor_reviews = topCompetitor.reviewCount;
      }
    }
  }

  // ── Cross-check: if site data has a verified city and Claude used a different one ──
  if (siteData.validation?.checks?.city?.status === "verified" && siteData.city) {
    if (report.city !== siteData.city && (!placeData || !placeData.city)) {
      corrections.push(`city: "${report.city}" → "${siteData.city}" (website verified)`);
      report.city = siteData.city;
    }
  }

  // ── Recalculate overall score with corrected category scores ──
  if (report.categories) {
    const cats = report.categories;
    const weights = { gbp: 0.2, ai_readiness: 0.2, reviews: 0.2, local_seo: 0.15, content: 0.15, technical: 0.1 };
    let weightedSum = 0;
    let totalWeight = 0;
    for (const [key, weight] of Object.entries(weights)) {
      if (cats[key] && typeof cats[key].score === "number") {
        weightedSum += cats[key].score * weight;
        totalWeight += weight;
      }
    }
    if (totalWeight > 0) {
      report.overall_score = Math.round(weightedSum / totalWeight);
      report.grade = scoreToGrade(report.overall_score);
    }
  }

  // ── Add data confidence indicator ──
  report.data_confidence = placeData?.matchConfidence || "unverified";
  if (placeData?.domainMatch) {
    report.data_confidence = "verified";
  }
  report.data_corrections = corrections.length > 0 ? corrections : undefined;
  report.google_verified = !!(placeData && placeData.matchConfidence !== "low");

  // Add multi-location data so the frontend can display it
  if (placeData?.isMultiLocation) {
    report.multi_location = {
      location_count: placeData.locations.length,
      locations: placeData.locations.map(l => ({
        name: l.name,
        city: l.city || l.address,
        rating: l.rating,
        review_count: l.reviewCount,
      })),
      combined_reviews: placeData.combinedReviewCount,
      combined_rating: placeData.combinedRating,
    };
  }

  return report;
}

function calculateReviewScore(count, rating, competitors) {
  // Base score from review count
  let score = 0;
  if (count >= 500) score += 40;
  else if (count >= 200) score += 35;
  else if (count >= 100) score += 28;
  else if (count >= 50) score += 20;
  else if (count >= 20) score += 12;
  else if (count >= 10) score += 8;
  else score += 3;

  // Rating bonus
  if (rating >= 4.8) score += 30;
  else if (rating >= 4.5) score += 25;
  else if (rating >= 4.0) score += 18;
  else if (rating >= 3.5) score += 10;
  else score += 3;

  // Competitive position bonus
  if (competitors.length > 0) {
    const topCompCount = competitors[0]?.reviewCount || 0;
    if (topCompCount > 0) {
      const ratio = count / topCompCount;
      if (ratio >= 1.0) score += 30; // More reviews than top competitor
      else if (ratio >= 0.5) score += 20;
      else if (ratio >= 0.25) score += 12;
      else score += 5; // Far behind
    }
  } else {
    score += 15; // No competitor data, give benefit of doubt
  }

  return Math.min(100, score);
}

function scoreToStatus(score) {
  if (score <= 30) return "critical";
  if (score <= 60) return "needs_work";
  if (score <= 80) return "good";
  return "excellent";
}

function scoreToGrade(score) {
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
}

// ════════════════════════════════════════════════════════════════
// ── Email Notifications via Resend ──
// ════════════════════════════════════════════════════════════════

async function sendAuditEmails(env, report, prospectEmail, prospectName, practiceUrl) {
  const cats = [
    { key: 'gbp', label: 'Google Business Profile' },
    { key: 'ai_readiness', label: 'AI Search Readiness' },
    { key: 'reviews', label: 'Review Strength' },
    { key: 'local_seo', label: 'Local SEO & Citations' },
    { key: 'content', label: 'Content & On-Page SEO' },
    { key: 'technical', label: 'Technical SEO' },
  ];

  const scoreColor = (s) => s >= 70 ? '#10b981' : s >= 45 ? '#f59e0b' : '#f87171';
  const statusLabel = (s) => s === 'critical' ? 'Critical' : s === 'needs_work' ? 'Needs Work' : s === 'good' ? 'Good' : 'Excellent';

  const categoryRows = cats.map(cat => {
    const d = report.categories?.[cat.key];
    if (!d) return '';
    return `<tr>
      <td style="padding:10px 16px;border-bottom:1px solid #eee;font-weight:600;">${cat.label}</td>
      <td style="padding:10px 16px;border-bottom:1px solid #eee;text-align:center;">
        <span style="color:${scoreColor(d.score)};font-weight:800;font-size:18px;">${d.score}</span><span style="color:#999;font-size:13px;">/100</span>
      </td>
      <td style="padding:10px 16px;border-bottom:1px solid #eee;text-align:center;">
        <span style="background:${scoreColor(d.score)}22;color:${scoreColor(d.score)};padding:3px 10px;border-radius:12px;font-size:12px;font-weight:700;">${statusLabel(d.status)}</span>
      </td>
    </tr>`;
  }).join('');

  const topFindings = [];
  for (const cat of cats) {
    const d = report.categories?.[cat.key];
    if (d?.findings) {
      for (const f of d.findings.slice(0, 2)) {
        topFindings.push(`<li style="margin-bottom:6px;color:#555;font-size:14px;">${f}</li>`);
      }
    }
    if (topFindings.length >= 6) break;
  }

  const practiceName = report.practice_name || practiceUrl;
  const city = report.city || '';
  const state = report.state || '';
  const location = city && state ? `${city}, ${state}` : city || state || '';

  // ── Prospect email ──
  const prospectHtml = `
  <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;margin:0 auto;background:#fff;">
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:40px 32px;text-align:center;border-radius:12px 12px 0 0;">
      <h1 style="color:#fff;margin:0 0 8px;font-size:24px;">Your PracticeRank Score</h1>
      <p style="color:#94a3b8;margin:0;font-size:14px;">${practiceName}${location ? ' — ' + location : ''}</p>
    </div>

    <div style="padding:32px;text-align:center;">
      <div style="display:inline-block;width:120px;height:120px;border-radius:50%;border:4px solid ${scoreColor(report.overall_score)};line-height:120px;margin-bottom:16px;">
        <span style="font-size:48px;font-weight:800;color:${scoreColor(report.overall_score)};">${report.overall_score}</span>
      </div>
      <p style="color:#64748b;font-size:15px;line-height:1.7;max-width:500px;margin:0 auto 24px;">${report.executive_summary || ''}</p>
      ${report.revenue_lost_annually ? `<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:12px 20px;display:inline-block;margin-bottom:24px;">
        <span style="color:#ef4444;font-weight:700;font-size:14px;">Estimated revenue lost: ${report.revenue_lost_annually}/year</span>
      </div>` : ''}

      <table style="width:100%;border-collapse:collapse;margin:24px 0;text-align:left;">
        <thead>
          <tr style="background:#f8fafc;">
            <th style="padding:10px 16px;border-bottom:2px solid #e2e8f0;font-size:13px;color:#64748b;">Category</th>
            <th style="padding:10px 16px;border-bottom:2px solid #e2e8f0;font-size:13px;color:#64748b;text-align:center;">Score</th>
            <th style="padding:10px 16px;border-bottom:2px solid #e2e8f0;font-size:13px;color:#64748b;text-align:center;">Status</th>
          </tr>
        </thead>
        <tbody>${categoryRows}</tbody>
      </table>

      <div style="text-align:left;margin:24px 0;">
        <h3 style="margin:0 0 12px;font-size:16px;color:#1e293b;">Key Findings</h3>
        <ul style="margin:0;padding-left:20px;">${topFindings.join('')}</ul>
      </div>

      <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:20px;margin:24px 0;">
        <h3 style="margin:0 0 8px;color:#16a34a;font-size:16px;">Ready to fix this?</h3>
        <p style="margin:0 0 16px;color:#555;font-size:14px;">PracticeRank can implement all these fixes in your first month — no effort from you.</p>
        <a href="https://practicerank.ai/#book" style="background:#10b981;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:700;font-size:14px;display:inline-block;">Book Your Free Strategy Call</a>
      </div>
    </div>

    <div style="background:#f8fafc;padding:20px 32px;text-align:center;border-radius:0 0 12px 12px;border-top:1px solid #e2e8f0;">
      <p style="margin:0;color:#94a3b8;font-size:12px;">PracticeRank — AI-Powered Dental Marketing</p>
      <p style="margin:4px 0 0;color:#94a3b8;font-size:12px;">practicerank.ai</p>
    </div>
  </div>`;

  // ── Internal lead notification ──
  const leadHtml = `
  <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;background:#fff;padding:24px;">
    <h2 style="color:#1e293b;margin:0 0 16px;">New PracticeRank Lead</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
      <tr><td style="padding:8px 0;color:#64748b;width:140px;">Practice</td><td style="padding:8px 0;font-weight:700;">${practiceName}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Location</td><td style="padding:8px 0;">${location || 'Unknown'}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Contact</td><td style="padding:8px 0;">${prospectName || 'Not provided'}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Email</td><td style="padding:8px 0;"><a href="mailto:${prospectEmail}" style="color:#10b981;">${prospectEmail}</a></td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">URL</td><td style="padding:8px 0;"><a href="${practiceUrl}" style="color:#10b981;">${practiceUrl}</a></td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Overall Score</td><td style="padding:8px 0;font-weight:800;color:${scoreColor(report.overall_score)};">${report.overall_score}/100 (${report.grade})</td></tr>
      <tr><td style="padding:8px 0;color:#64748b;">Revenue Lost</td><td style="padding:8px 0;color:#ef4444;font-weight:700;">${report.revenue_lost_annually || 'N/A'}</td></tr>
    </table>
    <h3 style="margin:0 0 8px;font-size:14px;color:#64748b;">Category Breakdown</h3>
    <table style="width:100%;border-collapse:collapse;">${categoryRows}</table>
  </div>`;

  const fromAddr = env.RESEND_FROM || 'PracticeRank <scores@practicerank.ai>';
  const internalRecipients = (env.LEAD_NOTIFY_EMAILS || 'kdoherty@practicerank.ai,jonlucas@lostrelic.com').split(',').map(e => e.trim());

  // Send both emails in parallel
  await Promise.all([
    // Prospect email
    sendResendEmail(env.RESEND_API_KEY, {
      from: fromAddr,
      to: [prospectEmail],
      subject: `Your PracticeRank Score: ${report.overall_score}/100 — ${practiceName}`,
      html: prospectHtml,
    }),
    // Internal lead notification
    sendResendEmail(env.RESEND_API_KEY, {
      from: fromAddr,
      to: internalRecipients,
      subject: `[Lead] ${practiceName} — ${report.overall_score}/100 (${prospectEmail})`,
      html: leadHtml,
    }),
  ]);
}

async function sendResendEmail(apiKey, payload) {
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Resend API error ${res.status}: ${err}`);
  }
  return res.json();
}

// ════════════════════════════════════════════════════════════════
// ── Scrape practice website for real data ──
// ════════════════════════════════════════════════════════════════

async function scrapePracticeSite(practiceUrl) {
  const domain = practiceUrl.replace(/^https?:\/\//, "").replace(/\/+$/, "");
  const urls = [`https://${domain}`, `https://www.${domain}`];

  let html = "";
  let finalUrl = "";

  for (const u of urls) {
    try {
      const res = await fetch(u, {
        headers: { "User-Agent": "PracticeRank-Auditor/1.0" },
        redirect: "follow",
        cf: { cacheTtl: 300 },
      });
      if (res.ok) {
        html = await res.text();
        finalUrl = res.url || u;
        break;
      }
    } catch (_) {
      continue;
    }
  }

  if (!html) {
    return { scraped: false, domain };
  }

  // Extract key info from HTML
  const title = extractMeta(html, /<title[^>]*>([^<]+)<\/title>/i);
  const metaDesc = extractMeta(html, /<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i);
  const ogTitle = extractMeta(html, /<meta[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["']/i);

  // Look for address in schema
  const streetAddress = extractMeta(html, /"streetAddress"\s*:\s*"([^"]+)"/);
  const city = extractMeta(html, /"addressLocality"\s*:\s*"([^"]+)"/);
  const state = extractMeta(html, /"addressRegion"\s*:\s*"([^"]+)"/);
  const postalCode = extractMeta(html, /"postalCode"\s*:\s*"([^"]+)"/);
  const phone = extractMeta(html, /(?:tel:|href=["']tel:)([^"'<]+)/i) ||
    extractMeta(html, /(\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4})/);
  const schemaName = extractMeta(html, /"@type"\s*:\s*"(?:Dentist|LocalBusiness|Dental[^"]*|MedicalBusiness|HealthBusiness|ProfessionalService)"[^}]*"name"\s*:\s*"([^"]+)"/) ||
    extractMeta(html, /"name"\s*:\s*"([^"]+)"[^}]*"@type"\s*:\s*"(?:Dentist|LocalBusiness|Dental[^"]*|MedicalBusiness)"/);
  const titleName = (title || "").replace(/\s*[|\-–—].*/g, "").trim();
  const practiceName = schemaName || ogTitle || titleName || "";

  // Extract visible text (strip tags) for content analysis — limit to 3000 chars
  const visibleText = html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 3000);

  // Check for key technical signals
  const hasSSL = finalUrl.startsWith("https://");
  const hasSchema = html.includes("application/ld+json");
  const schemaTypes = [];
  const schemaMatches = html.matchAll(/"@type"\s*:\s*"([^"]+)"/g);
  for (const m of schemaMatches) schemaTypes.push(m[1]);
  const hasFaqSchema = schemaTypes.includes("FAQPage");
  const hasSitemap = html.includes("sitemap.xml") || html.includes("sitemap");
  const hasViewport = /<meta[^>]*name=["']viewport["']/i.test(html);

  // Try to fetch robots.txt
  let robotsTxt = "";
  try {
    const rRes = await fetch(`https://${domain}/robots.txt`, {
      headers: { "User-Agent": "PracticeRank-Auditor/1.0" },
    });
    if (rRes.ok) robotsTxt = await rRes.text();
  } catch (_) {}

  // Try to check for llms.txt
  let hasLlmsTxt = false;
  try {
    const lRes = await fetch(`https://${domain}/llms.txt`, {
      headers: { "User-Agent": "PracticeRank-Auditor/1.0" },
    });
    hasLlmsTxt = lRes.ok && (await lRes.text()).length > 50;
  } catch (_) {}

  // ── Check if this is actually a dental practice website ──
  const allText = `${title} ${metaDesc} ${practiceName} ${visibleText}`.toLowerCase();
  const dentalSignals = DENTAL_KEYWORDS.filter(kw => allText.includes(kw));
  const hasDentalSchema = schemaTypes.some(t => /dentist|dental|medical/i.test(t));
  const isDentalSite = dentalSignals.length >= 2 || (dentalSignals.length >= 1 && hasDentalSchema);

  const raw = {
    scraped: true,
    domain,
    finalUrl,
    isDentalSite,
    dentalSignals,
    practiceName: practiceName || "",
    title: title || "",
    metaDescription: metaDesc || "",
    streetAddress: streetAddress || "",
    city: city || "",
    state: state || "",
    postalCode: postalCode || "",
    phone: phone || "",
    visibleText,
    hasSSL,
    hasSchema,
    schemaTypes,
    hasFaqSchema,
    hasSitemap,
    hasViewport,
    hasLlmsTxt,
    robotsTxt: robotsTxt.slice(0, 500),
  };

  // Run sanity checks on the scraped data
  return validateScrapedData(raw);
}

function extractMeta(html, regex) {
  const m = html.match(regex);
  return m ? m[1].trim() : "";
}

// ── Sanity check / validation for scraped data ──
const VALID_STATES = new Set([
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
  "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
  "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV",
  "WI","WY","DC","AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT",
]);

const AREA_CODE_STATES = {
  "201":"NJ","202":"DC","203":"CT","205":"AL","206":"WA","207":"ME","208":"ID",
  "209":"CA","210":"TX","212":"NY","213":"CA","214":"TX","215":"PA","216":"OH",
  "217":"IL","218":"MN","219":"IN","220":"OH","223":"PA","224":"IL","225":"LA",
  "228":"MS","229":"GA","231":"MI","234":"OH","239":"FL","240":"MD","248":"MI",
  "251":"AL","252":"NC","253":"WA","254":"TX","256":"AL","260":"IN","262":"WI",
  "267":"PA","269":"MI","270":"KY","272":"PA","276":"VA","281":"TX","301":"MD",
  "302":"DE","303":"CO","304":"WV","305":"FL","307":"WY","308":"NE","309":"IL",
  "310":"CA","312":"IL","313":"MI","314":"MO","315":"NY","316":"KS","317":"IN",
  "318":"LA","319":"IA","320":"MN","321":"FL","323":"CA","325":"TX","326":"OH",
  "330":"OH","331":"IL","332":"NY","334":"AL","336":"NC","337":"LA","339":"MA",
  "340":"VI","346":"TX","347":"NY","351":"MA","352":"FL","360":"WA","361":"TX",
  "364":"KY","380":"OH","385":"UT","386":"FL","401":"RI","402":"NE","404":"GA",
  "405":"OK","406":"MT","407":"FL","408":"CA","409":"TX","410":"MD","412":"PA",
  "413":"MA","414":"WI","415":"CA","417":"MO","419":"OH","423":"TN","424":"CA",
  "425":"WA","430":"TX","432":"TX","434":"VA","435":"UT","440":"OH","442":"CA",
  "443":"MD","445":"PA","458":"OR","463":"IN","469":"TX","470":"GA","475":"CT",
  "478":"GA","479":"AR","480":"AZ","484":"PA","501":"AR","502":"KY","503":"OR",
  "504":"LA","505":"NM","507":"MN","508":"MA","509":"WA","510":"CA","512":"TX",
  "513":"OH","515":"IA","516":"NY","517":"MI","518":"NY","520":"AZ","530":"CA",
  "531":"NE","534":"WI","539":"OK","540":"VA","541":"OR","551":"NJ","559":"CA",
  "561":"FL","562":"CA","563":"IA","567":"OH","570":"PA","571":"VA","573":"MO",
  "574":"IN","575":"NM","580":"OK","585":"NY","586":"MI","601":"MS","602":"AZ",
  "603":"NH","605":"SD","606":"KY","607":"NY","608":"WI","609":"NJ","610":"PA",
  "612":"MN","614":"OH","615":"TN","616":"MI","617":"MA","618":"IL","619":"CA",
  "620":"KS","623":"AZ","626":"CA","628":"CA","629":"TN","630":"IL","631":"NY",
  "636":"MO","641":"IA","646":"NY","650":"CA","651":"MN","657":"CA","660":"MO",
  "661":"CA","662":"MS","667":"MD","669":"CA","678":"GA","681":"WV","682":"TX",
  "689":"FL","701":"ND","702":"NV","703":"VA","704":"NC","706":"GA","707":"CA",
  "708":"IL","712":"IA","713":"TX","714":"CA","715":"WI","716":"NY","717":"PA",
  "718":"NY","719":"CO","720":"CO","724":"PA","725":"NV","726":"TX","727":"FL",
  "731":"TN","732":"NJ","734":"MI","737":"TX","740":"OH","743":"NC","747":"CA",
  "754":"FL","757":"VA","760":"CA","762":"GA","763":"MN","765":"IN","769":"MS",
  "770":"GA","772":"FL","773":"IL","774":"MA","775":"NV","779":"IL","781":"MA",
  "785":"KS","786":"FL","801":"UT","802":"VT","803":"SC","804":"VA","805":"CA",
  "806":"TX","808":"HI","810":"MI","812":"IN","813":"FL","814":"PA","815":"IL",
  "816":"MO","817":"TX","818":"CA","828":"NC","830":"TX","831":"CA","832":"TX",
  "838":"NY","843":"SC","845":"NY","847":"IL","848":"NJ","850":"FL","854":"SC",
  "856":"NJ","857":"MA","858":"CA","859":"KY","860":"CT","862":"NJ","863":"FL",
  "864":"SC","865":"TN","870":"AR","872":"IL","878":"PA","901":"TN","903":"TX",
  "904":"FL","906":"MI","907":"AK","908":"NJ","909":"CA","910":"NC","912":"GA",
  "913":"KS","914":"NY","915":"TX","916":"CA","917":"NY","918":"OK","919":"NC",
  "920":"WI","925":"CA","928":"AZ","929":"NY","930":"IN","931":"TN","934":"NY",
  "936":"TX","937":"OH","938":"AL","940":"TX","941":"FL","943":"GA","945":"TX",
  "947":"MI","949":"CA","951":"CA","952":"MN","954":"FL","956":"TX","959":"CT",
  "970":"CO","971":"OR","972":"TX","973":"NJ","975":"MO","978":"MA","979":"TX",
  "980":"NC","984":"NC","985":"LA","986":"ID",
};

const BAD_NAME_PATTERNS = [
  /^(eastern|central|mountain|pacific|atlantic)\s+time/i,
  /^(united states|canada|mexico|select|choose|option|none|n\/a|test)/i,
  /^(home|about|contact|services|blog|menu|navigation|footer|header|search)$/i,
  /^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)/i,
  /^\d+$/,
  /^.{1,2}$/,
  /^.{100,}$/,
];

const DENTAL_KEYWORDS = [
  "dental", "dentist", "dentistry", "orthodont", "smile", "tooth", "teeth",
  "oral", "perio", "endo", "prostho", "implant", "braces", "cosmetic dent",
  "family dent", "pediatric dent", "dds", "dmd",
];

function validateScrapedData(data) {
  const checks = {};
  let overallConfidence = "high";

  // ── Validate practice name ──
  const name = data.practiceName;
  if (!name) {
    checks.practiceName = { status: "missing", note: "No practice name detected" };
    overallConfidence = "low";
  } else if (BAD_NAME_PATTERNS.some(p => p.test(name))) {
    checks.practiceName = { status: "rejected", note: `Extracted name "${name}" looks invalid, cleared` };
    data.practiceName = "";
    overallConfidence = "low";
  } else {
    const nameLower = name.toLowerCase();
    const hasDentalWord = DENTAL_KEYWORDS.some(kw => nameLower.includes(kw));
    const appearsInText = data.visibleText.toLowerCase().includes(nameLower);
    if (hasDentalWord && appearsInText) {
      checks.practiceName = { status: "verified", note: "Name contains dental keyword and appears in page content" };
    } else if (appearsInText) {
      checks.practiceName = { status: "likely_valid", note: "Name appears in page content but has no dental keyword" };
    } else if (hasDentalWord) {
      checks.practiceName = { status: "likely_valid", note: "Name contains dental keyword but not found in visible text" };
    } else {
      checks.practiceName = { status: "unverified", note: "Name does not contain dental keywords and was not found in page body text" };
      if (overallConfidence === "high") overallConfidence = "medium";
    }
  }

  // ── Validate state ──
  const st = (data.state || "").toUpperCase().trim();
  if (!st) {
    checks.state = { status: "missing", note: "No state detected" };
    if (overallConfidence === "high") overallConfidence = "medium";
  } else if (!VALID_STATES.has(st)) {
    checks.state = { status: "rejected", note: `"${data.state}" is not a valid US/CA state abbreviation, cleared` };
    data.state = "";
    overallConfidence = "low";
  } else {
    checks.state = { status: "verified", note: `Valid state: ${st}` };
  }

  // ── Validate city appears in visible text ──
  const cityVal = data.city;
  if (!cityVal) {
    checks.city = { status: "missing", note: "No city detected" };
    if (overallConfidence === "high") overallConfidence = "medium";
  } else if (data.visibleText.toLowerCase().includes(cityVal.toLowerCase())) {
    checks.city = { status: "verified", note: "City name found in page content" };
  } else {
    checks.city = { status: "unverified", note: `City "${cityVal}" was NOT found in visible page text` };
    if (overallConfidence === "high") overallConfidence = "medium";
  }

  // ── Cross-check phone area code vs state ──
  const phoneDigits = (data.phone || "").replace(/\D/g, "");
  if (phoneDigits.length >= 10) {
    const areaCode = phoneDigits.slice(0, 3);
    const phoneState = AREA_CODE_STATES[areaCode];
    if (phoneState && st) {
      if (phoneState === st) {
        checks.phone = { status: "verified", note: `Area code ${areaCode} matches state ${st}` };
      } else {
        checks.phone = { status: "mismatch", note: `Area code ${areaCode} maps to ${phoneState}, but state is ${st}` };
        if (overallConfidence === "high") overallConfidence = "medium";
      }
    } else if (phoneState && !st) {
      checks.phone = { status: "inferred", note: `Area code ${areaCode} suggests state: ${phoneState}` };
      data.phoneInferredState = phoneState;
    } else {
      checks.phone = { status: "present", note: "Phone found but area code not in lookup table" };
    }
  } else if (data.phone) {
    checks.phone = { status: "partial", note: "Phone found but doesn't look like a full 10-digit number" };
  } else {
    checks.phone = { status: "missing", note: "No phone number detected" };
  }

  // ── Validate postal code format ──
  if (data.postalCode) {
    const zip = data.postalCode.replace(/\s/g, "");
    if (/^\d{5}(-\d{4})?$/.test(zip) || /^[A-Za-z]\d[A-Za-z]\d[A-Za-z]\d$/.test(zip)) {
      checks.postalCode = { status: "verified", note: "Valid postal code format" };
    } else {
      checks.postalCode = { status: "invalid_format", note: `"${data.postalCode}" doesn't match US/CA postal code format` };
    }
  }

  data.validation = {
    confidence: overallConfidence,
    checks,
  };

  return data;
}

// ════════════════════════════════════════════════════════════════
// ── Build the audit prompt with real scraped + verified data ──
// ════════════════════════════════════════════════════════════════

function buildAuditPrompt(practiceUrl, site, placeData, competitors) {
  let siteContext = "";

  if (site.scraped) {
    siteContext = `
IMPORTANT — REAL DATA SCRAPED FROM THE WEBSITE (use this, do NOT guess):
- Website URL: ${site.finalUrl}
- Practice Name (from site): ${site.practiceName || "Could not detect — use domain name"}
- Street Address: ${site.streetAddress || "Not found on website"}
- City: ${site.city || "Not found on website"}
- State: ${site.state || "Not found on website"}
- Postal Code: ${site.postalCode || "Not found on website"}
- Phone: ${site.phone || "Not found on website"}
- Page Title: ${site.title}
- Meta Description: ${site.metaDescription}
- SSL (HTTPS): ${site.hasSSL ? "Yes" : "No"}
- Has Schema Markup: ${site.hasSchema ? "Yes — types found: " + site.schemaTypes.join(", ") : "No"}
- Has FAQ Schema: ${site.hasFaqSchema ? "Yes" : "No"}
- Has AI Discoverability File: ${site.hasLlmsTxt ? "Yes" : "No"}
- Mobile Viewport Tag: ${site.hasViewport ? "Yes" : "No"}
- Robots.txt: ${site.robotsTxt ? "Found — " + site.robotsTxt.slice(0, 200) : "Not found or empty"}

Visible page content (first 3000 chars):
"""
${site.visibleText}
"""

DATA VALIDATION RESULTS (sanity checks on the scraped data):
Confidence level: ${site.validation?.confidence || "unknown"}
${site.validation?.checks ? Object.entries(site.validation.checks).map(([field, check]) =>
  `- ${field}: ${check.status} — ${check.note}`).join("\n") : "No validation data available"}
${site.phoneInferredState ? `- Phone area code suggests state: ${site.phoneInferredState}` : ""}`;
  } else {
    siteContext = `
WARNING: Could not reach the website at ${practiceUrl}. The site may be down or blocking requests.
Generate the report based on what you know about this domain, but clearly note in the executive summary that the website could not be reached for live analysis.`;
  }

  // ── Add VERIFIED Google data ──
  let googleContext = "";
  if (placeData) {
    googleContext = `

═══ VERIFIED GOOGLE BUSINESS DATA (use these EXACT numbers, do NOT modify them) ═══
Match confidence: ${placeData.matchConfidence} (domain match: ${placeData.domainMatch}, name match: ${placeData.nameMatch})
- Business Name (Google): ${placeData.name}
- Address (Google): ${placeData.address}
- City (Google): ${placeData.city}
- State (Google): ${placeData.state}
- Phone (Google): ${placeData.phone}
- Google Rating: ${placeData.rating} stars
- Google Review Count: ${placeData.reviewCount} reviews
- Business Status: ${placeData.businessStatus}
- Website (Google): ${placeData.website}

${placeData.isMultiLocation ? `
MULTI-LOCATION PRACTICE: This practice has ${placeData.locations.length} Google Business listings:
${placeData.locations.map((l, i) => `  ${i + 1}. ${l.name} — ${l.city || l.address} — ${l.rating} stars, ${l.reviewCount} reviews`).join("\n")}
Combined total: ${placeData.combinedReviewCount} reviews, ${placeData.combinedRating} avg rating

CRITICAL: For the reviews category, you MUST use the COMBINED totals:
- count: ${placeData.combinedReviewCount}
- rating: ${placeData.combinedRating}` : `
CRITICAL: For the reviews category, you MUST use:
- count: ${placeData.reviewCount}
- rating: ${placeData.rating}`}
These are REAL numbers from Google. Do NOT change them. Do NOT make up different numbers.
Use the Google-verified city and state for the report location fields.`;
  } else {
    googleContext = `

NOTE: Google Places data was not available for this practice. For the reviews section,
make your best estimate based on the website content, but clearly indicate these are estimates.
Be conservative — do NOT guess high review counts without evidence.`;
  }

  // ── Add verified competitor data ──
  let competitorContext = "";
  if (competitors.length > 0) {
    competitorContext = `

═══ VERIFIED LOCAL COMPETITORS (real Google data — use the top competitor for the report) ═══
${competitors.slice(0, 5).map((c, i) =>
  `${i + 1}. ${c.name} — ${c.rating} stars, ${c.reviewCount} reviews (${c.address})`
).join("\n")}

CRITICAL: For competitor_name and competitor_reviews, use the #1 competitor above:
- competitor_name: "${competitors[0].name}"
- competitor_reviews: ${competitors[0].reviewCount}
Do NOT make up competitor names or review counts.`;
  }

  return `You are PracticeRank's expert dental practice auditor. Generate an audit report for: "${practiceUrl}"

${siteContext}
${googleContext}
${competitorContext}

CRITICAL: You MUST use the practice name, city, and state from the verified Google data above (if available). For review count and rating, use the EXACT Google-verified numbers. For competitor data, use the EXACT competitor names and review counts provided. DO NOT fabricate or estimate any of these values — we have real data.

You MUST analyze the practice across these 7 categories and generate specific, actionable findings. Be realistic — most practices score poorly on AI readiness and Maps optimization. Do NOT inflate scores.

CRITICAL TONE RULES — READ CAREFULLY:
- Your job is to DIAGNOSE problems and show their IMPACT on patient inquiries — NOT to prescribe exact fixes.
- For findings: describe WHAT is wrong/missing and WHY it costs them patients. Do NOT tell them exactly how to fix it.
- BAD finding: "Add FAQPage JSON-LD schema markup to each service page to get cited by AI search engines"
- GOOD finding: "No structured FAQ data detected — AI search engines like ChatGPT and Gemini cannot extract service information from this site, making it invisible to the 40%+ of patients who now use AI to find dentists"
- BAD finding: "Create an llms.txt file at the site root following the llmstxt.org specification"
- GOOD finding: "Missing AI discoverability file — this site has no machine-readable summary for AI assistants, so ChatGPT, Gemini, and Perplexity have no structured way to learn about or recommend this practice"
- For priority_actions: frame as OUTCOMES they need ("Get visible in AI search results", "Fix Google Maps listing gaps") not HOW-TO instructions. The description should emphasize the patient/revenue impact and what's at stake — not the technical steps.
- Never mention specific technical implementations like "JSON-LD", "schema markup code", "llms.txt file format", "robots.txt directives", or specific tools/APIs. Use plain language: "structured data", "AI-readable content", "search engine signals", "directory presence".
- The goal: the practice owner reads this and thinks "I'm losing patients and I need expert help to fix this" — NOT "I can Google these fixes myself or hand this to another agency."

SCORING CATEGORIES (each 0-100):
1. OVERALL SCORE — weighted average of all categories
2. GOOGLE BUSINESS PROFILE — completeness, photos, posts frequency, Q&A, categories, hours accuracy
3. AI SEARCH READINESS — whether AI assistants (ChatGPT, Gemini, Grok, Claude, Perplexity) can find and recommend this practice
4. REVIEW STRENGTH — total review count, average rating, review velocity (new reviews/month), response rate, sentiment
5. LOCAL SEO — directory presence, Apple Maps, citation consistency, neighborhood visibility, local authority signals
6. CONTENT & ON-PAGE SEO — content depth, blog presence, keyword targeting, internal structure, meta optimization
7. TECHNICAL SEO — page speed, mobile-friendliness, SSL, sitemap, Core Web Vitals

For each category, provide:
- A score (0-100)
- A status: "critical" (0-30), "needs_work" (31-60), "good" (61-80), "excellent" (81-100)
- 2-3 specific findings — describe the PROBLEM and its PATIENT IMPACT, never the technical fix. Reference real data from the scrape where possible.

Also generate:
- Executive summary (2-3 sentences, lead with patient inquiry impact, create urgency)
- The practice name, city, and state — USE THE VERIFIED GOOGLE VALUES if available, otherwise use scraped values
- Top competitor name and their review count — USE THE VERIFIED COMPETITOR DATA provided above
- 5 priority recommendations ranked by patient inquiry impact (each with title, outcome-focused description emphasizing patients lost, impact level, and estimated new patients/month)
- AI platform visibility: for each of ChatGPT, Gemini, Grok, Claude, Perplexity — would they likely recommend this practice? (yes/no/partial + 1 sentence explaining what patients see when they ask about dentists in this area)
- Growth projections at 3, 6, and 12 months (estimated new patient inquiries/month)
- A "money left on the table" estimate — annual revenue being lost to competitors

Respond ONLY with valid JSON (no markdown, no code fences, no explanation):
{
  "practice_name": "<string>",
  "city": "<string>",
  "state": "<string>",
  "overall_score": <int>,
  "grade": "<A through F>",
  "executive_summary": "<string — 2-3 sentences, lead with patient impact>",
  "categories": {
    "gbp": { "score": <int>, "status": "<string>", "findings": ["<string>", "<string>"] },
    "ai_readiness": { "score": <int>, "status": "<string>", "findings": ["<string>", "<string>", "<string>"] },
    "reviews": { "score": <int>, "status": "<string>", "findings": ["<string>", "<string>"], "count": <int>, "rating": <number>, "competitor_name": "<string>", "competitor_reviews": <int> },
    "local_seo": { "score": <int>, "status": "<string>", "findings": ["<string>", "<string>"] },
    "content": { "score": <int>, "status": "<string>", "findings": ["<string>", "<string>"] },
    "technical": { "score": <int>, "status": "<string>", "findings": ["<string>", "<string>"] }
  },
  "ai_visibility": {
    "chatgpt": { "visible": "<yes|no|partial>", "reason": "<string>" },
    "gemini": { "visible": "<yes|no|partial>", "reason": "<string>" },
    "grok": { "visible": "<yes|no|partial>", "reason": "<string>" },
    "claude": { "visible": "<yes|no|partial>", "reason": "<string>" },
    "perplexity": { "visible": "<yes|no|partial>", "reason": "<string>" }
  },
  "priority_actions": [
    { "title": "<string>", "description": "<string>", "impact": "<high|medium>", "est_patients_mo": "<string like +5-8>" },
    { "title": "<string>", "description": "<string>", "impact": "<high|medium>", "est_patients_mo": "<string>" },
    { "title": "<string>", "description": "<string>", "impact": "<high|medium>", "est_patients_mo": "<string>" },
    { "title": "<string>", "description": "<string>", "impact": "<high|medium>", "est_patients_mo": "<string>" },
    { "title": "<string>", "description": "<string>", "impact": "<high|medium>", "est_patients_mo": "<string>" }
  ],
  "projections": {
    "current_inquiries_mo": "<string like 3-5>",
    "month_3": "<string like +8-12>",
    "month_6": "<string like +15-20>",
    "month_12": "<string like +25-35>"
  },
  "revenue_lost_annually": "<string like $180,000-$360,000>",
  "patient_lifetime_value": "<string like $800-$2,500>"
}`;
}

// ════════════════════════════════════════════════════════════════
// ── Input Validation & Security ──
// ════════════════════════════════════════════════════════════════

const BLOCKED_HOSTS = [
  /^localhost$/i, /^127\./, /^10\./, /^172\.(1[6-9]|2\d|3[01])\./, /^192\.168\./,
  /^0\./, /^169\.254\./, /^::1$/, /^fc00:/i, /^fe80:/i, /^fd/i,
  /\.local$/i, /\.internal$/i, /\.corp$/i, /\.lan$/i,
];

function validatePracticeUrl(input) {
  // Strip protocol if provided
  const domain = input.replace(/^https?:\/\//, "").replace(/\/+$/, "").split("/")[0].split("?")[0];

  if (!domain || domain.length < 4) return "Please enter a valid website URL.";
  if (domain.length > 253) return "URL is too long.";

  // Must have at least one dot (a real domain)
  if (!domain.includes(".")) return "Please enter a full domain (e.g. example.com).";

  // Block private/internal IPs and hostnames (SSRF protection)
  const hostname = domain.split(":")[0];
  for (const pattern of BLOCKED_HOSTS) {
    if (pattern.test(hostname)) return "Internal or private URLs are not allowed.";
  }

  // Block IP addresses entirely — we only accept domain names
  if (/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$/.test(domain)) {
    return "Please enter a domain name, not an IP address.";
  }

  // Basic domain format check
  if (!/^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$/.test(hostname)) {
    return "Please enter a valid domain name (e.g. example.com).";
  }

  return null; // valid
}

function isValidEmail(email) {
  if (!email || email.length > 254) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email);
}

function corsHeaders(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function classifyUserAgent(ua) {
  if (!ua) return "other";
  const lower = ua.toLowerCase();
  if (lower.includes("gptbot") || lower.includes("chatgpt") || lower.includes("openai")) return "chatgpt";
  if (lower.includes("claudebot") || lower.includes("anthropic")) return "claude";
  if (lower.includes("perplexitybot") || lower.includes("perplexity")) return "perplexity";
  if (lower.includes("googlebot") || lower.includes("google-extended") || lower.includes("gemini")) return "google";
  if (lower.includes("bingbot") || lower.includes("bingpreview")) return "bing";
  if (lower.includes("applebot")) return "apple";
  if (lower.includes("bot") || lower.includes("crawler") || lower.includes("spider")) return "other_bot";
  return "other";
}

// ── Exports for testing ──
export {
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
};
