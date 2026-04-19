"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle, Play, RefreshCw, ShieldAlert, XCircle } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { sources } from "@/lib/api";
import { CollectionLog, Source, SOURCE_FREQ_LABELS, SOURCE_KIND_LABELS, SOURCE_MODE_LABELS, SourceTestResult } from "@/lib/types";
import { formatDate, formatDateRelative } from "@/lib/utils";
import clsx from "clsx";

const STATUS_COLORS: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  success: "bg-green-100 text-green-700",
  partial: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<string, string> = {
  running: "En cours",
  success: "Succes",
  partial: "Partiel",
  failed: "Echec",
};

const HEALTH_COLORS: Record<string, string> = {
  excellent: "bg-green-100 text-green-700",
  bon: "bg-emerald-100 text-emerald-700",
  fragile: "bg-amber-100 text-amber-700",
  critique: "bg-red-100 text-red-700",
};

function getSourceKindBadge(source: Pick<Source, "collection_mode" | "source_kind">) {
  if (source.collection_mode === "manual" || source.source_kind === "pdf_manual") {
    return { label: "Source manuelle", tone: "bg-slate-100 text-slate-700" };
  }
  if (source.source_kind === "single_program_page" || source.source_kind === "institutional_project") {
    return { label: "Page éditoriale", tone: "bg-amber-100 text-amber-700" };
  }
  return { label: "Collecte automatique", tone: "bg-emerald-100 text-emerald-700" };
}

function isManualReference(source: Pick<Source, "collection_mode" | "source_kind">) {
  return source.collection_mode === "manual" || source.source_kind === "pdf_manual";
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-4">
      <div className="text-xs font-medium text-gray-500">{label}</div>
      <div className="text-2xl font-bold text-gray-900 mt-1">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-1">{sub}</div>}
    </div>
  );
}

export default function SourceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [source, setSource] = useState<Source | null>(null);
  const [logs, setLogs] = useState<CollectionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyAction, setBusyAction] = useState<"collect" | "toggle" | null>(null);
  const [testResult, setTestResult] = useState<SourceTestResult | null>(null);

  const sourceId = params?.id;

  const reload = async () => {
    if (!sourceId) return;
    setLoading(true);
    try {
      const [sourceData, logData] = await Promise.all([
        sources.get(sourceId),
        sources.logs(sourceId),
      ]);
      setSource(sourceData as Source);
      setLogs(logData as CollectionLog[]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, [sourceId]);

  const latestSuccess = useMemo(
    () => logs.find((log) => log.status === "success" || log.status === "partial") ?? null,
    [logs]
  );

  const latestFailure = useMemo(
    () => logs.find((log) => log.status === "failed" || (log.items_error ?? 0) > 0) ?? null,
    [logs]
  );

  const handleCollect = async () => {
    if (!source) return;
    setBusyAction("collect");
    try {
      await sources.collect(source.id);
      alert("Collecte declenchee.");
      await reload();
    } catch (e: any) {
      alert(`Erreur : ${e.message}`);
    } finally {
      setBusyAction(null);
    }
  };

  const handleToggleActive = async () => {
    if (!source) return;
    setBusyAction("toggle");
    try {
      await sources.update(source.id, { is_active: !source.is_active });
      await reload();
    } catch (e: any) {
      alert(`Erreur : ${e.message}`);
    } finally {
      setBusyAction(null);
    }
  };

  const handleTest = async () => {
    if (!source) return;
    setBusyAction("collect");
    try {
      const result = await sources.test({
        name: source.name,
        organism: source.organism,
        country: source.country,
        source_type: source.source_type,
        category: source.category,
        level: source.level,
        url: source.url,
        collection_mode: source.collection_mode,
        source_kind: source.source_kind,
        check_frequency: source.check_frequency,
        reliability: source.reliability,
        is_active: source.is_active,
        config: source.config,
        notes: source.notes,
      });
      setTestResult(result as SourceTestResult);
    } catch (e: any) {
      alert(`Erreur : ${e.message}`);
    } finally {
      setBusyAction(null);
    }
  };

  if (loading) {
    return (
      <RoleGate allow={["admin", "editor"]} title="Sources réservées à l'équipe" message="Cette fiche source n'est pas accessible aux utilisateurs standard.">
        <AppLayout>
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        </AppLayout>
      </RoleGate>
    );
  }

  if (!source) {
    return (
      <RoleGate allow={["admin", "editor"]} title="Sources réservées à l'équipe" message="Cette fiche source n'est pas accessible aux utilisateurs standard.">
        <AppLayout>
          <div className="card p-8 text-center text-gray-500">Source introuvable</div>
        </AppLayout>
      </RoleGate>
    );
  }

  const categoryPath = source.category === "private" ? "/sources/private" : "/sources";
  const manualReference = isManualReference(source);
  const healthBadge = manualReference
    ? { label: `Référence ${source.health_score}/100`, tone: "bg-slate-100 text-slate-700" }
    : { label: `Sante ${source.health_score}/100`, tone: HEALTH_COLORS[source.health_label] || "bg-gray-100 text-gray-700" };
  const lastSuccessLabel = manualReference
    ? { value: "À qualifier", sub: "Qualification manuelle attendue" }
    : { value: source.last_success_at ? formatDateRelative(source.last_success_at) : "Jamais", sub: source.last_success_at ? formatDate(source.last_success_at) : undefined };
  const lastCheckLabel = manualReference
    ? { value: "Suivi manuel", sub: "Pas de collecte automatique prévue" }
    : { value: source.last_checked_at ? formatDateRelative(source.last_checked_at) : "Jamais", sub: source.last_checked_at ? formatDate(source.last_checked_at) : undefined };
  const healthStatLabel = manualReference
    ? { value: `${source.health_score}/100`, sub: "référentiel manuel" }
    : { value: `${source.health_score}/100`, sub: source.health_label };

  return (
    <RoleGate allow={["admin", "editor"]} title="Sources réservées à l'équipe" message="Cette fiche source n'est pas accessible aux utilisateurs standard.">
    <AppLayout>
      <div className="flex items-center justify-between gap-3 mb-6">
        <div>
          <button
            onClick={() => router.push(categoryPath)}
            className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-3"
          >
            <ArrowLeft className="w-4 h-4" />
            Retour aux sources
          </button>
          <h1 className="text-2xl font-bold text-gray-900">{source.name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className={clsx("badge text-xs", healthBadge.tone)}>
              {healthBadge.label}
            </span>
            <span className={clsx("rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]", getSourceKindBadge(source).tone)}>
              {getSourceKindBadge(source).label}
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {source.organism} · {source.country} · {SOURCE_MODE_LABELS[source.collection_mode] || source.collection_mode}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleTest}
            disabled={busyAction !== null}
            className="btn-secondary disabled:opacity-50"
          >
            <ShieldAlert className="w-4 h-4" />
            Tester
          </button>
          <button
            onClick={handleCollect}
            disabled={busyAction !== null || manualReference}
            className="btn-primary disabled:opacity-50"
            title={manualReference ? "Collecte automatique indisponible pour une source manuelle" : "Relancer la collecte"}
          >
            {busyAction === "collect" ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {manualReference ? "Collecte auto indisponible" : "Relancer"}
          </button>
          <button
            onClick={handleToggleActive}
            disabled={busyAction !== null}
            className={clsx(
              "btn-secondary disabled:opacity-50",
              source.is_active ? "text-red-600" : "text-green-600"
            )}
          >
            {source.is_active ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
            {source.is_active ? "Desactiver" : "Reactiver"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <StatCard
          label="Statut"
          value={source.is_active ? "Active" : "Inactive"}
          sub={source.consecutive_errors > 0 ? `${source.consecutive_errors} erreur(s) consecutives` : "Aucune erreur"}
        />
        <StatCard
          label="Dernier succes"
          value={lastSuccessLabel.value}
          sub={lastSuccessLabel.sub}
        />
        <StatCard
          label="Derniere verification"
          value={lastCheckLabel.value}
          sub={lastCheckLabel.sub}
        />
        <StatCard
          label="Sante"
          value={healthStatLabel.value}
          sub={healthStatLabel.sub}
        />
        <StatCard
          label="Frequence"
          value={SOURCE_FREQ_LABELS[source.check_frequency] || source.check_frequency}
          sub={`Fiabilite ${source.reliability}/5`}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="card p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Informations source</h2>
            <Link href={source.url} target="_blank" className="text-xs text-primary-600 hover:underline">
              Ouvrir l'URL
            </Link>
          </div>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-400">Categorie</dt>
              <dd className="text-gray-900 mt-1">{source.category === "private" ? "Prive" : "Public"}</dd>
            </div>
            <div>
              <dt className="text-gray-400">Type</dt>
              <dd className="text-gray-900 mt-1">{source.source_type}</dd>
            </div>
            <div>
              <dt className="text-gray-400">Structure</dt>
              <dd className="text-gray-900 mt-1">{SOURCE_KIND_LABELS[source.source_kind] || source.source_kind}</dd>
            </div>
            <div>
              <dt className="text-gray-400">Niveau</dt>
              <dd className="text-gray-900 mt-1">{source.level}</dd>
            </div>
            <div>
              <dt className="text-gray-400">Creee le</dt>
              <dd className="text-gray-900 mt-1">{formatDate(source.created_at)}</dd>
            </div>
            <div className="md:col-span-2">
              <dt className="text-gray-400">URL</dt>
              <dd className="text-gray-900 mt-1 break-all">{source.url}</dd>
            </div>
            {source.notes && (
              <div className="md:col-span-2">
                <dt className="text-gray-400">Notes</dt>
                <dd className="text-gray-900 mt-1">{source.notes}</dd>
              </div>
            )}
          </dl>
          {testResult && (
            <div className={clsx("mt-4 rounded-xl border p-4 text-sm", testResult.success ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50")}>
              <div className="font-medium">{testResult.message}</div>
              <div className="text-xs mt-1 text-gray-600">
                {testResult.items_found} item(s) detecte(s) · activation {testResult.can_activate ? "possible" : "deconseillee"}
              </div>
              {testResult.preview && (
                <div className="mt-3 rounded-xl border border-white/80 bg-white/80 p-3">
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
                <ul className="mt-3 space-y-1 text-xs text-gray-700">
                  {testResult.sample_titles.map((title, index) => (
                    <li key={`${title}-${index}`} className="line-clamp-1">{title}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert className="w-4 h-4 text-red-500" />
            <h2 className="text-sm font-semibold text-gray-700">Derniere erreur</h2>
          </div>
          {latestFailure ? (
            <div className="space-y-2">
              <div className="text-xs text-gray-400">
                {formatDateRelative(latestFailure.started_at)}
                {latestFailure.ended_at && ` · fin ${formatDateRelative(latestFailure.ended_at)}`}
              </div>
              <div className="text-sm text-red-600">
                {latestFailure.error_message || "Aucun detail disponible"}
              </div>
              <div className="text-xs text-gray-500">
                {latestFailure.items_error > 0 && `${latestFailure.items_error} erreur(s) item`}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400">Aucune erreur enregistree.</p>
          )}

          <div className="border-t border-gray-100 mt-4 pt-4">
            <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Dernier succes</h3>
            {latestSuccess ? (
              <div className="text-sm text-gray-700 space-y-1">
                <div>{formatDateRelative(latestSuccess.started_at)}</div>
                <div className="text-xs text-gray-400">
                  {latestSuccess.items_new} nouveaux · {latestSuccess.items_updated} mis a jour · {latestSuccess.items_skipped} ignores
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-400">Aucun succes enregistre.</p>
            )}
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Historique de collecte</h2>
        </div>
        {logs.length === 0 ? (
          <div className="p-6 text-sm text-gray-400">Aucun log disponible pour cette source.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Date</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Statut</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Resultat</th>
                <th className="text-left px-4 py-2 font-medium text-gray-500">Erreur</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-gray-100 align-top">
                  <td className="px-4 py-3 text-gray-600">
                    <div>{formatDateRelative(log.started_at)}</div>
                    <div className="text-xs text-gray-400">{formatDate(log.started_at)}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={clsx("badge", STATUS_COLORS[log.status] || "bg-gray-100 text-gray-700")}>
                      {STATUS_LABELS[log.status] || log.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    <div>{log.items_found} trouves</div>
                    <div className="text-xs text-gray-400">
                      {log.items_new} nouveaux · {log.items_updated} maj · {log.items_skipped} ignores · {log.items_error} erreurs
                    </div>
                  </td>
                  <td className="px-4 py-3 text-red-600 max-w-xl">
                    <div className="line-clamp-3">{log.error_message || "-"}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </AppLayout>
    </RoleGate>
  );
}
