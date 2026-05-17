"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import AppLayout from "@/components/AppLayout";
import LimitNotice from "@/components/LimitNotice";
import { billing, devices, relevance } from "@/lib/api";
import { canAccessAdmin, getCurrentRole } from "@/lib/auth";
import { Device, DeviceListResponse, DEVICE_TYPE_COLORS, STATUS_LABELS, STATUS_COLORS } from "@/lib/types";
import { getUserDeviceTypeMeta } from "@/lib/deviceTypes";
import { COUNTRIES, SECTORS } from "@/lib/constants";
import { formatAmount, formatDate, daysUntil, getAiReadinessMeta, getDeviceNatureBanner, sanitizeDisplayText } from "@/lib/utils";
import { consumePendingSavedSearch, getSavedViewMode, getUserPreferences, saveSearch, saveUserPreferences, setSavedViewMode, isFavoriteDevice, toggleFavoriteDevice, getPipelineDevice, type DevicePipelineStatus } from "@/lib/workspace";
import {
  Search, SlidersHorizontal, Download, Plus,
  ChevronLeft, ChevronRight, X,
  ShieldCheck, XCircle, Trash2, Tag, CheckSquare,
  FileSpreadsheet, FileText, ChevronDown, Rows3, ExternalLink, BookmarkPlus,
  UserCircle2, Heart, Flag, Calendar, Building2, MapPin, Zap,
  ArrowUpRight, AlertTriangle, ThumbsUp, ThumbsDown, AlertCircle,
} from "lucide-react";
import clsx from "clsx";

const STATUSES = ["open", "recurring", "standby", "closed", "expired"];
const DEVICE_FILTERS_SESSION_PREFIX = "kafundo_devices_filters:";
const AI_READINESS_LABELS: Record<string, string> = {
  pret_pour_recommandation_ia: "Très recommandé",
  utilisable_avec_prudence: "À confirmer",
  a_verifier: "À vérifier",
  non_exploitable: "Non recommandé",
};
const STATUS_LABELS_DISPLAY: Record<string, string> = {
  open: "Ouvert", recurring: "Récurrent", standby: "Clôture non communiquée", closed: "Fermé", expired: "Expiré",
};

const PIPELINE_LABELS: Record<DevicePipelineStatus, string> = {
  a_etudier: "À étudier", interessant: "Prioritaire",
  candidature_en_cours: "En cours", soumis: "Soumis",
  refuse: "Refusé", non_pertinent: "Non pertinent",
};
const PIPELINE_COLORS: Record<DevicePipelineStatus, string> = {
  a_etudier: "bg-amber-100 text-amber-700",
  interessant: "bg-violet-100 text-violet-700",
  candidature_en_cours: "bg-blue-100 text-blue-700",
  soumis: "bg-indigo-100 text-indigo-700",
  refuse: "bg-red-100 text-red-700",
  non_pertinent: "bg-slate-100 text-slate-600",
};

interface Props {
  title: string;
  lockedDeviceTypes: string[];
  availableDeviceTypes: string[];
  defaultSort?: string;
  showClosingFilter?: boolean;
  newDeviceHref?: string;
  actionableNow?: boolean;
  introTitle?: string;
  introText?: string;
}

type ViewMode = "split" | "table";

type PersistedDeviceFilters = {
  q?: string;
  countries?: string[];
  deviceTypes?: string[];
  sectors?: string[];
  statuses?: string[];
  aiReadiness?: string[];
  closingSoon?: string;
  hasCloseDate?: boolean;
  actionableNow?: boolean | null;
  adminFullCatalog?: boolean;
  sortBy?: string;
  page?: number;
};

// ── Volet droit : résumé d'un dispositif ────────────────────────────────────

function DevicePanel({
  device,
  onClose,
  buildRelevanceExplanation,
}: {
  device: Device;
  onClose: () => void;
  buildRelevanceExplanation: (d: any) => string;
}) {
  const daysLeft = device.close_date ? daysUntil(device.close_date) : null;
  const isClosingSoon = daysLeft !== null && daysLeft >= 0 && daysLeft <= 14;
  const aiReadiness = getAiReadinessMeta(device);
  const [favorite, setFavorite] = useState(false);
  const [pipelineStatus, setPipelineStatus] = useState<DevicePipelineStatus | null>(null);

  useEffect(() => {
    setFavorite(isFavoriteDevice(device.id));
    setPipelineStatus(getPipelineDevice(device.id)?.pipelineStatus || null);
  }, [device.id]);

  const handleToggleFavorite = () => {
    const next = toggleFavoriteDevice({
      id: device.id, title: device.title, organism: device.organism,
      country: device.country, region: device.region, deviceType: device.device_type,
      status: device.status, closeDate: device.close_date,
      amountMax: device.amount_max, currency: device.currency, sourceUrl: device.source_url,
    });
    setFavorite(next);
  };

  const matchReason = buildRelevanceExplanation(device);
  const description = sanitizeDisplayText(device.short_description || device.auto_summary);
  const eligibility  = sanitizeDisplayText(device.eligibility_criteria);
  const fundingInfo  = sanitizeDisplayText(device.funding_details);
  const natureBanner = getDeviceNatureBanner(device);
  const typeMeta = getUserDeviceTypeMeta(device.device_type);

  const goNoGo = device.decision_analysis?.go_no_go;
  const goNoGoCfg = goNoGo === "go"
    ? { cls: "bg-emerald-50 border-emerald-200 text-emerald-800", Icon: ThumbsUp,   label: "Bonne opportunité" }
    : goNoGo === "no_go"
    ? { cls: "bg-red-50 border-red-200 text-red-800",             Icon: ThumbsDown, label: "Peu recommandé" }
    : goNoGo === "a_verifier"
    ? { cls: "bg-amber-50 border-amber-200 text-amber-800",       Icon: AlertCircle,label: "À vérifier" }
    : null;

  return (
    <div className="flex h-full flex-col">
      {/* Header fixe */}
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={clsx("rounded-full px-2.5 py-1 text-[11px] font-semibold", typeMeta.color || DEVICE_TYPE_COLORS[device.device_type] || "bg-slate-100 text-slate-600")} title={typeMeta.short}>
            {typeMeta.label}
          </span>
          <span className={clsx("rounded-full px-2.5 py-1 text-[11px] font-semibold", STATUS_COLORS[device.status])}>
            {STATUS_LABELS[device.status] || device.status}
          </span>
          {pipelineStatus && (
            <span className={clsx("flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold", PIPELINE_COLORS[pipelineStatus])}>
              <Flag className="h-3 w-3" />{PIPELINE_LABELS[pipelineStatus]}
            </span>
          )}
          {isClosingSoon && daysLeft !== null && (
            <span className="rounded-full bg-orange-100 px-2.5 py-1 text-[11px] font-bold text-orange-700">
              J-{daysLeft}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={handleToggleFavorite}
            className={clsx(
              "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
              favorite ? "bg-rose-100 text-rose-700 hover:bg-rose-200" : "bg-slate-100 text-slate-500 hover:bg-slate-200",
            )}
            title={favorite ? "Retirer des favoris" : "Ajouter aux favoris"}
          >
            <Heart className={clsx("h-3.5 w-3.5", favorite && "fill-current")} />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 md:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Corps défilable */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

        {/* Titre + organisme */}
        <div>
          <h2 className="text-lg font-bold leading-snug text-slate-950">{device.title}</h2>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
            <span className="flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5 shrink-0" />{device.organism}
            </span>
            <span className="flex items-center gap-1.5">
              <MapPin className="h-3.5 w-3.5 shrink-0" />
              {[device.country, device.region].filter(Boolean).join(" · ") || "Non renseigné"}
            </span>
          </div>
        </div>

        {/* Pourquoi ça correspond */}
        {(matchReason || device.relevance_label) && (
          <div className="rounded-2xl border border-primary-100 bg-primary-50/70 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-primary-600 mb-2">
              Pourquoi cette opportunité correspond
            </p>
            {device.relevance_label && (
              <p className="text-sm font-semibold text-primary-900 mb-1">{device.relevance_label}</p>
            )}
            {device.relevance_reasons?.length ? (
              <ul className="space-y-1">
                {device.relevance_reasons.slice(0, 4).map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-primary-800">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary-400" />
                    {r}
                  </li>
                ))}
              </ul>
            ) : matchReason ? (
              <p className="text-sm text-primary-800">{matchReason}</p>
            ) : null}
          </div>
        )}

        {/* Avis IA go/no-go */}
        {goNoGoCfg && device.decision_analysis && (
          <div className={clsx("rounded-2xl border px-4 py-3", goNoGoCfg.cls)}>
            <div className="flex items-center gap-1.5 mb-1">
              <goNoGoCfg.Icon className="h-3.5 w-3.5 shrink-0" />
              <p className="text-[10px] font-semibold uppercase tracking-widest">Avis IA · {goNoGoCfg.label}</p>
            </div>
            {(device.decision_analysis.recommended_action || device.decision_analysis.why_interesting) && (
              <p className="text-sm leading-6 opacity-90">
                {device.decision_analysis.recommended_action || device.decision_analysis.why_interesting}
              </p>
            )}
          </div>
        )}

        {/* Grille meta */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Date limite</p>
            <p className={clsx(
              "mt-1 text-sm font-semibold",
              isClosingSoon ? "text-orange-700" : device.close_date ? "text-slate-900" : "text-slate-400 italic",
            )}>
              {device.close_date
                ? formatDate(device.close_date)
                : natureBanner?.label || (device.status === "recurring" ? "Récurrent" : "Non communiquée")}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Montant</p>
            <p className={clsx("mt-1 text-sm font-semibold", device.amount_max ? "text-slate-900" : "text-slate-400 italic")}>
              {device.amount_max
                ? (device.amount_min && device.amount_min !== device.amount_max
                    ? `${formatAmount(device.amount_min, device.currency)} – ${formatAmount(device.amount_max, device.currency)}`
                    : `Jusqu'à ${formatAmount(device.amount_max, device.currency)}`)
                : "À confirmer"}
            </p>
          </div>
        </div>

        {/* Confiance IA */}
        <div className={clsx("rounded-2xl border px-4 py-2.5 text-sm", aiReadiness.className)}>
          <span className="text-[10px] font-semibold uppercase tracking-widest">{aiReadiness.label}</span>
          {aiReadiness.detail && <p className="mt-0.5 text-xs leading-5 opacity-80">{aiReadiness.detail}</p>}
        </div>

        {natureBanner && !device.close_date && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-800">
            <p className="text-[10px] font-semibold uppercase tracking-widest">{natureBanner.label}</p>
            <p className="mt-1 text-sm leading-6">{natureBanner.detail}</p>
          </div>
        )}

        {/* Présentation */}
        {description && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-2">Présentation</p>
            <p className="text-sm leading-6 text-slate-700 line-clamp-5">{description}</p>
          </div>
        )}

        {/* Conditions d'éligibilité */}
        {eligibility && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-2">Conditions d'éligibilité</p>
            <p className="text-sm leading-6 text-slate-700 line-clamp-4">{eligibility}</p>
          </div>
        )}

        {/* Montant / avantages */}
        {fundingInfo && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-2">Montant & avantages</p>
            <p className="text-sm leading-6 text-slate-700 line-clamp-3">{fundingInfo}</p>
          </div>
        )}

        {/* Secteurs */}
        {(device.sectors || []).length > 0 && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 mb-2">Secteurs</p>
            <div className="flex flex-wrap gap-1.5">
              {(device.sectors || []).map((s) => (
                <span key={s} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs capitalize text-slate-600">{s}</span>
              ))}
            </div>
          </div>
        )}

        {/* Score de confiance */}
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <div className={clsx("h-2 w-2 rounded-full", device.confidence_score >= 70 ? "bg-green-400" : device.confidence_score >= 40 ? "bg-yellow-400" : "bg-red-400")} />
          Fiabilité de la fiche : {device.confidence_score}%
        </div>
      </div>

      {/* Actions bas de volet */}
      <div className="shrink-0 border-t border-slate-100 px-5 py-4 space-y-2.5">
        <Link
          href={`/devices/${device.id}`}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-primary-700"
        >
          Voir la fiche complète
          <ArrowUpRight className="h-4 w-4" />
        </Link>
        {device.source_url && (
          <a
            href={device.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            <ExternalLink className="h-4 w-4 text-slate-400" />
            Source officielle
          </a>
        )}
      </div>
    </div>
  );
}

// ── Composant principal ──────────────────────────────────────────────────────

export default function DevicesPageContent({
  title,
  lockedDeviceTypes,
  availableDeviceTypes,
  defaultSort = "updated_at",
  showClosingFilter = true,
  newDeviceHref = "/devices/new",
  actionableNow = false,
  introTitle,
  introText,
}: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const panelRef = useRef<HTMLDivElement>(null);

  const [result,          setResult]          = useState<DeviceListResponse | null>(null);
  const [loading,         setLoading]         = useState(true);
  const [error,           setError]           = useState<string | null>(null);
  const [showFilters,     setShowFilters]     = useState(false);
  const [selectedDevice,  setSelectedDevice]  = useState<Device | null>(null);

  // Sélection & actions groupées
  const [selectedIds,       setSelectedIds]       = useState<Set<string>>(new Set());
  const [bulkLoading,       setBulkLoading]       = useState(false);
  const [bulkMsg,           setBulkMsg]           = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [showTagInput,      setShowTagInput]      = useState(false);
  const [tagInput,          setTagInput]          = useState("");
  const [deleteConfirmBulk, setDeleteConfirmBulk] = useState(false);

  // Filtres
  const [q,                setQ]                = useState("");
  const [debouncedQ,       setDebouncedQ]       = useState("");
  const [filterCountries,  setFilterCountries]  = useState<string[]>([]);
  const [filterTypes,      setFilterTypes]      = useState<string[]>([]);
  const [filterSectors,    setFilterSectors]    = useState<string[]>([]);
  const [filterStatuses,   setFilterStatuses]   = useState<string[]>([]);
  const [filterAiReadiness,setFilterAiReadiness]= useState<string[]>([]);
  const [closingSoon,      setClosingSoon]      = useState("");
  const [hasCloseDate,     setHasCloseDate]     = useState(false);
  const [sortBy,           setSortBy]           = useState(defaultSort);
  const [page,             setPage]             = useState(1);
  const [showExportMenu,   setShowExportMenu]   = useState(false);
  const [viewMode,         setViewMode]         = useState<ViewMode>("split");
  const [editingSavedSearchId, setEditingSavedSearchId] = useState<string | null>(null);
  const [exportsAllowed,   setExportsAllowed]   = useState(true);
  const [profileActive,    setProfileActive]    = useState(false);
  const [userIsStaff,      setUserIsStaff]      = useState(false);
  const [profileReady,     setProfileReady]     = useState(false);
  const [adminFullCatalog, setAdminFullCatalog] = useState(() => canAccessAdmin(getCurrentRole()));
  const [savedActionableNow, setSavedActionableNow] = useState<boolean | null>(null);
  const effectiveActionableNow = savedActionableNow ?? actionableNow;
  const adminCatalogEnabled = userIsStaff && adminFullCatalog;

  const applyPersistedFilters = useCallback((filters: PersistedDeviceFilters) => {
    const restoredTypes = Array.isArray(filters.deviceTypes) ? filters.deviceTypes : [];
    const allowedTypes = restoredTypes.filter((type) => !lockedDeviceTypes.length || lockedDeviceTypes.includes(type));
    setQ(filters.q || "");
    setDebouncedQ(filters.q || "");
    setFilterCountries(Array.isArray(filters.countries) ? filters.countries : []);
    setFilterTypes(allowedTypes);
    setFilterSectors(Array.isArray(filters.sectors) ? filters.sectors : []);
    setFilterStatuses(Array.isArray(filters.statuses) ? filters.statuses : []);
    setFilterAiReadiness(Array.isArray(filters.aiReadiness) ? filters.aiReadiness : []);
    setClosingSoon(filters.closingSoon || "");
    setHasCloseDate(Boolean(filters.hasCloseDate));
    setSavedActionableNow(typeof filters.actionableNow === "boolean" ? filters.actionableNow : null);
    if (typeof filters.adminFullCatalog === "boolean") setAdminFullCatalog(filters.adminFullCatalog);
    setSortBy(filters.sortBy || defaultSort);
    setPage(filters.page && filters.page > 0 ? filters.page : 1);
  }, [defaultSort, lockedDeviceTypes]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(q), 300);
    return () => clearTimeout(timer);
  }, [q]);

  useEffect(() => {
    billing.subscription()
      .then((s: any) => setExportsAllowed(!!s?.features?.exports))
      .catch(() => setExportsAllowed(true));
  }, []);

  useEffect(() => {
    const preferredView = getSavedViewMode(pathname) || getUserPreferences().defaultViewMode;
    if (preferredView === "table") setViewMode("table");

    const pendingSearch = consumePendingSavedSearch(pathname);
    if (pendingSearch) {
      applyPersistedFilters({
        q: pendingSearch.search.filters.q,
        countries: pendingSearch.search.filters.countries,
        deviceTypes: pendingSearch.search.filters.deviceTypes,
        sectors: pendingSearch.search.filters.sectors,
        statuses: pendingSearch.search.filters.statuses,
        closingSoon: pendingSearch.search.filters.closingSoon,
        hasCloseDate: pendingSearch.search.filters.hasCloseDate,
        actionableNow: pendingSearch.search.filters.actionableNow,
        sortBy: pendingSearch.search.filters.sortBy || defaultSort,
        page: 1,
      });
      setEditingSavedSearchId(pendingSearch.mode === "edit" ? pendingSearch.search.id : null);
      setProfileReady(true);
      return;
    }

    const sessionKey = `${DEVICE_FILTERS_SESSION_PREFIX}${pathname}`;
    let restoredFromSession = false;
    try {
      const raw = window.sessionStorage.getItem(sessionKey);
      if (raw) {
        applyPersistedFilters(JSON.parse(raw));
        restoredFromSession = true;
      } else {
        setSavedActionableNow(null);
      }
    } catch {
      setSavedActionableNow(null);
    }

    const role = getCurrentRole();
    const isStaff = canAccessAdmin(role);
    setUserIsStaff(isStaff);
    if (isStaff && !restoredFromSession) {
      setAdminFullCatalog(true);
    } else if (!isStaff) {
      setAdminFullCatalog(false);
    }

    // Pour les utilisateurs normaux, le filtre pays est appliqué silencieusement
    // côté backend. On affiche juste la bannière "Contenu personnalisé" pour informer.
    if (!isStaff) {
      relevance.getProfile().then((profile: any) => {
        const hasProfile = profile && (profile.countries?.length || profile.sectors?.length);
        if (hasProfile) setProfileActive(true);
        setPage(1);
        if (!restoredFromSession) {
          const preferences = getUserPreferences();
          const onboardingTypes = Array.isArray(preferences.onboardingDeviceTypes)
            ? preferences.onboardingDeviceTypes.filter((type) => !lockedDeviceTypes.length || lockedDeviceTypes.includes(type))
            : [];
          const profileSectors = Array.isArray(profile?.sectors) ? profile.sectors : [];
          const onboardingSectors = Array.isArray(preferences.onboardingSectors) ? preferences.onboardingSectors : [];
          setFilterTypes(onboardingTypes);
          setFilterSectors(onboardingSectors.length ? onboardingSectors : profileSectors);
          setFilterStatuses(actionableNow ? ["open", "recurring"] : []);
          setSavedActionableNow(actionableNow);
          setSortBy(defaultSort);
          setPage(1);
        }
        setProfileReady(true);
      }).catch(() => setProfileReady(true));
      return;
    }

    setProfileReady(true);
  }, [pathname, defaultSort, applyPersistedFilters, lockedDeviceTypes, actionableNow]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setSavedViewMode(pathname, viewMode);
    saveUserPreferences({ ...getUserPreferences(), defaultViewMode: viewMode });
  }, [pathname, viewMode]);

  // Scroll automatique vers le haut du volet à chaque changement de device
  useEffect(() => {
    if (selectedDevice && panelRef.current) {
      panelRef.current.scrollTop = 0;
    }
  }, [selectedDevice?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!profileReady) return;
    const payload: PersistedDeviceFilters = {
      q,
      countries: filterCountries,
      deviceTypes: filterTypes,
      sectors: filterSectors,
      statuses: filterStatuses,
      aiReadiness: filterAiReadiness,
      closingSoon,
      hasCloseDate,
      actionableNow: savedActionableNow,
      adminFullCatalog: adminCatalogEnabled,
      sortBy,
      page,
    };
    window.sessionStorage.setItem(`${DEVICE_FILTERS_SESSION_PREFIX}${pathname}`, JSON.stringify(payload));
  }, [profileReady, pathname, q, filterCountries, filterTypes, filterSectors, filterStatuses, filterAiReadiness, closingSoon, hasCloseDate, savedActionableNow, adminCatalogEnabled, sortBy, page]);

  const fetchDevices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const effectiveTypes = adminCatalogEnabled
        ? (filterTypes.length > 0 ? filterTypes : undefined)
        : filterTypes.length > 0 ? filterTypes : lockedDeviceTypes.length > 0 ? lockedDeviceTypes : undefined;
      const data = await devices.list({
        q: debouncedQ || undefined,
        countries:          filterCountries.length   ? filterCountries   : undefined,
        device_types:       effectiveTypes,
        sectors:            filterSectors.length     ? filterSectors     : undefined,
        status:             filterStatuses.length    ? filterStatuses    : undefined,
        ai_readiness_labels:filterAiReadiness.length ? filterAiReadiness : undefined,
        closing_soon_days:  closingSoon ? parseInt(closingSoon) : undefined,
        has_close_date:     hasCloseDate || undefined,
        actionable_now:     adminCatalogEnabled ? undefined : effectiveActionableNow || undefined,
        include_all_statuses: adminCatalogEnabled || undefined,
        include_rejected: adminCatalogEnabled || undefined,
        include_low_quality: adminCatalogEnabled || undefined,
        sort_by:            sortBy,
        sort_desc:          sortBy !== "close_date",
        page,
        page_size: viewMode === "table" ? 50 : 30,
      });
      if (data.total > 0 && data.items.length === 0 && page > 1) {
        setPage(1);
        return;
      }
      setResult(data);
      // Sélectionner automatiquement le premier élément en vue split
      if (viewMode === "split" && data.items.length > 0) {
        setSelectedDevice((prev) => prev ?? (data.items[0] as Device));
      } else if (data.items.length === 0) {
        setSelectedDevice(null);
      }
    } catch {
      setError("Impossible de charger les opportunités. Vérifiez votre connexion.");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, filterCountries, filterTypes, filterSectors, filterStatuses, filterAiReadiness, closingSoon, hasCloseDate, effectiveActionableNow, adminCatalogEnabled, sortBy, page, viewMode, lockedDeviceTypes]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { if (profileReady) fetchDevices(); }, [fetchDevices, profileReady]);

  const toggleFilter = (arr: string[], setArr: (v: string[]) => void, val: string) => {
    setArr(arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val]);
    setPage(1);
  };

  const clearFilters = () => {
    setFilterCountries([]); setFilterTypes([]); setFilterSectors([]);
    setFilterStatuses([]); setFilterAiReadiness([]); setClosingSoon(""); setHasCloseDate(false); setPage(1);
    setEditingSavedSearchId(null); setProfileActive(false); setAdminFullCatalog(userIsStaff); setSavedActionableNow(null);
  };

  const hasFilters = filterCountries.length || filterTypes.length || filterSectors.length ||
    filterStatuses.length || filterAiReadiness.length || closingSoon || hasCloseDate || adminCatalogEnabled;

  const pageIds = result?.items.map((d) => d.id) ?? [];
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };
  const selectAllPage = () => {
    setSelectedIds((prev) => { const n = new Set(prev); pageIds.forEach((id) => n.add(id)); return n; });
  };
  const toggleAllPageSelection = () => {
    if (allPageSelected) { setSelectedIds((prev) => { const n = new Set(prev); pageIds.forEach((id) => n.delete(id)); return n; }); return; }
    selectAllPage();
  };
  const clearSelection = () => { setSelectedIds(new Set()); setDeleteConfirmBulk(false); setShowTagInput(false); setTagInput(""); setBulkMsg(null); };

  const handleBulkAction = async (action: "validate" | "reject" | "delete" | "tag") => {
    if (action === "delete" && !deleteConfirmBulk) { setDeleteConfirmBulk(true); return; }
    if (action === "tag" && !showTagInput) { setShowTagInput(true); return; }
    const tags = action === "tag" ? tagInput.split(",").map((t) => t.trim()).filter(Boolean) : undefined;
    if (action === "tag" && (!tags || tags.length === 0)) return;
    setBulkLoading(true); setBulkMsg(null);
    try {
      const res = await devices.bulkAction(Array.from(selectedIds), action, tags);
      setBulkMsg({
        type: res.failed === 0 ? "success" : "error",
        text: res.failed === 0 ? `✓ ${res.processed} opportunité(s) traitée(s).` : `${res.processed} traité(s), ${res.failed} en erreur.`,
      });
      clearSelection(); fetchDevices();
    } catch (e: any) {
      setBulkMsg({ type: "error", text: e.message || "Erreur lors de l'action groupée." });
    } finally { setBulkLoading(false); setDeleteConfirmBulk(false); }
  };

  const handleSaveSearch = () => {
    const defaultName = q.trim() ? `${title} - ${q.trim()}` : `${title} - vue enregistrée`;
    let suggestedName = defaultName;
    if (editingSavedSearchId) {
      try {
        const parsed = JSON.parse(window.localStorage.getItem("kafundo_saved_searches") || "[]") as Array<{ id: string; name: string }>;
        suggestedName = parsed.find((item) => item.id === editingSavedSearchId)?.name || defaultName;
      } catch { /* ignore */ }
    }
    const name = window.prompt(editingSavedSearchId ? "Mettre à jour le nom de cette recherche" : "Nom de cette recherche enregistrée", suggestedName)?.trim();
    if (!name) return;
    saveSearch({
      id: editingSavedSearchId || crypto.randomUUID(), name, title, path: pathname,
      resultCount: result?.total ?? null, savedAt: new Date().toISOString(),
      filters: { q: q.trim(), countries: filterCountries, deviceTypes: filterTypes, sectors: filterSectors, statuses: filterStatuses, closingSoon, hasCloseDate, actionableNow: effectiveActionableNow, sortBy },
    });
    setBulkMsg({ type: "success", text: editingSavedSearchId ? `Recherche mise à jour : ${name}` : `Recherche enregistrée : ${name}` });
    setEditingSavedSearchId(null);
  };

  const effectiveTypesForExport = adminCatalogEnabled
    ? (filterTypes.length > 0 ? filterTypes : undefined)
    : filterTypes.length > 0 ? filterTypes : lockedDeviceTypes.length > 0 ? lockedDeviceTypes : undefined;
  const exportParams = {
    q: debouncedQ || undefined, countries: filterCountries.length ? filterCountries : undefined,
    device_types: effectiveTypesForExport, sectors: filterSectors.length ? filterSectors : undefined,
    status: filterStatuses.length ? filterStatuses : undefined,
    ai_readiness_labels: filterAiReadiness.length ? filterAiReadiness : undefined,
    closing_soon_days: closingSoon ? parseInt(closingSoon) : undefined,
    has_close_date: hasCloseDate || undefined,
    actionable_now: adminCatalogEnabled ? undefined : effectiveActionableNow || undefined,
    include_all_statuses: adminCatalogEnabled || undefined,
    include_rejected: adminCatalogEnabled || undefined,
    include_low_quality: adminCatalogEnabled || undefined,
  };
  const exportCsvUrl   = devices.exportCsv(exportParams);
  const exportExcelUrl = devices.exportExcel(exportParams);

  const applyQuickFilter = (kind: string) => {
    setPage(1); setEditingSavedSearchId(null);
    if (kind === "open")            { setFilterStatuses(["open"]); return; }
    if (kind === "with_deadline")   { setHasCloseDate(true); setFilterStatuses(["open"]); setSortBy("close_date"); return; }
    if (kind === "subvention")      { setFilterTypes(["subvention"]); return; }
    if (kind === "investissement")  { setFilterTypes(["investissement"]); return; }
    if (kind === "afrique")         { setFilterCountries(["Afrique", "Afrique de l'Ouest"]); return; }
    if (kind === "france")          { setFilterCountries(["France"]); return; }
    if (kind === "30days")          { setClosingSoon("30"); setHasCloseDate(true); setFilterStatuses(["open"]); return; }
    if (kind === "ai_ready")        { setFilterAiReadiness(["pret_pour_recommandation_ia"]); setSortBy("ai_readiness"); }
  };

  const buildRelevanceExplanation = (device: any) => {
    if (device.match_reasons?.length) return `Correspondance : ${device.match_reasons.slice(0, 3).join(" + ")}.`;
    const reasons: string[] = [];
    if (filterCountries.includes(device.country)) reasons.push(`pays ${device.country}`);
    if (filterTypes.includes(device.device_type)) reasons.push(`type ${getUserDeviceTypeMeta(device.device_type).label}`);
    const matchedSector = filterSectors.find((s) => (device.sectors || []).includes(s));
    if (matchedSector) reasons.push(`secteur ${matchedSector}`);
    if (q.trim()) reasons.push(`recherche "${q.trim()}"`);
    if (closingSoon) reasons.push(`échéance dans ${closingSoon} jours`);
    if (!reasons.length) return "";
    return `Correspond à votre ${reasons.slice(0, 3).join(" + ")}.`;
  };

  const quickFilters = [
    ["open", "Ouverts"], ["with_deadline", "Avec date limite"], ["subvention", "Subventions"],
    ["investissement", "Investissement"], ["afrique", "Afrique"], ["france", "France"],
    ["30days", "Moins de 30 jours"], ["ai_ready", "Recommandés"],
  ].filter(([kind]) => {
    // Les filtres pays ne sont visibles que pour les admins
    if ((kind === "afrique" || kind === "france") && !userIsStaff) return false;
    if (kind === "investissement") return availableDeviceTypes.includes("investissement") || lockedDeviceTypes.includes("investissement") || lockedDeviceTypes.length === 0;
    if (kind === "subvention")     return availableDeviceTypes.includes("subvention")     || lockedDeviceTypes.includes("subvention")     || lockedDeviceTypes.length === 0;
    return true;
  });

  // ── Rendu d'une ligne de liste ───────────────────────────────────────────────
  const renderListRow = (device: Device) => {
    const daysLeft = device.close_date ? daysUntil(device.close_date) : null;
    const isUrgent = daysLeft !== null && daysLeft >= 0 && daysLeft <= 7;
    const isSoon   = daysLeft !== null && daysLeft >= 0 && daysLeft <= 30;
    const isSelected = selectedDevice?.id === device.id;
    const natureBanner = getDeviceNatureBanner(device);
    const typeMeta = getUserDeviceTypeMeta(device.device_type);

    return (
      <button
        key={device.id}
        type="button"
        onClick={() => setSelectedDevice(device as Device)}
        className={clsx(
          "group w-full border-b border-slate-100 px-4 py-3 text-left transition-colors focus:outline-none",
          isSelected
            ? "bg-primary-50 border-l-[3px] border-l-primary-500"
            : "hover:bg-slate-50 border-l-[3px] border-l-transparent",
        )}
      >
        <div className="flex items-start gap-3">
          {userIsStaff && (
            <input
              type="checkbox"
              checked={selectedIds.has(device.id)}
              onChange={(e) => { e.stopPropagation(); toggleSelect(device.id); }}
              onClick={(e) => e.stopPropagation()}
              className="mt-1 h-4 w-4 shrink-0 cursor-pointer rounded border-gray-300 accent-primary-600"
            />
          )}
          <div className="min-w-0 flex-1">
            {/* Badges */}
            <div className="flex flex-wrap items-center gap-1 mb-1">
              <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-semibold", typeMeta.color || DEVICE_TYPE_COLORS[device.device_type] || "bg-slate-100 text-slate-600")} title={typeMeta.short}>
                {typeMeta.label}
              </span>
              {device.status !== "open" && (
                <span className={clsx("rounded-full px-2 py-0.5 text-[10px] font-semibold", STATUS_COLORS[device.status])}>
                  {STATUS_LABELS_DISPLAY[device.status] || device.status}
                </span>
              )}
              {isUrgent && daysLeft !== null && (
                <span className="rounded-full bg-orange-100 px-2 py-0.5 text-[10px] font-bold text-orange-700">J-{daysLeft}</span>
              )}
            </div>
            {/* Titre */}
            <p className={clsx("line-clamp-2 text-sm font-semibold leading-snug", isSelected ? "text-primary-900" : "text-slate-900 group-hover:text-primary-700")}>
              {device.title}
            </p>
            {/* Organism */}
            <p className="mt-0.5 text-xs text-slate-400 line-clamp-1">{device.organism}</p>
          </div>
          {/* Méta droite */}
          <div className="shrink-0 text-right pl-2">
            <p className={clsx("text-xs font-medium tabular-nums", isUrgent ? "text-orange-600 font-bold" : isSoon ? "text-amber-600" : "text-slate-500")}>
              {device.close_date ? formatDate(device.close_date) : natureBanner?.label || (device.status === "recurring" ? "Récurrent" : "—")}
            </p>
            <p className={clsx("mt-0.5 text-xs font-semibold", device.amount_max ? "text-slate-900" : "text-slate-300")}>
              {device.amount_max ? formatAmount(device.amount_max, device.currency) : "—"}
            </p>
          </div>
        </div>
      </button>
    );
  };

  // ── Pagination compacte ──────────────────────────────────────────────────────
  const renderPagination = (compact = false) => {
    if (!result || result.pages <= 1) return null;
    return (
      <div className={clsx("flex items-center justify-between gap-2", compact ? "px-4 py-2.5 border-t border-slate-100" : "mt-4")}>
        <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
          className="btn-secondary text-xs disabled:opacity-40 py-1.5 px-3">
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>
        <span className="text-xs text-gray-500">Page {result.page} / {result.pages} <span className="text-gray-400">({result.total.toLocaleString("fr")} résultats)</span></span>
        <button onClick={() => setPage((p) => Math.min(result.pages, p + 1))} disabled={page === result.pages}
          className="btn-secondary text-xs disabled:opacity-40 py-1.5 px-3">
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  };

  return (
    <AppLayout>
      {/* ── En-tête ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-gray-900">{title}</h1>
          {result && <p className="text-sm text-gray-500">{result.total.toLocaleString("fr")} résultats</p>}
        </div>
        <div className="flex items-center gap-2">
          {/* Toggle vue */}
          <div className="hidden items-center rounded-xl border border-gray-200 bg-white p-1 sm:flex">
            <button type="button" onClick={() => setViewMode("split")}
              className={clsx("inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                viewMode === "split" ? "bg-slate-900 text-white" : "text-gray-500 hover:bg-gray-50 hover:text-gray-800")}>
              <Rows3 className="w-3.5 h-3.5" /> Liste
            </button>
            <button type="button" onClick={() => setViewMode("table")}
              className={clsx("inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                viewMode === "table" ? "bg-slate-900 text-white" : "text-gray-500 hover:bg-gray-50 hover:text-gray-800")}>
              <Rows3 className="w-3.5 h-3.5 rotate-90" /> Tableau
            </button>
          </div>
          <button type="button" onClick={handleSaveSearch} className="btn-secondary text-xs flex items-center gap-1.5">
            <BookmarkPlus className="w-3.5 h-3.5" />
            {editingSavedSearchId ? "Mettre à jour" : "Enregistrer"}
          </button>
          {/* Export */}
          <div className="relative">
            <button onClick={() => setShowExportMenu((v) => !v)} className="btn-secondary text-xs flex items-center gap-1.5">
              <Download className="w-3 h-3" /> Exporter
              {result && <span className="text-gray-400">({result.total.toLocaleString("fr")})</span>}
              <ChevronDown className="w-3 h-3 text-gray-400" />
            </button>
            {showExportMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowExportMenu(false)} />
                <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-20 w-72 overflow-hidden">
                  {!exportsAllowed ? (
                    <div className="p-2"><LimitNotice compact title="Export réservé aux offres avancées" message="Les exports CSV/Excel sont disponibles avec Team, Expert ou Accompagnement Financement." /></div>
                  ) : (
                    <>
                      <a href={exportCsvUrl} download onClick={() => setShowExportMenu(false)} className="flex items-center gap-2.5 px-3.5 py-2.5 text-xs text-gray-700 hover:bg-gray-50">
                        <FileText className="w-3.5 h-3.5 text-gray-400" />
                        <div><div className="font-medium">CSV</div><div className="text-gray-400">Compatible Excel</div></div>
                      </a>
                      <div className="border-t border-gray-100" />
                      <a href={exportExcelUrl} download onClick={() => setShowExportMenu(false)} className="flex items-center gap-2.5 px-3.5 py-2.5 text-xs text-gray-700 hover:bg-gray-50">
                        <FileSpreadsheet className="w-3.5 h-3.5 text-green-500" />
                        <div><div className="font-medium">Excel (.xlsx)</div><div className="text-gray-400">Formaté + filtres</div></div>
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

      {/* ── Bannière profil ──────────────────────────────────────────────── */}
      {profileActive && (
        <div className="mb-3 flex items-center justify-between gap-3 rounded-2xl border border-primary-200 bg-primary-50/80 px-4 py-2.5">
          <div className="flex items-center gap-2 text-xs text-primary-800">
            <UserCircle2 className="h-4 w-4 shrink-0 text-primary-600" />
            <span>
              <span className="font-semibold">Contenu personnalisé</span>{" — "}les résultats sont filtrés selon votre profil.{" "}
              <Link href="/onboarding" className="underline hover:text-primary-600">Modifier mes préférences</Link>
            </span>
          </div>
          {userIsStaff && (
            <button type="button" onClick={clearFilters} className="shrink-0 text-xs text-primary-500 hover:text-primary-800 underline">Voir tout</button>
          )}
        </div>
      )}

      {/* ── Barre recherche + filtres ────────────────────────────────────── */}
      {userIsStaff && (
        <div className={clsx(
          "mb-3 flex flex-col gap-3 rounded-2xl border px-4 py-3 sm:flex-row sm:items-center sm:justify-between",
          adminFullCatalog ? "border-slate-300 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-700",
        )}>
          <div>
            <p className={clsx("text-xs font-semibold uppercase tracking-[0.16em]", adminFullCatalog ? "text-blue-200" : "text-slate-500")}>
              Vue admin
            </p>
            <p className="mt-1 text-sm font-semibold">
              {adminFullCatalog ? "Catalogue complet active" : "Catalogue publie uniquement"}
            </p>
            <p className={clsx("mt-0.5 text-xs", adminFullCatalog ? "text-slate-300" : "text-slate-500")}>
              {adminFullCatalog
                ? "Tous les statuts, fiches rejetees et fiches faibles sont inclus pour controle."
                : "Vue identique au catalogue propre expose aux utilisateurs."}
            </p>
          </div>
          <button
            type="button"
            onClick={() => { setAdminFullCatalog((value) => !value); setPage(1); setSelectedDevice(null); }}
            className={clsx(
              "inline-flex items-center justify-center rounded-full px-4 py-2 text-xs font-semibold transition",
              adminFullCatalog ? "bg-white text-slate-950 hover:bg-blue-50" : "bg-slate-950 text-white hover:bg-primary-700",
            )}
          >
            {adminFullCatalog ? "Revenir au catalogue publie" : "Voir tout le catalogue"}
          </button>
        </div>
      )}

      {introTitle && (
        <div className="mb-4 rounded-[28px] border border-emerald-200 bg-gradient-to-br from-emerald-50 via-white to-sky-50 px-5 py-4 shadow-[0_18px_45px_-34px_rgba(15,23,42,0.45)]">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">Selection prioritaire</p>
              <h2 className="mt-1 text-base font-bold text-slate-950">{introTitle}</h2>
              {introText && <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">{introText}</p>}
            </div>
            <div className="rounded-2xl border border-emerald-100 bg-white/80 px-4 py-2 text-xs font-medium text-emerald-800">
              Ouvert / Recurrent / Date fiable
            </div>
          </div>
        </div>
      )}

      <div className="flex gap-2 mb-3">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input type="text" className="input pl-9 pr-9" placeholder="Rechercher…" value={q}
            onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          {q !== debouncedQ && <span className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border-2 border-primary-400 border-t-transparent animate-spin" />}
        </div>
        {userIsStaff && (
          <button onClick={() => setShowFilters(!showFilters)}
            className={clsx("btn-secondary", hasFilters && "border-primary-500 text-primary-600")}>
            <SlidersHorizontal className="w-4 h-4" />
            Filtres
            {hasFilters && (
              <span className="bg-primary-600 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                {Number(filterCountries.length > 0) + Number(filterTypes.length > 0) + Number(filterSectors.length > 0) + Number(filterStatuses.length > 0) + Number(filterAiReadiness.length > 0) + Number(!!closingSoon) + Number(hasCloseDate) + Number(adminCatalogEnabled)}
              </span>
            )}
          </button>
        )}
        <select className="input w-auto" value={sortBy} onChange={(e) => { setSortBy(e.target.value); setPage(1); }}>
          <option value="relevance">✦ Pertinence</option>
          <option value="close_date">Date limite</option>
          <option value="amount_max">Montant</option>
          <option value="updated_at">Nouveauté</option>
          <option value="confidence">Fiabilité</option>
        </select>
      </div>

      {/* ── Filtres rapides ──────────────────────────────────────────────── */}
      <div className="mb-4 rounded-[24px] border border-slate-200 bg-white p-3 shadow-[0_12px_35px_-28px_rgba(15,23,42,0.35)]">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-2">
            {quickFilters.map(([kind, label]) => (
              <button key={kind} type="button" onClick={() => applyQuickFilter(kind)}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-primary-200 hover:bg-primary-50 hover:text-primary-700">
                {label}
              </button>
            ))}
          </div>
          <button type="button" onClick={handleSaveSearch}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-primary-700">
            <BookmarkPlus className="h-3.5 w-3.5" /> Sauvegarder cette recherche
          </button>
        </div>
      </div>

      {/* ── Panneau de filtres avancés (admins uniquement) ──────────────── */}
      {userIsStaff && showFilters && (
        <div className="card p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-700">Filtres avancés</h3>
            {hasFilters && <button onClick={clearFilters} className="text-xs text-red-500 flex items-center gap-1"><X className="w-3 h-3" /> Réinitialiser</button>}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            <div>
              <p className="label">Pays</p>
              <div className="flex flex-wrap gap-1">
                {COUNTRIES.map((c) => (
                  <button key={c} onClick={() => toggleFilter(filterCountries, setFilterCountries, c)}
                    className={clsx("badge cursor-pointer", filterCountries.includes(c) ? "bg-primary-100 text-primary-700 border border-primary-300" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                    {c}
                  </button>
                ))}
              </div>
            </div>
            {availableDeviceTypes.length > 0 && (
              <div>
                <p className="label">Type</p>
                <div className="flex flex-wrap gap-1">
                  {availableDeviceTypes.map((k) => (
                    <button key={k} onClick={() => toggleFilter(filterTypes, setFilterTypes, k)}
                      className={clsx("badge cursor-pointer", filterTypes.includes(k) ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                      {getUserDeviceTypeMeta(k).label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div>
              <p className="label">Secteurs</p>
              <div className="flex flex-wrap gap-1">
                {SECTORS.map((s) => (
                  <button key={s} onClick={() => toggleFilter(filterSectors, setFilterSectors, s)}
                    className={clsx("badge cursor-pointer capitalize", filterSectors.includes(s) ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              <div>
                <p className="label">Statut</p>
                <div className="flex flex-wrap gap-1">
                  {STATUSES.map((s) => (
                    <button key={s} onClick={() => toggleFilter(filterStatuses, setFilterStatuses, s)}
                      className={clsx("badge cursor-pointer", filterStatuses.includes(s) ? "bg-orange-100 text-orange-700" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                      {STATUS_LABELS_DISPLAY[s]}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="label">Pertinence IA</p>
                <div className="flex flex-wrap gap-1">
                  {Object.entries(AI_READINESS_LABELS).map(([key, label]) => (
                    <button key={key} onClick={() => toggleFilter(filterAiReadiness, setFilterAiReadiness, key)}
                      className={clsx("badge cursor-pointer", filterAiReadiness.includes(key) ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-600 hover:bg-gray-200")}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              {showClosingFilter && (
                <div>
                  <label className="label">Clôture dans</label>
                  <select className="input text-xs" value={closingSoon} onChange={(e) => { setClosingSoon(e.target.value); setPage(1); }}>
                    <option value="">Toutes les dates</option>
                    <option value="7">7 jours</option>
                    <option value="30">30 jours</option>
                    <option value="60">60 jours</option>
                    <option value="90">90 jours</option>
                  </select>
                </div>
              )}
              <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700">
                <input type="checkbox" checked={hasCloseDate} onChange={(e) => { setHasCloseDate(e.target.checked); setPage(1); }}
                  className="h-4 w-4 rounded border-gray-300 accent-primary-600" />
                Avec date limite renseignée
              </label>
            </div>
          </div>
        </div>
      )}

      {/* ── Messages ────────────────────────────────────────────────────── */}
      {bulkMsg && (
        <div className={clsx("flex items-center gap-2 text-sm rounded-lg px-4 py-3 mb-3 border",
          bulkMsg.type === "success" ? "bg-green-50 border-green-200 text-green-700" : "bg-red-50 border-red-200 text-red-700")}>
          <span>{bulkMsg.text}</span>
          <button onClick={() => setBulkMsg(null)} className="ml-auto opacity-60 hover:opacity-100">✕</button>
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-3">
          <span className="text-base">⚠️</span><span>{error}</span>
          <button onClick={fetchDevices} className="ml-auto text-xs underline hover:no-underline">Réessayer</button>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════ */}
      {/* VUE SPLIT (Liste + Volet)                                         */}
      {/* ══════════════════════════════════════════════════════════════════ */}
      {viewMode === "split" && (
        <>
          {loading ? (
            <div className="overflow-hidden rounded-[26px] border border-slate-200 bg-white shadow-[0_14px_40px_-28px_rgba(15,23,42,0.35)]" style={{ height: "calc(100vh - 22rem)", minHeight: 480 }}>
              <div className="flex h-full">
                <div className="w-full md:w-[45%] border-r border-slate-100 divide-y divide-slate-100">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="px-4 py-3 animate-pulse">
                      <div className="h-3 bg-gray-200 rounded w-1/4 mb-2" />
                      <div className="h-4 bg-gray-200 rounded w-3/4 mb-1" />
                      <div className="h-3 bg-gray-100 rounded w-1/2" />
                    </div>
                  ))}
                </div>
                <div className="hidden md:flex flex-1 items-center justify-center text-slate-300">
                  <div className="text-center"><div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mx-auto mb-3" /><p className="text-sm">Chargement…</p></div>
                </div>
              </div>
            </div>
          ) : result?.items.length === 0 ? (
            <div className="flex items-center justify-center rounded-[26px] border border-slate-200 bg-white py-20 text-center text-gray-400 shadow">
              <div><Search className="w-10 h-10 mx-auto mb-3 opacity-30" /><p className="font-medium">Aucun résultat trouvé</p><p className="text-sm mt-1">Essayez de modifier vos filtres</p></div>
            </div>
          ) : (
            <div
              className="flex overflow-hidden rounded-[26px] border border-slate-200 bg-white shadow-[0_14px_40px_-28px_rgba(15,23,42,0.35)]"
              style={{ height: "calc(100vh - 22rem)", minHeight: 480 }}
            >
              {/* ── GAUCHE : liste ──────────────────────────────────── */}
              <div className={clsx(
                "flex flex-col border-r border-slate-100 overflow-hidden",
                selectedDevice ? "hidden md:flex md:w-[45%]" : "w-full md:w-[45%]",
              )}>
                {/* En-tête colonnes */}
                <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/90 px-4 py-2">
                  <div className="flex items-center gap-3">
                    {userIsStaff && (
                      <input type="checkbox" checked={allPageSelected} onChange={toggleAllPageSelection}
                        className="h-4 w-4 rounded border-gray-300 accent-primary-600" />
                    )}
                    <span className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">Opportunité</span>
                  </div>
                  <div className="flex items-center gap-6 text-[11px] font-semibold uppercase tracking-widest text-slate-400 pr-1">
                    <span>Clôture</span>
                    <span>Montant</span>
                  </div>
                </div>

                {/* Lignes défilables */}
                <div className="flex-1 overflow-y-auto divide-y-0">
                  {result?.items.map((device) => renderListRow(device as Device))}
                </div>

                {/* Pagination */}
                {renderPagination(true)}
              </div>

              {/* ── DROITE : volet détail ────────────────────────── */}
              <div className={clsx(
                "flex-1 overflow-hidden",
                selectedDevice ? "flex flex-col" : "hidden md:flex md:items-center md:justify-center",
              )}>
                {selectedDevice ? (
                  <div ref={panelRef} className="h-full overflow-y-auto">
                    <DevicePanel
                      device={selectedDevice}
                      onClose={() => setSelectedDevice(null)}
                      buildRelevanceExplanation={buildRelevanceExplanation}
                    />
                  </div>
                ) : (
                  <div className="text-center text-slate-400 px-8">
                    <Zap className="w-10 h-10 mx-auto mb-3 opacity-20" />
                    <p className="font-medium text-sm">Sélectionnez une opportunité</p>
                    <p className="text-xs mt-1">Cliquez sur une ligne pour voir les détails</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* ══════════════════════════════════════════════════════════════════ */}
      {/* VUE TABLEAU                                                       */}
      {/* ══════════════════════════════════════════════════════════════════ */}
      {viewMode === "table" && (
        <>
          {loading ? (
            <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="card p-4 animate-pulse"><div className="h-4 bg-gray-200 rounded w-3/4 mb-2" /><div className="h-3 bg-gray-100 rounded w-1/2" /></div>)}</div>
          ) : result?.items.length === 0 ? (
            <div className="text-center py-20 text-gray-400"><Search className="w-10 h-10 mx-auto mb-3 opacity-30" /><p className="font-medium">Aucun résultat trouvé</p><p className="text-sm">Essayez de modifier vos filtres</p></div>
          ) : (
            <>
              <div className="overflow-hidden rounded-[26px] border border-slate-200 bg-white shadow-[0_14px_40px_-28px_rgba(15,23,42,0.35)]">
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[900px] text-sm">
                    <thead className="border-b border-slate-200 bg-slate-50/80">
                      <tr className="text-left text-[11px] uppercase tracking-[0.14em] text-slate-500">
                        {userIsStaff && <th className="px-4 py-3"><input type="checkbox" checked={allPageSelected} onChange={toggleAllPageSelection} className="h-4 w-4 rounded border-gray-300 accent-primary-600" /></th>}
                        <th className="px-4 py-3">Opportunité</th>
                        <th className="px-4 py-3">Type</th>
                        <th className="px-4 py-3">Pays</th>
                        <th className="px-4 py-3">Montant</th>
                        <th className="px-4 py-3">Clôture</th>
                        <th className="px-4 py-3">Statut</th>
                        <th className="px-4 py-3">Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result?.items.map((device) => (
                        <tr key={device.id} className="border-b border-slate-100 align-top transition-colors hover:bg-slate-50/70">
                          {userIsStaff && (
                            <td className="px-4 py-4">
                              <input type="checkbox" checked={selectedIds.has(device.id)} onChange={() => toggleSelect(device.id)} className="h-4 w-4 rounded border-gray-300 accent-primary-600" />
                            </td>
                          )}
                          <td className="min-w-[300px] px-4 py-4">
                            <button type="button" onClick={() => router.push(`/devices/${device.id}`)} className="block text-left group">
                              <div className="font-semibold leading-6 text-slate-900 group-hover:text-primary-700">{device.title}</div>
                            </button>
                            <div className="mt-1 text-xs text-slate-500">{device.organism}</div>
                          </td>
                          <td className="px-4 py-4">
                            {(() => {
                              const typeMeta = getUserDeviceTypeMeta(device.device_type);
                              return (
                                <div>
                                  <span className={clsx("rounded-full px-2.5 py-1 text-xs font-medium", typeMeta.color || DEVICE_TYPE_COLORS[device.device_type] || "bg-slate-100 text-slate-600")} title={typeMeta.short}>
                                    {typeMeta.label}
                                  </span>
                                  <p className="mt-1 max-w-[190px] text-[11px] leading-4 text-slate-400">{typeMeta.short}</p>
                                </div>
                              );
                            })()}
                          </td>
                          <td className="px-4 py-4 text-slate-700">{[device.country, device.region].filter(Boolean).join(" · ") || "—"}</td>
                          <td className="px-4 py-4 text-slate-700">{device.amount_max ? formatAmount(device.amount_max, device.currency) : "—"}</td>
                          <td className="px-4 py-4">
                            {device.close_date
                              ? <span className="font-medium text-slate-800">{formatDate(device.close_date)}</span>
                              : <span className="text-slate-400">{device.status === "recurring" ? "Récurrent" : "—"}</span>}
                          </td>
                          <td className="px-4 py-4">
                            <span className={clsx("rounded-full px-2.5 py-1 text-xs font-medium", STATUS_COLORS[device.status])}>
                              {STATUS_LABELS_DISPLAY[device.status] || device.status}
                            </span>
                          </td>
                          <td className="px-4 py-4">
                            <div className="flex items-center gap-2">
                              <span className="max-w-[140px] truncate text-xs text-slate-600">{device.organism}</span>
                              {device.source_url && (
                                <a href={device.source_url} target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-primary-600">
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
              {renderPagination()}
            </>
          )}
        </>
      )}

      {/* ── Barre actions groupées flottante (admins) ────────────────────── */}
      {userIsStaff && selectedIds.size > 0 && (
        <div className="fixed bottom-4 left-2 right-2 sm:left-1/2 sm:right-auto sm:-translate-x-1/2 z-50 flex items-center gap-2 flex-wrap bg-gray-900 text-white rounded-2xl shadow-2xl px-4 py-3 sm:max-w-xl">
          <div className="flex items-center gap-2 pr-3 border-r border-gray-700">
            <CheckSquare className="w-4 h-4 text-primary-400" />
            <span className="text-sm font-medium">{selectedIds.size} sélectionné{selectedIds.size > 1 ? "s" : ""}</span>
            <button onClick={selectAllPage} className="text-xs text-gray-400 hover:text-white underline">Toute la page</button>
            <button onClick={clearSelection} className="text-gray-500 hover:text-white"><X className="w-3.5 h-3.5" /></button>
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
                <input autoFocus type="text" value={tagInput} onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleBulkAction("tag")} placeholder="tag1, tag2…"
                  className="text-xs bg-gray-800 border border-gray-600 rounded-lg px-2 py-1.5 text-white placeholder-gray-500 w-32 focus:outline-none focus:border-primary-400" />
                <button onClick={() => handleBulkAction("tag")} disabled={bulkLoading || !tagInput.trim()}
                  className="text-xs bg-primary-600 hover:bg-primary-500 disabled:opacity-50 px-2.5 py-1.5 rounded-lg font-medium">OK</button>
                <button onClick={() => { setShowTagInput(false); setTagInput(""); }} className="text-gray-500 hover:text-white"><X className="w-3.5 h-3.5" /></button>
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
                  {bulkLoading ? <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />} Confirmer
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
