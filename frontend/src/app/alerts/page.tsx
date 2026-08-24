"use client";
import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import { alerts } from "@/lib/api";
import { Alert } from "@/lib/types";
import { formatDateRelative } from "@/lib/utils";
import {
  Plus, Bell, Trash2, Eye, ToggleLeft, ToggleRight,
  RefreshCw, XCircle, CheckCircle, MapPin, Tag, Clock,
} from "lucide-react";
import clsx from "clsx";
import { COUNTRIES, SECTORS } from "@/lib/constants";

const FREQ_LABELS: Record<string, string> = {
  instant: "Temps réel",
  daily: "Quotidien",
  weekly: "Hebdomadaire",
};

const TYPE_LABELS: Record<string, string> = {
  subvention: "Subvention", pret: "Prêt public", aap: "Appel à projets",
  investissement: "Investissement / Capital", garantie: "Garantie",
  accompagnement: "Accompagnement", concours: "Concours",
};

interface AlertTemplate {
  label: string;
  description: string;
  icon: string;
  preset: {
    name: string;
    frequency: string;
    criteria: { countries: string[]; sectors: string[]; device_types: string[]; keywords: string; close_within_days: string };
  };
}

const ALERT_TEMPLATES: AlertTemplate[] = [
  {
    label: "Subventions Europe",
    description: "Nouveaux appels à projets et subventions européennes",
    icon: "🇪🇺",
    preset: {
      name: "Subventions Europe",
      frequency: "weekly",
      criteria: { countries: ["France"], sectors: [], device_types: ["subvention", "aap"], keywords: "europe, horizon, feder", close_within_days: "" },
    },
  },
  {
    label: "Financements Afrique de l'Ouest",
    description: "Aides et appels à projets pour l'Afrique subsaharienne",
    icon: "🌍",
    preset: {
      name: "Financements Afrique de l'Ouest",
      frequency: "weekly",
      criteria: { countries: ["Sénégal", "Côte d'Ivoire", "Mali"], sectors: [], device_types: ["subvention", "aap", "investissement"], keywords: "", close_within_days: "" },
    },
  },
  {
    label: "AAP clôturant bientôt",
    description: "Appels à projets se terminant dans les 30 prochains jours",
    icon: "⏰",
    preset: {
      name: "AAP urgents — J-30",
      frequency: "daily",
      criteria: { countries: [], sectors: [], device_types: ["aap", "concours"], keywords: "", close_within_days: "30" },
    },
  },
  {
    label: "Innovation & Tech",
    description: "Aides à l'innovation, R&D et transformation numérique",
    icon: "🚀",
    preset: {
      name: "Innovation & Numérique",
      frequency: "weekly",
      criteria: { countries: [], sectors: ["technologie", "innovation"], device_types: ["subvention", "credit_impot", "aap"], keywords: "innovation, numérique, R&D", close_within_days: "" },
    },
  },
];

export default function AlertsPage() {
  const [alertList, setAlertList] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [preview, setPreview] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: "",
    frequency: "daily",
    channels: ["email", "dashboard"] as string[],
    alert_types: ["new", "updated", "closing_soon"] as string[],
    criteria: {
      countries: [] as string[],
      sectors: [] as string[],
      device_types: [] as string[],
      keywords: "",
      close_within_days: "",
    },
  });

  const loadAlerts = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await alerts.list();
      setAlertList(Array.isArray(data) ? data : []);
    } catch (e: any) {
      const msg = e.message || "Erreur inconnue";
      if (msg.includes("401") || msg.toLowerCase().includes("unauthorized")) {
        setError("Session expirée. Veuillez vous reconnecter.");
      } else {
        setError(`Impossible de charger les alertes : ${msg}`);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAlerts(); }, []);

  const resetForm = () => setForm({
    name: "",
    frequency: "daily",
    channels: ["email", "dashboard"],
    alert_types: ["new", "updated", "closing_soon"],
    criteria: { countries: [], sectors: [], device_types: [], keywords: "", close_within_days: "" },
  });

  const handleCreate = async () => {
    if (!form.name.trim()) { alert("Veuillez nommer cette alerte."); return; }
    setSaving(true);
    try {
      const payload = {
        ...form,
        criteria: {
          ...form.criteria,
          keywords: form.criteria.keywords
            ? form.criteria.keywords.split(",").map(k => k.trim()).filter(Boolean)
            : undefined,
          close_within_days: form.criteria.close_within_days
            ? parseInt(form.criteria.close_within_days)
            : undefined,
        },
      };
      const created = await alerts.create(payload) as Alert;
      setAlertList(prev => [created, ...prev]);
      setShowForm(false);
      resetForm();
    } catch (e: any) {
      alert(`Erreur : ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (alertItem: Alert) => {
    try {
      const updated = await alerts.update(alertItem.id, { is_active: !alertItem.is_active }) as Alert;
      setAlertList(prev => prev.map(a => a.id === alertItem.id ? updated : a));
    } catch (e: any) {
      window.alert(`Erreur : ${e.message}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Supprimer cette alerte définitivement ?")) return;
    try {
      await alerts.delete(id);
      setAlertList(prev => prev.filter(a => a.id !== id));
    } catch (e: any) {
      alert(`Erreur : ${e.message}`);
    }
  };

  const handlePreview = async (id: string) => {
    setPreviewLoading(true);
    try {
      const p = await alerts.preview(id) as any;
      setPreview(p);
    } catch (e: any) {
      alert(`Aperçu impossible : ${e.message}`);
    } finally {
      setPreviewLoading(false);
    }
  };

  const toggleMulti = (arr: string[], set: (v: string[]) => void, val: string) =>
    set(arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val]);

  const applyTemplate = (template: AlertTemplate) => {
    setForm({ ...template.preset, channels: ["email", "dashboard"], alert_types: ["new", "updated", "closing_soon"] });
    setShowForm(true);
    setTimeout(() => window.scrollTo({ top: 0, behavior: "smooth" }), 50);
  };

  return (
    <AppLayout>
      {/* En-tête */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Mes alertes</h1>
          <p className="text-sm text-gray-500">
            {alertList.filter(a => a.is_active).length} alerte(s) active(s) •{" "}
            Notifications par email & dashboard
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadAlerts} disabled={loading}
            className="btn-secondary text-xs flex items-center gap-1.5">
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            Actualiser
          </button>
          <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-1.5">
            <Plus className="w-4 h-4" /> Nouvelle alerte
          </button>
        </div>
      </div>

      {/* Erreur */}
      {error && (
        <div className="mb-6 px-5 py-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3">
          <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-700">{error}</p>
            <button onClick={loadAlerts}
              className="mt-2 text-xs text-red-600 underline hover:no-underline">
              Réessayer
            </button>
          </div>
        </div>
      )}

      {/* Formulaire création */}
      {showForm && (
        <div className="card p-5 mb-6 border-primary-200 bg-primary-50/30">
          <h2 className="text-sm font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <Bell className="w-4 h-4 text-primary-600" />
            Créer une alerte de veille
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            {/* Nom */}
            <div className="md:col-span-2">
              <label className="label">Nom de l'alerte *</label>
              <input className="input" placeholder="Ex : Subventions énergie Afrique de l'Ouest"
                value={form.name}
                onChange={e => setForm(p => ({ ...p, name: e.target.value }))} />
            </div>

            {/* Fréquence */}
            <div>
              <label className="label">Fréquence d'envoi</label>
              <select className="input" value={form.frequency}
                onChange={e => setForm(p => ({ ...p, frequency: e.target.value }))}>
                {Object.entries(FREQ_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>

            {/* Clôture */}
            <div>
              <label className="label">Clôture dans les prochains (jours)</label>
              <input className="input" type="number" placeholder="Ex : 30"
                value={form.criteria.close_within_days}
                onChange={e => setForm(p => ({
                  ...p, criteria: { ...p.criteria, close_within_days: e.target.value }
                }))} />
            </div>

            {/* Pays */}
            <div>
              <label className="label flex items-center gap-1"><MapPin className="w-3 h-3" /> Pays</label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {COUNTRIES.map(c => (
                  <button key={c} type="button"
                    onClick={() => toggleMulti(form.criteria.countries,
                      v => setForm(p => ({ ...p, criteria: { ...p.criteria, countries: v } })), c)}
                    className={clsx("px-2 py-1 rounded-md text-xs border transition-colors",
                      form.criteria.countries.includes(c)
                        ? "bg-primary-600 text-white border-primary-600"
                        : "bg-white text-gray-600 border-gray-200 hover:border-primary-300")}>
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {/* Secteurs */}
            <div>
              <label className="label flex items-center gap-1"><Tag className="w-3 h-3" /> Secteurs</label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {SECTORS.map(s => (
                  <button key={s} type="button"
                    onClick={() => toggleMulti(form.criteria.sectors,
                      v => setForm(p => ({ ...p, criteria: { ...p.criteria, sectors: v } })), s)}
                    className={clsx("px-2 py-1 rounded-md text-xs border transition-colors capitalize",
                      form.criteria.sectors.includes(s)
                        ? "bg-emerald-600 text-white border-emerald-600"
                        : "bg-white text-gray-600 border-gray-200 hover:border-emerald-300")}>
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Types de financement */}
            <div className="md:col-span-2">
              <label className="label">Types de financement</label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {Object.entries(TYPE_LABELS).map(([k, v]) => (
                  <button key={k} type="button"
                    onClick={() => toggleMulti(form.criteria.device_types,
                      dv => setForm(p => ({ ...p, criteria: { ...p.criteria, device_types: dv } })), k)}
                    className={clsx("px-2 py-1 rounded-md text-xs border transition-colors",
                      form.criteria.device_types.includes(k)
                        ? "bg-violet-600 text-white border-violet-600"
                        : "bg-white text-gray-600 border-gray-200 hover:border-violet-300")}>
                    {v}
                  </button>
                ))}
              </div>
            </div>

            {/* Mots-clés */}
            <div className="md:col-span-2">
              <label className="label">Mots-clés (séparés par des virgules)</label>
              <input className="input"
                placeholder="transition énergétique, startup, agroalimentaire"
                value={form.criteria.keywords}
                onChange={e => setForm(p => ({
                  ...p, criteria: { ...p.criteria, keywords: e.target.value }
                }))} />
            </div>
          </div>

          <div className="flex gap-2 mt-5 pt-4 border-t border-gray-100">
            <button onClick={handleCreate} disabled={saving} className="btn-primary text-xs">
              {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
              {saving ? "Création..." : "Créer l'alerte"}
            </button>
            <button onClick={() => { setShowForm(false); resetForm(); }} className="btn-secondary text-xs">
              Annuler
            </button>
          </div>
        </div>
      )}

      {/* Aperçu */}
      {preview && (
        <div className="card p-4 mb-4 border-blue-200 bg-blue-50">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-blue-800">
              Aperçu : {preview.count} dispositif(s) correspond(ent) à ces critères
            </h3>
            <button onClick={() => setPreview(null)} className="text-xs text-blue-600 hover:text-blue-800">
              Fermer ✕
            </button>
          </div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {preview.devices?.map((d: any) => (
              <div key={d.id} className="text-xs text-blue-700 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                {d.title} <span className="text-blue-400">({d.country})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chargement */}
      {loading && (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Chargement des alertes...
        </div>
      )}

      {/* Onboarding vide — suggestions automatiques */}
      {!loading && !error && alertList.length === 0 && (
        <div>
          <div className="text-center py-10 text-gray-400">
            <div className="w-16 h-16 bg-primary-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <Bell className="w-7 h-7 text-primary-400" />
            </div>
            <p className="font-semibold text-gray-700 mb-1 text-base">Aucune alerte configurée</p>
            <p className="text-sm text-gray-500 mb-2 max-w-sm mx-auto">
              Les alertes te notifient automatiquement dès qu'un nouveau dispositif correspond à ton profil.
            </p>
            <p className="text-xs text-gray-400 mb-6">Choisis un modèle ci-dessous pour démarrer en 10 secondes.</p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-6">
            {ALERT_TEMPLATES.map((tpl) => (
              <button
                key={tpl.label}
                type="button"
                onClick={() => applyTemplate(tpl)}
                className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-left transition-all hover:border-primary-300 hover:shadow-sm hover:-translate-y-0.5"
              >
                <span className="text-2xl">{tpl.icon}</span>
                <div>
                  <p className="text-sm font-semibold text-slate-800">{tpl.label}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{tpl.description}</p>
                </div>
              </button>
            ))}
          </div>

          <div className="text-center">
            <button onClick={() => setShowForm(true)} className="btn-primary text-sm">
              <Plus className="w-4 h-4" /> Créer une alerte personnalisée
            </button>
          </div>
        </div>
      )}

      {/* Suggestions pour utilisateurs existants */}
      {!loading && alertList.length > 0 && (
        <div className="mb-5 rounded-2xl border border-primary-100 bg-primary-50/40 px-4 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary-600 mb-3">Suggestions d'alertes</p>
          <div className="flex flex-wrap gap-2">
            {ALERT_TEMPLATES.map((tpl) => (
              <button
                key={tpl.label}
                type="button"
                onClick={() => applyTemplate(tpl)}
                className="flex items-center gap-1.5 rounded-full border border-primary-200 bg-white px-3 py-1.5 text-xs font-medium text-primary-700 transition-colors hover:bg-primary-100"
              >
                <span>{tpl.icon}</span>
                {tpl.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Liste */}
      {!loading && alertList.length > 0 && (
        <div className="space-y-3">
          {alertList.map(alert => (
            <div key={alert.id}
              className={clsx("card p-4 transition-opacity", !alert.is_active && "opacity-60")}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1.5">
                    <h3 className="text-sm font-semibold text-gray-900">{alert.name}</h3>
                    <span className="badge bg-gray-100 text-gray-600 text-xs">
                      <Clock className="w-3 h-3 inline mr-0.5" />
                      {FREQ_LABELS[alert.frequency] || alert.frequency}
                    </span>
                    {alert.is_active
                      ? <span className="badge bg-green-100 text-green-700 text-xs">● Active</span>
                      : <span className="badge bg-gray-100 text-gray-500 text-xs">Inactive</span>}
                  </div>

                  {/* Critères */}
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                    {(alert.criteria as any).countries?.length > 0 && (
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3 h-3" />
                        {(alert.criteria as any).countries.join(", ")}
                      </span>
                    )}
                    {(alert.criteria as any).sectors?.length > 0 && (
                      <span className="flex items-center gap-1">
                        <Tag className="w-3 h-3" />
                        {(alert.criteria as any).sectors.join(", ")}
                      </span>
                    )}
                    {(alert.criteria as any).device_types?.length > 0 && (
                      <span>Types : {(alert.criteria as any).device_types.join(", ")}</span>
                    )}
                    {(alert.criteria as any).keywords?.length > 0 && (
                      <span>Mots-clés : {(alert.criteria as any).keywords.join(", ")}</span>
                    )}
                  </div>

                  {alert.last_triggered_at && (
                    <p className="text-xs text-gray-400 mt-1.5 flex items-center gap-1">
                      <Bell className="w-3 h-3" />
                      Dernière notification : {formatDateRelative(alert.last_triggered_at)}
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    onClick={() => handlePreview(alert.id)}
                    disabled={previewLoading}
                    className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                    title="Aperçu des dispositifs correspondants">
                    <Eye className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleToggle(alert)}
                    className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                    title={alert.is_active ? "Désactiver" : "Activer"}>
                    {alert.is_active
                      ? <ToggleRight className="w-5 h-5 text-green-500" />
                      : <ToggleLeft className="w-5 h-5" />}
                  </button>
                  <button
                    onClick={() => handleDelete(alert.id)}
                    className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    title="Supprimer">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </AppLayout>
  );
}
