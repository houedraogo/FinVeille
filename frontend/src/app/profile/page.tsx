"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Bell,
  BookmarkPlus,
  FolderSearch,
  Heart,
  LayoutGrid,
  List,
  LogOut,
  Mail,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  CreditCard,
} from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { auth, billing, organizations } from "@/lib/api";
import { getCurrentRole, type AppRole } from "@/lib/auth";
import {
  DEVICES_VIEW_MODE_KEY,
  FAVORITE_DEVICES_KEY,
  DEVICE_PIPELINE_KEY,
  MATCH_STORAGE_KEY,
  SAVED_SEARCHES_KEY,
  USER_PREFERENCES_KEY,
  getUserPreferences,
  listFavoriteDevices,
  listPipelineDevices,
  listSavedSearches,
  saveUserPreferences,
  syncWorkspace,
  type UserPreferences,
} from "@/lib/workspace";

interface ProfileUser {
  email?: string;
  full_name?: string | null;
  name?: string | null;
  role?: AppRole;
}

function ProfileMetric({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof UserRound;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

export default function ProfilePage() {
  const [user, setUser] = useState<ProfileUser | null>(null);
  const [role, setRole] = useState<AppRole>("reader");
  const [preferences, setPreferences] = useState<UserPreferences>(() => getUserPreferences());
  const [savedCount, setSavedCount] = useState(0);
  const [favoriteCount, setFavoriteCount] = useState(0);
  const [pipelineCount, setPipelineCount] = useState(0);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [organizationName, setOrganizationName] = useState<string>("Aucune organisation");
  const [planName, setPlanName] = useState<string>("Free");
  const [planStatus, setPlanStatus] = useState<string>("free");
  const [creatingOrg, setCreatingOrg] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("kafundo_user");
      setUser(raw ? (JSON.parse(raw) as ProfileUser) : null);
    } catch {
      setUser(null);
    }

    const refreshLocalState = () => {
      setRole(getCurrentRole());
      setPreferences(getUserPreferences());
      setSavedCount(listSavedSearches().length);
      setFavoriteCount(listFavoriteDevices().length);
      setPipelineCount(listPipelineDevices().length);
    };

    refreshLocalState();
    syncWorkspace()
      .then(refreshLocalState)
      .catch(() => undefined);

    auth.context()
      .then((context: any) => {
        if (context?.current_organization?.name) {
          setOrganizationName(context.current_organization.name);
        }
      })
      .catch(() => setOrganizationName("Aucune organisation"));

    billing.subscription()
      .then((subscription: any) => {
        setPlanName(subscription?.plan?.name || "Free");
        setPlanStatus(subscription?.subscription_status || "free");
      })
      .catch(() => {
        setPlanName("Free");
        setPlanStatus("free");
      });
  }, []);

  const displayName = useMemo(
    () => user?.full_name || user?.name || user?.email || "Utilisateur Kafundo",
    [user],
  );

  const roleLabel = role === "admin" ? "Super admin" : role === "editor" ? "Equipe" : "Utilisateur standard";

  const updatePreferences = (patch: Partial<UserPreferences>) => {
    const next = { ...preferences, ...patch };
    setPreferences(next);
    saveUserPreferences(next);
    setFeedback("Préférences enregistrées.");
  };

  const clearPersonalWorkspace = () => {
    if (!confirm("Effacer tes favoris, recherches sauvegardées, suivi personnel et dernière analyse ?")) return;

    [
      SAVED_SEARCHES_KEY,
      FAVORITE_DEVICES_KEY,
      DEVICE_PIPELINE_KEY,
      MATCH_STORAGE_KEY,
      DEVICES_VIEW_MODE_KEY,
    ].forEach((key) => localStorage.removeItem(key));

    setSavedCount(0);
    setFavoriteCount(0);
    setPipelineCount(0);
    setFeedback("Données personnelles locales effacées.");
    window.dispatchEvent(new CustomEvent("kafundo:workspace-update"));
  };

  const handleLogout = () => {
    localStorage.removeItem("kafundo_token");
    localStorage.removeItem("kafundo_user");
    window.location.href = "/login";
  };

  const handleCreateOrganization = async () => {
    const name = window.prompt("Nom de ton organisation ou entreprise")?.trim();
    if (!name) return;

    setCreatingOrg(true);
    try {
      const organization = await organizations.create(name);
      setOrganizationName((organization as any).name || name);
      setFeedback("Organisation créée.");
    } catch (e: any) {
      setFeedback(e.message || "Impossible de créer l'organisation.");
    } finally {
      setCreatingOrg(false);
    }
  };

  return (
    <AppLayout>
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-medium text-primary-600">Profil utilisateur</p>
          <h1 className="mt-1 text-2xl font-bold text-slate-950">{displayName}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Gère tes informations de compte, tes préférences d'affichage et les données personnelles conservées dans ton navigateur.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link href="/workspace" className="btn-secondary text-xs">
            <FolderSearch className="h-3.5 w-3.5" />
            Mon espace
          </Link>
          <button type="button" onClick={handleLogout} className="btn-secondary text-xs text-red-600 hover:bg-red-50">
            <LogOut className="h-3.5 w-3.5" />
            Déconnexion
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="mb-5 flex items-start gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-[24px] bg-primary-50 text-primary-700">
              <UserRound className="h-8 w-8" />
            </div>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-slate-950">Informations du compte</h2>
              <p className="mt-1 text-sm text-slate-500">
                Ces informations proviennent de ta session actuelle.
              </p>
            </div>
          </div>

          <dl className="space-y-4">
            <div className="rounded-2xl bg-slate-50 px-4 py-3">
              <dt className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Nom</dt>
              <dd className="mt-1 text-sm font-medium text-slate-900">{displayName}</dd>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-3">
              <dt className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                <Mail className="h-3.5 w-3.5" />
                Email
              </dt>
              <dd className="mt-1 break-all text-sm font-medium text-slate-900">{user?.email || "Non renseigné"}</dd>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-3">
              <dt className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                <ShieldCheck className="h-3.5 w-3.5" />
                Rôle
              </dt>
              <dd className="mt-1 text-sm font-medium text-slate-900">{roleLabel}</dd>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-3">
              <dt className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Organisation</dt>
              <dd className="mt-1 flex flex-col gap-2 text-sm font-medium text-slate-900 sm:flex-row sm:items-center sm:justify-between">
                <span>{organizationName}</span>
                {organizationName === "Aucune organisation" && (
                  <button
                    type="button"
                    onClick={handleCreateOrganization}
                    disabled={creatingOrg}
                    className="btn-secondary text-xs"
                  >
                    {creatingOrg ? "Création..." : "Créer mon espace client"}
                  </button>
                )}
              </dd>
            </div>
            <div className="rounded-2xl bg-slate-50 px-4 py-3">
              <dt className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                <CreditCard className="h-3.5 w-3.5" />
                Abonnement
              </dt>
              <dd className="mt-1 flex flex-col gap-2 text-sm font-medium text-slate-900 sm:flex-row sm:items-center sm:justify-between">
                <span>{planName} · {planStatus}</span>
                <Link href="/billing" className="text-xs font-semibold text-primary-600 hover:text-primary-700">
                  Gerer le plan
                </Link>
              </dd>
            </div>
          </dl>
        </section>

        <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="mb-5">
            <h2 className="text-lg font-semibold text-slate-950">Activité personnelle</h2>
            <p className="mt-1 text-sm text-slate-500">Résumé des éléments que tu as sauvegardés dans ton espace.</p>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <ProfileMetric label="Recherches" value={savedCount.toLocaleString("fr")} icon={BookmarkPlus} />
            <ProfileMetric label="Favoris" value={favoriteCount.toLocaleString("fr")} icon={Heart} />
            <ProfileMetric label="Suivi" value={pipelineCount.toLocaleString("fr")} icon={Sparkles} />
          </div>
          <div className="mt-5 rounded-2xl border border-primary-100 bg-primary-50/70 px-4 py-4 text-sm leading-6 text-primary-800">
            Ton espace personnel est synchronise avec ton compte quand tu es connecte, avec le navigateur comme cache de confort.
          </div>
        </section>

        <section className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)] xl:col-span-2">
          <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Préférences</h2>
              <p className="mt-1 text-sm text-slate-500">Ajuste l'expérience par défaut pour ton usage quotidien.</p>
            </div>
            {feedback && <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">{feedback}</span>}
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-950">Vue par défaut des opportunités</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => updatePreferences({ defaultViewMode: "cards" })}
                  className={`rounded-xl border px-3 py-3 text-sm font-medium transition-colors ${
                    preferences.defaultViewMode === "cards"
                      ? "border-primary-300 bg-primary-50 text-primary-700"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  <LayoutGrid className="mx-auto mb-1 h-4 w-4" />
                  Cartes
                </button>
                <button
                  type="button"
                  onClick={() => updatePreferences({ defaultViewMode: "table" })}
                  className={`rounded-xl border px-3 py-3 text-sm font-medium transition-colors ${
                    preferences.defaultViewMode === "table"
                      ? "border-primary-300 bg-primary-50 text-primary-700"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  <List className="mx-auto mb-1 h-4 w-4" />
                  Tableau
                </button>
              </div>
            </div>

            <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 p-4 transition-colors hover:bg-slate-50">
              <input
                type="checkbox"
                checked={preferences.emailDigest}
                onChange={(e) => updatePreferences({ emailDigest: e.target.checked })}
                className="mt-1 h-4 w-4 rounded border-slate-300 accent-primary-600"
              />
              <span>
                <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-950">
                  <Bell className="h-4 w-4 text-primary-600" />
                  Synthèse email
                </span>
                <span className="mt-1 block text-sm leading-5 text-slate-500">
                  Préférence pour recevoir un résumé des nouvelles opportunités.
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 p-4 transition-colors hover:bg-slate-50">
              <input
                type="checkbox"
                checked={preferences.productTips}
                onChange={(e) => updatePreferences({ productTips: e.target.checked })}
                className="mt-1 h-4 w-4 rounded border-slate-300 accent-primary-600"
              />
              <span>
                <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-950">
                  <Sparkles className="h-4 w-4 text-primary-600" />
                  Conseils d'utilisation
                </span>
                <span className="mt-1 block text-sm leading-5 text-slate-500">
                  Afficher des indications pour mieux exploiter la veille.
                </span>
              </span>
            </label>
          </div>
        </section>

        <section className="rounded-[28px] border border-red-100 bg-red-50/60 p-6 xl:col-span-2">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-red-950">Confidentialité locale</h2>
              <p className="mt-1 text-sm leading-6 text-red-700">
                Tu peux effacer les données personnelles stockées dans ce navigateur : favoris, recherches, suivi et dernière analyse.
              </p>
            </div>
            <button type="button" onClick={clearPersonalWorkspace} className="btn-secondary shrink-0 border-red-200 text-xs text-red-700 hover:bg-red-100">
              <Trash2 className="h-3.5 w-3.5" />
              Effacer mes données locales
            </button>
          </div>
        </section>
      </div>
    </AppLayout>
  );
}
