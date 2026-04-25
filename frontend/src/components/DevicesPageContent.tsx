"use client";
import { useState, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import AppLayout from "@/components/AppLayout";
import DeviceCard from "@/components/DeviceCard";
import LimitNotice from "@/components/LimitNotice";
import { billing, devices, relevance } from "@/lib/api";
import { canAccessAdmin, getCurrentRole } from "@/lib/auth";
import { DeviceListResponse, DEVICE_TYPE_LABELS } from "@/lib/types";
import { COUNTRIES, SECTORS } from "@/lib/constants";
import { formatAmount, formatDate, getAiReadinessMeta } from "@/lib/utils";
import { consumePendingSavedSearch, getSavedViewMode, getUserPreferences, saveSearch, saveUserPreferences, setSavedViewMode } from "@/lib/workspace";
import {
  Search, SlidersHorizontal, Download, Plus,
  ChevronLeft, ChevronRight, X,
  ShieldCheck, XCircle, Trash2, Tag, CheckSquare,
  FileSpreadsheet, FileText, ChevronDown, LayoutGrid, Rows3, ExternalLink, BookmarkPlus,
  UserCircle2,
} from "lucide-react";
import clsx from "clsx";

const STATUSES = ["open", "recurring", "standby", "closed", "expired"];
const AI_READINESS_LABELS: Record<string, string> = {
  pret_pour_recommandation_ia: "Très recommandé",
  utilisable_avec_prudence: "À confirmer",
  a_verifier: "À vérifier",
  non_exploitable: "Non recommandé",
};
const STATUS_LABELS: Record<string, string> = {
  open: "Ouvert", recurring: "Récurrent", standby: "Clôture non communiquée", closed: "Fermé", expired: "Expiré",
};

interface Props {
  /** Titre affiché dans le header */
  title: string;
  /** Types de dispositifs toujours envoyés à l'API (non modifiables par l'utilisateur) */
  lockedDeviceTypes: string[];
  /** Types proposés dans le panneau filtre (si vide → filtre type masqué) */
  availableDeviceTypes: string[];
  /** Tri par défaut */
  defaultSort?: string;
  /** Afficher le filtre "Clôture dans" (non pertinent pour l'investissement privé) */
  showClosingFilter?: boolean;
  /** Lien vers la page d'ajout */
  newDeviceHref?: string;
}

type ViewMode = "cards" | "table";

export default function DevicesPageContent({
  title,
  lockedDeviceTypes,
  availableDeviceTypes,
  defaultSort = "updated_at",
  showClosingFilter = true,
  newDeviceHref = "/devices/new",
}: Props) {
  const router = useRouter();
  const pathname = usePathname();

  const [result, setResult] = useState<DeviceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // Sélection & actions groupées
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkMsg, setBulkMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [showTagInput, setShowTagInput] = useState(false);
  const [tagInput, setTagInput] = useState("");
  const [deleteConfirmBulk, setDeleteConfirmBulk] = useState(false);

  // Filtres utilisateur (indépendants par page — pas partagés via URL)
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [filterCountries, setFilterCountries] = useState<string[]>([]);
  const [filterTypes, setFilterTypes] = useState<string[]>([]);
  const [filterSectors, setFilterSectors] = useState<string[]>([]);
  const [filterStatuses, setFilterStatuses] = useState<string[]>([]);
  const [filterAiReadiness, setFilterAiReadiness] = useState<string[]>([]);
  const [closingSoon, setClosingSoon] = useState("");
  const [hasCloseDate, setHasCloseDate] = useState(false);
  const [sortBy, setSortBy] = useState(defaultSort);
  const [page, setPage] = useState(1);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const [editingSavedSearchId, setEditingSavedSearchId] = useState<string | null>(null);
  const [exportsAllowed, setExportsAllowed] = useState(true);
  const [profileActive, setProfileActive] = useState(false);
  const [userIsStaff, setUserIsStaff] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(q), 300);
    return () => clearTimeout(timer);
  }, [q]);

  useEffect(() => {
    billing.subscription()
      .then((subscription: any) => setExportsAllowed(!!subscription?.features?.exports))
      .catch(() => setExportsAllowed(true));
  }, []);

  useEffect(() => {
    const preferredView = getSavedViewMode(pathname) || getUserPreferences().defaultViewMode;
    if (preferredView) {
      setViewMode(preferredView);
    }

    const pendingSearch = consumePendingSavedSearch(pathname);
    if (pendingSearch) {
      // Restore a saved search (e.g. from onboarding "Voir tous les résultats")
      setQ(pendingSearch.search.filters.q);
      setDebouncedQ(pendingSearch.search.filters.q);
      setFilterCountries(pendingSearch.search.filters.countries);
      setFilterTypes(pendingSearch.search.filters.deviceTypes);
      setFilterSectors(pendingSearch.search.filters.sectors);
      setFilterStatuses(pendingSearch.search.filters.statuses);
      setClosingSoon(pendingSearch.search.filters.closingSoon);
      setHasCloseDate(!!pendingSearch.search.filters.hasCloseDate);
      setSortBy(pendingSearch.search.filters.sortBy || defaultSort);
      setPage(1);
      setEditingSavedSearchId(pendingSearch.mode === "edit" ? pendingSearch.search.id : null);
      return;
    }

    // No pending search → apply the user's saved profile as default filters
    // (skip for admins who manage the full catalog)
    const role = getCurrentRole();
    const isStaff = canAccessAdmin(role);
    setUserIsStaff(isStaff);
    if (isStaff) return;

    relevance.getProfile().then((profile: any) => {
      if (!profile) return;
      let applied = false;
      if (profile.countries?.length) {
        setFilterCountries(profile.countries);
        applied = true;
      }
      if (profile.sectors?.length) {
        setFilterSectors(profile.sectors);
        applied = true;
      }
      if (profile.target_funding_types?.length && availableDeviceTypes.length > 0) {
        const validTypes = (profile.target_funding_types as string[]).filter(
          (t) => availableDeviceTypes.includes(t)
        );
        if (validTypes.length) setFilterTypes(validTypes);
      }
      if (applied) setProfileActive(true);
    }).catch(() => {});
  }, [pathname, defaultSort]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setSavedViewMode(pathname, viewMode);
    saveUserPreferences({ ...getUserPreferences(), defaultViewMode: viewMode });
  }, [pathname, viewMode]);

  const fetchDevices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Types envoyés = filtres utilisateur (si vide → types verrouillés)
      const effectiveTypes =
        filterTypes.length > 0 ? filterTypes : lockedDeviceTypes.length > 0 ? lockedDeviceTypes : undefined;

      const data = await devices.list({
        q: debouncedQ || undefined,
        countries: filterCountries.length ? filterCountries : undefined,
        device_types: effectiveTypes,
        sectors: filterSectors.length ? filterSectors : undefined,
        status: filterStatuses.length ? filterStatuses : undefined,
        ai_readiness_labels: filterAiReadiness.length ? filterAiReadiness : undefined,
        closing_soon_days: closingSoon ? parseInt(closingSoon) : undefined,
        has_close_date: hasCloseDate || undefined,
        sort_by: sortBy,
        sort_desc: sortBy !== "close_date",
        page,
        page_size: viewMode === "table" ? 50 : 20,
      });
      setResult(data);
    } catch {
      setError("Impossible de charger les opportunités. Vérifiez votre connexion.");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, filterCountries, filterTypes, filterSectors, filterStatuses, filterAiReadiness, closingSoon, hasCloseDate, sortBy, page, viewMode, lockedDeviceTypes]);

  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  const toggleFilter = (arr: string[], setArr: (v: string[]) => void, val: string) => {
    setArr(arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val]);
    setPage(1);
  };

  const clearFilters = () => {
    setFilterCountries([]); setFilterTypes([]); setFilterSectors([]);
    setFilterStatuses([]); setFilterAiReadiness([]); setClosingSoon(""); setHasCloseDate(false); setPage(1);
    setEditingSavedSearchId(null);
    setProfileActive(false);
  };

  const hasFilters = filterCountries.length || filterTypes.length || filterSectors.length ||
    filterStatuses.length || filterAiReadiness.length || closingSoon || hasCloseDate;
  const pageIds = result?.items.map((d) => d.id) ?? [];
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));

  // Sélection
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };
  const selectAllPage = () => {
    const pageIds = result?.items.map(d => d.id) ?? [];
    setSelectedIds(prev => { const n = new Set(prev); pageIds.forEach(id => n.add(id)); return n; });
  };
  const toggleAllPageSelection = () => {
    if (allPageSelected) {
      setSelectedIds(prev => {
        const next = new Set(prev);
        pageIds.forEach((id) => next.delete(id));
        return next;
      });
      return;
    }
    selectAllPage();
  };
  const clearSelection = () => {
    setSelectedIds(new Set());
    setDeleteConfirmBulk(false);
    setShowTagInput(false);
    setTagInput("");
    setBulkMsg(null);
  };

  const handleBulkAction = async (action: "validate" | "reject" | "delete" | "tag") => {
    if (action === "delete" && !deleteConfirmBulk) { setDeleteConfirmBulk(true); return; }
    if (action === "tag" && !showTagInput) { setShowTagInput(true); return; }
    const tags = action === "tag" ? tagInput.split(",").map(t => t.trim()).filter(Boolean) : undefined;
    if (action === "tag" && (!tags || tags.length === 0)) return;

    setBulkLoading(true);
    setBulkMsg(null);
    try {
      const res = await devices.bulkAction(Array.from(selectedIds), action, tags);
      setBulkMsg({
        type: res.failed === 0 ? "success" : "error",
        text: res.failed === 0
          ? `✓ ${res.processed} opportunité(s) traitée(s) avec succès.`
          : `${res.processed} traité(s), ${res.failed} en erreur.`,
      });
      clearSelection();
      fetchDevices();
    } catch (e: any) {
      setBulkMsg({ type: "error", text: e.message || "Erreur lors de l'action groupée." });
    } finally {
      setBulkLoading(false);
      setDeleteConfirmBulk(false);
    }
  };

  const handleSaveSearch = () => {
    const defaultName = q.trim()
      ? `${title} - ${q.trim()}`
      : `${title} - vue enregistrée`;
    const existingSearchName = editingSavedSearchId
      ? window.localStorage.getItem("kafundo_saved_searches")
      : null;
    let suggestedName = defaultName;

    if (editingSavedSearchId && existingSearchName) {
      try {
        const parsed = JSON.parse(existingSearchName) as Array<{ id: string; name: string }>;
        suggestedName = parsed.find((item) => item.id === editingSavedSearchId)?.name || defaultName;
      } catch {
        suggestedName = defaultName;
      }
    }

    const name = window.prompt(
      editingSavedSearchId ? "Mettre à jour le nom de cette recherche" : "Nom de cette recherche enregistrée",
      suggestedName,
    )?.trim();
    if (!name) return;

    saveSearch({
      id: editingSavedSearchId || crypto.randomUUID(),
      name,
      title,
      path: pathname,
      resultCount: result?.total ?? null,
      savedAt: new Date().toISOString(),
      filters: {
        q: q.trim(),
        countries: filterCountries,
        deviceTypes: filterTypes,
        sectors: filterSectors,
        statuses: filterStatuses,
        closingSoon,
        hasCloseDate,
        sortBy,
      },
    });

    setBulkMsg({
      type: "success",
      text: editingSavedSearchId
        ? `Recherche mise à jour dans Mon espace : ${name}`
        : `Recherche enregistrée dans Mon espace : ${name}`,
    });
    setEditingSavedSearchId(null);
  };

  // Tous les filtres actifs transmis à l'export
  const effectiveTypesForExport =
    filterTypes.length > 0 ? filterTypes : lockedDeviceTypes.length > 0 ? lockedDeviceTypes : undefined;

  const exportParams = {
    q: debouncedQ || undefined,
    countries: filterCountries.length ? filterCountries : undefined,
    device_types: effectiveTypesForExport,
    sectors: filterSectors.length ? filterSectors : undefined,
    status: filterStatuses.length ? filterStatuses : undefined,
    ai_readiness_labels: filterAiReadiness.length ? filterAiReadiness : undefined,
    closing_soon_days: closingSoon ? parseInt(closingSoon) : undefined,
    has_close_date: hasCloseDate || undefined,
  };

  const exportCsvUrl   = devices.exportCsv(exportParams);
  const exportExcelUrl = devices.exportExcel(exportParams);

  const applyQuickFilter = (kind: string) => {
    setPage(1);
    setEditingSavedSearchId(null);

    if (kind === "open") {
      setFilterStatuses(["open"]);
      return;
    }
    if (kind === "with_deadline") {
      setHasCloseDate(true);
      setFilterStatuses(["open"]);
      setSortBy("close_date");
      return;
    }
    if (kind === "subvention") {
      setFilterTypes(["subvention"]);
      return;
    }
    if (kind === "investissement") {
      setFilterTypes(["investissement"]);
      return;
    }
    if (kind === "afrique") {
      setFilterCountries(["Afrique", "Afrique de l'Ouest"]);
      return;
    }
    if (kind === "france") {
      setFilterCountries(["France"]);
      return;
    }
    if (kind === "30days") {
      setClosingSoon("30");
      setHasCloseDate(true);
      setFilterStatuses(["open"]);
      return;
    }
    if (kind === "ai_ready") {
      setFilterAiReadiness(["pret_pour_recommandation_ia"]);
      setSortBy("ai_readiness");
    }
  };

  const buildRelevanceExplanation = (device: any) => {
    if (device.match_reasons?.length) {
      return `Correspondance : ${device.match_reasons.slice(0, 3).join(" + ")}.`;
    }
    const reasons: string[] = [];
    if (filterCountries.includes(device.country)) reasons.push(`pays ${device.country}`);
    if (filterTypes.includes(device.device_type)) reasons.push(`type ${DEVICE_TYPE_LABELS[device.device_type] || device.device_type}`);
    const matchedSector = filterSectors.find((sector) => (device.sectors || []).includes(sector));
    if (matchedSector) reasons.push(`secteur ${matchedSector}`);
    if (q.trim()) reasons.push(`recherche "${q.trim()}"`);
    if (closingSoon) reasons.push(`echeance dans ${closingSoon} jours`);
    if (hasCloseDate && device.close_date) reasons.push("date limite renseignee");
    if (filterAiReadiness.includes(device.ai_readiness_label)) reasons.push("forte pertinence");
    if (!reasons.length) return "";
    return `Correspond a votre ${reasons.slice(0, 3).join(" + ")}.`;
  };

  const quickFilters = [
    ["open", "Ouverts"],
    ["with_deadline", "Avec date limite"],
    ["subvention", "Subventions"],
    ["investissement", "Investissement"],
    ["afrique", "Afrique"],
    ["france", "France"],
    ["30days", "Moins de 30 jours"],
    ["ai_ready", "Recommandés"],
  ].filter(([kind]) => {
    if (kind === "investissement") {
      return availableDeviceTypes.includes("investissement") || lockedDeviceTypes.includes("investissement") || lockedDeviceTypes.length === 0;
    }
    if (kind === "subvention") {
      return availableDeviceTypes.includes("subvention") || lockedDeviceTypes.includes("subvention") || lockedDeviceTypes.length === 0;
    }
    return true;
  });

  return (
    <AppLayout>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-gray-900">{title}</h1>
          {result && (
            <p className="text-sm text-gray-500">{result.total.toLocaleString("fr")} résultats</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="hidden items-center rounded-xl border border-gray-200 bg-white p-1 sm:flex">
            <button
              type="button"
              onClick={() => setViewMode("cards")}
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                viewMode === "cards" ? "bg-slate-900 text-white" : "text-gray-500 hover:bg-gray-50 hover:text-gray-800",
              )}
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              Cartes
            </button>
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                viewMode === "table" ? "bg-slate-900 text-white" : "text-gray-500 hover:bg-gray-50 hover:text-gray-800",
              )}
            >
              <Rows3 className="w-3.5 h-3.5" />
              Tableau
            </button>
          </div>
          <button
            type="button"
            onClick={handleSaveSearch}
            className="btn-secondary text-xs flex items-center gap-1.5"
            title={editingSavedSearchId ? "Mettre à jour cette recherche sauvegardée" : "Enregistrer cette recherche dans Mon espace"}
          >
            <BookmarkPlus className="w-3.5 h-3.5" />
            {editingSavedSearchId ? "Mettre à jour" : "Enregistrer"}
          </button>
          {/* Dropdown Export */}
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(v => !v)}
              className="btn-secondary text-xs flex items-center gap-1.5"
              title={result ? `Exporter ${result.total.toLocaleString("fr")} résultat(s)` : "Exporter"}
            >
              <Download className="w-3 h-3" />
              Exporter
              {result && <span className="text-gray-400">({result.total.toLocaleString("fr")})</span>}
              <ChevronDown className="w-3 h-3 text-gray-400" />
            </button>
            {showExportMenu && (
              <>
                {/* Overlay invisible pour fermer */}
                <div className="fixed inset-0 z-10" onClick={() => setShowExportMenu(false)} />
                <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-20 w-72 overflow-hidden">
                  {!exportsAllowed ? (
                    <div className="p-2">
                      <LimitNotice
                        compact
                        title="Export reserve aux offres avancees"
                        message="Les exports CSV/Excel sont disponibles avec Team, Expert ou Accompagnement Financement."
                      />
                    </div>
                  ) : (
                    <>
                  <a
                    href={exportCsvUrl}
                    download
                    onClick={() => setShowExportMenu(false)}
                    className="flex items-center gap-2.5 px-3.5 py-2.5 text-xs text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <FileText className="w-3.5 h-3.5 text-gray-400" />
                    <div>
                      <div className="font-medium">CSV</div>
                      <div className="text-gray-400">Compatible Excel</div>
                    </div>
                  </a>
                  <div className="border-t border-gray-100" />
                  <a
                    href={exportExcelUrl}
                    download
                    onClick={() => setShowExportMenu(false)}
                    className="flex items-center gap-2.5 px-3.5 py-2.5 text-xs text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <FileSpreadsheet className="w-3.5 h-3.5 text-green-500" />
                    <div>
                      <div className="font-medium">Excel (.xlsx)</div>
                      <div className="text-gray-400">Formaté + filtres</div>
                    </div>
                  </a>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
          <button onClick={() => router.push(newDeviceHref)} className="btn-primary text-xs">
            <Plus className="w-3 h-3" /> Ajouter
          </button>
        </div>
      </div>

      {/* Bannière profil actif */}
      {profileActive && (
        <div className="mb-3 flex items-center justify-between gap-3 rounded-2xl border border-primary-200 bg-primary-50/80 px-4 py-2.5">
          <div className="flex items-center gap-2 text-xs text-primary-800">
            <UserCircle2 className="h-4 w-4 shrink-0 text-primary-600" />
            <span>
              <span className="font-semibold">Contenu personnalisé</span>
              {" — "}les résultats sont filtrés selon votre profil.{" "}
              <Link href="/onboarding" className="underline hover:text-primary-600">
                Modifier mes préférences
              </Link>
            </span>
          </div>
          {userIsStaff && (
            <button
              type="button"
              onClick={clearFilters}
              className="shrink-0 text-xs text-primary-500 hover:text-primary-800 underline"
            >
              Voir tout
            </button>
          )}
        </div>
      )}

      {/* Bannière tri intelligent */}
      {sortBy !== "relevance" && (
        <div className="mb-3 flex items-center justify-between gap-3 rounded-2xl border border-violet-200 bg-violet-50/70 px-4 py-2.5">
          <p className="text-xs text-violet-800">
            <span className="font-semibold">✦ Tri intelligent disponible</span> — Trier par pertinence profil pour voir les opportunités les plus adaptées à ton organisation en premier.
          </p>
          <button
            type="button"
            onClick={() => { setSortBy("relevance"); setPage(1); }}
            className="shrink-0 rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-violet-700"
          >
            Activer
          </button>
        </div>
      )}
      {sortBy === "relevance" && (
        <div className="mb-3 flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-2">
          <span className="text-xs font-semibold text-emerald-700">✦ Tri intelligent activé</span>
          <span className="text-xs text-emerald-600">— Les résultats sont triés par pertinence pour ton profil.</span>
        </div>
      )}

      {/* Barre de recherche */}
      <div className="flex gap-2 mb-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            className="input pl-9 pr-9"
            placeholder="Rechercher…"
            value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1); }}
          />
          {q !== debouncedQ && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border-2 border-primary-400 border-t-transparent animate-spin" />
          )}
        </div>
        {userIsStaff && (
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={clsx("btn-secondary", hasFilters && "border-primary-500 text-primary-600")}
          >
            <SlidersHorizontal className="w-4 h-4" />
            Filtres
            {hasFilters ? (
              <span className="bg-primary-600 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                {Number(filterCountries.length > 0) + Number(filterTypes.length > 0) +
                 Number(filterSectors.length > 0) + Number(filterStatuses.length > 0) + Number(filterAiReadiness.length > 0) + Number(!!closingSoon) + Number(hasCloseDate)}
              </span>
            ) : null}
          </button>
        )}
        <select className="input w-auto" value={sortBy} onChange={(e) => { setSortBy(e.target.value); setPage(1); }}>
          <option value="relevance">✦ Pertinence profil</option>
          <option value="close_date">Date limite</option>
          <option value="amount_max">Montant</option>
          <option value="updated_at">Nouveauté</option>
          <option value="confidence">Fiabilité</option>
          <option value="ai_readiness">Score IA</option>
        </select>
      </div>

      {userIsStaff && (
        <div className="mb-4 rounded-[24px] border border-slate-200 bg-white p-3 shadow-[0_12px_35px_-28px_rgba(15,23,42,0.35)]">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              {quickFilters.map(([kind, label]) => (
                <button
                  key={kind}
                  type="button"
                  onClick={() => applyQuickFilter(kind)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-primary-200 hover:bg-primary-50 hover:text-primary-700"
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={handleSaveSearch}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-primary-700"
            >
              <BookmarkPlus className="h-3.5 w-3.5" />
              Sauvegarder cette recherche
            </button>
          </div>
        </div>
      )}

      {/* Panneau filtres */}
      {userIsStaff && showFilters && (
        <div className="card p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-700">Filtres</h3>
            {hasFilters && (
              <button onClick={clearFilters} className="text-xs text-red-500 flex items-center gap-1">
                <X className="w-3 h-3" /> Réinitialiser
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            {/* Pays */}
            <div>
              <p className="label">Pays</p>
              <div className="flex flex-wrap gap-1">
                {COUNTRIES.map(c => (
                  <button key={c} onClick={() => toggleFilter(filterCountries, setFilterCountries, c)}
                    className={clsx("badge cursor-pointer", filterCountries.includes(c)
                      ? "bg-primary-100 text-primary-700 border border-primary-300"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {/* Type — uniquement si la page expose des choix */}
            {availableDeviceTypes.length > 0 && (
              <div>
                <p className="label">Type</p>
                <div className="flex flex-wrap gap-1">
                  {availableDeviceTypes.map(k => (
                    <button key={k} onClick={() => toggleFilter(filterTypes, setFilterTypes, k)}
                      className={clsx("badge cursor-pointer", filterTypes.includes(k)
                        ? "bg-blue-100 text-blue-700"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                      {DEVICE_TYPE_LABELS[k] ?? k}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Secteurs */}
            <div>
              <p className="label">Secteurs</p>
              <div className="flex flex-wrap gap-1">
                {SECTORS.map(s => (
                  <button key={s} onClick={() => toggleFilter(filterSectors, setFilterSectors, s)}
                    className={clsx("badge cursor-pointer capitalize", filterSectors.includes(s)
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Statut + clôture */}
            <div className="space-y-3">
              <div>
                <p className="label">Statut</p>
                <div className="flex flex-wrap gap-1">
                  {STATUSES.map(s => (
                    <button key={s} onClick={() => toggleFilter(filterStatuses, setFilterStatuses, s)}
                      className={clsx("badge cursor-pointer", filterStatuses.includes(s)
                        ? "bg-orange-100 text-orange-700"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                      {STATUS_LABELS[s]}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="label">Pertinence</p>
                <div className="flex flex-wrap gap-1">
                  {Object.entries(AI_READINESS_LABELS).map(([key, label]) => (
                    <button
                      key={key}
                      onClick={() => toggleFilter(filterAiReadiness, setFilterAiReadiness, key)}
                      className={clsx("badge cursor-pointer", filterAiReadiness.includes(key)
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200")}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              {showClosingFilter && (
                <div>
                  <label className="label">Clôture dans</label>
                  <select className="input text-xs" value={closingSoon}
                    onChange={(e) => { setClosingSoon(e.target.value); setPage(1); }}>
                    <option value="">Toutes les dates</option>
                    <option value="7">7 jours</option>
                    <option value="30">30 jours</option>
                    <option value="60">60 jours</option>
                    <option value="90">90 jours</option>
                  </select>
                </div>
              )}
              <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={hasCloseDate}
                  onChange={(e) => {
                    setHasCloseDate(e.target.checked);
                    setPage(1);
                  }}
                  className="h-4 w-4 rounded border-gray-300 accent-primary-600"
                />
                Avec date limite renseignee
              </label>
            </div>
          </div>
        </div>
      )}

      {/* Retour actions groupées */}
      {bulkMsg && (
        <div className={clsx(
          "flex items-center gap-2 text-sm rounded-lg px-4 py-3 mb-3 border",
          bulkMsg.type === "success"
            ? "bg-green-50 border-green-200 text-green-700"
            : "bg-red-50 border-red-200 text-red-700",
        )}>
          <span>{bulkMsg.text}</span>
          <button onClick={() => setBulkMsg(null)} className="ml-auto opacity-60 hover:opacity-100">✕</button>
        </div>
      )}

      {/* Bandeau erreur API */}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-3">
          <span className="text-base">⚠️</span>
          <span>{error}</span>
          <button onClick={fetchDevices} className="ml-auto text-xs underline hover:no-underline">
            Réessayer
          </button>
        </div>
      )}

      {/* Résultats */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card p-4 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-1/4 mb-2" />
              <div className="h-4 bg-gray-200 rounded w-3/4 mb-1" />
              <div className="h-3 bg-gray-100 rounded w-full" />
            </div>
          ))}
        </div>
      ) : result?.items.length === 0 ? (
        <div className="text-center py-20 text-gray-400">
          <Search className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Aucun résultat trouvé</p>
          <p className="text-sm">Essayez de modifier vos filtres</p>
        </div>
      ) : (
        <>
          {viewMode === "cards" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {result?.items.map((device) => (
                <div key={device.id} className="space-y-2">
                  <DeviceCard
                    device={device}
                    selected={selectedIds.has(device.id)}
                    onSelect={toggleSelect}
                  />
                  {buildRelevanceExplanation(device) && (
                    <div className="rounded-2xl border border-primary-100 bg-primary-50/70 px-4 py-2 text-xs font-medium text-primary-700">
                      {buildRelevanceExplanation(device)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="overflow-hidden rounded-[26px] border border-slate-200 bg-white shadow-[0_14px_40px_-28px_rgba(15,23,42,0.35)]">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1020px] text-sm">
                  <thead className="border-b border-slate-200 bg-slate-50/80">
                    <tr className="text-left text-[11px] uppercase tracking-[0.14em] text-slate-500">
                      <th className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={allPageSelected}
                          onChange={toggleAllPageSelection}
                          className="h-4 w-4 rounded border-gray-300 accent-primary-600"
                          aria-label="Sélectionner toute la page"
                        />
                      </th>
                      <th className="px-4 py-3">Opportunité</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Pays</th>
                      <th className="px-4 py-3">Montant</th>
                      <th className="px-4 py-3">Clôture</th>
                      <th className="px-4 py-3">Statut</th>
                      <th className="px-4 py-3">Pertinence</th>
                      <th className="px-4 py-3">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result?.items.map((device) => (
                      <tr key={device.id} className="border-b border-slate-100 align-top transition-colors hover:bg-slate-50/70">
                        <td className="px-4 py-4">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(device.id)}
                            onChange={() => toggleSelect(device.id)}
                            className="h-4 w-4 rounded border-gray-300 accent-primary-600"
                            aria-label={`Sélectionner ${device.title}`}
                          />
                        </td>
                        <td className="min-w-[340px] px-4 py-4">
                          <button
                            type="button"
                            onClick={() => router.push(`/devices/${device.id}`)}
                            className="block text-left group"
                          >
                            <div className="font-semibold leading-6 text-slate-900 group-hover:text-primary-700">
                              {device.title}
                            </div>
                          </button>
                          <div className="mt-1 text-xs text-slate-500">{device.organism}</div>
                          {device.short_description && (
                            <p className="mt-2 line-clamp-2 max-w-xl text-sm leading-6 text-slate-600">
                              {device.short_description}
                            </p>
                          )}
                          {buildRelevanceExplanation(device) && (
                            <p className="mt-2 inline-flex rounded-full bg-primary-50 px-2.5 py-1 text-xs font-medium text-primary-700">
                              {buildRelevanceExplanation(device)}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-4">
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                            {DEVICE_TYPE_LABELS[device.device_type] || device.device_type}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-slate-700">
                          {[device.country, device.region].filter(Boolean).join(" · ") || "Non renseigné"}
                        </td>
                        <td className="px-4 py-4 text-slate-700">
                          {device.amount_max ? formatAmount(device.amount_max, device.currency) : "À confirmer"}
                        </td>
                        <td className="px-4 py-4">
                          {device.close_date ? (
                            <span className="font-medium text-slate-800">{formatDate(device.close_date)}</span>
                          ) : (
                            <span className="text-slate-400">{device.status === "recurring" ? "Récurrent" : "Non communiquée"}</span>
                          )}
                        </td>
                        <td className="px-4 py-4">
                          <span
                            className={clsx(
                              "rounded-full px-2.5 py-1 text-xs font-medium",
                              device.status === "open" && "bg-green-100 text-green-700",
                              device.status === "recurring" && "bg-blue-100 text-blue-700",
                              device.status === "closed" && "bg-slate-200 text-slate-700",
                              device.status === "expired" && "bg-red-100 text-red-700",
                            )}
                          >
                            {STATUS_LABELS[device.status] || device.status}
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          {(() => {
                            const meta = getAiReadinessMeta(device);
                            return (
                              <span className={clsx("rounded-full border px-2.5 py-1 text-xs font-medium", meta.className)} title={meta.detail}>
                                {meta.label}
                              </span>
                            );
                          })()}
                        </td>
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-2">
                            <span className="max-w-[180px] truncate text-slate-600">{device.organism}</span>
                            {device.source_url && (
                              <a
                                href={device.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-slate-400 transition-colors hover:text-primary-600"
                                title="Ouvrir la source officielle"
                              >
                                <ExternalLink className="h-4 w-4" />
                              </a>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result && result.pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                className="btn-secondary text-xs disabled:opacity-40">
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm text-gray-600">Page {result.page} sur {result.pages}</span>
              <button onClick={() => setPage(p => Math.min(result.pages, p + 1))} disabled={page === result.pages}
                className="btn-secondary text-xs disabled:opacity-40">
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </>
      )}

      {/* Barre d'actions groupées flottante */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-4 left-2 right-2 sm:left-1/2 sm:right-auto sm:-translate-x-1/2 z-50 flex items-center gap-2 flex-wrap
                        bg-gray-900 text-white rounded-2xl shadow-2xl px-4 py-3 sm:max-w-xl">
          <div className="flex items-center gap-2 pr-3 border-r border-gray-700">
            <CheckSquare className="w-4 h-4 text-primary-400" />
            <span className="text-sm font-medium">{selectedIds.size} sélectionné{selectedIds.size > 1 ? "s" : ""}</span>
            <button onClick={selectAllPage} className="text-xs text-gray-400 hover:text-white underline">Tout la page</button>
            <button onClick={clearSelection} className="text-gray-500 hover:text-white" title="Désélectionner">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="flex items-center gap-1.5">
            <button onClick={() => handleBulkAction("validate")} disabled={bulkLoading}
              className="flex items-center gap-1.5 text-xs bg-green-600 hover:bg-green-500 disabled:opacity-50 px-3 py-1.5 rounded-lg font-medium">
              <ShieldCheck className="w-3.5 h-3.5" /> Valider
            </button>
            <button onClick={() => handleBulkAction("reject")} disabled={bulkLoading}
              className="flex items-center gap-1.5 text-xs bg-orange-600 hover:bg-orange-500 disabled:opacity-50 px-3 py-1.5 rounded-lg font-medium">
              <XCircle className="w-3.5 h-3.5" /> Rejeter
            </button>
            {showTagInput ? (
              <div className="flex items-center gap-1.5">
                <input autoFocus type="text" value={tagInput}
                  onChange={e => setTagInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleBulkAction("tag")}
                  placeholder="tag1, tag2…"
                  className="text-xs bg-gray-800 border border-gray-600 rounded-lg px-2 py-1.5 text-white placeholder-gray-500 w-32 focus:outline-none focus:border-primary-400"
                />
                <button onClick={() => handleBulkAction("tag")} disabled={bulkLoading || !tagInput.trim()}
                  className="text-xs bg-primary-600 hover:bg-primary-500 disabled:opacity-50 px-2.5 py-1.5 rounded-lg font-medium">
                  OK
                </button>
                <button onClick={() => { setShowTagInput(false); setTagInput(""); }} className="text-gray-500 hover:text-white">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <button onClick={() => handleBulkAction("tag")} disabled={bulkLoading}
                className="flex items-center gap-1.5 text-xs bg-gray-700 hover:bg-gray-600 disabled:opacity-50 px-3 py-1.5 rounded-lg font-medium">
                <Tag className="w-3.5 h-3.5" /> Tagger
              </button>
            )}
            {deleteConfirmBulk ? (
              <div className="flex items-center gap-1">
                <button onClick={() => handleBulkAction("delete")} disabled={bulkLoading}
                  className="flex items-center gap-1.5 text-xs bg-red-600 hover:bg-red-500 disabled:opacity-50 px-3 py-1.5 rounded-lg font-medium">
                  {bulkLoading
                    ? <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    : <Trash2 className="w-3.5 h-3.5" />}
                  Confirmer
                </button>
                <button onClick={() => setDeleteConfirmBulk(false)} className="text-xs text-gray-400 hover:text-white px-1">Annuler</button>
              </div>
            ) : (
              <button onClick={() => handleBulkAction("delete")} disabled={bulkLoading}
                className="flex items-center gap-1.5 text-xs bg-red-700/70 hover:bg-red-600 disabled:opacity-50 px-3 py-1.5 rounded-lg font-medium">
                <Trash2 className="w-3.5 h-3.5" /> Supprimer
              </button>
            )}
          </div>
        </div>
      )}
    </AppLayout>
  );
}
