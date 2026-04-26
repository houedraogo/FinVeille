"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  ArrowRight, Bell, BriefcaseBusiness, Building2, CheckCircle2,
  Globe2, Landmark, Loader2, Rocket, Sparkles, Users, ChevronRight,
  Target, TrendingUp, Zap, Clock, DollarSign,
} from "lucide-react";
import clsx from "clsx";

import { alerts, devices, relevance } from "@/lib/api";
import { SECTORS } from "@/lib/constants";
import { DEVICE_TYPE_LABELS } from "@/lib/types";
import {
  queueSavedSearch, saveSearch, saveUserPreferences,
  getUserPreferences, type SavedSearch,
} from "@/lib/workspace";

// ── Zones géographiques ───────────────────────────────────────────────────────

const ZONES = [
  { key: "france",         label: "France",              emoji: "🇫🇷", countries: ["France"] },
  { key: "afrique-ouest",  label: "Afrique de l'Ouest",  emoji: "🌍", countries: ["Sénégal", "Côte d'Ivoire", "Mali", "Burkina Faso", "Niger", "Togo", "Bénin", "Guinée", "Ghana", "Nigeria", "Afrique de l'Ouest"] },
  { key: "maghreb",        label: "Maghreb",              emoji: "🌐", countries: ["Maroc", "Tunisie"] },
  { key: "afrique-centrale", label: "Afrique centrale",  emoji: "🌍", countries: ["RD Congo", "Cameroun"] },
  { key: "afrique-est",    label: "Afrique de l'Est",    emoji: "🌍", countries: ["Kenya", "Éthiopie", "Madagascar"] },
  { key: "international",  label: "International",        emoji: "🌐", countries: [] },
] as const;

type ZoneKey = (typeof ZONES)[number]["key"];

// ── Labels secteurs ───────────────────────────────────────────────────────────

const SECTOR_LABELS: Record<string, string> = {
  agriculture:    "🌾 Agriculture",
  energie:        "⚡ Énergie",
  sante:          "🏥 Santé",
  numerique:      "💻 Numérique",
  education:      "📚 Éducation",
  environnement:  "🌿 Environnement",
  industrie:      "🏭 Industrie",
  tourisme:       "✈️ Tourisme",
  transport:      "🚀 Transport",
  finance:        "💰 Finance",
  eau:            "💧 Eau",
  social:         "🤝 Social",
  culture:        "🎨 Culture",
  immobilier:     "🏗️ Immobilier",
};

// ── Profils ───────────────────────────────────────────────────────────────────

const PROFILES = [
  { key: "entrepreneur",  label: "Entrepreneur",  description: "Je cherche des aides, subventions ou financements pour mon entreprise.", icon: Rocket,           sectors: ["agriculture", "numerique", "energie"] },
  { key: "association",   label: "Association",   description: "Je suis une structure associative ou ESS avec des projets à financer.",   icon: Users,            sectors: ["social", "education", "culture"] },
  { key: "collectivite",  label: "Collectivité",  description: "Je suis une institution locale ou un acteur territorial.",               icon: Landmark,         sectors: ["environnement", "energie", "immobilier"] },
  { key: "investisseur",  label: "Investisseur",  description: "Je suis un fonds, business angel ou acteur de l'investissement.",         icon: BriefcaseBusiness, sectors: ["finance", "numerique", "sante"] },
  { key: "consultant",    label: "Consultant",    description: "J'accompagne plusieurs clients et veux surveiller les opportunités.",     icon: Globe2,           sectors: ["agriculture", "energie", "numerique"] },
] as const;

// ── Type de financement ───────────────────────────────────────────────────────

type FinancingScope = "public" | "private" | "both";

const PUBLIC_TYPES  = ["subvention", "aap", "concours", "pret", "accompagnement", "garantie"];
const PRIVATE_TYPES = ["investissement"];
const ALL_TYPES     = [...PUBLIC_TYPES, ...PRIVATE_TYPES];

const FINANCING_SCOPES: { key: FinancingScope; label: string; sub: string; icon: typeof Building2; types: string[] }[] = [
  { key: "public",   label: "Financements publics",       sub: "Subventions, AAP, concours, prêts, accompagnement…",                icon: Building2,   types: PUBLIC_TYPES },
  { key: "private",  label: "Investisseurs privés",        sub: "Fonds d'investissement, business angels, capital-risque…",         icon: TrendingUp,  types: PRIVATE_TYPES },
  { key: "both",     label: "Les deux",                    sub: "Je recherche à la fois des financements publics et privés.",        icon: Sparkles,    types: ALL_TYPES },
];

// ── Simulation de résultats ───────────────────────────────────────────────────

function simulateOpportunityCount(zones: ZoneKey[], sectors: string[]): number {
  const base = 48;
  const zoneBonus = zones.length * 16;
  const sectorBonus = sectors.length * 6;
  const variation = ((zones.length * 7 + sectors.length * 11) % 19) - 9;
  return Math.max(12, base + zoneBonus + sectorBonus + variation);
}

function simulateBreakdown(total: number, scope: FinancingScope | "") {
  const isPrivate = scope === "private";
  const isBoth    = scope === "both";
  const subventions  = isPrivate ? 0  : Math.round(total * 0.14);
  const investisseurs = !isPrivate || isBoth ? Math.round(total * 0.06) : Math.round(total * 0.35);
  const urgentes    = Math.round(total * 0.04);
  const projMin     = Math.round(total * 900  / 10000) * 10;
  const projMax     = Math.round(total * 4500 / 10000) * 10;
  return { subventions, investisseurs, urgentes, projMin, projMax };
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function toggleValue<T>(arr: T[], value: T): T[] {
  return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
}

function formatAmount(k: number): string {
  return k >= 1000 ? `${(k / 1000).toFixed(0)} M€` : `${k} 000€`;
}

const STEP_LABELS = ["Profil", "Ciblage", "Financement"] as const;

const LOADING_CHECKS = [
  "Croisement avec +3 000 dispositifs",
  "Filtrage par éligibilité",
  "Priorisation intelligente",
] as const;

// ── Composant principal ───────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();

  // step: 0=profil 1=ciblage 2=loading 3=financement+résultat 4=terminé
  const [step,            setStep]            = useState(0);
  const [profile,         setProfile]         = useState<string>("");
  const [selectedZones,   setSelectedZones]   = useState<ZoneKey[]>([]);
  const [sectors,         setSectors]         = useState<string[]>([]);
  const [financingScope,  setFinancingScope]  = useState<FinancingScope | "">("");
  const [saving,          setSaving]          = useState(false);
  const [error,           setError]           = useState<string | null>(null);

  // Simulation
  const [analysisPhase,   setAnalysisPhase]   = useState<0 | 1 | 2>(0); // 0=idle 1=computing 2=done
  const [simCount,        setSimCount]        = useState(0);
  const [resultVisible,   setResultVisible]   = useState(false);
  const [loadingChecks,   setLoadingChecks]   = useState(0); // nombre de ✔ affichés

  // Alert créée
  const [createdAlertName, setCreatedAlertName] = useState<string | null>(null);

  // Dérive les pays réels depuis les zones sélectionnées
  const selectedCountries = useMemo(() => {
    const list = selectedZones.flatMap((zk) => ZONES.find((z) => z.key === zk)?.countries ?? []);
    return Array.from(new Set(list)) as string[];
  }, [selectedZones]);

  const deviceTypes = useMemo(() => {
    const scope = FINANCING_SCOPES.find((s) => s.key === financingScope);
    return scope?.types ?? [];
  }, [financingScope]);

  const selectedProfile = useMemo(() => PROFILES.find((p) => p.key === profile), [profile]);

  // Affichage du displayStep dans le header (0,1,2 → ignorer step=2 loading)
  const displayStep = step === 0 ? 0 : step === 1 ? 1 : step >= 3 ? 2 : 1;

  // ── Simulation analyse (step 1) ─────────────────────────────────────────────

  useEffect(() => {
    if (step !== 1) return;
    if (selectedZones.length === 0 && sectors.length === 0) return;

    setAnalysisPhase(1);
    const t = setTimeout(() => {
      setSimCount(simulateOpportunityCount(selectedZones, sectors));
      setAnalysisPhase(2);
    }, 900);
    return () => clearTimeout(t);
  }, [selectedZones.join(","), sectors.join(","), step]); // eslint-disable-line

  // ── Écran de chargement (step 2) ────────────────────────────────────────────

  useEffect(() => {
    if (step !== 2) { setLoadingChecks(0); return; }
    // Apparition progressive des checks
    const timers = LOADING_CHECKS.map((_, i) =>
      setTimeout(() => setLoadingChecks(i + 1), 500 + i * 600),
    );
    // Avancer à step 3 après 2s
    const advance = setTimeout(() => setStep(3), 2100);
    return () => { timers.forEach(clearTimeout); clearTimeout(advance); };
  }, [step]);

  // ── Résultats (step 3) ───────────────────────────────────────────────────────

  useEffect(() => {
    if (financingScope && step === 3) {
      setTimeout(() => setResultVisible(true), 150);
    } else {
      setResultVisible(false);
    }
  }, [financingScope, step]);

  // ── Sélection de profil ──────────────────────────────────────────────────────

  const selectProfile = (key: string) => {
    const next = PROFILES.find((p) => p.key === key);
    setProfile(key);
    if (next) setSectors((cur) => (cur.length ? cur : [...next.sectors]));
    if (!financingScope) {
      setFinancingScope(key === "investisseur" ? "private" : "public");
    }
  };

  const selectScope = (scope: FinancingScope) => {
    setFinancingScope(scope);
    localStorage.setItem("kafundo_financing_scope", scope);
  };

  // ── Can continue ────────────────────────────────────────────────────────────

  const canContinue = useMemo(() => {
    if (step === 0) return !!profile;
    if (step === 1) return selectedZones.length > 0;
    if (step === 3) return !!financingScope;
    return true;
  }, [profile, selectedZones.length, financingScope, step]);

  // ── Sauvegardes & données ────────────────────────────────────────────────────

  const buildSavedSearch = (): SavedSearch => ({
    id: crypto.randomUUID(),
    name: `Veille ${selectedProfile?.label || "personnalisée"}`,
    title: financingScope === "private" ? "Fonds & Investisseurs" : "Opportunités recommandées",
    path: financingScope === "private" ? "/devices/private" : "/devices",
    resultCount: null,
    savedAt: new Date().toISOString(),
    filters: {
      q: sectors.slice(0, 2).join(" "),
      countries: selectedCountries,
      deviceTypes,
      sectors,
      statuses: financingScope === "private" ? [] : ["open", "recurring"],
      closingSoon: "",
      hasCloseDate: false,
      sortBy: "relevance",
    },
  });

  const finishOnboarding = async () => {
    setSaving(true);
    setError(null);

    const alertName = `Veille ${selectedProfile?.label || "Kafundo"} — ${selectedZones.slice(0, 2).join(", ")}`;
    const savedSearch = buildSavedSearch();

    try {
      const data = await devices.list({
        q: sectors.slice(0, 2).join(" ") || undefined,
        countries: selectedCountries,
        sectors,
        device_types: deviceTypes,
        status: financingScope === "private" ? undefined : ["open", "recurring"],
        sort_by: "relevance",
        page: 1,
        page_size: 5,
      });

      await relevance.saveProfile({
        organization_type: profile || null,
        countries: selectedCountries,
        sectors,
        target_funding_types: deviceTypes,
        strategic_priorities: sectors.slice(0, 3),
      });

      const existingProjects = await relevance.listProjects().catch(() => []);
      if (!Array.isArray(existingProjects) || existingProjects.length === 0) {
        await relevance.createProject({
          name: `Projet ${selectedProfile?.label || "prioritaire"}`,
          summary: "Projet créé automatiquement depuis l'onboarding Kafundo.",
          countries: selectedCountries,
          sectors,
          target_funding_types: deviceTypes,
          is_primary: true,
        });
      }

      await alerts.create({
        name: alertName,
        frequency: "daily",
        channels: ["email", "dashboard"],
        alert_types: ["new", "updated", "closing_soon"],
        criteria: {
          countries: selectedCountries,
          sectors,
          device_types: deviceTypes,
          keywords: sectors,
          close_within_days: 30,
        },
      });

      saveSearch({ ...savedSearch, resultCount: data?.total ?? 0 });
      saveUserPreferences({
        ...getUserPreferences(),
        onboardingCompleted: true,
        onboardingProfile: profile,
        onboardingCountries: selectedCountries,
        onboardingSectors: sectors,
        onboardingDeviceTypes: deviceTypes,
      });
      localStorage.setItem("kafundo_onboarding_completed", "1");
      localStorage.setItem("kafundo_financing_scope", financingScope as string);
      setCreatedAlertName(alertName);
      setStep(4);
    } catch (e: any) {
      setError(e.message || "Impossible de finaliser la configuration.");
    } finally {
      setSaving(false);
    }
  };

  const openOpportunities = () => {
    queueSavedSearch(buildSavedSearch());
    router.push(financingScope === "private" ? "/devices/private" : "/devices");
  };

  // ── Rendu ─────────────────────────────────────────────────────────────────

  const breakdown = simulateBreakdown(simCount, financingScope);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/40">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200/70 bg-white/90 px-4 backdrop-blur-sm sm:px-6">
        <div className="flex items-center gap-3">
          <Image src="/brand/kafundo-picto.png" alt="Kafundo" width={34} height={34} className="h-[34px] w-[34px] rounded-xl object-cover" />
          <div>
            <span className="block text-sm font-bold text-slate-900">Kafundo</span>
            <span className="block text-[10px] leading-tight text-slate-400">Trouve tes financements</span>
          </div>
        </div>

        {/* Progress steps (desktop) */}
        {step < 4 && (
          <div className="hidden items-center gap-1.5 sm:flex">
            {STEP_LABELS.map((label, i) => (
              <div key={label} className="flex items-center gap-1.5">
                <div className={clsx(
                  "flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold transition-all",
                  i < displayStep ? "bg-primary-600 text-white"
                    : i === displayStep ? "border-2 border-primary-600 text-primary-700"
                      : "border-2 border-slate-200 text-slate-400",
                )}>
                  {i < displayStep ? "✓" : i + 1}
                </div>
                <span className={clsx("text-xs font-medium", i <= displayStep ? "text-slate-700" : "text-slate-400")}>
                  {label}
                </span>
                {i < STEP_LABELS.length - 1 && <ChevronRight className="h-3.5 w-3.5 text-slate-300" />}
              </div>
            ))}
          </div>
        )}

        <span className="text-xs text-slate-400">
          {step < 4 ? `Étape ${displayStep + 1} / 3` : "Configuration terminée ✓"}
        </span>
      </header>

      {/* ── Corps ───────────────────────────────────────────────────────────── */}
      <div className="mx-auto flex min-h-[calc(100vh-64px)] max-w-7xl flex-col lg:flex-row">

        {/* ── Panneau gauche ── */}
        {step < 4 && step !== 2 && (
          <aside className="hidden lg:flex lg:w-80 xl:w-88 flex-col justify-center border-r border-slate-200/60 bg-white/50 px-10 py-12">
            {step === 0 && (
              <>
                <span className="inline-block rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 w-fit">
                  ✨ Personnalisation
                </span>
                <h2 className="mt-4 text-xl font-bold text-slate-950">Votre veille sur-mesure<br />en 2 minutes.</h2>
                <p className="mt-3 text-sm leading-6 text-slate-500">Indiquez qui vous êtes pour que Kafundo filtre automatiquement les opportunités qui vous correspondent.</p>
                <div className="mt-8 space-y-4">
                  {[
                    "Un catalogue filtré selon votre profil exact",
                    "Des recommandations triées par pertinence",
                    "Des alertes sur vos opportunités clés",
                    "Un suivi de vos candidatures centralisé",
                  ].map((text) => (
                    <div key={text} className="flex items-start gap-3">
                      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary-600 text-white">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l2.5 2.5L10 3.5" />
                        </svg>
                      </div>
                      <span className="text-sm text-slate-600">{text}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-10 rounded-2xl bg-gradient-to-br from-primary-50 to-blue-50/60 border border-primary-100 px-4 py-4">
                  <p className="text-xs font-semibold text-primary-700">💡 Pourquoi c'est important</p>
                  <p className="mt-2 text-xs leading-5 text-primary-800">
                    Sans configuration, vous verrez plus de 1 900 dispositifs. Avec votre profil, seules les opportunités pertinentes s'affichent.
                  </p>
                </div>
              </>
            )}
            {step === 1 && (
              <>
                <span className="inline-block rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700 w-fit">
                  🎯 Ciblage
                </span>
                <h2 className="mt-4 text-xl font-bold text-slate-950">Plus vous êtes précis,<br />meilleurs les résultats.</h2>
                <p className="mt-3 text-sm leading-6 text-slate-500">La combinaison zone + secteur permet d'identifier exactement les financements disponibles pour votre situation.</p>
                <div className="mt-8 space-y-3">
                  {[
                    { icon: "🌍", text: "Les zones définissent la couverture géographique de votre veille" },
                    { icon: "🏷️", text: "Les secteurs filtrent par domaine d'activité" },
                    { icon: "🔄", text: "Combinables à volonté — modifiables à tout moment" },
                  ].map(({ icon, text }) => (
                    <div key={text} className="flex items-start gap-3 rounded-xl border border-slate-100 bg-white/70 px-3 py-2.5">
                      <span className="text-base">{icon}</span>
                      <span className="text-xs leading-5 text-slate-600">{text}</span>
                    </div>
                  ))}
                </div>
                {simCount > 0 && (
                  <div className="mt-8 rounded-2xl bg-gradient-to-br from-emerald-50 to-green-50/60 border border-emerald-200 px-4 py-4">
                    <p className="text-xs font-semibold text-emerald-700">🎯 Analyse en temps réel</p>
                    <p className="mt-2 text-2xl font-bold text-emerald-900">{simCount}</p>
                    <p className="text-xs text-emerald-700">financements potentiels identifiés</p>
                  </div>
                )}
              </>
            )}
            {step === 3 && (
              <>
                <span className="inline-block rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700 w-fit">
                  🏁 Dernière étape
                </span>
                <h2 className="mt-4 text-xl font-bold text-slate-950">Prêt à découvrir<br />vos financements.</h2>
                <p className="mt-3 text-sm leading-6 text-slate-500">Sélectionnez le type de financement qui vous correspond. Le résultat de votre analyse s'affichera immédiatement.</p>
                {simCount > 0 && (
                  <div className="mt-8 rounded-2xl bg-gradient-to-br from-violet-50 to-indigo-50/60 border border-violet-200 px-4 py-5">
                    <p className="text-xs font-semibold text-violet-600 uppercase tracking-wider">Votre profil</p>
                    <div className="mt-3 space-y-2 text-sm text-slate-700">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Profil</span>
                        <span className="font-semibold capitalize">{selectedProfile?.label}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Zones</span>
                        <span className="font-semibold">{selectedZones.length} sélectionnée{selectedZones.length > 1 ? "s" : ""}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Secteurs</span>
                        <span className="font-semibold">{sectors.length} sélectionné{sectors.length > 1 ? "s" : ""}</span>
                      </div>
                      <div className="flex justify-between border-t border-violet-100 pt-2 mt-2">
                        <span className="text-violet-700 font-semibold">Potentiel</span>
                        <span className="font-bold text-violet-900">{simCount} financements</span>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </aside>
        )}

        {/* ── Contenu principal ── */}
        <main className={clsx(
          "flex flex-1 flex-col justify-center px-4 py-8 sm:px-8 lg:px-12",
          step === 2 && "items-center justify-center",
        )}>
          <div className={clsx("mx-auto w-full", step === 2 ? "max-w-lg" : "max-w-3xl")}>

            {/* Barre mobile */}
            {step < 4 && step !== 2 && (
              <div className="mb-5 flex gap-1.5 lg:hidden">
                {STEP_LABELS.map((_, i) => (
                  <div key={i} className={clsx("h-1.5 flex-1 rounded-full transition-all", i <= displayStep ? "bg-primary-600" : "bg-slate-200")} />
                ))}
              </div>
            )}

            {/* ═══════════════════════════════════════════════════════════════ */}
            {/* ÉTAPE 0 — Hook + Profil                                         */}
            {/* ═══════════════════════════════════════════════════════════════ */}
            {step === 0 && (
              <div>
                {/* Hero copy */}
                <div className="mb-8 text-center lg:text-left">
                  <span className="inline-block rounded-full bg-primary-100 px-3 py-1 text-xs font-semibold text-primary-700">
                    ⚡ Analyse personnalisée
                  </span>
                  <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl lg:text-4xl leading-tight">
                    Trouvez les financements<br className="hidden sm:block" />
                    <span className="text-primary-600"> faits pour vous</span><br />
                    en moins de 2 minutes
                  </h1>
                  <p className="mt-3 text-base text-slate-500 max-w-lg mx-auto lg:mx-0">
                    En moyenne, nos utilisateurs découvrent entre{" "}
                    <span className="font-semibold text-slate-700">50 000€ et 500 000€</span>{" "}
                    d'aides disponibles.
                  </p>
                </div>

                {/* Profil cards */}
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                  {PROFILES.map((item) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => selectProfile(item.key)}
                        className={clsx(
                          "group rounded-3xl border p-4 text-left transition-all hover:-translate-y-0.5",
                          profile === item.key
                            ? "border-primary-300 bg-primary-50 shadow-[0_12px_32px_-20px_rgba(37,99,235,0.4)]"
                            : "border-slate-200 bg-white hover:border-primary-200 hover:bg-primary-50/40",
                        )}
                      >
                        <span className={clsx(
                          "flex h-11 w-11 items-center justify-center rounded-2xl transition-colors",
                          profile === item.key
                            ? "bg-primary-600 text-white"
                            : "bg-slate-100 text-slate-600 group-hover:bg-primary-100 group-hover:text-primary-700",
                        )}>
                          <Icon className="h-5 w-5" />
                        </span>
                        <p className="mt-3.5 font-semibold text-slate-950">{item.label}</p>
                        <p className="mt-1 text-xs leading-5 text-slate-500 hidden sm:block">{item.description}</p>
                      </button>
                    );
                  })}
                </div>

                {/* Message après sélection */}
                <div className={clsx(
                  "mt-5 rounded-2xl border px-4 py-3.5 transition-all duration-300",
                  profile
                    ? "border-primary-200 bg-primary-50/80 opacity-100"
                    : "border-slate-100 bg-slate-50/60 opacity-60",
                )}>
                  <p className="text-sm text-primary-800">
                    <span className="font-semibold">🎯</span>{" "}
                    {profile
                      ? "Basé sur votre profil, nous allons analyser automatiquement vos opportunités de financement."
                      : "Sélectionnez votre profil pour commencer l'analyse personnalisée."}
                  </p>
                </div>
              </div>
            )}

            {/* ═══════════════════════════════════════════════════════════════ */}
            {/* ÉTAPE 1 — Ciblage (Zones + Secteurs)                            */}
            {/* ═══════════════════════════════════════════════════════════════ */}
            {step === 1 && (
              <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_20px_60px_-30px_rgba(15,23,42,0.15)] sm:p-8">
                <h1 className="text-xl font-bold text-slate-950 sm:text-2xl">
                  Où et dans quels domaines souhaitez-vous<br className="hidden md:block" /> trouver des financements ?
                </h1>
                <p className="mt-1.5 text-sm text-slate-500">
                  Sélectionnez au moins une zone géographique.
                </p>

                {/* Zones */}
                <div className="mt-6">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
                    🌍 Zones géographiques
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {ZONES.map((zone) => (
                      <button
                        key={zone.key}
                        type="button"
                        onClick={() => setSelectedZones((cur) => toggleValue(cur, zone.key))}
                        className={clsx(
                          "rounded-full border px-4 py-2 text-sm font-medium transition-all",
                          selectedZones.includes(zone.key)
                            ? "border-primary-600 bg-primary-600 text-white shadow-sm"
                            : "border-slate-200 bg-slate-50 text-slate-700 hover:border-primary-200 hover:bg-primary-50",
                        )}
                      >
                        {zone.emoji} {zone.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Secteurs */}
                <div className="mt-7">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
                    🏷️ Secteurs d'activité
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {SECTORS.map((sector) => (
                      <button
                        key={sector}
                        type="button"
                        onClick={() => setSectors((cur) => toggleValue(cur, sector))}
                        className={clsx(
                          "rounded-full border px-4 py-2 text-sm font-medium transition-all",
                          sectors.includes(sector)
                            ? "border-emerald-600 bg-emerald-600 text-white shadow-sm"
                            : "border-slate-200 bg-slate-50 text-slate-700 hover:border-emerald-200 hover:bg-emerald-50",
                        )}
                      >
                        {SECTOR_LABELS[sector] ?? sector}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Analyse dynamique */}
                <div className={clsx(
                  "mt-6 rounded-2xl border px-5 py-4 transition-all duration-300",
                  analysisPhase === 2
                    ? "border-emerald-200 bg-gradient-to-r from-emerald-50 to-green-50/60"
                    : analysisPhase === 1
                      ? "border-blue-200 bg-blue-50/60"
                      : "border-slate-100 bg-slate-50/50",
                )}>
                  {analysisPhase === 0 && (
                    <p className="text-sm text-slate-400 text-center py-1">
                      Sélectionnez une zone pour lancer l'analyse…
                    </p>
                  )}
                  {analysisPhase === 1 && (
                    <div className="flex items-center gap-3">
                      <Loader2 className="h-4 w-4 animate-spin text-blue-600 shrink-0" />
                      <p className="text-sm font-medium text-blue-700">🔍 Analyse en cours…</p>
                    </div>
                  )}
                  {analysisPhase === 2 && (
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-emerald-800">
                          🎯 Nous avons identifié{" "}
                          <span className="text-2xl font-bold text-emerald-700">{simCount}</span>{" "}
                          financements potentiels correspondant à votre profil
                        </p>
                        {sectors.length > 0 && selectedZones.length > 0 && (
                          <p className="mt-1 text-xs text-emerald-600">
                            {selectedZones.length} zone{selectedZones.length > 1 ? "s" : ""} · {sectors.length} secteur{sectors.length > 1 ? "s" : ""}
                          </p>
                        )}
                      </div>
                      <CheckCircle2 className="h-8 w-8 text-emerald-500 shrink-0" />
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ═══════════════════════════════════════════════════════════════ */}
            {/* ÉTAPE 2 — Loading screen                                        */}
            {/* ═══════════════════════════════════════════════════════════════ */}
            {step === 2 && (
              <div className="w-full max-w-md mx-auto rounded-3xl border border-slate-200/80 bg-white p-8 shadow-[0_30px_80px_-30px_rgba(37,99,235,0.2)] text-center">
                {/* Spinner */}
                <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-primary-100 to-blue-200 shadow-inner">
                  <div className="h-10 w-10 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
                </div>

                <h2 className="text-xl font-bold text-slate-950">
                  Analyse de votre profil en cours…
                </h2>
                <p className="mt-2 text-sm text-slate-400">Identification des financements les plus pertinents pour vous.</p>

                {/* Checks progressifs */}
                <div className="mt-8 space-y-3 text-left">
                  {LOADING_CHECKS.map((check, i) => (
                    <div
                      key={check}
                      className={clsx(
                        "flex items-center gap-3 rounded-xl border px-4 py-3 transition-all duration-500",
                        loadingChecks > i
                          ? "border-emerald-200 bg-emerald-50/70"
                          : "border-slate-100 bg-slate-50/50 opacity-40",
                      )}
                    >
                      <div className={clsx(
                        "flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-all",
                        loadingChecks > i ? "bg-emerald-500" : "bg-slate-200",
                      )}>
                        {loadingChecks > i && (
                          <svg className="h-3 w-3 text-white" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l2.5 2.5L10 3.5" />
                          </svg>
                        )}
                      </div>
                      <span className="text-sm font-medium text-slate-700">{check}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ═══════════════════════════════════════════════════════════════ */}
            {/* ÉTAPE 3 — Type de financement + Résultat                        */}
            {/* ═══════════════════════════════════════════════════════════════ */}
            {step === 3 && (
              <div className="space-y-6">
                {/* Titre */}
                <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_20px_60px_-30px_rgba(15,23,42,0.15)] sm:p-8">
                  <h1 className="text-xl font-bold text-slate-950 sm:text-2xl">
                    Quel type de financement vous intéresse ?
                  </h1>
                  <p className="mt-1.5 text-sm text-slate-500">
                    Sélectionnez un type pour révéler votre analyse complète.
                  </p>

                  {/* Cards scope */}
                  <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
                    {FINANCING_SCOPES.map(({ key, label, sub, icon: Icon }) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => selectScope(key)}
                        className={clsx(
                          "rounded-3xl border p-5 text-left transition-all hover:-translate-y-0.5",
                          financingScope === key
                            ? "border-violet-300 bg-violet-50 shadow-[0_12px_32px_-20px_rgba(124,58,237,0.35)]"
                            : "border-slate-200 bg-white hover:border-violet-200 hover:bg-violet-50/40",
                        )}
                      >
                        <span className={clsx(
                          "flex h-12 w-12 items-center justify-center rounded-2xl transition-colors",
                          financingScope === key ? "bg-violet-600 text-white" : "bg-slate-100 text-slate-600",
                        )}>
                          <Icon className="h-6 w-6" />
                        </span>
                        <p className="mt-4 font-semibold text-slate-950">{label}</p>
                        <p className="mt-1.5 text-sm leading-6 text-slate-500">{sub}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Bloc résultat — apparaît après sélection */}
                <div className={clsx(
                  "transition-all duration-500",
                  resultVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none",
                )}>
                  <div className="rounded-3xl border-2 border-primary-200 bg-gradient-to-br from-primary-50 via-white to-blue-50/40 p-6 shadow-[0_20px_60px_-30px_rgba(37,99,235,0.25)] sm:p-8">
                    {/* Header résultat */}
                    <div className="flex items-center gap-3 mb-6">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-600 text-white shadow-sm">
                        <Target className="h-6 w-6" />
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-widest text-primary-600">Résultat de votre analyse</p>
                        <p className="text-2xl font-bold text-slate-950">{simCount} financements disponibles</p>
                      </div>
                    </div>

                    {/* KPIs */}
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 mb-6">
                      {financingScope !== "private" && breakdown.subventions > 0 && (
                        <div className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50/80 px-4 py-3">
                          <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
                          <div>
                            <p className="text-xl font-bold text-emerald-800">{breakdown.subventions}</p>
                            <p className="text-xs text-emerald-600">subventions prioritaires</p>
                          </div>
                        </div>
                      )}
                      {financingScope !== "public" && breakdown.investisseurs > 0 && (
                        <div className="flex items-center gap-3 rounded-2xl border border-violet-200 bg-violet-50/80 px-4 py-3">
                          <TrendingUp className="h-5 w-5 text-violet-600 shrink-0" />
                          <div>
                            <p className="text-xl font-bold text-violet-800">{breakdown.investisseurs}</p>
                            <p className="text-xs text-violet-600">investisseurs pertinents</p>
                          </div>
                        </div>
                      )}
                      <div className="flex items-center gap-3 rounded-2xl border border-orange-200 bg-orange-50/80 px-4 py-3">
                        <Clock className="h-5 w-5 text-orange-600 shrink-0" />
                        <div>
                          <p className="text-xl font-bold text-orange-800">{breakdown.urgentes}</p>
                          <p className="text-xs text-orange-600">opportunités urgentes (&lt;30j)</p>
                        </div>
                      </div>
                    </div>

                    {/* Projection financière */}
                    <div className="rounded-2xl border border-primary-200 bg-white/80 px-5 py-4 mb-6">
                      <div className="flex items-center gap-3">
                        <DollarSign className="h-5 w-5 text-primary-600 shrink-0" />
                        <div>
                          <p className="text-xs text-primary-600 font-semibold uppercase tracking-wider">💰 Potentiel estimé</p>
                          <p className="text-xl font-bold text-slate-950">
                            {formatAmount(breakdown.projMin)} à {formatAmount(breakdown.projMax)}
                          </p>
                          <p className="text-xs text-slate-400 mt-0.5">Estimation basée sur votre profil et vos zones</p>
                        </div>
                      </div>
                    </div>

                    {/* Erreur */}
                    {error && (
                      <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                        {error}
                      </div>
                    )}

                    {/* CTA principal */}
                    <button
                      type="button"
                      onClick={finishOnboarding}
                      disabled={saving}
                      className="w-full flex items-center justify-center gap-2 rounded-2xl bg-primary-600 px-6 py-4 text-base font-bold text-white shadow-lg shadow-primary-500/30 transition-all hover:bg-primary-700 hover:shadow-xl disabled:opacity-60"
                    >
                      {saving ? (
                        <>
                          <Loader2 className="h-5 w-5 animate-spin" />
                          Préparation de votre espace…
                        </>
                      ) : (
                        <>
                          <Zap className="h-5 w-5" />
                          Voir mes {simCount} financements
                          <ArrowRight className="h-5 w-5" />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ═══════════════════════════════════════════════════════════════ */}
            {/* ÉTAPE 4 — Terminé                                               */}
            {/* ═══════════════════════════════════════════════════════════════ */}
            {step === 4 && (
              <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_20px_60px_-30px_rgba(15,23,42,0.2)] sm:p-8">
                <div className="rounded-3xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-green-50/50 p-6">
                  <div className="flex items-start gap-4">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-emerald-500 text-white shadow-sm">
                      <CheckCircle2 className="h-6 w-6" />
                    </div>
                    <div>
                      <h1 className="text-xl font-bold text-emerald-950 sm:text-2xl">
                        Votre veille est prête ! 🎉
                      </h1>
                      <p className="mt-2 text-sm leading-6 text-emerald-800">
                        La veille <span className="font-semibold">«&nbsp;{createdAlertName}&nbsp;»</span> a été créée.
                        Votre catalogue est maintenant personnalisé — seules les opportunités correspondant à votre profil s'afficheront.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={openOpportunities}
                    className="btn-primary"
                  >
                    <Zap className="h-4 w-4" />
                    Voir mes opportunités maintenant
                  </button>
                  <button
                    type="button"
                    onClick={() => router.push("/")}
                    className="btn-secondary"
                  >
                    Accéder au dashboard
                    <ArrowRight className="h-4 w-4" />
                  </button>
                  <Link href="/alerts" className="btn-secondary">
                    <Bell className="h-4 w-4" />
                    Ma veille
                  </Link>
                </div>
              </div>
            )}

            {/* ── Navigation (steps 0, 1, 3 seulement) ───────────────────── */}
            {(step === 0 || step === 1 || step === 3) && (
              <div className="mt-6 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setStep((cur) => (cur === 3 ? 1 : Math.max(0, cur - 1)))}
                  disabled={step === 0}
                  className="btn-secondary text-sm disabled:opacity-30"
                >
                  Retour
                </button>

                {step < 3 && (
                  <button
                    type="button"
                    onClick={() => setStep((cur) => (cur === 1 ? 2 : cur + 1))}
                    disabled={!canContinue}
                    className="btn-primary text-sm disabled:opacity-50"
                  >
                    Continuer
                    <ArrowRight className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}

            {/* Indication bas de page */}
            {step < 4 && step !== 2 && (
              <p className="mt-4 text-center text-xs text-slate-400">
                Toutes ces informations peuvent être modifiées à tout moment dans vos préférences.
              </p>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
