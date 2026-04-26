"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  ArrowRight, Bell, BriefcaseBusiness, Building2, CheckCircle2,
  Globe2, Landmark, Loader2, MapPin, Rocket, Sparkles, Tags,
  TrendingUp, Users, ChevronRight,
} from "lucide-react";
import clsx from "clsx";

import { alerts, devices, relevance } from "@/lib/api";
import { COUNTRIES, SECTORS } from "@/lib/constants";
import { Device, DEVICE_TYPE_LABELS } from "@/lib/types";
import {
  queueSavedSearch, saveSearch, saveUserPreferences,
  getUserPreferences, type SavedSearch,
} from "@/lib/workspace";

// ── Profils ───────────────────────────────────────────────────────────────────
const PROFILES = [
  {
    key: "entrepreneur",
    label: "Entrepreneur",
    description: "Je cherche des aides, concours ou financements pour mon entreprise.",
    icon: Rocket,
    sectors: ["agriculture", "numerique", "energie"],
  },
  {
    key: "association",
    label: "Association",
    description: "Je suis une structure associative ou ESS avec des projets à financer.",
    icon: Users,
    sectors: ["social", "education", "culture"],
  },
  {
    key: "collectivite",
    label: "Collectivité",
    description: "Je suis une institution locale ou un acteur territorial.",
    icon: Landmark,
    sectors: ["environnement", "energie", "immobilier"],
  },
  {
    key: "investisseur",
    label: "Investisseur",
    description: "Je suis un fonds, business angel ou acteur de l'investissement.",
    icon: BriefcaseBusiness,
    sectors: ["finance", "numerique", "sante"],
  },
  {
    key: "consultant",
    label: "Consultant",
    description: "J'accompagne plusieurs clients et veux surveiller les opportunités.",
    icon: Globe2,
    sectors: ["agriculture", "energie", "numerique"],
  },
] as const;

// ── Scope financement ─────────────────────────────────────────────────────────
type FinancingScope = "public" | "private" | "both";

const PUBLIC_TYPES  = ["subvention", "aap", "concours", "pret", "accompagnement", "garantie"];
const PRIVATE_TYPES = ["investissement"];
const ALL_TYPES     = [...PUBLIC_TYPES, ...PRIVATE_TYPES];

const FINANCING_SCOPES: {
  key: FinancingScope; label: string; sub: string;
  icon: typeof Building2; types: string[];
}[] = [
  {
    key: "public",
    label: "Financement public",
    sub: "Subventions, AAP, concours, prêts, accompagnement…",
    icon: Building2,
    types: PUBLIC_TYPES,
  },
  {
    key: "private",
    label: "Investisseurs & fonds privés",
    sub: "Fonds d'investissement, business angels, capital-risque…",
    icon: TrendingUp,
    types: PRIVATE_TYPES,
  },
  {
    key: "both",
    label: "Les deux",
    sub: "Je recherche à la fois des financements publics et privés.",
    icon: Sparkles,
    types: ALL_TYPES,
  },
];

// ── Bénéfices affichés dans le panneau gauche ─────────────────────────────────
const BENEFITS = [
  { text: "Un catalogue filtré selon votre profil exact" },
  { text: "Des alertes automatiques sur vos opportunités" },
  { text: "Des recommandations triées par pertinence" },
  { text: "Un suivi de vos candidatures en un seul endroit" },
];

const STEP_LABELS = ["Profil", "Zones", "Secteurs", "Financement", "Résultats"];

function toggleValue(values: string[], value: string) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

// ── Composant principal ───────────────────────────────────────────────────────
export default function OnboardingPage() {
  const router = useRouter();

  const [step, setStep]                     = useState(0);
  const [profile, setProfile]               = useState<string>("");
  const [countries, setCountries]           = useState<string[]>([]);
  const [sectors, setSectors]               = useState<string[]>([]);
  const [financingScope, setFinancingScope] = useState<FinancingScope | "">("");
  const [saving, setSaving]                 = useState(false);
  const [createdAlertName, setCreatedAlertName] = useState<string | null>(null);
  const [recommendations, setRecommendations]   = useState<Device[]>([]);
  const [error, setError]                   = useState<string | null>(null);

  const selectedProfile = useMemo(
    () => PROFILES.find((item) => item.key === profile),
    [profile],
  );

  const deviceTypes = useMemo(() => {
    const scope = FINANCING_SCOPES.find((s) => s.key === financingScope);
    return scope?.types ?? [];
  }, [financingScope]);

  const canContinue = useMemo(() => {
    if (step === 0) return !!profile;
    if (step === 1) return countries.length > 0;
    if (step === 2) return sectors.length > 0;
    if (step === 3) return !!financingScope;
    return true;
  }, [countries.length, financingScope, profile, sectors.length, step]);

  const selectProfile = (key: string) => {
    const next = PROFILES.find((item) => item.key === key);
    setProfile(key);
    if (next) setSectors((cur) => cur.length ? cur : [...next.sectors]);
    if (!financingScope) {
      setFinancingScope(key === "investisseur" ? "private" : "public");
    }
  };

  const selectScope = (scope: FinancingScope) => {
    setFinancingScope(scope);
    localStorage.setItem("kafundo_financing_scope", scope);
  };

  const buildSavedSearch = (): SavedSearch => ({
    id: crypto.randomUUID(),
    name: `Veille ${selectedProfile?.label || "personnalisée"}`,
    title: financingScope === "private" ? "Fonds & Investisseurs" : "Opportunités recommandées",
    path: financingScope === "private" ? "/devices/private" : "/devices",
    resultCount: null,
    savedAt: new Date().toISOString(),
    filters: {
      q: sectors.slice(0, 2).join(" "),
      countries,
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

    const alertName = `Veille ${selectedProfile?.label || "Kafundo"} — ${countries.slice(0, 2).join(", ")}`;
    const savedSearch = buildSavedSearch();

    try {
      const data = await devices.list({
        q: sectors.slice(0, 2).join(" ") || undefined,
        countries,
        sectors,
        device_types: deviceTypes,
        status: financingScope === "private" ? undefined : ["open", "recurring"],
        sort_by: "relevance",
        page: 1,
        page_size: 5,
      });

      await relevance.saveProfile({
        organization_type: profile || null,
        countries,
        sectors,
        target_funding_types: deviceTypes,
        strategic_priorities: sectors.slice(0, 3),
      });

      const existingProjects = await relevance.listProjects().catch(() => []);
      if (!Array.isArray(existingProjects) || existingProjects.length === 0) {
        await relevance.createProject({
          name: `Projet ${selectedProfile?.label || "prioritaire"}`,
          summary: "Projet créé automatiquement depuis l'onboarding Kafundo.",
          countries,
          sectors,
          target_funding_types: deviceTypes,
          is_primary: true,
        });
      }

      const items = Array.isArray(data?.items) ? data.items : [];
      try {
        const recData = await relevance.recommendations({ page_size: 5 });
        const recItems = Array.isArray(recData?.items)
          ? recData.items.map((i: any) => i.device).filter(Boolean)
          : [];
        setRecommendations(recItems.length ? recItems : items);
      } catch {
        setRecommendations(items);
      }

      await alerts.create({
        name: alertName,
        frequency: "daily",
        channels: ["email", "dashboard"],
        alert_types: ["new", "updated", "closing_soon"],
        criteria: {
          countries,
          sectors,
          device_types: deviceTypes,
          keywords: sectors,
          close_within_days: 30,
        },
      });

      saveSearch({ ...savedSearch, resultCount: data?.total ?? items.length });
      saveUserPreferences({
        ...getUserPreferences(),
        onboardingCompleted: true,
        onboardingProfile: profile,
        onboardingCountries: countries,
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

  const goToDashboard = () => {
    router.push("/");
  };

  const openConfiguredSearch = () => {
    queueSavedSearch(buildSavedSearch());
    router.push(financingScope === "private" ? "/devices/private" : "/devices");
  };

  // ── Rendu ─────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/40">

      {/* ── Barre de navigation ─────────────────────────────────────────────── */}
      <header className="flex h-16 items-center justify-between border-b border-slate-200/70 bg-white/80 px-6 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <Image
            src="/brand/kafundo-picto.png"
            alt="Kafundo"
            width={36}
            height={36}
            className="h-9 w-9 rounded-xl object-cover"
          />
          <div>
            <span className="block text-sm font-bold text-slate-900">Kafundo</span>
            <span className="block text-[10px] text-slate-400 leading-tight">Trouve tes financements</span>
          </div>
        </div>

        {/* Indicateur de progression — étapes */}
        {step < 4 && (
          <div className="hidden items-center gap-1.5 sm:flex">
            {STEP_LABELS.slice(0, 4).map((label, i) => (
              <div key={label} className="flex items-center gap-1.5">
                <div className={clsx(
                  "flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold transition-colors",
                  i < step
                    ? "bg-primary-600 text-white"
                    : i === step
                      ? "border-2 border-primary-600 text-primary-700"
                      : "border-2 border-slate-200 text-slate-400",
                )}>
                  {i < step ? "✓" : i + 1}
                </div>
                <span className={clsx(
                  "text-xs font-medium",
                  i <= step ? "text-slate-700" : "text-slate-400",
                )}>
                  {label}
                </span>
                {i < 3 && <ChevronRight className="h-3.5 w-3.5 text-slate-300" />}
              </div>
            ))}
          </div>
        )}

        <div className="text-xs text-slate-400">
          {step < 4 ? `Étape ${step + 1} / 4` : "Configuration terminée"}
        </div>
      </header>

      {/* ── Corps ──────────────────────────────────────────────────────────── */}
      <div className="mx-auto flex min-h-[calc(100vh-64px)] max-w-7xl flex-col lg:flex-row">

        {/* ─ Panneau gauche (branding + bénéfices) ─ */}
        {step < 4 && (
          <aside className="hidden lg:flex lg:w-80 xl:w-96 flex-col justify-center border-r border-slate-200/70 bg-white/60 px-10 py-12">
            <div className="mb-8">
              <span className="inline-block rounded-full bg-primary-100 px-3 py-1 text-xs font-semibold text-primary-700">
                Configuration initiale
              </span>
              <h2 className="mt-4 text-2xl font-bold tracking-tight text-slate-950">
                Paramétrez Kafundo<br />en 2 minutes.
              </h2>
              <p className="mt-3 text-sm leading-6 text-slate-500">
                Ces informations nous permettent de vous afficher uniquement les opportunités qui correspondent réellement à votre profil.
              </p>
            </div>

            <ul className="space-y-4">
              {BENEFITS.map(({ text }, i) => (
                <li key={i} className="flex items-start gap-3">
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary-600 text-white">
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2 6l2.5 2.5L10 3.5" />
                    </svg>
                  </div>
                  <span className="text-sm text-slate-600">{text}</span>
                </li>
              ))}
            </ul>

            <div className="mt-10 rounded-2xl border border-primary-100 bg-primary-50/60 px-4 py-4">
              <p className="text-xs font-semibold text-primary-700">💡 Pourquoi c'est important</p>
              <p className="mt-2 text-xs leading-5 text-primary-800">
                Sans configuration, vous verrez tous les dispositifs disponibles — plus de 1 900. Avec votre profil, seules les opportunités pertinentes s'affichent.
              </p>
            </div>
          </aside>
        )}

        {/* ─ Contenu principal (wizard) ─ */}
        <main className="flex flex-1 flex-col justify-center px-4 py-8 sm:px-8 lg:px-12">
          <div className="mx-auto w-full max-w-3xl">

            {/* Barre de progression mobile */}
            {step < 4 && (
              <div className="mb-6 flex gap-1.5 lg:hidden">
                {STEP_LABELS.slice(0, 4).map((_, i) => (
                  <div
                    key={i}
                    className={clsx(
                      "h-1.5 flex-1 rounded-full transition-colors",
                      i <= step ? "bg-primary-600" : "bg-slate-200",
                    )}
                  />
                ))}
              </div>
            )}

            {/* Carte étape */}
            <div className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_20px_60px_-30px_rgba(15,23,42,0.2)] sm:p-8">

              {/* ── Étape 0 : Profil ── */}
              {step === 0 && (
                <div>
                  <h1 className="text-xl font-bold text-slate-950 sm:text-2xl">
                    Quel est votre profil principal ?
                  </h1>
                  <p className="mt-1.5 text-sm text-slate-500">
                    Ce choix oriente les opportunités affichées dans votre catalogue.
                  </p>
                  <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
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
                            profile === item.key ? "bg-primary-600 text-white" : "bg-slate-100 text-slate-600 group-hover:bg-primary-100 group-hover:text-primary-700",
                          )}>
                            <Icon className="h-5 w-5" />
                          </span>
                          <p className="mt-3.5 font-semibold text-slate-950">{item.label}</p>
                          <p className="mt-1.5 text-xs leading-5 text-slate-500">{item.description}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* ── Étape 1 : Zones géographiques ── */}
              {step === 1 && (
                <div>
                  <div className="flex items-center gap-3 mb-4">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary-100 text-primary-700">
                      <MapPin className="h-5 w-5" />
                    </span>
                    <div>
                      <h1 className="text-xl font-bold text-slate-950 sm:text-2xl">
                        Sur quels pays ou zones voulez-vous veiller ?
                      </h1>
                      <p className="text-sm text-slate-500">Sélectionnez au moins une zone. Modifiable à tout moment.</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {COUNTRIES.map((country) => (
                      <button
                        key={country}
                        type="button"
                        onClick={() => setCountries((cur) => toggleValue(cur, country))}
                        className={clsx(
                          "rounded-full border px-4 py-2 text-sm font-medium transition-all",
                          countries.includes(country)
                            ? "border-primary-600 bg-primary-600 text-white shadow-sm"
                            : "border-slate-200 bg-slate-50 text-slate-700 hover:border-primary-200 hover:bg-primary-50",
                        )}
                      >
                        {country}
                      </button>
                    ))}
                  </div>
                  {countries.length > 0 && (
                    <p className="mt-4 text-xs text-primary-600 font-medium">
                      {countries.length} zone{countries.length > 1 ? "s" : ""} sélectionnée{countries.length > 1 ? "s" : ""}
                    </p>
                  )}
                </div>
              )}

              {/* ── Étape 2 : Secteurs ── */}
              {step === 2 && (
                <div>
                  <div className="flex items-center gap-3 mb-4">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
                      <Tags className="h-5 w-5" />
                    </span>
                    <div>
                      <h1 className="text-xl font-bold text-slate-950 sm:text-2xl">
                        Quels secteurs souhaitez-vous suivre ?
                      </h1>
                      <p className="text-sm text-slate-500">Seules les opportunités de ces secteurs s'afficheront dans votre catalogue.</p>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {SECTORS.map((sector) => (
                      <button
                        key={sector}
                        type="button"
                        onClick={() => setSectors((cur) => toggleValue(cur, sector))}
                        className={clsx(
                          "rounded-full border px-4 py-2 text-sm font-medium capitalize transition-all",
                          sectors.includes(sector)
                            ? "border-emerald-600 bg-emerald-600 text-white shadow-sm"
                            : "border-slate-200 bg-slate-50 text-slate-700 hover:border-emerald-200 hover:bg-emerald-50",
                        )}
                      >
                        {sector}
                      </button>
                    ))}
                  </div>
                  {sectors.length > 0 && (
                    <p className="mt-4 text-xs text-emerald-600 font-medium">
                      {sectors.length} secteur{sectors.length > 1 ? "s" : ""} sélectionné{sectors.length > 1 ? "s" : ""}
                    </p>
                  )}
                </div>
              )}

              {/* ── Étape 3 : Type de financement ── */}
              {step === 3 && (
                <div>
                  <div className="flex items-center gap-3 mb-4">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-violet-100 text-violet-700">
                      <Sparkles className="h-5 w-5" />
                    </span>
                    <div>
                      <h1 className="text-xl font-bold text-slate-950 sm:text-2xl">
                        Quel type de financement recherchez-vous ?
                      </h1>
                      <p className="text-sm text-slate-500">
                        Ce choix détermine quelles sections du catalogue vous seront affichées.
                      </p>
                    </div>
                  </div>
                  <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
                    {FINANCING_SCOPES.map(({ key, label, sub, icon: Icon, types }) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => selectScope(key)}
                        className={clsx(
                          "rounded-3xl border p-5 text-left transition-all hover:-translate-y-0.5",
                          financingScope === key
                            ? "border-violet-300 bg-violet-50 shadow-[0_12px_32px_-20px_rgba(124,58,237,0.4)]"
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
                        <p className="mt-2 text-sm leading-6 text-slate-500">{sub}</p>
                        <div className="mt-4 flex flex-wrap gap-1.5">
                          {types.slice(0, 4).map((t) => (
                            <span key={t} className={clsx(
                              "rounded-full px-2.5 py-1 text-[11px] font-medium",
                              financingScope === key ? "bg-violet-100 text-violet-700" : "bg-slate-100 text-slate-500",
                            )}>
                              {DEVICE_TYPE_LABELS[t] || t}
                            </span>
                          ))}
                          {types.length > 4 && (
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-400">
                              +{types.length - 4}
                            </span>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* ── Étape 4 : Résultats ── */}
              {step === 4 && (
                <div>
                  {/* Succès */}
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

                  {/* CTAs */}
                  <div className="mt-6 flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={goToDashboard}
                      className="btn-primary"
                    >
                      Accéder à mon dashboard
                      <ArrowRight className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={openConfiguredSearch}
                      className="btn-secondary"
                    >
                      {financingScope === "private" ? "Voir les investisseurs" : "Voir mes opportunités"}
                    </button>
                    <Link href="/alerts" className="btn-secondary">
                      <Bell className="h-4 w-4" />
                      Ma veille
                    </Link>
                  </div>

                  {/* Aperçu résultats */}
                  {recommendations.length > 0 && (
                    <>
                      <h2 className="mt-8 text-base font-semibold text-slate-900">
                        5 premières opportunités pour vous
                      </h2>
                      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
                        {recommendations.map((device) => (
                          <Link
                            key={device.id}
                            href={`/devices/${device.id}`}
                            className="rounded-2xl border border-slate-200 bg-white p-4 transition-colors hover:border-primary-200 hover:bg-primary-50/40"
                          >
                            <p className="line-clamp-3 text-sm font-semibold leading-6 text-slate-950">{device.title}</p>
                            <p className="mt-2 line-clamp-1 text-xs text-slate-500">{device.organism}</p>
                            <span className="mt-3 inline-block rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                              {device.country}
                            </span>
                          </Link>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Erreur */}
              {error && (
                <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              {/* ── Navigation ─────────────────────────────────────────────── */}
              {step < 4 && (
                <div className="mt-8 flex items-center justify-between border-t border-slate-100 pt-6">
                  <button
                    type="button"
                    onClick={() => setStep((cur) => Math.max(0, cur - 1))}
                    className="btn-secondary text-sm"
                    disabled={step === 0}
                  >
                    Retour
                  </button>

                  {step === 3 ? (
                    <button
                      type="button"
                      onClick={finishOnboarding}
                      disabled={!canContinue || saving}
                      className="btn-primary text-sm disabled:opacity-50"
                    >
                      {saving ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Bell className="h-4 w-4" />
                      )}
                      Créer ma veille personnalisée
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setStep((cur) => cur + 1)}
                      disabled={!canContinue}
                      className="btn-primary text-sm disabled:opacity-50"
                    >
                      Continuer
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Indication sous la carte */}
            {step < 4 && (
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
