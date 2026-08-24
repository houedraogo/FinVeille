import { test, expect } from "@playwright/test";

test("ouvre la fiche source puis revient a la liste privee", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("kafundo_token", "fake-token");
  });

  await page.route("**/api/v1/sources*", async (route) => {
    const url = route.request().url();

    if (url.includes("/api/v1/sources") && url.includes("category=private")) {
      await route.fulfill({
        json: [
          {
            id: "source-1",
            name: "Partech Africa - VC tech Afrique",
            organism: "Partech Africa",
            country: "Afrique",
            region: null,
            source_type: "fonds_prive",
            category: "private",
            level: 1,
            url: "https://partechpartners.com/africa",
            collection_mode: "manual",
            check_frequency: "monthly",
            reliability: 3,
            is_active: false,
            last_checked_at: null,
            last_success_at: null,
            consecutive_errors: 0,
            config: {},
            notes: "Source de reference",
            last_error: null,
            health_score: 62,
            health_label: "fragile",
            created_at: "2026-01-01T00:00:00+00:00",
          },
        ],
      });
      return;
    }

    if (url.endsWith("/api/v1/sources/source-1")) {
      await route.fulfill({
        json: {
          id: "source-1",
          name: "Partech Africa - VC tech Afrique",
          organism: "Partech Africa",
          country: "Afrique",
          region: null,
          source_type: "fonds_prive",
          category: "private",
          level: 1,
          url: "https://partechpartners.com/africa",
          collection_mode: "manual",
          check_frequency: "monthly",
          reliability: 3,
          is_active: false,
          last_checked_at: null,
          last_success_at: null,
          consecutive_errors: 0,
          config: {},
          notes: "Source de reference",
          last_error: null,
          health_score: 62,
          health_label: "fragile",
          created_at: "2026-01-01T00:00:00+00:00",
        },
      });
      return;
    }

    if (url.endsWith("/api/v1/sources/source-1/logs")) {
      await route.fulfill({ json: [] });
      return;
    }

    await route.continue();
  });

  await page.goto("/sources/private");
  await expect(page.getByText("Sources referentielles / manuelles")).toBeVisible();
  await page.getByRole("link", { name: /Partech Africa - VC tech Afrique/i }).click();

  await expect(page).toHaveURL(/\/sources\/source-1/);
  await expect(page.getByText("Informations source")).toBeVisible();

  await page.getByRole("button", { name: /Retour aux sources/i }).click();
  await expect(page).toHaveURL(/\/sources\/private/);
});
