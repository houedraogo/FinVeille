"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Save } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { devices } from "@/lib/api";
import { COUNTRIES, SECTORS } from "@/lib/constants";
import { DEVICE_TYPE_LABELS, type Device } from "@/lib/types";

const BENEFICIARIES = [
  "startup",
  "pme",
  "tpe",
  "entreprise",
  "association",
  "ong",
  "collectivite",
  "porteur projet",
  "agriculteur",
  "chercheur",
  "femme entrepreneure",
  "jeune entrepreneur",
  "cooperative",
];

const BENEFICIARY_LABELS: Record<string, string> = {
  startup: "Startup",
  pme: "PME",
  tpe: "TPE",
  entreprise: "Entreprise",
  association: "Association",
  ong: "ONG",
  collectivite: "Collectivite",
  "porteur projet": "Porteur de projet",
  agriculteur: "Agriculteur",
  chercheur: "Chercheur / labo",
  "femme entrepreneure": "Femme entrepreneure",
  "jeune entrepreneur": "Jeune entrepreneur",
  cooperative: "Cooperative",
};

const STATUSES = [
  { value: "open", label: "Ouvert" },
  { value: "recurring", label: "Permanent / recurrent" },
  { value: "standby", label: "Date non communiquee" },
  { value: "closed", label: "Ferme" },
  { value: "expired", label: "Expire" },
];

const VALIDATION_STATUSES = [
  { value: "auto_published", label: "Publie automatiquement" },
  { value: "approved", label: "Approuve" },
  { value: "validated", label: "Valide" },
  { value: "pending_review", label: "A verifier" },
  { value: "rejected", label: "Masque / rejete" },
];

const USER_QUALITY_DECISIONS = [
  { value: "", label: "Recalcul automatique" },
  { value: "publish", label: "Publier" },
  { value: "publish_with_caution", label: "Publier avec prudence" },
  { value: "admin_only", label: "Admin uniquement" },
  { value: "reject", label: "Rejeter" },
];

type FormState = {
  title: string;
  organism: string;
  country: string;
  region: string;
  zone: string;
  device_type: string;
  aid_nature: string;
  status: string;
  validation_status: string;
  user_quality_decision: string;
  source_url: string;
  short_description: string;
  full_description: string;
  eligibility_criteria: string;
  funding_details: string;
  specific_conditions: string;
  required_documents: string;
  amount_min: string;
  amount_max: string;
  currency: string;
  funding_rate: string;
  open_date: string;
  close_date: string;
  is_recurring: boolean;
  recurrence_notes: string;
  sectors: string[];
  beneficiaries: string[];
  keywords: string;
  tags: string;
};

function toDateInput(value?: string | null) {
  return value ? value.slice(0, 10) : "";
}

function toNumberInput(value?: number | string | null) {
  if (value === null || value === undefined) return "";
  return String(value);
}

function splitCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function getEditableSection(device: Device, keys: string[]) {
  const sections =
    device.ai_rewrite_status === "done" && Array.isArray(device.ai_rewritten_sections_json)
      ? device.ai_rewritten_sections_json
      : Array.isArray(device.content_sections_json)
        ? device.content_sections_json
        : [];

  for (const key of keys) {
    const content = sections.find((section) => section?.key === key)?.content?.trim();
    if (content) return content;
  }

  return "";
}

function buildForm(device: Device): FormState {
  return {
    title: device.title || "",
    organism: device.organism || "",
    country: device.country || "France",
    region: device.region || "",
    zone: (device as any).zone || "",
    device_type: device.device_type || "subvention",
    aid_nature: device.aid_nature || "",
    status: device.status || "open",
    validation_status: device.validation_status || "pending_review",
    user_quality_decision: device.user_quality_decision || "",
    source_url: device.source_url || "",
    short_description: getEditableSection(device, ["why_this_opportunity"]) || device.short_description || "",
    full_description: getEditableSection(device, ["presentation"]) || device.full_description || "",
    eligibility_criteria: getEditableSection(device, ["eligibility", "audience"]) || device.eligibility_criteria || "",
    funding_details: getEditableSection(device, ["funding", "benefits"]) || device.funding_details || "",
    specific_conditions: getEditableSection(device, ["checks"]) || device.specific_conditions || "",
    required_documents: getEditableSection(device, ["application"]) || device.required_documents || "",
    amount_min: toNumberInput(device.amount_min),
    amount_max: toNumberInput(device.amount_max),
    currency: device.currency || "EUR",
    funding_rate: toNumberInput(device.funding_rate),
    open_date: toDateInput(device.open_date),
    close_date: toDateInput(device.close_date),
    is_recurring: Boolean(device.is_recurring),
    recurrence_notes: (device as any).recurrence_notes || "",
    sectors: device.sectors || [],
    beneficiaries: device.beneficiaries || [],
    keywords: (device.keywords || []).join(", "),
    tags: (device.tags || []).join(", "),
  };
}

function Field({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div>
      <label className="label">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
      {children}
    </div>
  );
}

function TogglePill({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border px-2.5 py-1 text-xs transition-colors ${
        active
          ? "border-primary-300 bg-primary-50 text-primary-700"
          : "border-gray-200 bg-white text-gray-500 hover:bg-gray-50"
      }`}
    >
      {children}
    </button>
  );
}

function EditDeviceFormPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [form, setForm] = useState<FormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    devices
      .get(id)
      .then((device) => setForm(buildForm(device as Device)))
      .catch((e: any) => setError(e.message || "Impossible de charger la fiche."))
      .finally(() => setLoading(false));
  }, [id]);

  const setValue = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const toggleArrayValue = (key: "sectors" | "beneficiaries", value: string) => {
    setForm((prev) => {
      if (!prev) return prev;
      const values = prev[key];
      return {
        ...prev,
        [key]: values.includes(value) ? values.filter((item) => item !== value) : [...values, value],
      };
    });
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form) return;
    if (!form.title.trim() || !form.organism.trim() || !form.source_url.trim()) {
      setError("Titre, organisme et URL source sont obligatoires.");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const payload = {
        title: form.title.trim(),
        organism: form.organism.trim(),
        country: form.country,
        region: form.region || undefined,
        zone: form.zone || undefined,
        device_type: form.device_type,
        aid_nature: form.aid_nature || undefined,
        status: form.status,
        validation_status: form.validation_status,
        user_quality_decision: form.user_quality_decision || undefined,
        source_url: form.source_url.trim(),
        short_description: form.short_description || undefined,
        full_description: form.full_description || undefined,
        eligibility_criteria: form.eligibility_criteria || undefined,
        funding_details: form.funding_details || undefined,
        specific_conditions: form.specific_conditions || undefined,
        required_documents: form.required_documents || undefined,
        amount_min: form.amount_min ? Number(form.amount_min) : undefined,
        amount_max: form.amount_max ? Number(form.amount_max) : undefined,
        currency: form.currency || "EUR",
        funding_rate: form.funding_rate ? Number(form.funding_rate) : undefined,
        open_date: form.open_date || undefined,
        close_date: form.close_date || undefined,
        is_recurring: form.is_recurring,
        recurrence_notes: form.recurrence_notes || undefined,
        sectors: form.sectors,
        beneficiaries: form.beneficiaries,
        keywords: splitCsv(form.keywords),
        tags: splitCsv(form.tags),
      };
      await devices.update(id, payload as any);
      router.push(`/devices/${id}?from=devices&updated=${Date.now()}`);
    } catch (e: any) {
      setError(e.message || "Impossible d'enregistrer les modifications.");
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="flex h-80 items-center justify-center text-slate-400">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Chargement de la fiche...
        </div>
      </AppLayout>
    );
  }

  if (!form) {
    return (
      <AppLayout>
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error || "Fiche introuvable."}
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="max-w-5xl">
        <div className="mb-6 flex items-center gap-4">
          <button onClick={() => router.back()} className="btn-secondary text-xs">
            <ArrowLeft className="h-4 w-4" />
            Retour
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Modifier la fiche</h1>
            <p className="text-sm text-gray-500">Correction manuelle avant publication ou amélioration utilisateur.</p>
          </div>
        </div>

        {error && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="card p-5">
            <h2 className="mb-4 text-sm font-semibold text-gray-700">Informations principales</h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="md:col-span-2">
                <Field label="Titre" required>
                  <input className="input" value={form.title} onChange={(e) => setValue("title", e.target.value)} />
                </Field>
              </div>
              <Field label="Organisme" required>
                <input className="input" value={form.organism} onChange={(e) => setValue("organism", e.target.value)} />
              </Field>
              <Field label="Pays">
                <select className="input" value={form.country} onChange={(e) => setValue("country", e.target.value)}>
                  {Array.from(new Set([form.country, ...COUNTRIES, "Bénin", "Burkina Faso", "Côte d'Ivoire", "Afrique", "Afrique de l'Ouest"].filter(Boolean))).map((country) => (
                    <option key={country} value={country}>
                      {country}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Région">
                <input className="input" value={form.region} onChange={(e) => setValue("region", e.target.value)} />
              </Field>
              <Field label="Zone">
                <input className="input" value={form.zone} onChange={(e) => setValue("zone", e.target.value)} />
              </Field>
              <Field label="Type">
                <select className="input" value={form.device_type} onChange={(e) => setValue("device_type", e.target.value)}>
                  {Object.entries(DEVICE_TYPE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Nature / précision">
                <input className="input" value={form.aid_nature} onChange={(e) => setValue("aid_nature", e.target.value)} />
              </Field>
              <Field label="Statut">
                <select className="input" value={form.status} onChange={(e) => setValue("status", e.target.value)}>
                  {STATUSES.map((status) => (
                    <option key={status.value} value={status.value}>
                      {status.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Validation admin">
                <select className="input" value={form.validation_status} onChange={(e) => setValue("validation_status", e.target.value)}>
                  {VALIDATION_STATUSES.map((status) => (
                    <option key={status.value} value={status.value}>
                      {status.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Visibilité utilisateur">
                <select className="input" value={form.user_quality_decision} onChange={(e) => setValue("user_quality_decision", e.target.value)}>
                  {USER_QUALITY_DECISIONS.map((decision) => (
                    <option key={decision.value} value={decision.value}>
                      {decision.label}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="md:col-span-2">
                <Field label="URL source officielle" required>
                  <input className="input" value={form.source_url} onChange={(e) => setValue("source_url", e.target.value)} />
                </Field>
              </div>
            </div>
          </div>

          <div className="card p-5">
            <h2 className="mb-4 text-sm font-semibold text-gray-700">Contenu utilisateur</h2>
            <div className="space-y-4">
              <Field label="Résumé court">
                <textarea className="input min-h-[110px]" value={form.short_description} onChange={(e) => setValue("short_description", e.target.value)} />
              </Field>
              <Field label="Présentation complète">
                <textarea className="input min-h-[180px]" value={form.full_description} onChange={(e) => setValue("full_description", e.target.value)} />
              </Field>
              <Field label="Pour qui / critères">
                <textarea className="input min-h-[130px]" value={form.eligibility_criteria} onChange={(e) => setValue("eligibility_criteria", e.target.value)} />
              </Field>
              <Field label="Montant / avantages">
                <textarea className="input min-h-[120px]" value={form.funding_details} onChange={(e) => setValue("funding_details", e.target.value)} />
              </Field>
              <Field label="Conditions particulières">
                <textarea className="input min-h-[100px]" value={form.specific_conditions} onChange={(e) => setValue("specific_conditions", e.target.value)} />
              </Field>
              <Field label="Documents ou démarche">
                <textarea className="input min-h-[100px]" value={form.required_documents} onChange={(e) => setValue("required_documents", e.target.value)} />
              </Field>
            </div>
          </div>

          <div className="card p-5">
            <h2 className="mb-4 text-sm font-semibold text-gray-700">Montants et calendrier</h2>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <Field label="Montant min">
                <input className="input" type="number" value={form.amount_min} onChange={(e) => setValue("amount_min", e.target.value)} />
              </Field>
              <Field label="Montant max">
                <input className="input" type="number" value={form.amount_max} onChange={(e) => setValue("amount_max", e.target.value)} />
              </Field>
              <Field label="Devise">
                <select className="input" value={form.currency} onChange={(e) => setValue("currency", e.target.value)}>
                  {["EUR", "USD", "XOF", "GBP", "MAD", "TND"].map((currency) => (
                    <option key={currency} value={currency}>
                      {currency}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Taux (%)">
                <input className="input" type="number" value={form.funding_rate} onChange={(e) => setValue("funding_rate", e.target.value)} />
              </Field>
              <Field label="Ouverture">
                <input className="input" type="date" value={form.open_date} onChange={(e) => setValue("open_date", e.target.value)} />
              </Field>
              <Field label="Clôture">
                <input className="input" type="date" value={form.close_date} onChange={(e) => setValue("close_date", e.target.value)} />
              </Field>
              <div className="col-span-2 flex items-center gap-2 pt-6">
                <input
                  id="is_recurring"
                  type="checkbox"
                  checked={form.is_recurring}
                  onChange={(e) => setValue("is_recurring", e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 accent-primary-600"
                />
                <label htmlFor="is_recurring" className="text-sm text-gray-700">
                  Opportunité permanente ou récurrente
                </label>
              </div>
              <div className="col-span-2 md:col-span-4">
                <Field label="Note de récurrence">
                  <input className="input" value={form.recurrence_notes} onChange={(e) => setValue("recurrence_notes", e.target.value)} />
                </Field>
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
                    <TogglePill key={sector} active={form.sectors.includes(sector)} onClick={() => toggleArrayValue("sectors", sector)}>
                      {sector}
                    </TogglePill>
                  ))}
                </div>
              </div>
              <div>
                <label className="label">Bénéficiaires</label>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {BENEFICIARIES.map((beneficiary) => (
                    <TogglePill key={beneficiary} active={form.beneficiaries.includes(beneficiary)} onClick={() => toggleArrayValue("beneficiaries", beneficiary)}>
                      {BENEFICIARY_LABELS[beneficiary] || beneficiary}
                    </TogglePill>
                  ))}
                </div>
              </div>
              <Field label="Mots-clés, séparés par virgules">
                <input className="input" value={form.keywords} onChange={(e) => setValue("keywords", e.target.value)} />
              </Field>
              <Field label="Tags internes, séparés par virgules">
                <input className="input" value={form.tags} onChange={(e) => setValue("tags", e.target.value)} />
              </Field>
            </div>
          </div>

          <div className="sticky bottom-0 z-10 -mx-2 flex items-center justify-end gap-2 border-t border-slate-200 bg-white/90 px-2 py-4 backdrop-blur">
            <button type="button" onClick={() => router.back()} className="btn-secondary text-xs">
              Annuler
            </button>
            <button type="submit" disabled={saving} className="btn-primary text-xs">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              {saving ? "Enregistrement..." : "Enregistrer les modifications"}
            </button>
          </div>
        </form>
      </div>
    </AppLayout>
  );
}

export default function EditDevicePage() {
  return (
    <RoleGate
      allow={["admin", "editor"]}
      title="Modification réservée à l'équipe"
      message="La correction manuelle des fiches est réservée aux profils équipe et super admin."
      backHref="/devices"
    >
      <EditDeviceFormPage />
    </RoleGate>
  );
}
