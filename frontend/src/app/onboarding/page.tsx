"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Bell,
  BriefcaseBusiness,
  CheckCircle2,
  Globe2,
  Landmark,
  Loader2,
  MapPin,
  Rocket,
  Sparkles,
  Tags,
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

const PROFILES = [
  {
    key: "entrepreneur",
    label: "Entrepreneur",
    description: "Je cherche des aides, concours ou financements pour mon entreprise.",
    icon: Rocket,
    sectors: ["agriculture", "numerique", "energie"],
    types: ["subvention", "concours", "pret", "accompagnement"],
  },
  {
    key: "association",
    label: "Association",
    description: "Je suis une structure associative ou ESS avec des projets a financer.",
    icon: Users,
    sectors: ["social", "education", "culture"],
    types: ["subvention", "aap", "accompagnement", "concours"],
  },
  {
    key: "collectivite",
    label: "Collectivite",
    description: "Je suis une institution locale ou un acteur territorial.",
    icon: Landmark,
    sectors: ["environnement", "energie", "immobilier"],
    types: ["subvention", "aap", "pret", "accompagnement"],
  },
  {
    key: "investisseur",
    label: "Investisseur",
    description: "Je suis un fonds, business angel ou acteur de l'investissement.",
    icon: BriefcaseBusiness,
    sectors: ["finance", "numerique", "sante"],
    types: ["investissement", "accompagnement", "concours"],
  },
  {
    key: "consultant",
    label: "Consultant",
    description: "J'accompagne plusieurs clients et veux surveiller les opportunites.",
    icon: Globe2,
    sectors: ["agriculture", "energie", "numerique"],
    types: ["subvention", "aap", "concours", "pret", "investissement"],
  },
] as const;

const DEVICE_TYPES = ["subvention", "concours", "investissement", "pret", "accompagnement", "aap"] as const;

function toggleValue(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<string>("");
  const [countries, setCountries] = useState<string[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [deviceTypes, setDeviceTypes] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [createdAlertName, setCreatedAlertName] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<Device[]>([]);
  const [error, setError] = useState<string | null>(null);

  const selectedProfile = useMemo(
    () => PROFILES.find((item) => item.key === profile),
    [profile],
  );

  const canContinue = useMemo(() => {
    if (step === 0) return !!profile;
    if (step === 1) return countries.length > 0;
    if (step === 2) return sectors.length > 0;
    if (step === 3) return deviceTypes.length > 0;
    return true;
  }, [countries.length, deviceTypes.length, profile, sectors.length, step]);

  const selectProfile = (key: string) => {
    const nextProfile = PROFILES.find((item) => item.key === key);
    setProfile(key);
    if (nextProfile) {
      setSectors((current) => current.length ? current : [...nextProfile.sectors]);
      setDeviceTypes((current) => current.length ? current : [...nextProfile.types]);
    }
  };

  const buildSavedSearch = (): SavedSearch => ({
    id: crypto.randomUUID(),
    name: `Veille ${selectedProfile?.label || "personnalisee"}`,
    title: "Opportunités recommandées",
    path: "/devices",
    resultCount: null,
    savedAt: new Date().toISOString(),
    filters: {
      q: sectors.slice(0, 2).join(" "),
      countries,
      deviceTypes,
      sectors,
      statuses: ["open", "recurring"],
      closingSoon: "",
      hasCloseDate: false,
      sortBy: "relevance",
    },
  });

  const finishOnboarding = async () => {
    setSaving(true);
    setError(null);

    const alertName = `Veille ${selectedProfile?.label || "Kafundo"} - ${countries.slice(0, 2).join(", ")}`;
    const savedSearch = buildSavedSearch();

    try {
      const data = await devices.list({
        q: sectors.slice(0, 2).join(" ") || undefined,
        countries,
        sectors,
        device_types: deviceTypes,
        status: ["open", "recurring"],
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
          summary: `Projet cree automatiquement depuis l'onboarding Kafundo pour orienter les opportunites recommandees.`,
          countries,
          sectors,
          target_funding_types: deviceTypes,
          is_primary: true,
        });
      }

      const items = Array.isArray(data?.items) ? data.items : [];
      try {
        const recommendationData = await relevance.recommendations({ page_size: 5 });
        const recommendationItems = Array.isArray(recommendationData?.items)
          ? recommendationData.items.map((item: any) => item.device).filter(Boolean)
          : [];
        setRecommendations(recommendationItems.length ? recommendationItems : items);
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
      setCreatedAlertName(alertName);
      setStep(4);
    } catch (e: any) {
      setError(e.message || "Impossible de finaliser la configuration.");
    } finally {
      setSaving(false);
    }
  };

  const openConfiguredSearch = () => {
    const savedSearch = buildSavedSearch();
    queueSavedSearch(savedSearch);
    router.push("/devices");
  };

  const skipOnboarding = () => {
    saveUserPreferences({ ...getUserPreferences(), onboardingCompleted: true });
    localStorage.setItem("kafundo_onboarding_completed", "1");
    router.push("/workspace");
  };

  return (
    <AppLayout>
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 overflow-hidden rounded-[34px] border border-slate-200 bg-[radial-gradient(circle_at_top_left,#dcfce7,transparent_32%),linear-gradient(135deg,#ffffff_0%,#f8fafc_52%,#eef2ff_100%)] p-6 shadow-[0_18px_55px_-34px_rgba(15,23,42,0.35)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-sm font-semibold text-primary-700">Configuration de veille</p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
                Parametrez Kafundo en moins de 2 minutes.
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
                On part de votre profil, de vos pays, secteurs et types de financement pour creer une premiere veille et proposer des opportunités pertinentes.
              </p>
            </div>
            <button type="button" onClick={skipOnboarding} className="btn-secondary text-xs">
              Passer pour le moment
            </button>
          </div>
        </div>

        <div className="mb-6 grid grid-cols-5 gap-2">
          {["Profil", "Zones", "Secteurs", "Financements", "Resultats"].map((label, index) => (
            <div key={label} className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
              <div className={clsx("mb-2 h-1.5 rounded-full", index <= step ? "bg-primary-600" : "bg-slate-100")} />
              <p className={clsx("text-xs font-semibold", index <= step ? "text-slate-900" : "text-slate-400")}>{label}</p>
            </div>
          ))}
        </div>

        <div className="rounded-[30px] border border-slate-200 bg-white p-5 shadow-[0_18px_55px_-34px_rgba(15,23,42,0.35)]">
          {step === 0 && (
            <div>
              <h2 className="text-xl font-semibold text-slate-950">Quel est votre profil principal ?</h2>
              <p className="mt-1 text-sm text-slate-500">Cela sert a pre-remplir les secteurs et types de financement utiles.</p>
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

          {step === 1 && (
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-950">
                <MapPin className="h-5 w-5 text-primary-600" />
                Sur quels pays ou zones voulez-vous veiller ?
              </h2>
              <p className="mt-1 text-sm text-slate-500">Choisissez au moins une zone. Vous pourrez modifier cela plus tard.</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {COUNTRIES.map((country) => (
                  <button
                    key={country}
                    type="button"
                    onClick={() => setCountries((current) => toggleValue(current, country))}
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

          {step === 2 && (
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-950">
                <Tags className="h-5 w-5 text-emerald-600" />
                Quels secteurs suivre ?
              </h2>
              <p className="mt-1 text-sm text-slate-500">Les secteurs permettent de mieux filtrer les appels pertinents.</p>
              <div className="mt-5 flex flex-wrap gap-2">
                {SECTORS.map((sector) => (
                  <button
                    key={sector}
                    type="button"
                    onClick={() => setSectors((current) => toggleValue(current, sector))}
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

          {step === 3 && (
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-950">
                <Sparkles className="h-5 w-5 text-violet-600" />
                Quels types de financement recherchez-vous ?
              </h2>
              <p className="mt-1 text-sm text-slate-500">On utilisera ces choix pour creer votre premiere veille.</p>
              <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {DEVICE_TYPES.map((type) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setDeviceTypes((current) => toggleValue(current, type))}
                    className={clsx(
                      "rounded-3xl border px-4 py-4 text-left transition-colors",
                      deviceTypes.includes(type)
                        ? "border-violet-400 bg-violet-50 text-violet-800"
                        : "border-slate-200 bg-white text-slate-700 hover:border-violet-200",
                    )}
                  >
                    <p className="font-semibold">{DEVICE_TYPE_LABELS[type] || type}</p>
                    <p className="mt-1 text-sm text-slate-500">Inclure ce type dans ma veille.</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 4 && (
            <div>
              <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5">
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-6 w-6 text-emerald-600" />
                  <div>
                    <h2 className="text-xl font-semibold text-emerald-950">Votre veille est prete.</h2>
                    <p className="mt-1 text-sm leading-6 text-emerald-800">
                      La veille <span className="font-semibold">{createdAlertName}</span> a ete creee et une recherche est disponible dans Mon espace.
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <button type="button" onClick={openConfiguredSearch} className="btn-primary">
                  Voir tous les resultats
                  <ArrowRight className="h-4 w-4" />
                </button>
                <Link href="/workspace" className="btn-secondary">
                  Aller dans Mon espace
                </Link>
                <Link href="/alerts" className="btn-secondary">
                  <Bell className="h-4 w-4" />
                  Voir ma veille
                </Link>
              </div>

              <h3 className="mt-8 text-lg font-semibold text-slate-950">5 opportunités pour demarrer</h3>
              {recommendations.length === 0 ? (
                <div className="mt-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-5 py-8 text-center text-sm text-slate-500">
                  Aucun resultat immediat. Essayez d'elargir vos pays ou vos secteurs.
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
                      <p className="mt-3 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                        {device.country}
                      </p>
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

          {step < 4 && (
            <div className="mt-8 flex items-center justify-between border-t border-slate-100 pt-5">
              <button
                type="button"
                onClick={() => setStep((current) => Math.max(0, current - 1))}
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
                  Creer ma premiere veille
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setStep((current) => current + 1)}
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
