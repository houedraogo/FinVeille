import { test, expect } from "@playwright/test";

const matchState = {
  fileName: "pitch.txt",
  fileSize: 1024,
  error: null,
  step: "done",
  result: {
    total: 1,
    profile: {
      sectors: ["finance"],
      countries: ["France"],
      types: ["investissement"],
      amount_min: null,
      amount_max: null,
      keywords: ["fintech", "paiement"],
      summary: "Startup fintech de paiement",
    },
    matches: [
      {
        id: "device-1",
        title: "Fonds seed fintech",
        description_courte: "Investissement seed pour fintech",
        device_type: "investissement",
        country: "France",
        sectors: ["finance"],
        amount_min: null,
        amount_max: null,
        source_url: "https://example.org/device-1",
        close_date: null,
        match_score: 88,
      },
    ],
  },
};

test("conserve les resultats de matching apres retour depuis la fiche dispositif", async ({ page }) => {
  await page.addInitScript((state) => {
    localStorage.setItem("finveille_token", "fake-token");
    localStorage.setItem("finveille_match_state", JSON.stringify(state));
  }, matchState);

  await page.route("**/api/v1/devices/device-1", async (route) => {
    await route.fulfill({
      json: {
        id: "device-1",
        slug: null,
        title: "Fonds seed fintech",
        organism: "Org A",
        country: "France",
        region: null,
        zone: null,
        device_type: "investissement",
        aid_nature: null,
        sectors: ["finance"],
        beneficiaries: ["startup"],
        short_description: "Investissement seed pour fintech",
        full_description: null,
        eligibility_criteria: null,
        eligible_expenses: null,
        specific_conditions: null,
        required_documents: null,
        amount_min: null,
        amount_max: null,
        currency: "EUR",
        funding_rate: null,
        open_date: null,
        close_date: null,
        is_recurring: false,
        status: "open",
        source_url: "https://example.org/device-1",
        source_id: null,
        language: "fr",
        keywords: [],
        tags: [],
        auto_summary: null,
        confidence_score: 88,
        completeness_score: 80,
        relevance_score: 85,
        validation_status: "approved",
        first_seen_at: "2026-01-01T00:00:00+00:00",
        last_verified_at: "2026-01-02T00:00:00+00:00",
        created_at: "2026-01-01T00:00:00+00:00",
        updated_at: "2026-01-02T00:00:00+00:00",
      },
    });
  });
  await page.route("**/api/v1/devices/device-1/history", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto("/match");
  await expect(page.getByText("Fonds seed fintech")).toBeVisible();

  await page.getByRole("link", { name: /Voir la fiche/i }).click();
  await expect(page).toHaveURL(/\/devices\/device-1\?from=match/);

  await page.getByRole("button", { name: /Retour/i }).click();
  await expect(page).toHaveURL(/\/match/);
  await expect(page.getByText("Fonds seed fintech")).toBeVisible();
});
