"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Bell,
  BookmarkPlus,
  FolderSearch,
  Flag,
  Heart,
  Pencil,
  RefreshCw,
  Sparkles,
  StickyNote,
  Trash2,
  ArrowRight,
  ExternalLink,
} from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { alerts } from "@/lib/api";
import { Alert, DEVICE_TYPE_LABELS } from "@/lib/types";
import { formatDateRelative } from "@/lib/utils";
import {
  deleteSavedSearch,
  DevicePipelineEntry,
  FavoriteDevice,
  listPipelineDevices,
  listSavedSearches,
  listFavoriteDevices,
  removePipelineDevice,
  removeFavoriteDevice,
  queueSavedSearch,
  readLatestMatchSnapshot,
  SavedSearch,
  saveSearch,
  MatchWorkspaceSnapshot,
  syncWorkspace,
} from "@/lib/workspace";

function WorkspaceCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-[24px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
      <p className="mt-1 text-sm text-slate-500">{sub}</p>
    </div>
  );
}

export default function WorkspacePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [alertList, setAlertList] = useState<Alert[]>([]);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [favoriteDevices, setFavoriteDevices] = useState<FavoriteDevice[]>([]);
  const [pipelineDevices, setPipelineDevices] = useState<DevicePipelineEntry[]>([]);
  const [matchSnapshot, setMatchSnapshot] = useState<MatchWorkspaceSnapshot | null>(null);
  const [userName, setUserName] = useState("Mon espace");
  const PIPELINE_LABELS = {
    a_etudier: "A etudier",
    candidature_en_cours: "Candidature en cours",
    non_pertinent: "Non pertinent",
  } as const;
  const PIPELINE_COLORS = {
    a_etudier: "bg-amber-100 text-amber-700",
    candidature_en_cours: "bg-blue-100 text-blue-700",
    non_pertinent: "bg-slate-200 text-slate-600",
  } as const;

  useEffect(() => {
    let cancelled = false;

    const loadWorkspace = async () => {
      try {
        const [alertsData] = await Promise.all([
          alerts.list(),
          syncWorkspace().catch(() => false),
        ]);
        if (cancelled) return;
        setAlertList(Array.isArray(alertsData) ? alertsData : []);
      } catch {
        if (!cancelled) setAlertList([]);
      } finally {
        if (!cancelled) {
          setSavedSearches(listSavedSearches());
          setFavoriteDevices(listFavoriteDevices());
          setPipelineDevices(listPipelineDevices());
          setMatchSnapshot(readLatestMatchSnapshot());

          try {
            const rawUser = localStorage.getItem("finveille_user");
            if (rawUser) {
              const parsedUser = JSON.parse(rawUser);
              setUserName(parsedUser.full_name || parsedUser.name || parsedUser.email || "Mon espace");
            }
          } catch {
            setUserName("Mon espace");
          }

          setLoading(false);
        }
      }
    };

    loadWorkspace();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const syncWorkspace = () => {
      setSavedSearches(listSavedSearches());
      setFavoriteDevices(listFavoriteDevices());
      setPipelineDevices(listPipelineDevices());
      setMatchSnapshot(readLatestMatchSnapshot());
    };

    window.addEventListener("finveille:workspace-update", syncWorkspace);
    window.addEventListener("storage", syncWorkspace);

    return () => {
      window.removeEventListener("finveille:workspace-update", syncWorkspace);
      window.removeEventListener("storage", syncWorkspace);
    };
  }, []);

  const activeAlerts = useMemo(() => alertList.filter((item) => item.is_active), [alertList]);
  const recentAlerts = useMemo(
    () =>
      [...alertList]
        .sort((a, b) => (b.last_triggered_at || b.created_at).localeCompare(a.last_triggered_at || a.created_at))
        .slice(0, 4),
    [alertList]
  );

  const openSavedSearch = (search: SavedSearch) => {
    queueSavedSearch(search);
    router.push(search.path);
  };

  const removeSavedSearch = (searchId: string) => {
    deleteSavedSearch(searchId);
    setSavedSearches((prev) => prev.filter((item) => item.id !== searchId));
  };

  const renameSavedSearch = (search: SavedSearch) => {
    const nextName = window.prompt("Nouveau nom pour cette recherche", search.name)?.trim();
    if (!nextName) return;

    const updatedSearch = { ...search, name: nextName, savedAt: new Date().toISOString() };
    saveSearch(updatedSearch);
    setSavedSearches((prev) => [updatedSearch, ...prev.filter((item) => item.id !== search.id)]);
  };

  const editSavedSearch = (search: SavedSearch) => {
    queueSavedSearch(search, "edit");
    router.push(search.path);
  };

  const removeFavorite = (deviceId: string) => {
    removeFavoriteDevice(deviceId);
    setFavoriteDevices((prev) => prev.filter((item) => item.id !== deviceId));
  };

  const removePipelineItem = (deviceId: string) => {
    removePipelineDevice(deviceId);
    setPipelineDevices((prev) => prev.filter((item) => item.id !== deviceId));
  };

  return (
    <AppLayout>
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-medium text-primary-600">Espace personnel</p>
          <h1 className="mt-1 text-2xl font-bold text-slate-950">{userName}</h1>
          <p className="mt-2 text-sm text-slate-500">
            Retrouve ici tes recherches sauvegardées, ton dernier matching et les alertes récentes.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link href="/devices" className="btn-secondary text-xs">
            <FolderSearch className="h-3.5 w-3.5" />
            Explorer les dispositifs
          </Link>
          <Link href="/match" className="btn-primary text-xs">
            <Sparkles className="h-3.5 w-3.5" />
            Relancer un matching
          </Link>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        <WorkspaceCard
          label="Recherches sauvegardées"
          value={savedSearches.length.toLocaleString("fr")}
          sub={savedSearches.length ? "Vues prêtes à rejouer" : "Aucune recherche sauvegardée pour le moment"}
        />
        <WorkspaceCard
          label="Favoris"
          value={favoriteDevices.length.toLocaleString("fr")}
          sub={favoriteDevices.length ? "Fiches que tu veux suivre de près" : "Aucun favori pour le moment"}
        />
        <WorkspaceCard
          label="Pipeline perso"
          value={pipelineDevices.length.toLocaleString("fr")}
          sub={pipelineDevices.length ? "Dispositifs marqués pour suivi" : "Aucun suivi personnel pour le moment"}
        />
        <WorkspaceCard
          label="Alertes actives"
          value={activeAlerts.length.toLocaleString("fr")}
          sub={alertList.length ? `${alertList.length} alerte(s) configurée(s)` : "Aucune alerte configurée"}
        />
        <WorkspaceCard
          label="Dernier matching"
          value={matchSnapshot ? matchSnapshot.total.toLocaleString("fr") : "0"}
          sub={matchSnapshot ? "Résultats conservés dans ton espace" : "Aucun matching récent enregistré"}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Recherches sauvegardées</h2>
              <p className="text-sm text-slate-500">Les vues que tu veux rejouer rapidement sans refaire tous les filtres.</p>
            </div>
            <Link href="/devices" className="text-xs font-medium text-primary-600 hover:text-primary-700">
              En créer une
            </Link>
          </div>

          {loading ? (
            <div className="flex items-center gap-2 py-8 text-sm text-slate-400">
              <RefreshCw className="h-4 w-4 animate-spin" />
              Chargement de ton espace...
            </div>
          ) : savedSearches.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
              <BookmarkPlus className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm font-medium text-slate-700">Aucune recherche sauvegardée</p>
              <p className="mt-1 text-sm text-slate-500">
                Depuis la liste des dispositifs, utilise le bouton <span className="font-medium">Enregistrer</span>.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {savedSearches.map((search) => (
                <div key={search.id} className="rounded-2xl border border-slate-200 px-4 py-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-950">{search.name}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {search.title} · sauvegardée {formatDateRelative(search.savedAt)}
                        {search.resultCount !== null && ` · ${search.resultCount.toLocaleString("fr")} résultat(s)`}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {search.filters.q && (
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                            Recherche : {search.filters.q}
                          </span>
                        )}
                        {search.filters.countries.slice(0, 2).map((country) => (
                          <span key={country} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                            {country}
                          </span>
                        ))}
                        {search.filters.deviceTypes.slice(0, 2).map((deviceType) => (
                          <span key={deviceType} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                            {DEVICE_TYPE_LABELS[deviceType] || deviceType}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => renameSavedSearch(search)}
                        className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                        title="Renommer cette recherche"
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => editSavedSearch(search)}
                        className="btn-secondary text-xs"
                      >
                        Modifier
                      </button>
                      <button
                        type="button"
                        onClick={() => openSavedSearch(search)}
                        className="btn-secondary text-xs"
                      >
                        Ouvrir
                        <ArrowRight className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeSavedSearch(search.id)}
                        className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
                        title="Supprimer cette recherche"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <div className="space-y-6">
          <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">Fiches favorites</h2>
                <p className="text-sm text-slate-500">Les dispositifs que tu veux retrouver rapidement dans ton espace.</p>
              </div>
              <Link href="/devices" className="text-xs font-medium text-primary-600 hover:text-primary-700">
                Ajouter des favoris
              </Link>
            </div>

            {favoriteDevices.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
                <Heart className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm font-medium text-slate-700">Aucun favori enregistré</p>
                <p className="mt-1 text-sm text-slate-500">Ajoute une fiche en favori depuis une carte ou la page détail.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {favoriteDevices.slice(0, 6).map((device) => (
                  <div
                    key={device.id}
                    className="flex items-center gap-3 rounded-2xl border border-slate-200 px-3 py-3"
                  >
                    <Link href={`/devices/${device.id}`} className="min-w-0 flex-1">
                      <p className="line-clamp-1 text-sm font-medium text-slate-900">{device.title}</p>
                      <p className="text-xs text-slate-500">
                        {device.organism} · {device.country}
                        {device.closeDate ? ` · clôture ${formatDateRelative(device.closeDate)}` : ""}
                      </p>
                    </Link>
                    <button
                      type="button"
                      onClick={() => removeFavorite(device.id)}
                      className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
                      title="Retirer des favoris"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">Suivi pipeline</h2>
                <p className="text-sm text-slate-500">Les dispositifs que tu veux étudier, pousser en candidature ou écarter.</p>
              </div>
              <Link href="/devices" className="text-xs font-medium text-primary-600 hover:text-primary-700">
                Voir les fiches
              </Link>
            </div>

            {pipelineDevices.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
                <Flag className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm font-medium text-slate-700">Aucun dispositif suivi</p>
                <p className="mt-1 text-sm text-slate-500">Depuis une fiche, ajoute un statut personnel et une note pour alimenter ton pipeline.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {pipelineDevices.slice(0, 8).map((device) => (
                  <div key={device.id} className="rounded-2xl border border-slate-200 px-4 py-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${PIPELINE_COLORS[device.pipelineStatus]}`}>
                            {PIPELINE_LABELS[device.pipelineStatus]}
                          </span>
                          <span className="text-xs text-slate-400">mis à jour {formatDateRelative(device.updatedAt)}</span>
                        </div>
                        <Link href={`/devices/${device.id}`} className="block">
                          <p className="line-clamp-1 text-sm font-semibold text-slate-950">{device.title}</p>
                        </Link>
                        <p className="mt-1 text-xs text-slate-500">
                          {device.organism} · {device.country}
                          {device.closeDate ? ` · clôture ${formatDateRelative(device.closeDate)}` : ""}
                        </p>
                        {device.note && (
                          <div className="mt-3 rounded-xl bg-slate-50 px-3 py-3">
                            <p className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                              <StickyNote className="h-3 w-3" />
                              Note
                            </p>
                            <p className="text-sm leading-6 text-slate-700">{device.note}</p>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Link href={`/devices/${device.id}`} className="btn-secondary text-xs">
                          Ouvrir
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                        <button
                          type="button"
                          onClick={() => removePipelineItem(device.id)}
                          className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
                          title="Retirer du pipeline"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">Dernier matching</h2>
                <p className="text-sm text-slate-500">Le dernier projet analysé et ses premiers résultats.</p>
              </div>
              <Link href="/match" className="text-xs font-medium text-primary-600 hover:text-primary-700">
                Voir le matching
              </Link>
            </div>

            {!matchSnapshot ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
                <Sparkles className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm font-medium text-slate-700">Aucun matching récent</p>
                <p className="mt-1 text-sm text-slate-500">Lance une analyse de document pour retrouver les meilleurs dispositifs ici.</p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="rounded-2xl bg-slate-50 px-4 py-4">
                  <p className="text-sm font-semibold text-slate-900">{matchSnapshot.fileName || "Projet sans nom"}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {matchSnapshot.updatedAt ? `Mis à jour ${formatDateRelative(matchSnapshot.updatedAt)}` : "Projet conservé dans l'espace"}
                    {` · ${matchSnapshot.total.toLocaleString("fr")} correspondance(s)`}
                  </p>
                </div>
                <div className="space-y-2">
                  {matchSnapshot.topMatches.map((item) => (
                    <Link
                      key={item.id}
                      href={`/devices/${item.id}?from=match`}
                      className="flex items-center gap-3 rounded-2xl border border-slate-200 px-3 py-3 transition-colors hover:bg-slate-50"
                    >
                      <div className="rounded-xl bg-primary-50 px-2.5 py-1 text-sm font-semibold text-primary-700">
                        {item.matchScore}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="line-clamp-1 text-sm font-medium text-slate-900">{item.title}</p>
                        <p className="text-xs text-slate-500">
                          {item.country} · {DEVICE_TYPE_LABELS[item.deviceType] || item.deviceType}
                        </p>
                      </div>
                      <ExternalLink className="h-4 w-4 text-slate-300" />
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </section>

          <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">Alertes récentes</h2>
                <p className="text-sm text-slate-500">Les dernières veilles configurées et leurs déclenchements récents.</p>
              </div>
              <Link href="/alerts" className="text-xs font-medium text-primary-600 hover:text-primary-700">
                Gérer les alertes
              </Link>
            </div>

            {recentAlerts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
                <Bell className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm font-medium text-slate-700">Aucune alerte récente</p>
                <p className="mt-1 text-sm text-slate-500">Crée une alerte pour suivre les nouveaux dispositifs depuis ton espace.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {recentAlerts.map((alert) => (
                  <Link
                    key={alert.id}
                    href="/alerts"
                    className="flex items-center gap-3 rounded-2xl border border-slate-200 px-3 py-3 transition-colors hover:bg-slate-50"
                  >
                    <div className={`h-2.5 w-2.5 rounded-full ${alert.is_active ? "bg-emerald-400" : "bg-slate-300"}`} />
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-1 text-sm font-medium text-slate-900">{alert.name}</p>
                      <p className="text-xs text-slate-500">
                        {alert.last_triggered_at
                          ? `Dernière notification ${formatDateRelative(alert.last_triggered_at)}`
                          : `Créée ${formatDateRelative(alert.created_at)}`}
                      </p>
                    </div>
                    <ArrowRight className="h-4 w-4 text-slate-300" />
                  </Link>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </AppLayout>
  );
}
