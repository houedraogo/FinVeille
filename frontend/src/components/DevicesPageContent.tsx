"use client";
import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import AppLayout from "@/components/AppLayout";
import DeviceCard from "@/components/DeviceCard";
import { devices } from "@/lib/api";
import { DeviceListResponse, DEVICE_TYPE_LABELS } from "@/lib/types";
import { COUNTRIES, SECTORS } from "@/lib/constants";
import {
  Search, SlidersHorizontal, Download, Plus,
  ChevronLeft, ChevronRight, X,
  ShieldCheck, XCircle, Trash2, Tag, CheckSquare,
  FileSpreadsheet, FileText, ChevronDown,
} from "lucide-react";
import clsx from "clsx";

const STATUSES = ["open", "recurring", "closed", "expired"];
const STATUS_LABELS: Record<string, string> = {
  open: "Ouvert", recurring: "Récurrent", closed: "Fermé", expired: "Expiré",
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

export default function DevicesPageContent({
  title,
  lockedDeviceTypes,
  availableDeviceTypes,
  defaultSort = "updated_at",
  showClosingFilter = true,
  newDeviceHref = "/devices/new",
}: Props) {
  const router = useRouter();

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
  const [closingSoon, setClosingSoon] = useState("");
  const [sortBy, setSortBy] = useState(defaultSort);
  const [page, setPage] = useState(1);
  const [showExportMenu, setShowExportMenu] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(q), 300);
    return () => clearTimeout(timer);
  }, [q]);

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
        closing_soon_days: closingSoon ? parseInt(closingSoon) : undefined,
        sort_by: sortBy,
        page,
        page_size: 20,
      });
      setResult(data);
    } catch {
      setError("Impossible de charger les dispositifs. Vérifiez votre connexion.");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, filterCountries, filterTypes, filterSectors, filterStatuses, closingSoon, sortBy, page, lockedDeviceTypes]);

  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  const toggleFilter = (arr: string[], setArr: (v: string[]) => void, val: string) => {
    setArr(arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val]);
    setPage(1);
  };

  const clearFilters = () => {
    setFilterCountries([]); setFilterTypes([]); setFilterSectors([]);
    setFilterStatuses([]); setClosingSoon(""); setPage(1);
  };

  const hasFilters = filterCountries.length || filterTypes.length || filterSectors.length ||
    filterStatuses.length || closingSoon;

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
          ? `✓ ${res.processed} dispositif(s) traité(s) avec succès.`
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

  // Tous les filtres actifs transmis à l'export
  const effectiveTypesForExport =
    filterTypes.length > 0 ? filterTypes : lockedDeviceTypes.length > 0 ? lockedDeviceTypes : undefined;

  const exportParams = {
    q: debouncedQ || undefined,
    countries: filterCountries.length ? filterCountries : undefined,
    device_types: effectiveTypesForExport,
    sectors: filterSectors.length ? filterSectors : undefined,
    status: filterStatuses.length ? filterStatuses : undefined,
    closing_soon_days: closingSoon ? parseInt(closingSoon) : undefined,
  };

  const exportCsvUrl   = devices.exportCsv(exportParams);
  const exportExcelUrl = devices.exportExcel(exportParams);

  return (
    <AppLayout>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          {result && (
            <p className="text-sm text-gray-500">{result.total.toLocaleString("fr")} résultats</p>
          )}
        </div>
        <div className="flex items-center gap-2">
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
                <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-xl shadow-lg z-20 w-44 overflow-hidden">
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
                </div>
              </>
            )}
          </div>
          <button onClick={() => router.push(newDeviceHref)} className="btn-primary text-xs">
            <Plus className="w-3 h-3" /> Ajouter
          </button>
        </div>
      </div>

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
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={clsx("btn-secondary", hasFilters && "border-primary-500 text-primary-600")}
        >
          <SlidersHorizontal className="w-4 h-4" />
          Filtres
          {hasFilters ? (
            <span className="bg-primary-600 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
              {Number(filterCountries.length > 0) + Number(filterTypes.length > 0) +
               Number(filterSectors.length > 0) + Number(filterStatuses.length > 0) + Number(!!closingSoon)}
            </span>
          ) : null}
        </button>
        <select className="input w-auto" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
          <option value="updated_at">Récents</option>
          <option value="close_date">Date limite</option>
          <option value="amount_max">Montant</option>
          <option value="relevance">Pertinence</option>
          <option value="confidence">Fiabilité</option>
        </select>
      </div>

      {/* Panneau filtres */}
      {showFilters && (
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {result?.items.map((device) => (
              <DeviceCard
                key={device.id}
                device={device}
                selected={selectedIds.has(device.id)}
                onSelect={toggleSelect}
              />
            ))}
          </div>

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
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 flex-wrap
                        bg-gray-900 text-white rounded-2xl shadow-2xl px-4 py-3 max-w-xl w-max">
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
