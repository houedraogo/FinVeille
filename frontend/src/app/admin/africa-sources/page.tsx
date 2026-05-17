"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  ExternalLink,
  Globe2,
  RefreshCw,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import clsx from "clsx";

import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { admin } from "@/lib/api";

const ACTION_LABELS: Record<string, string> = {
  a_configurer: "A configurer",
  nettoyer_textes: "Textes a nettoyer",
  corriger_collecte: "Collecte a corriger",
  a_requalifier: "A requalifier",
  dates_a_completer: "Dates a completer",
  veille_manuelle: "Veille manuelle",
  ok: "OK",
};

const ACTION_STYLES: Record<string, string> = {
  a_configurer: "bg-red-50 text-red-700 border-red-100",
  nettoyer_textes: "bg-orange-50 text-orange-700 border-orange-100",
  corriger_collecte: "bg-red-50 text-red-700 border-red-100",
  a_requalifier: "bg-violet-50 text-violet-700 border-violet-100",
  dates_a_completer: "bg-amber-50 text-amber-700 border-amber-100",
  veille_manuelle: "bg-blue-50 text-blue-700 border-blue-100",
  ok: "bg-emerald-50 text-emerald-700 border-emerald-100",
};

function Kpi({ label, value, detail, icon: Icon, tone }: { label: string; value: string; detail: string; icon: any; tone: string }) {
  return (
    <div className={`rounded-[24px] border p-5 ${tone}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] opacity-70">{label}</p>
          <p className="mt-2 text-3xl font-semibold">{value}</p>
          <p className="mt-1 text-xs opacity-70">{detail}</p>
        </div>
        <Icon className="h-5 w-5 shrink-0 opacity-70" />
      </div>
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "Jamais";
  return new Date(value).toLocaleDateString("fr", { day: "2-digit", month: "short", year: "numeric" });
}

export default function AdminAfricaSourcesPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const load = async () => {
    setLoading(true);
    try {
      setData(await admin.africaSources());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const rows = data?.rows || [];
  const filteredRows = useMemo(
    () => rows.filter((row: any) => (filter === "all" ? true : row.recommended_action === filter)),
    [rows, filter],
  );

  const summary = data?.summary || {};
  const actions = data?.action_counts || {};

  return (
    <RoleGate allow={["admin"]} title="Sources Afrique reservees" message="Cette page est reservee au super admin." backHref="/admin/workspace">
      <AppLayout>
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-medium text-primary-600">Super admin</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-950">Sources africaines actionnables</h1>
            <p className="mt-2 text-sm text-slate-500">
              Suivi des sources qui peuvent produire de vraies opportunites candidatables pour l'Afrique.
            </p>
          </div>
          <button onClick={load} disabled={loading} className="btn-secondary text-xs">
            <RefreshCw className={loading ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
            Actualiser
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center rounded-[28px] border border-slate-200 bg-white py-16 text-sm text-slate-400">
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
            Chargement des sources africaines...
          </div>
        ) : (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
              <Kpi label="Sources suivies" value={(summary.total_sources || 0).toLocaleString("fr")} detail={`${summary.active_sources || 0} actives`} icon={Globe2} tone="border-blue-200 bg-blue-50 text-blue-950" />
              <Kpi label="Opportunites publiques" value={(summary.public_devices || 0).toLocaleString("fr")} detail="visibles cote utilisateur" icon={CheckCircle2} tone="border-emerald-200 bg-emerald-50 text-emerald-950" />
              <Kpi label="Admin only" value={(summary.admin_only_devices || 0).toLocaleString("fr")} detail="signaux ou fiches a verifier" icon={ShieldCheck} tone="border-slate-200 bg-slate-50 text-slate-950" />
              <Kpi label="Sources manuelles" value={(summary.manual_sources || 0).toLocaleString("fr")} detail="curees plutot que scrappees" icon={Wrench} tone="border-violet-200 bg-violet-50 text-violet-950" />
              <Kpi label="A traiter" value={(summary.sources_to_fix || 0).toLocaleString("fr")} detail="hors veille manuelle et OK" icon={AlertTriangle} tone="border-amber-200 bg-amber-50 text-amber-950" />
            </div>

            <section className="mb-6 rounded-[28px] border border-slate-200 bg-white p-5">
              <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-slate-950">Priorites par source</h2>
                  <p className="text-sm text-slate-500">
                    Le but n'est pas le volume : chaque source doit produire des opportunites lisibles, credibles et actionnables.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {["all", "dates_a_completer", "a_requalifier", "nettoyer_textes", "corriger_collecte", "veille_manuelle", "ok"].map((action) => (
                    <button
                      key={action}
                      onClick={() => setFilter(action)}
                      className={clsx(
                        "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                        filter === action ? "border-primary-600 bg-primary-600 text-white" : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-primary-50",
                      )}
                    >
                      {action === "all" ? "Toutes" : ACTION_LABELS[action] || action}
                      {action !== "all" && actions[action] ? ` (${actions[action]})` : ""}
                    </button>
                  ))}
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-slate-200">
                <div className="grid grid-cols-[1.25fr_0.8fr_0.75fr_0.75fr_0.75fr_0.8fr] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                  <span>Source</span>
                  <span>Action</span>
                  <span>Public</span>
                  <span>Admin</span>
                  <span>Sante</span>
                  <span>Acces</span>
                </div>
                <div className="divide-y divide-slate-100">
                  {filteredRows.length === 0 ? (
                    <p className="py-12 text-center text-sm text-slate-400">Aucune source pour ce filtre.</p>
                  ) : (
                    filteredRows.map((source: any) => (
                      <div key={source.source_id} className="grid grid-cols-[1.25fr_0.8fr_0.75fr_0.75fr_0.75fr_0.8fr] gap-3 px-4 py-4 text-sm">
                        <div className="min-w-0">
                          <Link href={`/sources/${source.source_id}`} className="truncate font-semibold text-slate-950 hover:text-primary-700">
                            {source.name}
                          </Link>
                          <p className="truncate text-xs text-slate-400">
                            {source.organism} · {source.country || "Afrique"} · {source.collection_mode}
                          </p>
                          <p className="mt-1 text-xs text-slate-400">Derniere verif. {formatDate(source.last_checked_at)}</p>
                        </div>
                        <div>
                          <span className={clsx("inline-flex rounded-full border px-2.5 py-1 text-xs font-medium", ACTION_STYLES[source.recommended_action] || ACTION_STYLES.ok)}>
                            {ACTION_LABELS[source.recommended_action] || source.recommended_action}
                          </span>
                          {source.consecutive_errors > 0 && (
                            <p className="mt-1 text-xs text-red-500">{source.consecutive_errors} erreur(s)</p>
                          )}
                        </div>
                        <div>
                          <p className="font-semibold text-slate-950">{source.public_total}</p>
                          <p className="text-xs text-slate-400">{source.open_total} ouvertes · {source.recurring_total} perm.</p>
                        </div>
                        <div>
                          <p className="font-semibold text-slate-950">{source.admin_only_total}</p>
                          <p className="text-xs text-slate-400">{source.missing_dates} sans date</p>
                        </div>
                        <div>
                          <p className={clsx("font-semibold", source.health >= 80 ? "text-emerald-700" : source.health >= 60 ? "text-amber-700" : "text-red-700")}>
                            {source.health}/100
                          </p>
                          <p className="text-xs text-slate-400">{source.reliability || 0}/5 fiabilite</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Link href={`/sources/${source.source_id}`} className="btn-secondary text-xs">
                            <Database className="h-3.5 w-3.5" />
                            Source
                          </Link>
                          {source.url && (
                            <a href={source.url} target="_blank" rel="noreferrer" className="btn-secondary text-xs">
                              <ExternalLink className="h-3.5 w-3.5" />
                              Site
                            </a>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>
          </>
        )}
      </AppLayout>
    </RoleGate>
  );
}
