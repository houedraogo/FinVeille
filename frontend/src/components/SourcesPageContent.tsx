"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AppLayout from "@/components/AppLayout";
import { sources } from "@/lib/api";
import { Source, SOURCE_FREQ_LABELS, SOURCE_KIND_LABELS, SOURCE_MODE_LABELS, SourceKind, SourceTestResult } from "@/lib/types";
import { formatDateRelative } from "@/lib/utils";
import { Plus, Play, Trash2, CheckCircle, XCircle, Database, ChevronRight, Search, FlaskConical } from "lucide-react";
import clsx from "clsx";

interface Props {
  category: "public" | "private";
  title: string;
  subtitle: string;
  defaultSourceType: string;
}

type SortKey = "name" | "errors" | "last_success" | "reliability";

const HEALTH_COLORS: Record<string, string> = {
  excellent: "bg-green-100 text-green-700",
  bon: "bg-emerald-100 text-emerald-700",
  fragile: "bg-amber-100 text-amber-700",
  critique: "bg-red-100 text-red-700",
};

function isManualPrivateSource(source: Source): boolean {
  return source.category === "private" && source.collection_mode === "manual";
}

function inferDefaultSourceKind(collectionMode: string): SourceKind {
  if (collectionMode === "manual") return "pdf_manual";
  return "listing";
}

function getSourceKindBadge(source: Pick<Source, "collection_mode" | "source_kind">) {
  if (source.collection_mode === "manual" || source.source_kind === "pdf_manual") {
    return { label: "Source manuelle", tone: "bg-slate-100 text-slate-700" };
  }
  if (source.source_kind === "single_program_page" || source.source_kind === "institutional_project") {
    return { label: "Page éditoriale", tone: "bg-amber-100 text-amber-700" };
  }
  return { label: "Collecte automatique", tone: "bg-emerald-100 text-emerald-700" };
}

function getSourceCollectionPreview(source: Pick<Source, "collection_mode" | "source_kind" | "is_active">) {
  if (source.collection_mode === "manual" || source.source_kind === "pdf_manual") {
    return "Création ou suivi manuel d'une fiche à partir d'un document de référence.";
  }
  if (source.source_kind === "single_program_page") {
    return "Créera surtout une fiche principale depuis une page unique déjà éditorialisée.";
  }
  if (source.source_kind === "institutional_project") {
    return "Interprétera la source comme un projet institutionnel plutôt qu'une liste d'appels.";
  }
  if (!source.is_active) {
    return "Source inactive conservée à titre de référence tant qu'elle n'est pas réactivée.";
  }
  return "Cherchera une liste d'items et générera une fiche distincte pour chaque dispositif détecté.";
}

export default function SourcesPageContent({ category, title, subtitle, defaultSourceType }: Props) {
  const router = useRouter();
  const [sourceList, setSourceList] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [collecting, setCollecting] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<SourceTestResult | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive" | "error">("all");
  const [modeFilter, setModeFilter] = useState("all");
  const [levelFilter, setLevelFilter] = useState("all");
  const [sortBy, setSortBy] = useState<SortKey>("errors");
  const [sortDesc, setSortDesc] = useState(true);
  const [newSource, setNewSource] = useState({
    name: "",
    organism: "",
    country: "",
    source_type: defaultSourceType,
    category,
    level: 2,
    url: "",
    collection_mode: "html",
    source_kind: "listing" as SourceKind,
    check_frequency: "daily",
    reliability: 3,
    is_active: true,
    config: {} as Record<string, unknown>,
  });

  useEffect(() => {
    sources.list({ category }).then(setSourceList).finally(() => setLoading(false));
  }, [category]);

  const handleAuthError = (message: string) => {
    if (!message.toLowerCase().includes("session expir")) return false;
    alert("Session expirée. Veuillez vous reconnecter pour gérer les sources.");
    router.replace("/login");
    return true;
  };

  const filteredSources = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    const list = sourceList.filter((source) => {
      if (statusFilter === "active" && !source.is_active) return false;
      if (statusFilter === "inactive" && source.is_active) return false;
      if (statusFilter === "error" && source.consecutive_errors <= 0) return false;
      if (modeFilter !== "all" && source.collection_mode !== modeFilter) return false;
      if (levelFilter !== "all" && String(source.level) !== levelFilter) return false;
      if (!normalizedSearch) return true;
      return [
        source.name,
        source.organism,
        source.country,
        source.source_type,
        source.notes || "",
      ].some((value) => value.toLowerCase().includes(normalizedSearch));
    });

    const sorted = [...list].sort((a, b) => {
      let cmp = 0;
      if (sortBy === "errors") cmp = a.consecutive_errors - b.consecutive_errors;
      if (sortBy === "reliability") cmp = a.health_score - b.health_score;
      if (sortBy === "name") cmp = a.name.localeCompare(b.name, "fr", { sensitivity: "base" });
      if (sortBy === "last_success") cmp = (a.last_success_at || "").localeCompare(b.last_success_at || "");
      return sortDesc ? -cmp : cmp;
    });

    return sorted;
  }, [sourceList, search, statusFilter, modeFilter, levelFilter, sortBy, sortDesc]);

  const handleCollect = async (id: string) => {
    setCollecting(id);
    try {
      await sources.collect(id);
      alert("Collecte declenchee.");
    } catch (e: any) {
      if (handleAuthError(e.message || "")) return;
      alert(`Erreur : ${e.message}`);
    } finally {
      setCollecting(null);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Supprimer la source "${name}" ?`)) return;
    try {
      await sources.delete(id);
      setSourceList((prev) => prev.filter((s) => s.id !== id));
    } catch (e: any) {
      if (handleAuthError(e.message || "")) return;
      alert(`Erreur : ${e.message}`);
    }
  };

  const handleAddSource = async () => {
    try {
      const created = await sources.create(newSource);
      setSourceList((prev) => [created as Source, ...prev]);
      setShowAdd(false);
      setTestResult(null);
    } catch (e: any) {
      if (handleAuthError(e.message || "")) return;
      alert(`Erreur : ${e.message}`);
    }
  };

  const handleTestSource = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await sources.test(newSource);
      setTestResult(result as SourceTestResult);
    } catch (e: any) {
      if (handleAuthError(e.message || "")) return;
      setTestResult({
        success: false,
        message: e.message || "Erreur de test",
        collection_mode: newSource.collection_mode,
        items_found: 0,
        sample_titles: [],
        sample_urls: [],
        can_activate: false,
      });
    } finally {
      setTesting(false);
    }
  };

  const byLevel = (level: number) => filteredSources.filter((s) => s.level === level);

  const homepageLikeUrl = useMemo(() => {
    try {
      const parsed = new URL(newSource.url);
      const normalized = (parsed.pathname || "/").replace(/\/+$/, "") || "/";
      return ["/", "/fr", "/en", "/francais", "/english", "/home", "/accueil"].includes(normalized);
    } catch {
      return false;
    }
  }, [newSource.url]);

  const automatedPrivateSources = useMemo(
    () => filteredSources.filter((source) => !isManualPrivateSource(source)),
    [filteredSources]
  );

  const manualPrivateSources = useMemo(
    () => filteredSources.filter((source) => isManualPrivateSource(source)),
    [filteredSources]
  );

  const renderSourceTable = (items: Source[]) => (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] table-fixed text-xs">
          <colgroup>
            <col className="w-[46%]" />
            <col className="w-[9%]" />
            <col className="w-[9%]" />
            <col className="w-[10%]" />
            <col className="w-[14%]" />
            <col className="w-[8%]" />
            <col className="w-[4%]" />
          </colgroup>
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-gray-500">Source</th>
              <th className="text-left px-4 py-2 font-medium text-gray-500">Pays</th>
              <th className="text-left px-4 py-2 font-medium text-gray-500">Mode</th>
              <th className="text-left px-4 py-2 font-medium text-gray-500">Frequence</th>
              <th className="text-left px-4 py-2 font-medium text-gray-500">Derniere collecte</th>
              <th className="text-left px-4 py-2 font-medium text-gray-500">Statut</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3 align-top">
                  <span
                    className={clsx(
                      "mb-2 inline-flex rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]",
                      getSourceKindBadge(s).tone,
                    )}
                  >
                    {getSourceKindBadge(s).label}
                  </span>
                  <Link href={`/sources/${s.id}`} className="block font-medium text-gray-900 hover:text-primary-600 break-words">
                    {s.name}
                  </Link>
                  <div className="text-gray-400 break-words">{s.organism}</div>
                  <div className="mt-1 max-w-[95%] text-[11px] leading-5 text-slate-500">
                    {getSourceCollectionPreview(s)}
                  </div>
                  <div className="mt-1">
                    <span className={clsx("badge text-[10px]", HEALTH_COLORS[s.health_label] || "bg-gray-100 text-gray-700")}>
                      Sante {s.health_score}/100
                    </span>
                  </div>
                  {s.last_error && (
                    <div
                      className="mt-1 max-w-full overflow-hidden text-ellipsis break-words text-red-500 text-[11px] leading-5 line-clamp-3"
                      title={s.last_error}
                    >
                      {s.last_error}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 align-top text-gray-600 break-words">{s.country}</td>
                <td className="px-4 py-3 align-top">
                  <span className="badge bg-gray-100 text-gray-700">
                    {SOURCE_MODE_LABELS[s.collection_mode] || s.collection_mode}
                  </span>
                </td>
                <td className="px-4 py-3 align-top text-gray-500">
                  {SOURCE_FREQ_LABELS[s.check_frequency] || s.check_frequency}
                </td>
                <td className="px-4 py-3 align-top text-gray-500 break-words">
                  <span className="block">{s.last_success_at ? formatDateRelative(s.last_success_at) : "Jamais"}</span>
                  {s.consecutive_errors > 0 && (
                    <span className="mt-1 block text-red-500">
                      {s.consecutive_errors} erreur{s.consecutive_errors > 1 ? "s" : ""}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 align-top">
                  {s.is_active ? (
                    <span className="flex items-center gap-1 text-green-600">
                      <CheckCircle className="w-3 h-3" /> Active
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-red-500">
                      <XCircle className="w-3 h-3" /> Inactive
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 align-top">
                  <div className="flex items-center gap-1">
                    <Link href={`/sources/${s.id}`} className="p-1 text-gray-400 hover:text-primary-600" title="Voir la fiche">
                      <ChevronRight className="w-3 h-3" />
                    </Link>
                    <button
                      onClick={() => handleCollect(s.id)}
                      disabled={collecting === s.id || s.collection_mode === "manual"}
                      className="p-1 text-gray-400 hover:text-primary-600 disabled:opacity-50"
                      title={s.collection_mode === "manual" ? "Collecte automatique indisponible" : "Declencher la collecte"}
                    >
                      <Play className={clsx("w-3 h-3", collecting === s.id && "animate-spin")} />
                    </button>
                    <button
                      onClick={() => handleDelete(s.id, s.name)}
                      className="p-1 text-gray-400 hover:text-red-500"
                      title="Supprimer"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          <p className="text-sm text-gray-500">
            {loading ? "Chargement..." : `${filteredSources.filter((s) => s.is_active).length} actives · ${filteredSources.length} affichees`}
            {subtitle && <span className="ml-2 text-gray-400">· {subtitle}</span>}
          </p>
        </div>
        <button onClick={() => setShowAdd(true)} className="btn-primary">
          <Plus className="w-4 h-4" /> Ajouter une source
        </button>
      </div>

      <div className="card p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          <label className="relative block">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              className="input pl-9"
              placeholder="Rechercher une source"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <select className="input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as any)}>
            <option value="all">Tous les statuts</option>
            <option value="active">Actives</option>
            <option value="inactive">Inactives</option>
            <option value="error">En erreur</option>
          </select>
          <select className="input" value={modeFilter} onChange={(e) => setModeFilter(e.target.value)}>
            <option value="all">Tous les modes</option>
            {Object.entries(SOURCE_MODE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <select className="input" value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)}>
            <option value="all">Tous les niveaux</option>
            <option value="1">Niveau 1</option>
            <option value="2">Niveau 2</option>
            <option value="3">Niveau 3</option>
          </select>
          <div className="flex gap-2">
            <select className="input" value={sortBy} onChange={(e) => setSortBy(e.target.value as SortKey)}>
              <option value="errors">Trier par erreurs</option>
              <option value="last_success">Trier par dernier succes</option>
              <option value="reliability">Trier par fiabilite</option>
              <option value="name">Trier par nom</option>
            </select>
            <button className="btn-secondary px-3" onClick={() => setSortDesc((v) => !v)}>
              {sortDesc ? "Desc" : "Asc"}
            </button>
          </div>
        </div>
      </div>

      {showAdd && (
        <div className="card p-4 mb-6">
          <h2 className="text-sm font-semibold mb-3">Nouvelle source</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            {[
              { label: "Nom", key: "name", type: "text" },
              { label: "Organisme", key: "organism", type: "text" },
              { label: "Pays", key: "country", type: "text" },
              { label: "URL", key: "url", type: "url" },
            ].map(({ label, key, type }) => (
              <div key={key}>
                <label className="label">{label}</label>
                <input
                  type={type}
                  className="input"
                  value={(newSource as any)[key]}
                  onChange={(e) => setNewSource((p) => ({ ...p, [key]: e.target.value }))}
                />
              </div>
            ))}
            <div>
              <label className="label">Mode de collecte</label>
              <select
                className="input"
                value={newSource.collection_mode}
                onChange={(e) =>
                  setNewSource((p) => {
                    const nextMode = e.target.value;
                    const nextKind =
                      p.source_kind === "pdf_manual" && nextMode !== "manual"
                        ? "listing"
                        : nextMode === "manual" && p.source_kind !== "pdf_manual"
                          ? inferDefaultSourceKind(nextMode)
                          : p.source_kind;
                    return { ...p, collection_mode: nextMode, source_kind: nextKind };
                  })
                }
              >
                {Object.entries(SOURCE_MODE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Type de source</label>
              <select
                className="input"
                value={newSource.source_kind}
                onChange={(e) =>
                  setNewSource((p) => {
                    const nextKind = e.target.value as SourceKind;
                    return {
                      ...p,
                      source_kind: nextKind,
                      collection_mode: nextKind === "pdf_manual" ? "manual" : p.collection_mode === "manual" ? "html" : p.collection_mode,
                    };
                  })
                }
              >
                {(Object.entries(SOURCE_KIND_LABELS) as Array<[SourceKind, string]>).map(([key, label]) => (
                  <option
                    key={key}
                    value={key}
                    disabled={newSource.collection_mode === "manual" ? key !== "pdf_manual" : key === "pdf_manual"}
                  >
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Niveau</label>
              <select className="input" value={newSource.level} onChange={(e) => setNewSource((p) => ({ ...p, level: Number(e.target.value) }))}>
                <option value={1}>1 - Prioritaire</option>
                <option value={2}>2 - Secondaire</option>
                <option value={3}>3 - Relais</option>
              </select>
            </div>
          </div>
          {newSource.collection_mode === "html" && homepageLikeUrl && newSource.source_kind === "listing" && (
            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              Cette URL ressemble a une page d'accueil. Pour creer une source HTML valide, ajoute une config minimale cote API
              ou choisis plutot <span className="font-semibold">Page unique programme</span>.
            </div>
          )}
          <div className="flex gap-2 mt-3">
            <button onClick={handleAddSource} className="btn-primary text-xs">Creer</button>
            <button onClick={handleTestSource} disabled={testing} className="btn-secondary text-xs disabled:opacity-50">
              {testing ? <Database className="w-4 h-4 animate-pulse" /> : <FlaskConical className="w-4 h-4" />} Tester
            </button>
            <button onClick={() => { setShowAdd(false); setTestResult(null); }} className="btn-secondary text-xs">Annuler</button>
          </div>
          {testResult && (
            <div className={clsx("mt-4 rounded-xl border p-4 text-sm", testResult.success ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50")}>
              <div className="font-medium">{testResult.message}</div>
              <div className="text-xs mt-1 text-gray-600">
                {testResult.items_found} item(s) detecte(s) · activation {testResult.can_activate ? "possible" : "deconseillee"}
              </div>
              {testResult.preview && (
                <div className="mt-3 rounded-xl border border-white/70 bg-white/70 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-primary-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-primary-700">
                      {testResult.preview.badge}
                    </span>
                    <span className="text-sm font-semibold text-slate-900">{testResult.preview.headline}</span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-600">{testResult.preview.summary}</p>
                  {testResult.preview.examples.length > 0 && (
                    <div className="mt-3">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">Ce que la collecte va probablement creer</div>
                      <ul className="mt-2 space-y-1 text-xs text-slate-700">
                        {testResult.preview.examples.map((title, index) => (
                          <li key={`${title}-${index}`} className="line-clamp-1">{title}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {testResult.sample_titles.length > 0 && (
                <div className="mt-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Apercu</div>
                  <ul className="space-y-1 text-xs text-gray-700">
                    {testResult.sample_titles.map((title, index) => (
                      <li key={`${title}-${index}`} className="line-clamp-1">{title}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-20 text-gray-400">
          <Database className="w-5 h-5 animate-pulse mr-2" /> Chargement...
        </div>
      )}

      {!loading && category !== "private" && [1, 2, 3].map((level) => {
        const levelSources = byLevel(level);
        if (!levelSources.length) return null;
        return (
          <div key={level} className="mb-6">
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Niveau {level} - {level === 1 ? "Sources prioritaires" : level === 2 ? "Sources secondaires" : "Sources relais"}
              <span className="ml-2 font-normal normal-case">({levelSources.length})</span>
            </h2>
            {renderSourceTable(levelSources)}
          </div>
        );
      })}

      {!loading && category === "private" && automatedPrivateSources.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Sources automatisees
            <span className="ml-2 font-normal normal-case">({automatedPrivateSources.length})</span>
          </h2>
          <p className="text-xs text-gray-400 mb-3">
            Sources collectables automatiquement, avec relance et supervision directe.
          </p>
          {renderSourceTable(automatedPrivateSources)}
        </div>
      )}

      {!loading && category === "private" && manualPrivateSources.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Sources referentielles / manuelles
            <span className="ml-2 font-normal normal-case">({manualPrivateSources.length})</span>
          </h2>
          <p className="text-xs text-gray-400 mb-3">
            Sources de reference a qualifier manuellement avant toute automatisation.
          </p>
          {renderSourceTable(manualPrivateSources)}
        </div>
      )}

      {!loading && filteredSources.length === 0 && (
        <div className="card p-10 text-center text-gray-400">
          <Database className="w-8 h-8 mx-auto mb-3 opacity-40" />
          <p className="font-medium">Aucune source correspondante</p>
          <p className="text-sm mt-1">Ajuste les filtres ou ajoute une nouvelle source.</p>
        </div>
      )}
    </AppLayout>
  );
}
