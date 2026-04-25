"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  BarChart2,
  Bell,
  BookmarkPlus,
  CalendarDays,
  CheckCircle2,
  Clock,
  FolderSearch,
  Flag,
  Heart,
  Kanban,
  List,
  Paperclip,
  Pencil,
  RefreshCw,
  Sparkles,
  StickyNote,
  Target,
  Trash2,
  TrendingUp,
  Users,
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
  fetchActivityFeed,
  fetchTeamView,
  fetchReporting,
  listPipelineDevices,
  listSavedSearches,
  listFavoriteDevices,
  removePipelineDevice,
  removeFavoriteDevice,
  queueSavedSearch,
  readLatestMatchSnapshot,
  SavedSearch,
  savePipelineDevice,
  saveSearch,
  MatchWorkspaceSnapshot,
  syncWorkspace,
  type ActivityFeed,
  type TeamView,
  type PipelineReporting,
  type DevicePipelinePriority,
  type DevicePipelineStatus,
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

function toTimestamp(value?: string | null) {
  if (!value) return 0;
  const timestamp = new Date(value).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function isFutureDate(value?: string | null) {
  if (!value) return false;
  const timestamp = toTimestamp(value);
  return timestamp > Date.now();
}

function isWithinDays(value: string | null | undefined, days: number) {
  if (!value) return false;
  const timestamp = toTimestamp(value);
  if (!timestamp) return false;
  const now = Date.now();
  return timestamp >= now && timestamp <= now + days * 24 * 60 * 60 * 1000;
}

const PIPELINE_COLUMNS: Array<{ key: DevicePipelineStatus; label: string; helper: string; dotColor: string }> = [
  { key: "a_etudier", label: "À étudier", helper: "À qualifier", dotColor: "bg-amber-400" },
  { key: "interessant", label: "Prioritaire", helper: "À prioriser", dotColor: "bg-violet-500" },
  { key: "candidature_en_cours", label: "En cours", helper: "En préparation", dotColor: "bg-blue-500" },
  { key: "soumis", label: "Soumis", helper: "En attente de réponse", dotColor: "bg-indigo-500" },
  { key: "refuse", label: "Refusé", helper: "Archivé", dotColor: "bg-red-400" },
  { key: "non_pertinent", label: "Non pertinent", helper: "Écarté", dotColor: "bg-slate-300" },
];

const PIPELINE_LABELS: Record<DevicePipelineStatus, string> = {
  a_etudier: "À étudier",
  interessant: "Prioritaire",
  candidature_en_cours: "En cours",
  soumis: "Soumis",
  refuse: "Refusé",
  non_pertinent: "Non pertinent",
};

const PIPELINE_COLORS: Record<DevicePipelineStatus, string> = {
  a_etudier: "bg-amber-100 text-amber-700",
  interessant: "bg-violet-100 text-violet-700",
  candidature_en_cours: "bg-blue-100 text-blue-700",
  soumis: "bg-indigo-100 text-indigo-700",
  refuse: "bg-red-100 text-red-700",
  non_pertinent: "bg-slate-200 text-slate-600",
};

const PRIORITY_LABELS: Record<DevicePipelinePriority, string> = {
  faible: "Faible",
  moyenne: "Moyenne",
  haute: "Haute",
};

const PRIORITY_COLORS: Record<DevicePipelinePriority, string> = {
  faible: "bg-slate-100 text-slate-600",
  moyenne: "bg-sky-100 text-sky-700",
  haute: "bg-red-100 text-red-700",
};

export default function WorkspacePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [alertList, setAlertList] = useState<Alert[]>([]);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [favoriteDevices, setFavoriteDevices] = useState<FavoriteDevice[]>([]);
  const [pipelineDevices, setPipelineDevices] = useState<DevicePipelineEntry[]>([]);
  const [matchSnapshot, setMatchSnapshot] = useState<MatchWorkspaceSnapshot | null>(null);
  const [userName, setUserName] = useState("Mon espace");
  const [pipelineView, setPipelineView] = useState<"kanban" | "list">("kanban");
  const [teamView, setTeamView] = useState<TeamView | null>(null);
  const [remoteActivity, setRemoteActivity] = useState<ActivityFeed | null>(null);
  const [reporting, setReporting] = useState<PipelineReporting | null>(null);

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

        // Fetch team view, activity feed and reporting in background (non-blocking)
        fetchTeamView().then((tv) => { if (!cancelled) setTeamView(tv); }).catch(() => undefined);
        fetchActivityFeed(20).then((af) => { if (!cancelled) setRemoteActivity(af); }).catch(() => undefined);
        fetchReporting().then((r) => { if (!cancelled) setReporting(r); }).catch(() => undefined);
      } catch {
        if (!cancelled) setAlertList([]);
      } finally {
        if (!cancelled) {
          setSavedSearches(listSavedSearches());
          setFavoriteDevices(listFavoriteDevices());
          setPipelineDevices(listPipelineDevices());
          setMatchSnapshot(readLatestMatchSnapshot());

          try {
            const rawUser = localStorage.getItem("kafundo_user");
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

    window.addEventListener("kafundo:workspace-update", syncWorkspace);
    window.addEventListener("storage", syncWorkspace);

    return () => {
      window.removeEventListener("kafundo:workspace-update", syncWorkspace);
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
  const firstName = useMemo(() => {
    const clean = userName.split("@")[0]?.trim() || "toi";
    return clean.split(" ")[0] || clean;
  }, [userName]);
  const pipelineInProgress = useMemo(
    () => pipelineDevices.filter((item) => item.pipelineStatus === "candidature_en_cours"),
    [pipelineDevices]
  );
  const pipelineToStudy = useMemo(
    () => pipelineDevices.filter((item) => item.pipelineStatus === "a_etudier"),
    [pipelineDevices]
  );
  const pipelineClosingSoon = useMemo(
    () =>
      pipelineDevices
        .filter((item) => item.pipelineStatus === "candidature_en_cours" && isWithinDays(item.closeDate, 30))
        .sort((a, b) => toTimestamp(a.closeDate) - toTimestamp(b.closeDate)),
    [pipelineDevices]
  );
  const pipelineByStatus = useMemo(() => {
    const grouped = new Map<DevicePipelineStatus, DevicePipelineEntry[]>();
    PIPELINE_COLUMNS.forEach((column) => grouped.set(column.key, []));
    pipelineDevices.forEach((item) => {
      const key = item.pipelineStatus || "a_etudier";
      const list = grouped.get(key) || [];
      list.push(item);
      grouped.set(key, list);
    });
    return grouped;
  }, [pipelineDevices]);
  const upcomingDeadlines = useMemo(() => {
    const byId = new Map<string, FavoriteDevice | DevicePipelineEntry>();
    [...favoriteDevices, ...pipelineDevices].forEach((item) => {
      if (isFutureDate(item.closeDate)) byId.set(item.id, item);
    });
    return Array.from(byId.values())
      .sort((a, b) => toTimestamp(a.closeDate) - toTimestamp(b.closeDate))
      .slice(0, 5);
  }, [favoriteDevices, pipelineDevices]);
  const recommendations = useMemo(() => {
    const followedIds = new Set([
      ...favoriteDevices.map((item) => item.id),
      ...pipelineDevices.map((item) => item.id),
    ]);
    return (matchSnapshot?.topMatches || [])
      .filter((item) => !followedIds.has(item.id))
      .slice(0, 4);
  }, [favoriteDevices, matchSnapshot, pipelineDevices]);
  const activityFeed = useMemo(() => {
    const items = [
      ...favoriteDevices.map((item) => ({
        id: `favorite-${item.id}`,
        type: "Favori ajoute",
        label: item.title,
        date: item.savedAt,
        href: `/devices/${item.id}`,
      })),
      ...pipelineDevices.map((item) => ({
        id: `pipeline-${item.id}`,
        type: PIPELINE_LABELS[item.pipelineStatus],
        label: item.title,
        date: item.updatedAt,
        href: `/devices/${item.id}`,
      })),
      ...savedSearches.map((item) => ({
        id: `search-${item.id}`,
        type: "Recherche sauvegardee",
        label: item.name,
        date: item.savedAt,
        href: item.path,
      })),
      ...alertList.map((item) => ({
        id: `alert-${item.id}`,
        type: item.is_active ? "Alerte active" : "Alerte inactive",
        label: item.name,
        date: item.last_triggered_at || item.created_at,
        href: "/alerts",
      })),
    ];
    return items
      .filter((item) => item.date)
      .sort((a, b) => toTimestamp(b.date) - toTimestamp(a.date))
      .slice(0, 8);
  }, [alertList, favoriteDevices, pipelineDevices, savedSearches]);

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

  const movePipelineItem = (device: DevicePipelineEntry, status: DevicePipelineStatus) => {
    const updated = { ...device, pipelineStatus: status };
    savePipelineDevice(updated);
    setPipelineDevices((prev) => [updated, ...prev.filter((item) => item.id !== device.id)]);
  };

  return (
    <AppLayout>
      <div className="mb-6 overflow-hidden rounded-[34px] border border-slate-200 bg-[radial-gradient(circle_at_top_left,#e0f2fe,transparent_34%),linear-gradient(135deg,#ffffff_0%,#f8fafc_48%,#eef2ff_100%)] p-6 shadow-[0_18px_55px_-34px_rgba(15,23,42,0.35)]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-primary-600">Tableau de bord personnel</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">
              Bonjour {firstName}, voici les opportunites a traiter.
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
              Ton espace rassemble les opportunités suivies, les prochaines échéances, ta veille et les recommandations issues de tes recherches.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link href="/devices?closing_soon=30" className="btn-secondary text-xs">
              <CalendarDays className="h-3.5 w-3.5" />
              Voir les echeances
            </Link>
            <Link href="/devices" className="btn-secondary text-xs">
              <FolderSearch className="h-3.5 w-3.5" />
              Explorer
            </Link>
            <Link href="/match" className="btn-primary text-xs">
              <Sparkles className="h-3.5 w-3.5" />
              Recommandations
            </Link>
          </div>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-3 lg:grid-cols-4">
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-800">
          <p className="text-sm font-semibold">
            {recentAlerts.length
              ? `Bonne nouvelle : ${recentAlerts.length} signal(aux) récents dans ta veille`
              : "Astuce : crée ta première veille"}
          </p>
          <p className="mt-1 text-xs leading-5 opacity-85">
            {recentAlerts.length
              ? "Ouvre les dernières opportunités détectées avant qu'elles ne passent sous le radar."
              : "Une veille bien réglée t'évite de chercher les mêmes financements chaque semaine."}
          </p>
        </div>
        <div className="rounded-2xl border border-orange-200 bg-orange-50 px-4 py-3 text-orange-800">
          <p className="text-sm font-semibold">
            {upcomingDeadlines.length ? "Attention : deadline proche" : "Aucune deadline critique"}
          </p>
          <p className="mt-1 text-xs leading-5 opacity-85">
            {upcomingDeadlines.length
              ? `${upcomingDeadlines[0].title} arrive ${formatDateRelative(upcomingDeadlines[0].closeDate || "")}.`
              : "Tu peux te concentrer sur la qualification et la priorisation des opportunités."}
          </p>
        </div>
        <div className="rounded-2xl border border-primary-200 bg-primary-50 px-4 py-3 text-primary-800">
          <p className="text-sm font-semibold">
            {recommendations.length ? "Conseil : priorise cette aide" : "Conseil : relance une analyse"}
          </p>
          <p className="mt-1 text-xs leading-5 opacity-85">
            {recommendations.length
              ? `${recommendations[0].title} ressort comme une piste recommandée pour ton profil.`
              : "Une analyse de projet peut faire remonter des opportunités plus ciblées."}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-700">
          <p className="text-sm font-semibold">Résumé hebdo utile, pas spam</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Objectif : recevoir seulement les nouvelles priorités, les rappels de deadline et les changements importants.
          </p>
        </div>
      </div>

      <div className="hidden">
        <div>
          <p className="text-sm font-medium text-primary-600">Espace personnel</p>
          <h1 className="mt-1 text-2xl font-bold text-slate-950">{userName}</h1>
          <p className="mt-2 text-sm text-slate-500">
            Retrouve ici tes recherches sauvegardées, tes recommandations et ta veille récente.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link href="/devices" className="btn-secondary text-xs">
            <FolderSearch className="h-3.5 w-3.5" />
            Explorer les opportunités
          </Link>
          <Link href="/match" className="btn-primary text-xs">
            <Sparkles className="h-3.5 w-3.5" />
            Relancer une analyse
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
          label="Suivi"
          value={pipelineDevices.length.toLocaleString("fr")}
          sub={pipelineInProgress.length ? `${pipelineInProgress.length} candidature(s) en cours` : `${pipelineToStudy.length} opportunité(s) à étudier`}
        />
        <WorkspaceCard
          label="Veille active"
          value={activeAlerts.length.toLocaleString("fr")}
          sub={alertList.length ? `${alertList.length} veille(s) configurée(s)` : "Tu ne suis encore aucune opportunité"}
        />
        <WorkspaceCard
          label="Dernière recommandation"
          value={matchSnapshot ? matchSnapshot.total.toLocaleString("fr") : "0"}
          sub={matchSnapshot ? "Résultats conservés dans ton espace" : "Aucune recommandation récente"}
        />
      </div>

      <section className="mb-6 overflow-hidden rounded-[30px] border border-slate-200 bg-white shadow-[0_18px_55px_-34px_rgba(15,23,42,0.35)]">
        <div className="border-b border-slate-100 bg-slate-50/70 px-5 py-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary-500">Suivi de tes opportunités</p>
              <h2 className="mt-1 text-lg font-semibold text-slate-950">Pipeline de candidature</h2>
              <p className="mt-1 text-sm text-slate-500">
                De la découverte jusqu'au dépôt — pilote chaque opportunité par statut, priorité et note.
              </p>
            </div>
            <div className="flex items-center gap-3">
              {pipelineClosingSoon.length > 0 && (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">⚡ Deadline proche</p>
                  <p className="mt-1 text-sm text-amber-900">{pipelineClosingSoon.length} dossier(s) à traiter rapidement</p>
                </div>
              )}
              {/* Toggle vue */}
              <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white p-1">
                <button
                  type="button"
                  onClick={() => setPipelineView("kanban")}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${pipelineView === "kanban" ? "bg-primary-600 text-white" : "text-slate-500 hover:text-slate-700"}`}
                >
                  <Kanban className="h-3.5 w-3.5" /> Kanban
                </button>
                <button
                  type="button"
                  onClick={() => setPipelineView("list")}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${pipelineView === "list" ? "bg-primary-600 text-white" : "text-slate-500 hover:text-slate-700"}`}
                >
                  <List className="h-3.5 w-3.5" /> Liste
                </button>
              </div>
            </div>
          </div>
        </div>

        {pipelineDevices.length === 0 ? (
          <div className="px-5 py-8">
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
              <Flag className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm font-medium text-slate-700">Tu ne suis encore aucune opportunité</p>
              <p className="mt-1 text-sm text-slate-500">
                Depuis une opportunité, clique sur "Ajouter à mon suivi" pour construire ton pipeline.
              </p>
            </div>
          </div>
        ) : pipelineView === "kanban" ? (
          /* ── Vue Kanban ── */
          <div className="overflow-x-auto px-5 py-5">
            <div className="grid min-w-[1100px] grid-cols-6 gap-3">
              {PIPELINE_COLUMNS.map((column) => {
                const items = pipelineByStatus.get(column.key) || [];
                return (
                  <div key={column.key} className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <span className={`h-2 w-2 rounded-full ${column.dotColor}`} />
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{column.label}</p>
                          <p className="text-[11px] text-slate-400">{column.helper}</p>
                        </div>
                      </div>
                      <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-slate-500 shadow-sm">
                        {items.length}
                      </span>
                    </div>

                    <div className="space-y-3">
                      {items.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-slate-200 bg-white/70 px-3 py-6 text-center text-xs text-slate-400">
                          Vide
                        </div>
                      ) : (
                        items.map((device) => (
                          <div key={device.id} className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm hover:shadow-md transition-shadow">
                            <div className="mb-2 flex flex-wrap items-center gap-1.5">
                              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${PIPELINE_COLORS[device.pipelineStatus]}`}>
                                {PIPELINE_LABELS[device.pipelineStatus]}
                              </span>
                              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${PRIORITY_COLORS[device.priority]}`}>
                                {PRIORITY_LABELS[device.priority]}
                              </span>
                            </div>
                            <Link href={`/devices/${device.id}`} className="block">
                              <p className="line-clamp-2 text-sm font-semibold leading-5 text-slate-950 hover:text-primary-700">
                                {device.title}
                              </p>
                            </Link>
                            <p className="mt-1 line-clamp-1 text-xs text-slate-500">
                              {device.organism} · {device.country}
                            </p>
                            <div className="mt-2 space-y-1 text-xs text-slate-500">
                              {device.closeDate && (
                                <p className={isWithinDays(device.closeDate, 30) ? "font-semibold text-amber-700" : ""}>
                                  {isWithinDays(device.closeDate, 30) ? "⚡ " : ""}Clôture {formatDateRelative(device.closeDate)}
                                </p>
                              )}
                              {device.reminderDate && (
                                <p className="text-primary-600">🔔 Rappel {formatDateRelative(device.reminderDate)}</p>
                              )}
                            </div>
                            {device.note && (
                              <p className="mt-2 line-clamp-2 rounded-xl bg-slate-50 px-2.5 py-2 text-xs leading-5 text-slate-600 italic">
                                "{device.note}"
                              </p>
                            )}
                            <div className="mt-3 flex items-center gap-2">
                              <select
                                value={device.pipelineStatus}
                                onChange={(event) => movePipelineItem(device, event.target.value as DevicePipelineStatus)}
                                className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700"
                              >
                                {PIPELINE_COLUMNS.map((option) => (
                                  <option key={option.key} value={option.key}>{option.label}</option>
                                ))}
                              </select>
                              <button
                                type="button"
                                onClick={() => removePipelineItem(device.id)}
                                className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
                                title="Retirer du suivi"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* ── Vue Liste ── */
          <div className="divide-y divide-slate-100">
            {/* En-tête colonnes */}
            <div className="hidden grid-cols-[2fr_1fr_1fr_1fr_auto] gap-4 px-5 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 lg:grid">
              <span>Opportunité</span>
              <span>Statut</span>
              <span>Priorité</span>
              <span>Deadline</span>
              <span />
            </div>
            {pipelineDevices.map((device) => (
              <div key={device.id} className="flex flex-col gap-3 px-5 py-4 hover:bg-slate-50/80 lg:grid lg:grid-cols-[2fr_1fr_1fr_1fr_auto] lg:items-center lg:gap-4">
                {/* Titre + orga */}
                <div className="min-w-0">
                  <Link href={`/devices/${device.id}`} className="block">
                    <p className="line-clamp-1 text-sm font-semibold text-slate-950 hover:text-primary-700">{device.title}</p>
                  </Link>
                  <p className="mt-0.5 text-xs text-slate-500">{device.organism} · {device.country}</p>
                  {device.note && (
                    <p className="mt-1 line-clamp-1 text-xs italic text-slate-400">"{device.note}"</p>
                  )}
                </div>

                {/* Statut */}
                <div>
                  <select
                    value={device.pipelineStatus}
                    onChange={(event) => movePipelineItem(device, event.target.value as DevicePipelineStatus)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700"
                  >
                    {PIPELINE_COLUMNS.map((option) => (
                      <option key={option.key} value={option.key}>{option.label}</option>
                    ))}
                  </select>
                </div>

                {/* Priorité */}
                <div>
                  <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${PRIORITY_COLORS[device.priority]}`}>
                    {PRIORITY_LABELS[device.priority]}
                  </span>
                </div>

                {/* Deadline */}
                <div className="text-xs">
                  {device.closeDate ? (
                    <span className={isWithinDays(device.closeDate, 30) ? "font-semibold text-amber-700" : "text-slate-500"}>
                      {isWithinDays(device.closeDate, 30) ? "⚡ " : ""}{formatDateRelative(device.closeDate)}
                    </span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                  {device.reminderDate && (
                    <p className="mt-0.5 text-[11px] text-primary-600">🔔 {formatDateRelative(device.reminderDate)}</p>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <Link href={`/devices/${device.id}`} className="btn-secondary text-xs">
                    Voir
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                  <button
                    type="button"
                    onClick={() => removePipelineItem(device.id)}
                    className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
                    title="Retirer du suivi"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[1fr_1fr_0.9fr]">
        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="mb-4 flex items-start gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-amber-50 text-amber-600">
              <CalendarDays className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Mes prochaines echeances</h2>
              <p className="text-sm text-slate-500">Favoris et fiches suivies avec une date limite proche.</p>
            </div>
          </div>

          {upcomingDeadlines.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-7 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm font-medium text-slate-700">Aucune echeance suivie</p>
              <p className="mt-1 text-sm text-slate-500">Ajoute une opportunité en favori ou dans ton suivi pour la voir ici.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {upcomingDeadlines.map((device) => (
                <Link key={device.id} href={`/devices/${device.id}`} className="block rounded-2xl border border-slate-200 px-4 py-3 transition-colors hover:bg-slate-50">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="line-clamp-1 text-sm font-semibold text-slate-950">{device.title}</p>
                      <p className="mt-1 text-xs text-slate-500">{device.organism} - {device.country}</p>
                    </div>
                    <span className="shrink-0 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                      {formatDateRelative(device.closeDate || "")}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="mb-4 flex items-start gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary-50 text-primary-700">
              <Target className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Recommandes pour moi</h2>
              <p className="text-sm text-slate-500">Les meilleures pistes recommandées et pas encore suivies.</p>
            </div>
          </div>

          {recommendations.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-7 text-center">
              <Sparkles className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm font-medium text-slate-700">Aucune recommandation recente</p>
              <p className="mt-1 text-sm text-slate-500">Lance une analyse pour obtenir des opportunités recommandées.</p>
              <Link href="/match" className="btn-secondary mt-4 inline-flex text-xs">
                Lancer une analyse
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {recommendations.map((item) => (
                <Link key={item.id} href={`/devices/${item.id}?from=workspace`} className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 transition-colors hover:bg-slate-50">
                  <span className="rounded-xl bg-primary-50 px-2.5 py-1 text-sm font-semibold text-primary-700">{item.matchScore}</span>
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-1 text-sm font-semibold text-slate-950">{item.title}</p>
                    <p className="text-xs text-slate-500">{item.country} - {DEVICE_TYPE_LABELS[item.deviceType] || item.deviceType}</p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-slate-300" />
                </Link>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="mb-4 flex items-start gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
              <Activity className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Historique d'activité</h2>
              <p className="text-sm text-slate-500">Ce qui a bougé dans ton espace de veille et de suivi.</p>
            </div>
          </div>

          {remoteActivity ? (
            remoteActivity.items.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-7 text-center">
                <Activity className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm font-medium text-slate-700">Pas encore d'activité</p>
                <p className="mt-1 text-sm text-slate-500">Les favoris, veilles et recherches apparaîtront ici.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {remoteActivity.items.map((item) => (
                  <div key={item.id} className={`rounded-2xl border px-4 py-3 ${item.device_id ? "" : ""}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{item.label}</p>
                        {item.device_title && (
                          <Link href={`/devices/${item.device_id}`} className="mt-0.5 block">
                            <p className="line-clamp-1 text-sm font-medium text-slate-900 hover:text-primary-700">{item.device_title}</p>
                          </Link>
                        )}
                        {!item.device_title && (
                          <p className="mt-0.5 line-clamp-1 text-sm font-medium text-slate-900">{item.description}</p>
                        )}
                        {item.description && item.device_title && (
                          <p className="mt-0.5 text-xs text-slate-500 line-clamp-1">{item.description}</p>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-1 text-xs text-slate-400">
                        <Clock className="h-3 w-3" />
                        {formatDateRelative(item.occurred_at)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )
          ) : activityFeed.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-7 text-center">
              <Activity className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm font-medium text-slate-700">Pas encore d'activité</p>
              <p className="mt-1 text-sm text-slate-500">Les favoris, veilles et recherches apparaîtront ici.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {activityFeed.map((item) => (
                <Link key={item.id} href={item.href} className="block rounded-2xl border border-slate-200 px-4 py-3 transition-colors hover:bg-slate-50">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">{item.type}</p>
                  <p className="mt-1 line-clamp-1 text-sm font-medium text-slate-900">{item.label}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatDateRelative(item.date || "")}</p>
                </Link>
              ))}
            </div>
          )}
        </section>
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
                Depuis la liste des opportunités, utilise le bouton <span className="font-medium">Enregistrer</span>.
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
                <p className="text-sm text-slate-500">Les opportunités que tu veux retrouver rapidement dans ton espace.</p>
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

          <section className="hidden">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">Suivi de tes opportunités</h2>
                <p className="text-sm text-slate-500">Les opportunités que tu veux étudier, prioriser, pousser en candidature ou écarter.</p>
              </div>
              <Link href="/devices" className="text-xs font-medium text-primary-600 hover:text-primary-700">
                Voir les fiches
              </Link>
            </div>

            {pipelineDevices.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
                <Flag className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm font-medium text-slate-700">Tu ne suis encore aucune opportunité</p>
                <p className="mt-1 text-sm text-slate-500">Depuis une opportunité, ajoute un statut personnel et une note pour alimenter ton suivi.</p>
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
                          title="Retirer du suivi"
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
                <h2 className="text-lg font-semibold text-slate-950">Dernière analyse</h2>
                <p className="text-sm text-slate-500">Le dernier projet analysé et ses premiers résultats.</p>
              </div>
              <Link href="/match" className="text-xs font-medium text-primary-600 hover:text-primary-700">
                Voir les recommandations
              </Link>
            </div>

            {!matchSnapshot ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
                <Sparkles className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm font-medium text-slate-700">Aucune analyse récente</p>
                <p className="mt-1 text-sm text-slate-500">Lance une analyse de document pour retrouver les meilleures opportunités ici.</p>
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
                <h2 className="text-lg font-semibold text-slate-950">Veille récente</h2>
                <p className="text-sm text-slate-500">Les dernières veilles configurées et leurs déclenchements récents.</p>
              </div>
              <Link href="/alerts" className="text-xs font-medium text-primary-600 hover:text-primary-700">
                Gérer ma veille
              </Link>
            </div>

            {recentAlerts.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-5 py-8 text-center">
                <Bell className="mx-auto h-8 w-8 text-slate-300" />
                <p className="mt-3 text-sm font-medium text-slate-700">Tu ne suis encore aucune opportunité</p>
                <p className="mt-1 text-sm text-slate-500">Crée une veille pour suivre les nouvelles opportunités depuis ton espace.</p>
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

      {/* ── Reporting décisionnel ── */}
      {reporting && reporting.total > 0 && (
        <div className="mt-6">
          <div className="mb-4 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
              <BarChart2 className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Reporting décisionnel</h2>
              <p className="text-sm text-slate-500">Vue d'ensemble de ton pipeline de candidature.</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6 mb-4">
            {[
              {
                label: "Pipeline total",
                value: reporting.total.toLocaleString("fr"),
                sub: `${reporting.active} actif${reporting.active !== 1 ? "s" : ""}`,
                color: "text-slate-700",
                bg: "bg-slate-50",
                border: "border-slate-200",
                icon: BarChart2,
              },
              {
                label: "Soumis",
                value: reporting.submitted.toLocaleString("fr"),
                sub: `taux ${reporting.submission_rate}%`,
                color: "text-indigo-700",
                bg: "bg-indigo-50",
                border: "border-indigo-200",
                icon: TrendingUp,
              },
              {
                label: "Refusés",
                value: reporting.refused.toLocaleString("fr"),
                sub: `taux refus ${reporting.refusal_rate}%`,
                color: "text-red-600",
                bg: "bg-red-50",
                border: "border-red-100",
                icon: BarChart2,
              },
              {
                label: "Non pertinents",
                value: reporting.non_pertinent.toLocaleString("fr"),
                sub: "écartés du pipeline",
                color: "text-slate-500",
                bg: "bg-slate-50",
                border: "border-slate-200",
                icon: BarChart2,
              },
              {
                label: "Montant détecté",
                value: reporting.total_amount_detected > 0
                  ? reporting.total_amount_detected >= 1_000_000
                    ? `${(reporting.total_amount_detected / 1_000_000).toFixed(1)} M€`
                    : `${Math.round(reporting.total_amount_detected / 1000)} k€`
                  : "—",
                sub: "cumul des aides suivies",
                color: "text-emerald-700",
                bg: "bg-emerald-50",
                border: "border-emerald-200",
                icon: TrendingUp,
              },
              ...(reporting.team_stats
                ? [{
                    label: "Équipe",
                    value: reporting.team_stats.member_count.toLocaleString("fr"),
                    sub: `${reporting.team_stats.total_tracked} opportunité(s) suivies`,
                    color: "text-violet-700",
                    bg: "bg-violet-50",
                    border: "border-violet-200",
                    icon: Users,
                  }]
                : []),
            ].map(({ label, value, sub, color, bg, border, icon: Icon }) => (
              <div key={label} className={`rounded-2xl border ${border} ${bg} p-4`}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
                <p className={`mt-1.5 text-2xl font-bold ${color}`}>{value}</p>
                <p className="mt-0.5 text-xs text-slate-500">{sub}</p>
              </div>
            ))}
          </div>

          {/* Barre statuts */}
          {reporting.total > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Répartition par statut</p>
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-100">
                {[
                  { key: "a_etudier", color: "bg-amber-400" },
                  { key: "interessant", color: "bg-violet-500" },
                  { key: "candidature_en_cours", color: "bg-blue-500" },
                  { key: "soumis", color: "bg-indigo-500" },
                  { key: "refuse", color: "bg-red-400" },
                  { key: "non_pertinent", color: "bg-slate-300" },
                ].map(({ key, color }) => {
                  const count = reporting.by_status[key] || 0;
                  const pct = reporting.total > 0 ? (count / reporting.total) * 100 : 0;
                  if (pct === 0) return null;
                  return (
                    <div
                      key={key}
                      className={`${color} h-full`}
                      style={{ width: `${pct}%` }}
                      title={`${PIPELINE_LABELS[key as DevicePipelineStatus] || key} : ${count}`}
                    />
                  );
                })}
              </div>
              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
                {PIPELINE_COLUMNS.map(({ key, label, dotColor }) => {
                  const count = reporting.by_status[key] || 0;
                  return (
                    <div key={key} className="flex items-center gap-1.5 text-xs text-slate-600">
                      <span className={`h-2 w-2 rounded-full ${dotColor}`} />
                      {label}
                      <span className="font-semibold text-slate-900">{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Vue Équipe ── */}
      {teamView && teamView.members.length > 1 && (
        <div className="mt-6">
          <div className="mb-4 flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
              <Users className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-semibold text-slate-950">Vue Équipe</h2>
              <p className="text-sm text-slate-500">
                {teamView.organization_name
                  ? `Suivi des membres de ${teamView.organization_name}`
                  : "Ce que suivent tes collègues"}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {teamView.members.map((member) => (
              <div key={member.user_id} className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-[0_14px_40px_-28px_rgba(15,23,42,0.18)]">
                <div className="mb-3 flex items-center gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
                    {(member.full_name || member.email).charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-900">{member.full_name || member.email}</p>
                    <p className="text-xs text-slate-400 capitalize">{member.role}</p>
                  </div>
                  <span className="ml-auto shrink-0 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                    {member.pipeline.length} suivi{member.pipeline.length !== 1 ? "s" : ""}
                  </span>
                </div>

                {member.pipeline.length === 0 ? (
                  <p className="text-xs italic text-slate-400">Aucune opportunité suivie</p>
                ) : (
                  <ul className="space-y-1.5">
                    {member.pipeline.slice(0, 5).map((entry) => {
                      const title = (entry.snapshot as any)?.title || "Opportunité";
                      const status = PIPELINE_LABELS[entry.pipeline_status as DevicePipelineStatus] || entry.pipeline_status;
                      const statusColor = PIPELINE_COLORS[entry.pipeline_status as DevicePipelineStatus] || "bg-slate-100 text-slate-600";
                      return (
                        <li key={entry.device_id} className="flex items-center gap-2 rounded-xl border border-slate-100 bg-slate-50 px-2.5 py-1.5">
                          <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusColor}`}>
                            {status}
                          </span>
                          <Link href={`/devices/${entry.device_id}`} className="min-w-0 flex-1 truncate text-xs font-medium text-slate-700 hover:text-primary-700">
                            {title}
                          </Link>
                          {entry.documents_count > 0 && (
                            <span className="flex shrink-0 items-center gap-0.5 text-[10px] text-slate-400">
                              <Paperclip className="h-2.5 w-2.5" />{entry.documents_count}
                            </span>
                          )}
                        </li>
                      );
                    })}
                    {member.pipeline.length > 5 && (
                      <li className="text-center text-[10px] text-slate-400">+{member.pipeline.length - 5} autres</li>
                    )}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </AppLayout>
  );
}
