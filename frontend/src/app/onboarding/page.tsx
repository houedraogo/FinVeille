"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Bell,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  Globe2,
  Landmark,
  Loader2,
  MapPin,
  Rocket,
  Sparkles,
  Tags,
  TrendingUp,
  Users,
} from "lucide-react";
import clsx from "clsx";

import AppLayout from "@/components/AppLayout";
import { alerts, devices, relevance } from "@/lib/api";
import { COUNTRIES, SECTORS } from "@/lib/constants";
import { Device, DEVICE_TYPE_LABELS } from "@/lib/types";
import {
  queueSavedSearch,
  saveSearch,
  saveUserPreferences,
  getUserPreferences,
  type SavedSearch,
} from "@/lib/workspace";

// ── Profils ──────────────────────────────────────────────────────────────────
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

const PUBLIC_TYPES = ["subvention", "aap", "concours", "pret", "accompagnement", "garantie"];
const PRIVATE_TYPES = ["investissement"];
const ALL_TYPES = [...PUBLIC_TYPES, ...PRIVATE_TYPES];

const FINANCING_SCOPES: { key: FinancingScope; label: string; sub: string; icon: typeof Building2; types: string[] }[] = [
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

function toggleValue(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

// ── Composant principal ───────────────────────────────────────────────────────
export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<string>("");
  const [countries, setCountries] = useState<string[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [financingScope, setFinancingScope] = useState<FinancingScope | "">("");
  const [saving, setSaving] = useState(false);
  const [createdAlertName, setCreatedAlertName] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Device[]>([]);
  const [error, setError] = useState<string | null>(null);

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
    // Pré-remplir les secteurs si pas encore renseignés
    if (next) setSectors((cur) => cur.length ? cur : [...next.sectors]);
    // Pré-sélectionner le scope : investisseur → private, sinon public
    if (!financingScope) {
      setFinancingScope(key === "investisseur" ? "private" : "public");
    }
  };

  const selectScope = (scope: FinancingScope) => {
    setFinancingScope(scope);
    // Sauvegarder immédiatement dans localStorage pour la sidebar
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
      localStorage.setItem("kafundo_financing_scope", financingScope);
      setCreatedAlertName(alertName);
      setStep(4);
    } catch (e: any) {
      setError(e.message || "Impossible de finaliser la configuration.");
    } finally {
      setSaving(false);
    }
  };

  const openConfiguredSearch = () => {
    queueSavedSearch(buildSavedSearch());
    router.push(financingScope === "private" ? "/devices/private" : "/devices");
  };

  const skipOnboarding = () => {
    saveUserPreferences({ ...getUserPreferences(), onboardingCompleted: true });
    localStorage.setItem("kafundo_onboarding_completed", "1");
    router.push("/workspace");
  };

  const STEP_LABELS = ["Profil", "Zones", "Secteurs", "Financement", "Résultats"];

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl">
        {/* Hero */}
        <div className="mb-6 overflow-hidden rounded-[34px] border border-slate-200 bg-[radial-gradient(circle_at_top_left,#dcfce7,transparent_32%),linear-gradient(135deg,#ffffff_0%,#f8fafc_52%,#eef2ff_100%)] p-6 shadow-[0_18px_55px_-34px_rgba(15,23,42,0.35)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-semibold text-primary-700">Configuration de veille</p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
                Paramétrez Kafundo en moins de 2 minutes.
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
                On part de votre profil, de vos pays, secteurs et type de financement pour vous afficher uniquement les opportunités qui vous correspondent.
              </p>
            </div>
            <button type="button" onClick={skipOnboarding} className="btn-secondary text-xs">
              Passer pour le moment
            </button>
          </div>
        </div>

        {/* Indicateur de progression */}
        <div className="mb-6 grid grid-cols-5 gap-2">
          {STEP_LABELS.map((label, index) => (
            <div key={label} className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
              <div className={clsx("mb-2 h-1.5 rounded-full", index <= step ? "bg-primary-600" : "bg-slate-100")} />
              <p className={clsx("text-xs font-semibold", index <= step ? "text-slate-900" : "text-slate-400")}>{label}</p>
            </div>
          ))}
        </div>

        {/* Carte étape */}
        <div className="rounded-[30px] border border-slate-200 bg-white p-5 shadow-[0_18px_55px_-34px_rgba(15,23,42,0.35)]">

          {/* ── Étape 0 : Profil ── */}
          {step === 0 && (
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Quel est votre profil principal ?</h2>
              <p className="mt-1 text-sm text-slate-500">Cela sert à orienter les opportunités affichées.</p>
              <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
                {PROFILES.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => selectProfile(item.key)}
                      className={clsx(
                        "rounded-3xl border p-4 text-left transition-all hover:-translate-y-0.5",
                        profile === item.key
                          ? "border-primary-300 bg-primary-50 shadow-[0_16px_42px_-30px_rgba(37,99,235,0.45)]"
                          : "border-slate-200 bg-white hover:border-primary-200",
                      )}
                    >
                      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-950 text-white">
                        <Icon className="h-5 w-5" />
                      </span>
                      <p className="mt-4 font-semibold text-slate-950">{item.label}</p>
                      <p className="mt-2 text-sm leading-6 text-slate-500">{item.description}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Étape 1 : Pays / Zones ── */}
          {step === 1 && (
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-950">
                <MapPin className="h-5 w-5 text-primary-600" />
                Sur quels pays ou zones voulez-vous veiller ?
              </h2>
              <p className="mt-1 text-sm text-slate-500">Choisissez au moins une zone. Modifiable plus tard.</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {COUNTRIES.map((country) => (
                  <button
                    key={country}
                    type="button"
                    onClick={() => setCountries((cur) => toggleValue(cur, country))}
                    className={clsx(
                      "rounded-full border px-4 py-2 text-sm font-medium transition-colors",
                      countries.includes(country)
                        ? "border-primary-600 bg-primary-600 text-white"
                        : "border-slate-200 bg-slate-50 text-slate-700 hover:border-primary-200 hover:bg-primary-50",
                    )}
                  >
                    {country}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ── Étape 2 : Secteurs ── */}
          {step === 2 && (
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-950">
                <Tags className="h-5 w-5 text-emerald-600" />
                Quels secteurs souhaitez-vous suivre ?
              </h2>
              <p className="mt-1 text-sm text-slate-500">Les secteurs filtrent les opportunités affichées dans votre catalogue.</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {SECTORS.map((sector) => (
                  <button
                    key={sector}
                    type="button"
                    onClick={() => setSectors((cur) => toggleValue(cur, sector))}
                    className={clsx(
                      "rounded-full border px-4 py-2 text-sm font-medium capitalize transition-colors",
                      sectors.includes(sector)
                        ? "border-emerald-600 bg-emerald-600 text-white"
                        : "border-slate-200 bg-slate-50 text-slate-700 hover:border-emerald-200 hover:bg-emerald-50",
                    )}
                  >
                    {sector}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* ── Étape 3 : Type de financement (PUBLIC / PRIVÉ / LES DEUX) ── */}
          {step === 3 && (
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-950">
                <Sparkles className="h-5 w-5 text-violet-600" />
                Quel type de financement recherchez-vous ?
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Ce choix détermine quelles sections du catalogue vous seront affichées.
              </p>
              <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
                {FINANCING_SCOPES.map(({ key, label, sub, icon: Icon, types }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => selectScope(key)}
                    className={clsx(
                      "rounded-3xl border p-5 text-left transition-all hover:-translate-y-0.5",
                      financingScope === key
                        ? "border-violet-300 bg-violet-50 shadow-[0_16px_42px_-30px_rgba(124,58,237,0.4)]"
                        : "border-slate-200 bg-white hover:border-violet-200 hover:bg-violet-50/40",
                    )}
                  >
                    <span className={clsx(
                      "flex h-12 w-12 items-center justify-center rounded-2xl",
                      financingScope === key ? "bg-violet-600 text-white" : "bg-slate-100 text-slate-600"
                    )}>
                      <Icon className="h-6 w-6" />
                    </span>
                    <p className="mt-4 font-semibold text-slate-950">{label}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-500">{sub}</p>
                    {/* Types inclus */}
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {types.slice(0, 4).map((t) => (
                        <span key={t} className={clsx(
                          "rounded-full px-2.5 py-1 text-[11px] font-medium",
                          financingScope === key ? "bg-violet-100 text-violet-700" : "bg-slate-100 text-slate-500"
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
              <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-6 w-6 text-emerald-600" />
                  <div>
                    <h2 className="text-xl font-semibold text-emerald-950">Votre veille est prête.</h2>
                    <p className="mt-1 text-sm leading-6 text-emerald-800">
                      La veille <span className="font-semibold">{createdAlertName}</span> a été créée.
                      Votre catalogue est maintenant personnalisé : seules les opportunités qui correspondent à votre profil s'afficheront.
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <button type="button" onClick={openConfiguredSearch} className="btn-primary">
                  {financingScope === "private" ? "Voir les investisseurs" : "Voir mes opportunités"}
                  <ArrowRight className="h-4 w-4" />
                </button>
                <Link href="/workspace" className="btn-secondary">Aller dans Mon espace</Link>
                <Link href="/alerts" className="btn-secondary">
                  <Bell className="h-4 w-4" />
                  Voir ma veille
                </Link>
              </div>

              <h3 className="mt-8 text-lg font-semibold text-slate-950">5 opportunités pour démarrer</h3>
              {recommendations.length === 0 ? (
                <div className="mt-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-5 py-8 text-center text-sm text-slate-500">
                  Aucun résultat immédiat. Essayez d'élargir vos pays ou secteurs.
                </div>
              ) : (
                <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-5">
                  {recommendations.map((device) => (
                    <Link
                      key={device.id}
                      href={`/devices/${device.id}`}
                      className="rounded-2xl border border-slate-200 bg-white p-4 transition-colors hover:border-primary-200 hover:bg-primary-50/40"
                    >
                      <p className="line-clamp-3 text-sm font-semibold leading-6 text-slate-950">{device.title}</p>
                      <p className="mt-2 line-clamp-1 text-xs text-slate-500">{device.organism}</p>
                      <p className="mt-3 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">{device.country}</p>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Navigation entre étapes */}
          {step < 4 && (
            <div className="mt-8 flex items-center justify-between border-t border-slate-100 pt-5">
              <button
                type="button"
                onClick={() => setStep((cur) => Math.max(0, cur - 1))}
                className="btn-secondary text-xs"
                disabled={step === 0}
              >
                Retour
              </button>
              {step === 3 ? (
                <button
                  type="button"
                  onClick={finishOnboarding}
                  disabled={!canContinue || saving}
                  className="btn-primary text-xs disabled:opacity-50"
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
                  Créer ma veille personnalisée
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setStep((cur) => cur + 1)}
                  disabled={!canContinue}
                  className="btn-primary text-xs disabled:opacity-50"
                >
                  Continuer
                  <ArrowRight className="h-4 w-4" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
