import { expect, test } from "@playwright/test";

const device = {
  id: "device-regression-1",
  slug: null,
  title: "Prêt Flash Carburant Bpifrance",
  organism: "Bpifrance",
  country: "France",
  region: null,
  zone: null,
  device_type: "pret",
  aid_nature: null,
  sectors: ["transport"],
  beneficiaries: ["pme", "eti"],
  short_description: "Soutenir rapidement la trésorerie des petites entreprises exposées à la hausse des coûts du carburant.",
  full_description:
    "## Présentation\nLe prêt Flash Carburant soutient rapidement la trésorerie des entreprises les plus exposées à la hausse des coûts du carburant.\n\n## Montants & Financement\n- Montant compris entre 5 000 € et 50 000 €\n- Différé d'amortissement de 12 mois",
  eligibility_criteria:
    "## Critères d'éligibilité\n- Exister depuis plus de 3 ans\n- Ne pas faire l'objet d'une procédure collective",
  eligible_expenses:
    "## Dépenses concernées\n- Besoins de trésorerie liés à l'activité\n- Charges d'exploitation liées au carburant",
  specific_conditions: null,
  required_documents: "## Pièces et documents utiles\n- Derniers bilans\n- Attestation de l'expert-comptable",
  amount_min: 5000,
  amount_max: 50000,
  currency: "EUR",
  funding_rate: null,
  open_date: "2026-04-13",
  close_date: "2026-09-30",
  is_recurring: false,
  status: "open",
  source_url: "https://example.org/bpifrance/pret-flash-carburant",
  source_id: "source-1",
  language: "fr",
  keywords: ["trésorerie", "carburant"],
  tags: [],
  auto_summary: "Fiche enrichie automatiquement depuis la source officielle.",
  confidence_score: 90,
  completeness_score: 88,
  relevance_score: 91,
  validation_status: "approved",
  first_seen_at: "2026-04-08T00:00:00+00:00",
  last_verified_at: "2026-04-09T10:00:00+00:00",
  created_at: "2026-04-08T00:00:00+00:00",
  updated_at: "2026-04-09T10:00:00+00:00",
};

test("affiche les sections enrichies et la source de vérité sur la fiche dispositif", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("finveille_token", "fake-token");
  });

  await page.route("**/api/v1/devices/device-regression-1", async (route) => {
    await route.fulfill({ json: device });
  });

  await page.route("**/api/v1/devices/device-regression-1/history", async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.route("**/api/v1/devices/?*", async (route) => {
    await route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 4, pages: 0 } });
  });

  await page.goto("/devices/device-regression-1");

  await expect(page.getByRole("heading", { name: /Prêt Flash Carburant Bpifrance/i })).toBeVisible();
  await expect(page.getByText("Appel en cours")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Présentation du dispositif/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Conditions d'attribution/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Pour quel projet \?/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Informations pratiques/i })).toBeVisible();
  await expect(page.getByText("Montant compris entre 5 000 € et 50 000 €")).toBeVisible();
  await expect(page.getByText("Exister depuis plus de 3 ans")).toBeVisible();
  await expect(page.getByText("Besoins de trésorerie liés à l'activité")).toBeVisible();
  await expect(page.getByText("Texte enrichi automatiquement")).toBeVisible();
  await expect(page.getByText("Dernière vérification")).toBeVisible();
  await expect(page.getByText("Certaines conditions doivent être confirmées sur le site officiel.")).toBeVisible();
});
