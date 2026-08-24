"use client";

import { useEffect, useState } from "react";
import { X, Sparkles, Bell, FolderKanban, TrendingUp, ArrowRight, CheckCircle2, MapPin, Tag, Loader2 } from "lucide-react";
import Link from "next/link";
import { auth } from "@/lib/api";
import { COUNTRIES, SECTORS } from "@/lib/constants";
import clsx from "clsx";

const STORAGE_KEY = "kafundo_onboarding_done";

const SECTOR_SUGGESTIONS = [
  "agriculture", "énergie", "technologie", "santé", "education",
  "environnement", "industrie", "commerce", "tourisme", "finance",
];

function StepWelcome({ onNext }: { onNext: () => void }) {
  const BENEFITS = [
    { icon: Sparkles, color: "bg-primary-100 text-primary-700", title: "Matching IA personnalisé", detail: "Détectez en 30 s les financements adaptés à votre profil parmi 2 500+ dispositifs." },
    { icon: Bell, color: "bg-emerald-100 text-emerald-700", title: "Alertes automatiques", detail: "Soyez notifié dès qu'un nouveau dispositif correspond à vos secteurs cibles." },
    { icon: FolderKanban, color: "bg-violet-100 text-violet-700", title: "Pipeline de candidature", detail: "Suivez chaque opportunité de la découverte au dépôt de dossier." },
    { icon: TrendingUp, color: "bg-amber-100 text-amber-700", title: "Jusqu'à 500 k€ détectés", detail: "Nos utilisateurs identifient 3× plus d'aides qu'avec une veille manuelle." },
  ];
  return (
    <>
      <div className="bg-gradient-to-br from-primary-600 to-blue-600 px-6 pt-6 pb-8 text-white">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles className="h-5 w-5 text-white/80" />
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-white/70">Bienvenue sur Kafundo</span>
        </div>
        <h2 className="text-2xl font-bold leading-tight mb-2">Découvrez les aides auxquelles vous avez droit</h2>
        <p className="text-sm text-white/80 leading-relaxed">20+ opportunités vous attendent. Personnalisez votre veille pour les trouver en 1 clic.</p>
      </div>

      <div className="px-6 py-5">
        <div className="grid grid-cols-2 gap-3 mb-6">
          {BENEFITS.map((b) => (
            <div key={b.title} className="flex flex-col gap-2 rounded-2xl border border-slate-100 p-3">
              <div className={`inline-flex w-fit rounded-xl p-1.5 ${b.color}`}>
                <b.icon className="h-4 w-4" />
              </div>
              <p className="text-xs font-semibold text-slate-800">{b.title}</p>
              <p className="text-[11px] leading-4 text-slate-500">{b.detail}</p>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={onNext}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-700"
        >
          Personnaliser ma veille
          <ArrowRight className="h-4 w-4" />
        </button>
        <p className="text-center text-xs text-slate-400 mt-2">Prend moins d'une minute</p>
      </div>
    </>
  );
}

function StepProfile({ onDone }: { onDone: () => void }) {
  const [country, setCountry] = useState("");
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [countrySearch, setCountrySearch] = useState("");

  const filteredCountries = countrySearch.trim()
    ? COUNTRIES.filter((c) => c.toLowerCase().includes(countrySearch.toLowerCase())).slice(0, 8)
    : COUNTRIES.slice(0, 20);

  const toggleSector = (s: string) =>
    setSelectedSectors((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await auth.updateMe({
        country: country || undefined,
        sectors: selectedSectors.join(",") || undefined,
      });
      // Sync localStorage so DevicesPageContent can read it immediately
      const raw = localStorage.getItem("kafundo_user");
      const existing = raw ? JSON.parse(raw) : {};
      localStorage.setItem("kafundo_user", JSON.stringify({
        ...existing,
        country: updated.country,
        sectors: updated.sectors,
      }));
    } catch {
      // Non-blocking — save fails silently, user can update from profile later
    } finally {
      setSaving(false);
      onDone();
    }
  };

  return (
    <>
      <div className="bg-gradient-to-br from-slate-800 to-slate-900 px-6 pt-6 pb-7 text-white">
        <div className="flex items-center gap-2 mb-3">
          <MapPin className="h-5 w-5 text-white/70" />
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-white/60">Étape 2 / 2 — Mon profil de veille</span>
        </div>
        <h2 className="text-xl font-bold leading-tight mb-1">Où exercez-vous votre activité ?</h2>
        <p className="text-sm text-white/70">Kafundo filtrera automatiquement les dispositifs de votre pays.</p>
      </div>

      <div className="px-6 py-5 space-y-5">
        {/* Pays */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 mb-2">
            <MapPin className="h-3 w-3" /> Pays principal
          </label>
          <input
            className="input mb-2 text-sm"
            placeholder="Rechercher un pays…"
            value={countrySearch}
            onChange={(e) => setCountrySearch(e.target.value)}
          />
          <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
            {filteredCountries.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => { setCountry(c); setCountrySearch(c); }}
                className={clsx(
                  "px-2.5 py-1 rounded-full text-xs border transition-colors",
                  country === c
                    ? "bg-primary-600 text-white border-primary-600 font-semibold"
                    : "bg-white text-slate-600 border-slate-200 hover:border-primary-300"
                )}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        {/* Secteurs */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 mb-2">
            <Tag className="h-3 w-3" /> Secteurs d'activité <span className="normal-case font-normal text-slate-400">(optionnel)</span>
          </label>
          <div className="flex flex-wrap gap-1.5">
            {SECTOR_SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => toggleSector(s)}
                className={clsx(
                  "px-2.5 py-1 rounded-full text-xs border capitalize transition-colors",
                  selectedSectors.includes(s)
                    ? "bg-emerald-600 text-white border-emerald-600"
                    : "bg-white text-slate-600 border-slate-200 hover:border-emerald-300"
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="flex gap-2 pt-1">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-700 disabled:opacity-60"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            {saving ? "Enregistrement…" : "Lancer ma veille personnalisée"}
          </button>
        </div>
        <button
          type="button"
          onClick={onDone}
          className="w-full text-center text-xs text-slate-400 hover:text-slate-600"
        >
          Passer — je définirai ça plus tard depuis mon profil
        </button>
      </div>
    </>
  );
}

export default function OnboardingModal() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const done = localStorage.getItem(STORAGE_KEY);
    if (!done) setOpen(true);
  }, []);

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    setOpen(false);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={dismiss} />
      <div className="relative w-full max-w-lg rounded-[28px] bg-white shadow-[0_32px_80px_-16px_rgba(15,23,42,0.5)] overflow-hidden">
        <button
          type="button"
          onClick={dismiss}
          className="absolute top-4 right-4 z-10 rounded-full p-1.5 text-white/60 hover:text-white hover:bg-white/10 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Indicateur d'étape */}
        <div className="absolute top-4 left-6 flex items-center gap-1.5 z-10">
          <span className={`h-1.5 w-6 rounded-full transition-colors ${step >= 1 ? "bg-white/80" : "bg-white/30"}`} />
          <span className={`h-1.5 w-6 rounded-full transition-colors ${step >= 2 ? "bg-white/80" : "bg-white/30"}`} />
        </div>

        {step === 1
          ? <StepWelcome onNext={() => setStep(2)} />
          : <StepProfile onDone={dismiss} />
        }
      </div>
    </div>
  );
}
