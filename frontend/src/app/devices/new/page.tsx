"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import AppLayout from "@/components/AppLayout";
import { devices } from "@/lib/api";
import { DEVICE_TYPE_LABELS } from "@/lib/types";
import { COUNTRIES, SECTORS } from "@/lib/constants";
import { ArrowLeft, Save, RefreshCw } from "lucide-react";

const BENEFICIARIES = [
  "startup", "pme", "eti", "association", "collectivite",
  "porteur_projet", "agriculteur", "chercheur",
];

const BENE_LABELS: Record<string, string> = {
  startup: "Startup", pme: "PME / TPE", eti: "ETI",
  association: "Association / ONG", collectivite: "Collectivité",
  porteur_projet: "Porteur de projet", agriculteur: "Agriculteur",
  chercheur: "Chercheur / Labo",
};

export default function NewDevicePage() {
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

  const toggle = (arr: string[], set: (v: string[]) => void, val: string) =>
    set(arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val]);

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
      const created = await devices.create(payload) as { id: string };
      router.push(`/devices/${created.id}`);
    } catch (e: any) {
      setError(e.message || "Erreur lors de la création");
      setSaving(false);
    }
  };

  const F = ({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) => (
    <div>
      <label className="label">{label}{required && <span className="text-red-500 ml-1">*</span>}</label>
      {children}
    </div>
  );

  return (
    <AppLayout>
      <div className="max-w-3xl">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <button onClick={() => router.back()} className="btn-secondary text-xs">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Ajouter un dispositif</h1>
            <p className="text-sm text-gray-500">Saisie manuelle d'un dispositif de financement</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Identité */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Informations principales</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <F label="Titre du dispositif" required>
                  <input className="input" placeholder="Ex : Appel à projets Transition Énergétique 2026"
                    value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} />
                </F>
              </div>
              <F label="Organisme / Émetteur" required>
                <input className="input" placeholder="Ex : ADEME, Bpifrance, BAD..."
                  value={form.organism} onChange={e => setForm(p => ({ ...p, organism: e.target.value }))} />
              </F>
              <F label="Pays">
                <select className="input" value={form.country}
                  onChange={e => setForm(p => ({ ...p, country: e.target.value }))}>
                  {COUNTRIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </F>
              <F label="Type de financement">
                <select className="input" value={form.device_type}
                  onChange={e => setForm(p => ({ ...p, device_type: e.target.value }))}>
                  {Object.entries(DEVICE_TYPE_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>{v}</option>
                  ))}
                </select>
              </F>
              <F label="Statut">
                <select className="input" value={form.status}
                  onChange={e => setForm(p => ({ ...p, status: e.target.value }))}>
                  <option value="open">Ouvert</option>
                  <option value="recurring">Récurrent</option>
                  <option value="closed">Fermé</option>
                  <option value="standby">En veille</option>
                </select>
              </F>
              <div className="md:col-span-2">
                <F label="URL source (lien officiel)" required>
                  <input className="input" type="url" placeholder="https://..."
                    value={form.source_url} onChange={e => setForm(p => ({ ...p, source_url: e.target.value }))} />
                </F>
              </div>
            </div>
          </div>

          {/* Descriptions */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Description</h2>
            <div className="space-y-4">
              <F label="Résumé">
                <textarea className="input min-h-[80px]" placeholder="Description courte du dispositif..."
                  value={form.short_description}
                  onChange={e => setForm(p => ({ ...p, short_description: e.target.value }))} />
              </F>
              <F label="Critères d'éligibilité">
                <textarea className="input min-h-[80px]" placeholder="Qui peut candidater ? Quelles conditions ?"
                  value={form.eligibility_criteria}
                  onChange={e => setForm(p => ({ ...p, eligibility_criteria: e.target.value }))} />
              </F>
            </div>
          </div>

          {/* Financement */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Montants & Dates</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <F label="Montant min (€)">
                <input className="input" type="number" placeholder="0"
                  value={form.amount_min} onChange={e => setForm(p => ({ ...p, amount_min: e.target.value }))} />
              </F>
              <F label="Montant max (€)">
                <input className="input" type="number" placeholder="500000"
                  value={form.amount_max} onChange={e => setForm(p => ({ ...p, amount_max: e.target.value }))} />
              </F>
              <F label="Devise">
                <select className="input" value={form.currency}
                  onChange={e => setForm(p => ({ ...p, currency: e.target.value }))}>
                  <option value="EUR">EUR €</option>
                  <option value="USD">USD $</option>
                  <option value="XOF">XOF FCFA</option>
                  <option value="MAD">MAD DH</option>
                  <option value="TND">TND DT</option>
                </select>
              </F>
              <F label="Taux de financement (%)">
                <input className="input" type="number" min="0" max="100" placeholder="70"
                  value={form.funding_rate} onChange={e => setForm(p => ({ ...p, funding_rate: e.target.value }))} />
              </F>
              <F label="Date d'ouverture">
                <input className="input" type="date"
                  value={form.open_date} onChange={e => setForm(p => ({ ...p, open_date: e.target.value }))} />
              </F>
              <F label="Date de clôture">
                <input className="input" type="date"
                  value={form.close_date} onChange={e => setForm(p => ({ ...p, close_date: e.target.value }))} />
              </F>
              <div className="flex items-center gap-2 mt-6">
                <input type="checkbox" id="recurring" className="w-4 h-4 text-primary-600"
                  checked={form.is_recurring}
                  onChange={e => setForm(p => ({ ...p, is_recurring: e.target.checked }))} />
                <label htmlFor="recurring" className="text-sm text-gray-700">Dispositif récurrent</label>
              </div>
            </div>
          </div>

          {/* Ciblage */}
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Secteurs & Bénéficiaires</h2>
            <div className="space-y-4">
              <div>
                <label className="label">Secteurs concernés</label>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {SECTORS.map(s => (
                    <button key={s} type="button"
                      onClick={() => toggle(form.sectors, v => setForm(p => ({ ...p, sectors: v })), s)}
                      className={`px-2.5 py-1 rounded-lg text-xs border capitalize transition-colors ${
                        form.sectors.includes(s)
                          ? "bg-emerald-600 text-white border-emerald-600"
                          : "bg-white text-gray-600 border-gray-200 hover:border-emerald-300"
                      }`}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="label">Bénéficiaires cibles</label>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {BENEFICIARIES.map(b => (
                    <button key={b} type="button"
                      onClick={() => toggle(form.beneficiaries, v => setForm(p => ({ ...p, beneficiaries: v })), b)}
                      className={`px-2.5 py-1 rounded-lg text-xs border transition-colors ${
                        form.beneficiaries.includes(b)
                          ? "bg-primary-600 text-white border-primary-600"
                          : "bg-white text-gray-600 border-gray-200 hover:border-primary-300"
                      }`}>
                      {BENE_LABELS[b] || b}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pb-6">
            <button type="submit" disabled={saving} className="btn-primary flex items-center gap-2">
              {saving
                ? <><RefreshCw className="w-4 h-4 animate-spin" /> Enregistrement...</>
                : <><Save className="w-4 h-4" /> Enregistrer le dispositif</>}
            </button>
            <button type="button" onClick={() => router.back()} className="btn-secondary">
              Annuler
            </button>
          </div>
        </form>
      </div>
    </AppLayout>
  );
}
