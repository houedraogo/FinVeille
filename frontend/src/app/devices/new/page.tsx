"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Save } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { devices } from "@/lib/api";
import { COUNTRIES, SECTORS } from "@/lib/constants";
import { DEVICE_TYPE_LABELS } from "@/lib/types";

const BENEFICIARIES = [
  "startup",
  "pme",
  "eti",
  "association",
  "collectivite",
  "porteur_projet",
  "agriculteur",
  "chercheur",
];

const BENEFICIARY_LABELS: Record<string, string> = {
  startup: "Startup",
  pme: "PME / TPE",
  eti: "ETI",
  association: "Association / ONG",
  collectivite: "Collectivité",
  porteur_projet: "Porteur de projet",
  agriculteur: "Agriculteur",
  chercheur: "Chercheur / Labo",
};

function NewDeviceFormPage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    title: "",
    organism: "",
    country: "France",
    device_type: "subvention",
    status: "open",
    source_url: "",
    short_description: "",
    eligibility_criteria: "",
    amount_min: "",
    amount_max: "",
    currency: "EUR",
    funding_rate: "",
    open_date: "",
    close_date: "",
    sectors: [] as string[],
    beneficiaries: [] as string[],
    is_recurring: false,
  });

  const toggleValue = (values: string[], value: string) =>
    values.includes(value) ? values.filter((item) => item !== value) : [...values, value];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim() || !form.organism.trim() || !form.source_url.trim()) {
      setError("Titre, organisme et URL source sont obligatoires.");
      return;
    }

    setSaving(true);
    setError("");

    try {
      const payload = {
        ...form,
        amount_min: form.amount_min ? parseFloat(form.amount_min) : undefined,
        amount_max: form.amount_max ? parseFloat(form.amount_max) : undefined,
        funding_rate: form.funding_rate ? parseFloat(form.funding_rate) : undefined,
        open_date: form.open_date || undefined,
        close_date: form.close_date || undefined,
        sectors: form.sectors.length ? form.sectors : ["transversal"],
      };
      const created = await devices.create(payload as any);
      router.push(`/devices/${(created as { id: string }).id}`);
    } catch (e: any) {
      setError(e.message || "Erreur lors de la création");
      setSaving(false);
    }
  };

  const Field = ({
    label,
    required,
    children,
  }: {
    label: string;
    required?: boolean;
    children: React.ReactNode;
  }) => (
    <div>
      <label className="label">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
      {children}
    </div>
  );

  return (
    <AppLayout>
      <div className="max-w-3xl">
        <div className="mb-6 flex items-center gap-4">
          <button onClick={() => router.back()} className="btn-secondary text-xs">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Ajouter une opportunité</h1>
            <p className="text-sm text-gray-500">Saisie manuelle d'une opportunité de financement</p>
          </div>
        </div>

        {error && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="card p-5">
            <h2 className="mb-4 text-sm font-semibold text-gray-700">Informations principales</h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="md:col-span-2">
                <Field label="Titre de l'opportunité" required>
                  <input
                    className="input"
                    value={form.title}
                    onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                    placeholder="Ex : Appel à projets Transition Énergétique 2026"
                  />
                </Field>
              </div>
              <Field label="Organisme / Émetteur" required>
                <input className="input" value={form.organism} onChange={(e) => setForm((prev) => ({ ...prev, organism: e.target.value }))} />
              </Field>
              <Field label="Pays">
                <select className="input" value={form.country} onChange={(e) => setForm((prev) => ({ ...prev, country: e.target.value }))}>
                  {COUNTRIES.map((country) => (
                    <option key={country} value={country}>
                      {country}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Type de financement">
                <select className="input" value={form.device_type} onChange={(e) => setForm((prev) => ({ ...prev, device_type: e.target.value }))}>
                  {Object.entries(DEVICE_TYPE_LABELS).map(([key, value]) => (
                    <option key={key} value={key}>
                      {value}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Statut">
                <select className="input" value={form.status} onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}>
                  <option value="open">Ouvert</option>
                  <option value="recurring">Récurrent</option>
                  <option value="closed">Fermé</option>
                  <option value="standby">En veille</option>
                </select>
              </Field>
              <div className="md:col-span-2">
                <Field label="URL source" required>
                  <input
                    type="url"
                    className="input"
                    value={form.source_url}
                    onChange={(e) => setForm((prev) => ({ ...prev, source_url: e.target.value }))}
                    placeholder="https://..."
                  />
                </Field>
              </div>
            </div>
          </div>

          <div className="card p-5">
            <h2 className="mb-4 text-sm font-semibold text-gray-700">Description</h2>
            <div className="space-y-4">
              <Field label="Résumé">
                <textarea className="input min-h-[96px]" value={form.short_description} onChange={(e) => setForm((prev) => ({ ...prev, short_description: e.target.value }))} />
              </Field>
              <Field label="Critères d'éligibilité">
                <textarea className="input min-h-[96px]" value={form.eligibility_criteria} onChange={(e) => setForm((prev) => ({ ...prev, eligibility_criteria: e.target.value }))} />
              </Field>
            </div>
          </div>

          <div className="card p-5">
            <h2 className="mb-4 text-sm font-semibold text-gray-700">Montants & dates</h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <Field label="Montant min">
                <input className="input" type="number" value={form.amount_min} onChange={(e) => setForm((prev) => ({ ...prev, amount_min: e.target.value }))} />
              </Field>
              <Field label="Montant max">
                <input className="input" type="number" value={form.amount_max} onChange={(e) => setForm((prev) => ({ ...prev, amount_max: e.target.value }))} />
              </Field>
              <Field label="Devise">
                <select className="input" value={form.currency} onChange={(e) => setForm((prev) => ({ ...prev, currency: e.target.value }))}>
                  <option value="EUR">EUR</option>
                  <option value="USD">USD</option>
                  <option value="XOF">XOF</option>
                  <option value="MAD">MAD</option>
                  <option value="TND">TND</option>
                </select>
              </Field>
              <Field label="Taux (%)">
                <input className="input" type="number" min="0" max="100" value={form.funding_rate} onChange={(e) => setForm((prev) => ({ ...prev, funding_rate: e.target.value }))} />
              </Field>
              <Field label="Date d'ouverture">
                <input className="input" type="date" value={form.open_date} onChange={(e) => setForm((prev) => ({ ...prev, open_date: e.target.value }))} />
              </Field>
              <Field label="Date de clôture">
                <input className="input" type="date" value={form.close_date} onChange={(e) => setForm((prev) => ({ ...prev, close_date: e.target.value }))} />
              </Field>
              <div className="col-span-2 flex items-center gap-2 pt-6">
                <input
                  id="recurring"
                  type="checkbox"
                  checked={form.is_recurring}
                  onChange={(e) => setForm((prev) => ({ ...prev, is_recurring: e.target.checked }))}
                  className="h-4 w-4 rounded border-gray-300 accent-primary-600"
                />
                <label htmlFor="recurring" className="text-sm text-gray-700">
                  Financement récurrent
                </label>
              </div>
            </div>
          </div>

          <div className="card p-5">
            <h2 className="mb-4 text-sm font-semibold text-gray-700">Ciblage</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Secteurs</label>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {SECTORS.map((sector) => (
                    <button
                      key={sector}
                      type="button"
                      onClick={() => setForm((prev) => ({ ...prev, sectors: toggleValue(prev.sectors, sector) }))}
                      className={`rounded-lg border px-2.5 py-1 text-xs capitalize transition-colors ${
                        form.sectors.includes(sector)
                          ? "border-primary-300 bg-primary-50 text-primary-700"
                          : "border-gray-200 bg-white text-gray-500 hover:bg-gray-50"
                      }`}
                    >
                      {sector}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="label">Bénéficiaires</label>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {BENEFICIARIES.map((beneficiary) => (
                    <button
                      key={beneficiary}
                      type="button"
                      onClick={() => setForm((prev) => ({ ...prev, beneficiaries: toggleValue(prev.beneficiaries, beneficiary) }))}
                      className={`rounded-lg border px-2.5 py-1 text-xs transition-colors ${
                        form.beneficiaries.includes(beneficiary)
                          ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                          : "border-gray-200 bg-white text-gray-500 hover:bg-gray-50"
                      }`}
                    >
                      {BENEFICIARY_LABELS[beneficiary]}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2">
            <button type="button" onClick={() => router.back()} className="btn-secondary text-xs">
              Annuler
            </button>
            <button type="submit" disabled={saving} className="btn-primary text-xs">
              {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
              {saving ? "Enregistrement..." : "Créer l'opportunité"}
            </button>
          </div>
        </form>
      </div>
    </AppLayout>
  );
}

export default function NewDevicePage() {
  return (
    <RoleGate
      allow={["admin", "editor"]}
      title="Création réservée à l'équipe"
      message="La création manuelle d'opportunités est réservée aux profils équipe et super admin."
      backHref="/devices"
    >
      <NewDeviceFormPage />
    </RoleGate>
  );
}
