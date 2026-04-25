"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CalendarOff, Database, FileWarning, Filter, RefreshCw, ShieldCheck, Sparkles, Zap } from "lucide-react";
import clsx from "clsx";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { admin } from "@/lib/api";
import { formatDateRelative } from "@/lib/utils";

function Kpi({ label, value, icon: Icon, tone }: { label: string; value: string; icon: any; tone: string }) {
  return (
    <div className={`rounded-[24px] border p-5 ${tone}`}>
      <Icon className="h-5 w-5" />
      <p className="mt-3 text-xs font-semibold uppercase tracking-[0.16em] opacity-70">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

export default function AdminDataQualityPage() {
  const [quality, setQuality] = useState<any>(null);
  const [audit, setAudit] = useState<any>(null);
  const [pending, setPending] = useState<any>(null);
  const [operations, setOperations] = useState<any>(null);
  const [catalogAudit, setCatalogAudit] = useState<any>(null);
  const [sourceReport, setSourceReport] = useState<any>(null);
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [qualityData, auditData, pendingData, operationsData, sourceReportData] = await Promise.all([
        admin.quality(),
        admin.qualityAudit().catch(() => null),
        admin.pending(),
        admin.operations(),
        admin.sourceQualityReport().catch(() => null),
      ]);
      const catalogData = await admin.catalogAudit().catch(() => null);
      setQuality(qualityData);
      setAudit(auditData);
      setPending(pendingData);
      setOperations(operationsData);
      setCatalogAudit(catalogData);
      setSourceReport(sourceReportData);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const runAudit = async () => {
    await admin.runQualityAudit();
    setMessage("Audit qualite declenche en arriere-plan.");
  };

  const runCatalogControl = async () => {
    await admin.runCatalogQualityControl();
    setMessage("Controle qualite catalogue declenche en arriere-plan.");
  };

  const fixExpired = async () => {
    const result = await admin.fixExpired() as any;
    setMessage(result.message || "Correction lancee.");
    await load();
  };

  const enrich = async () => {
    const result = await admin.enrich(50) as any;
    setMessage(result.message || "Enrichissement lance.");
  };

  const collectAll = async () => {
    await admin.collectAll();
    setMessage("Collecte globale declenchee.");
  };

  const recentErrors = operations?.recent_errors || [];
  const auditSources = audit?.sources || audit?.source_health || [];
  const weakDevices = audit?.weak_devices || audit?.thin_devices || [];
  const noDateDevices = audit?.missing_close_dates || audit?.open_without_close_date || [];
  const sourcePriorities = (catalogAudit?.source_priorities || []).filter((source: any) =>
    actionFilter === "all" ? true : source.recommended_action === actionFilter
  );
  const reportRows = sourceReport?.rows || catalogAudit?.source_report?.rows || [];
  const actionLabels = catalogAudit?.action_labels || {
    a_enrichir: "A enrichir",
    a_purger: "A purger",
    a_verifier: "A verifier",
    source_a_revoir: "Source a revoir",
    ok: "OK",
  };
  const actionColors: Record<string, string> = {
    a_enrichir: "bg-blue-50 text-blue-700",
    a_purger: "bg-red-50 text-red-700",
    a_verifier: "bg-amber-50 text-amber-700",
    source_a_revoir: "bg-violet-50 text-violet-700",
    ok: "bg-emerald-50 text-emerald-700",
  };

  return (
    <RoleGate allow={["admin"]} title="Qualite reservee" message="Cette page est reservee au super admin." backHref="/admin/workspace">
      <AppLayout>
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-primary-600">Super admin</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-950">Qualite donnees</h1>
            <p className="mt-2 text-sm text-slate-500">Sources en erreur, fiches pending, sans date et textes faibles.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={load} disabled={loading} className="btn-secondary text-xs">
              <RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
              Actualiser
            </button>
            <button onClick={runAudit} className="btn-secondary text-xs">
              <ShieldCheck className="h-3.5 w-3.5" />
              Lancer audit
            </button>
            <button onClick={runCatalogControl} className="btn-secondary text-xs">
              <Database className="h-3.5 w-3.5" />
              Controle catalogue
            </button>
            <button onClick={collectAll} className="btn-primary text-xs">
              <Zap className="h-3.5 w-3.5" />
              Collecte globale
            </button>
          </div>
        </div>

        {message && (
          <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {message}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center rounded-[28px] border border-slate-200 bg-white py-16 text-sm text-slate-400">
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            Chargement qualite...
          </div>
        ) : (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
              <Kpi label="Fiches faibles" value={(catalogAudit?.risk_counts?.weak_text ?? quality?.incomplete_devices ?? 0).toLocaleString("fr")} icon={FileWarning} tone="border-orange-200 bg-orange-50 text-orange-950" />
              <Kpi label="Pending" value={(catalogAudit?.risk_counts?.pending_review ?? quality?.pending_validation ?? 0).toLocaleString("fr")} icon={ShieldCheck} tone="border-amber-200 bg-amber-50 text-amber-950" />
              <Kpi label="Open sans date" value={(catalogAudit?.risk_counts?.open_without_date ?? 0).toLocaleString("fr")} icon={CalendarOff} tone="border-red-200 bg-red-50 text-red-950" />
              <Kpi label="Texte anglais" value={(catalogAudit?.risk_counts?.english_text ?? 0).toLocaleString("fr")} icon={AlertTriangle} tone="border-slate-200 bg-slate-50 text-slate-950" />
              <Kpi label="Sources erreur" value={recentErrors.length.toLocaleString("fr")} icon={Database} tone="border-red-200 bg-red-50 text-red-950" />
              <Kpi label="Completion moy." value={`${quality?.avg_completeness || 0}%`} icon={Sparkles} tone="border-emerald-200 bg-emerald-50 text-emerald-950" />
            </div>

            {catalogAudit && (
              <section className="mb-6 rounded-[28px] border border-slate-200 bg-white p-5">
                <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-950">Audit catalogue priorise</h2>
                    <p className="text-sm text-slate-500">
                      {catalogAudit.totals.devices.toLocaleString("fr")} fiches · {catalogAudit.totals.sources.toLocaleString("fr")} sources · generation {new Date(catalogAudit.generated_at).toLocaleString("fr")}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {["all", "a_enrichir", "a_purger", "a_verifier", "source_a_revoir", "ok"].map((action) => (
                      <button
                        key={action}
                        onClick={() => setActionFilter(action)}
                        className={clsx(
                          "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium",
                          actionFilter === action ? "border-primary-600 bg-primary-600 text-white" : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-primary-50",
                        )}
                      >
                        <Filter className="h-3 w-3" />
                        {action === "all" ? "Toutes" : actionLabels[action]}
                        {action !== "all" && catalogAudit.action_counts?.[action] ? ` (${catalogAudit.action_counts[action]})` : ""}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
                  {Object.entries(catalogAudit.risk_counts || {}).slice(0, 12).map(([key, value]: any) => (
                    <div key={key} className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-3">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{key.replaceAll("_", " ")}</p>
                      <p className="mt-1 text-lg font-semibold text-slate-950">{Number(value || 0).toLocaleString("fr")}</p>
                    </div>
                  ))}
                </div>

                <div className="overflow-hidden rounded-2xl border border-slate-200">
                  <div className="grid grid-cols-[1.2fr_0.55fr_1.4fr_0.7fr_0.7fr] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                    <span>Source</span>
                    <span>Action</span>
                    <span>Problemes</span>
                    <span>Qualite</span>
                    <span>Acces</span>
                  </div>
                  <div className="divide-y divide-slate-100">
                    {sourcePriorities.length === 0 ? (
                      <p className="py-10 text-center text-sm text-slate-400">Aucune source pour ce filtre.</p>
                    ) : (
                      sourcePriorities.slice(0, 80).map((source: any) => (
                        <div key={source.source_id} className="grid grid-cols-[1.2fr_0.55fr_1.4fr_0.7fr_0.7fr] gap-3 px-4 py-4 text-sm">
                          <div className="min-w-0">
                            <Link href={`/sources/${source.source_id}`} className="truncate font-semibold text-slate-950 hover:text-primary-700">
                              {source.source_name}
                            </Link>
                            <p className="truncate text-xs text-slate-400">{source.organism} · {source.country} · {source.device_count} fiche(s)</p>
                          </div>
                          <div>
                            <span className={clsx("rounded-full px-2.5 py-1 text-xs font-medium", actionColors[source.recommended_action] || "bg-slate-100 text-slate-600")}>
                              {actionLabels[source.recommended_action] || source.recommended_action}
                            </span>
                            <p className="mt-1 text-xs text-slate-400">score {source.priority_score}</p>
                          </div>
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(source.issues || {})
                              .filter(([, value]: any) => Number(value || 0) > 0)
                              .slice(0, 7)
                              .map(([key, value]: any) => (
                                <span key={key} className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                                  {key.replaceAll("_", " ")}: {String(value)}
                                </span>
                              ))}
                          </div>
                          <div className="text-xs text-slate-500">
                            <p>Completion {source.avg_completeness}%</p>
                            <p>Confiance {source.avg_confidence}%</p>
                            <p>Publiable {source.publishable_rate ?? 0}%</p>
                          </div>
                          <div className="text-xs text-slate-500">
                            <p>{source.is_active ? "Active" : "Inactive"}</p>
                            <p>Dates {source.date_rate ?? 0}% Â· Erreurs {source.error_rate_30d ?? 0}%</p>
                            <p>{source.last_success_at ? `Succes ${new Date(source.last_success_at).toLocaleDateString("fr")}` : "Jamais collectee"}</p>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </section>
            )}

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[1fr_0.8fr]">
              <section className="rounded-[28px] border border-slate-200 bg-white p-5">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-950">Sources en erreur</h2>
                    <p className="text-sm text-slate-500">Actions rapides: voir logs, relancer, desactiver depuis la source.</p>
                  </div>
                  <Link href="/sources" className="btn-secondary text-xs">Toutes les sources</Link>
                </div>
                <div className="space-y-2">
                  {recentErrors.length === 0 ? (
                    <p className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-4 text-sm text-emerald-800">Aucune erreur recente.</p>
                  ) : (
                    recentErrors.map((item: any) => (
                      <div key={item.id} className="rounded-2xl border border-red-100 bg-red-50/70 px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate font-semibold text-red-950">{item.source_name}</p>
                            <p className="mt-1 text-xs text-red-700">{item.status} · {formatDateRelative(item.started_at)}</p>
                            {item.error_message && <p className="mt-1 line-clamp-2 text-xs text-red-600">{item.error_message}</p>}
                          </div>
                          <Link href={`/sources/${item.source_id}`} className="btn-secondary shrink-0 text-xs">Voir logs</Link>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>

              <section className="rounded-[28px] border border-slate-200 bg-white p-5">
                <h2 className="text-lg font-semibold text-slate-950">Actions rapides</h2>
                <div className="mt-4 grid gap-2">
                  <button onClick={fixExpired} className="btn-secondary justify-start text-xs">
                    <CalendarOff className="h-3.5 w-3.5" />
                    Corriger open avec date passee
                  </button>
                  <button onClick={enrich} className="btn-secondary justify-start text-xs">
                    <Sparkles className="h-3.5 w-3.5" />
                    Enrichir 50 fiches faibles
                  </button>
                  <Link href="/admin" className="btn-secondary justify-start text-xs">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    Deduplication et validation
                  </Link>
                  <Link href="/sources" className="btn-secondary justify-start text-xs">
                    <Database className="h-3.5 w-3.5" />
                    Desactiver / relancer une source
                  </Link>
                </div>
              </section>
            </div>

            <section className="mb-6 rounded-[28px] border border-slate-200 bg-white p-5">
              <div className="mb-4 flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-slate-950">Rapport source par source</h2>
                  <p className="text-sm text-slate-500">
                    Volume, taux publiable, taux de dates, erreurs recentes et qualite moyenne.
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500">
                  {(reportRows.length || 0).toLocaleString("fr")} sources analysees
                </span>
              </div>
              <div className="overflow-hidden rounded-2xl border border-slate-200">
                <div className="grid grid-cols-[1.35fr_0.45fr_0.55fr_0.55fr_0.55fr_0.6fr] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  <span>Source</span>
                  <span>Volume</span>
                  <span>Publiable</span>
                  <span>Dates</span>
                  <span>Erreurs</span>
                  <span>Action</span>
                </div>
                <div className="max-h-[520px] divide-y divide-slate-100 overflow-y-auto">
                  {reportRows.slice(0, 120).map((source: any) => (
                    <div key={source.source_id} className="grid grid-cols-[1.35fr_0.45fr_0.55fr_0.55fr_0.55fr_0.6fr] gap-3 px-4 py-3 text-sm">
                      <div className="min-w-0">
                        <Link href={`/sources/${source.source_id}`} className="truncate font-semibold text-slate-950 hover:text-primary-700">
                          {source.source_name}
                        </Link>
                        <p className="truncate text-xs text-slate-400">{source.organism} Â· {source.country}</p>
                      </div>
                      <span className="text-slate-600">{source.device_count}</span>
                      <span className={clsx("font-medium", Number(source.publishable_rate || 0) >= 70 ? "text-emerald-700" : "text-amber-700")}>
                        {source.publishable_rate ?? 0}%
                      </span>
                      <span className={clsx("font-medium", Number(source.date_rate || 0) >= 60 ? "text-emerald-700" : "text-orange-700")}>
                        {source.date_rate ?? 0}%
                      </span>
                      <span className={clsx("font-medium", Number(source.error_rate_30d || 0) > 20 ? "text-red-700" : "text-slate-600")}>
                        {source.error_rate_30d ?? 0}%
                      </span>
                      <span className={clsx("w-fit rounded-full px-2.5 py-1 text-xs font-medium", actionColors[source.recommended_action] || "bg-slate-100 text-slate-600")}>
                        {actionLabels[source.recommended_action] || source.recommended_action}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
              <section className="rounded-[28px] border border-slate-200 bg-white p-5">
                <h2 className="text-lg font-semibold text-slate-950">Fiches pending</h2>
                <p className="mt-1 text-sm text-slate-500">{(pending?.total || 0).toLocaleString("fr")} fiches a valider.</p>
                <div className="mt-4 space-y-2">
                  {(pending?.items || []).slice(0, 5).map((device: any) => (
                    <Link key={device.id} href={`/devices/${device.id}`} className="block rounded-2xl border border-slate-100 px-4 py-3 hover:bg-slate-50">
                      <p className="line-clamp-1 text-sm font-semibold text-slate-900">{device.title}</p>
                      <p className="mt-1 text-xs text-slate-500">{device.organism} · {device.country}</p>
                    </Link>
                  ))}
                </div>
              </section>
              <section className="rounded-[28px] border border-slate-200 bg-white p-5">
                <h2 className="text-lg font-semibold text-slate-950">Fiches sans date</h2>
                <p className="mt-1 text-sm text-slate-500">Extrait audit si disponible.</p>
                <div className="mt-4 space-y-2">
                  {Array.isArray(noDateDevices) && noDateDevices.length ? noDateDevices.slice(0, 5).map((item: any, index: number) => (
                    <div key={item.id || index} className="rounded-2xl border border-slate-100 px-4 py-3 text-sm text-slate-700">
                      {item.title || item.source_name || JSON.stringify(item).slice(0, 80)}
                    </div>
                  )) : <p className="rounded-2xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-400">Audit detaille non disponible.</p>}
                </div>
              </section>
              <section className="rounded-[28px] border border-slate-200 bg-white p-5">
                <h2 className="text-lg font-semibold text-slate-950">Textes faibles</h2>
                <p className="mt-1 text-sm text-slate-500">Extrait audit si disponible.</p>
                <div className="mt-4 space-y-2">
                  {Array.isArray(weakDevices) && weakDevices.length ? weakDevices.slice(0, 5).map((item: any, index: number) => (
                    <div key={item.id || index} className="rounded-2xl border border-slate-100 px-4 py-3 text-sm text-slate-700">
                      {item.title || item.source_name || JSON.stringify(item).slice(0, 80)}
                    </div>
                  )) : <p className="rounded-2xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-400">Audit detaille non disponible.</p>}
                </div>
              </section>
            </div>

            {Array.isArray(auditSources) && auditSources.length > 0 && (
              <section className="mt-6 rounded-[28px] border border-slate-200 bg-white p-5">
                <h2 className="text-lg font-semibold text-slate-950">Sources bruitees ou fragiles</h2>
                <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
                  {auditSources.slice(0, 10).map((source: any, index: number) => (
                    <div key={source.source_id || source.id || index} className="rounded-2xl border border-slate-100 px-4 py-3">
                      <p className="font-semibold text-slate-900">{source.source_name || source.name || "Source"}</p>
                      <p className="mt-1 text-xs text-slate-500">{source.reason || source.status || JSON.stringify(source).slice(0, 100)}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </AppLayout>
    </RoleGate>
  );
}
