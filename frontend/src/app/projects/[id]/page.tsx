"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import clsx from "clsx";
import {
  RefreshCw, ArrowLeft, Zap, TrendingUp, Target, Clock,
  AlertTriangle, CheckCircle2, ChevronRight, Trash2, RotateCcw,
} from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { projects } from "@/lib/api";
import {
  UserProject,
  ProjectMatch,
  ProjectNextAction,
  PROJECT_STAGE_LABELS,
  PROJECT_STAGE_COLORS,
  ProjectStage,
  DEVICE_TYPE_LABELS,
} from "@/lib/types";
import { formatDate, estimateEffort } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Score ring
// ---------------------------------------------------------------------------

function ScoreRing({ score }: { score: number }) {
  const pct = Math.min(100, Math.round(score));
  const color = pct >= 60 ? "#10b981" : pct >= 35 ? "#f59e0b" : "#9ca3af";
  const r = 28;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;

  return (
    <div className="relative w-20 h-20 flex items-center justify-center">
      <svg className="absolute inset-0 -rotate-90" viewBox="0 0 72 72">
        <circle cx="36" cy="36" r={r} fill="none" stroke="#f3f4f6" strokeWidth="7" />
        <circle
          cx="36" cy="36" r={r} fill="none"
          stroke={color} strokeWidth="7"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
        />
      </svg>
      <span className="text-lg font-bold text-gray-900">{pct}%</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Next actions
// ---------------------------------------------------------------------------

const ACTION_ICONS: Record<string, React.ElementType> = {
  deadline: Clock,
  complete: AlertTriangle,
  opportunity: CheckCircle2,
};
const ACTION_COLORS: Record<string, string> = {
  deadline: "text-red-600 bg-red-50",
  complete: "text-yellow-600 bg-yellow-50",
  opportunity: "text-emerald-600 bg-emerald-50",
};

function NextActions({ actions }: { actions: ProjectNextAction[] }) {
  if (actions.length === 0) return null;
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Prochaines actions</h3>
      <div className="space-y-2">
        {actions.map((a, i) => {
          const Icon = ACTION_ICONS[a.type] ?? Target;
          return (
            <Link
              key={i}
              href={a.href}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-gray-50 transition-colors group"
            >
              <div className={clsx("p-1.5 rounded-md flex-shrink-0", ACTION_COLORS[a.type])}>
                <Icon className="w-3.5 h-3.5" />
              </div>
              <span className="text-xs text-gray-700 group-hover:text-gray-900 flex-1 line-clamp-1">
                {a.label}
              </span>
              <ChevronRight className="w-3 h-3 text-gray-400 group-hover:text-gray-600" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Match card
// ---------------------------------------------------------------------------

function MatchCard({ match }: { match: ProjectMatch }) {
  const urgent = match.days_left !== null && match.days_left <= 7;
  const scoreColor =
    match.score >= 60 ? "bg-emerald-100 text-emerald-700" :
    match.score >= 35 ? "bg-orange-100 text-orange-700" :
    "bg-gray-100 text-gray-600";

  return (
    <Link
      href={`/devices/${match.id}`}
      className="flex items-center gap-4 py-3 px-2 -mx-2 hover:bg-gray-50 rounded-lg transition-colors group"
    >
      <span className={clsx("badge text-[10px] flex-shrink-0", scoreColor)}>
        {Math.round(match.score)}%
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-gray-900 line-clamp-1">{match.title}</p>
        <p className="text-[10px] text-gray-400 mt-0.5">
          {DEVICE_TYPE_LABELS[match.device_type] || match.device_type} · {match.organism} · {match.country}
        </p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {match.amount_max && (
          <span className="text-xs font-medium text-gray-700">
            {match.amount_max >= 1_000_000
              ? `${(match.amount_max / 1_000_000).toFixed(1)}M€`
              : `${Math.round(match.amount_max / 1_000)}k€`}
          </span>
        )}
        <span className="text-[10px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded hidden sm:inline">
          ⏱ {estimateEffort(match.device_type)}
        </span>
        {match.days_left !== null && (
          <span className={clsx(
            "text-[10px] font-medium px-1.5 py-0.5 rounded",
            urgent ? "bg-red-50 text-red-600" : "bg-orange-50 text-orange-600"
          )}>
            J-{match.days_left}
          </span>
        )}
        <ChevronRight className="w-3 h-3 text-gray-300 group-hover:text-gray-500" />
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [project, setProject] = useState<UserProject | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<"matches" | "actions">("matches");

  useEffect(() => {
    if (!id) return;
    projects.get(id)
      .then(setProject)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  async function handleRefreshMatch() {
    if (!id) return;
    setRefreshing(true);
    try {
      const result = await projects.refreshMatch(id);
      setProject((prev) =>
        prev
          ? {
              ...prev,
              cached_matches: result.matches,
              match_score: result.global_score,
              matched_at: new Date().toISOString(),
              match_summary: result,
            }
          : prev
      );
    } catch (err) {
      console.error(err);
    } finally {
      setRefreshing(false);
    }
  }

  async function handleDelete() {
    if (!id || !confirm("Supprimer ce projet ?")) return;
    await projects.delete(id);
    router.push("/projects");
  }

  if (loading) {
    return (
      <AppLayout>
        <div className="flex items-center justify-center h-48">
          <RefreshCw className="w-5 h-5 text-gray-400 animate-spin" />
        </div>
      </AppLayout>
    );
  }

  if (!project) {
    return (
      <AppLayout>
        <div className="text-center py-20 text-gray-400 text-sm">Projet introuvable</div>
      </AppLayout>
    );
  }

  const summary = project.match_summary ?? {
    matches: project.cached_matches ?? [],
    global_score: project.match_score ?? 0,
    total_compatible: project.cached_matches?.length ?? 0,
    potential_funding: project.cached_matches?.slice(0, 5).reduce((s, m) => s + (m.amount_max ?? 0), 0) ?? 0,
    next_actions: [],
  };

  const urgentCount = summary.matches.filter((m) => m.days_left !== null && m.days_left <= 14).length;

  return (
    <AppLayout>
      {/* Back */}
      <Link href="/projects" className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 mb-5">
        <ArrowLeft className="w-3.5 h-3.5" /> Retour aux projets
      </Link>

      {/* Header */}
      <div className="card p-5 mb-4">
        <div className="flex items-start gap-5">
          <ScoreRing score={summary.global_score} />

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h1 className="text-xl font-bold text-gray-900">{project.name}</h1>
                {project.description && (
                  <p className="text-sm text-gray-500 mt-1">{project.description}</p>
                )}
              </div>
              <span className={clsx(
                "badge text-xs flex-shrink-0",
                PROJECT_STAGE_COLORS[project.stage as ProjectStage]
              )}>
                {PROJECT_STAGE_LABELS[project.stage as ProjectStage]}
              </span>
            </div>

            {/* Tags */}
            {(project.sectors.length > 0 || project.countries.length > 0) && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {project.sectors.map((s) => (
                  <span key={s} className="badge bg-blue-50 text-blue-700 text-[10px]">{s}</span>
                ))}
                {project.countries.map((c) => (
                  <span key={c} className="badge bg-gray-100 text-gray-600 text-[10px]">{c}</span>
                ))}
              </div>
            )}

            {/* KPIs */}
            <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-gray-100">
              <div>
                <div className="flex items-center gap-1.5 text-emerald-600 mb-0.5">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-sm font-bold">
                    {summary.potential_funding >= 1_000_000
                      ? `${(summary.potential_funding / 1_000_000).toFixed(1)}M€`
                      : summary.potential_funding >= 1_000
                      ? `${Math.round(summary.potential_funding / 1_000)}k€`
                      : summary.potential_funding > 0 ? `${summary.potential_funding}€` : "—"}
                  </span>
                </div>
                <p className="text-[10px] text-gray-400">Financement potentiel</p>
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-blue-600 mb-0.5">
                  <Zap className="w-4 h-4" />
                  <span className="text-sm font-bold">{summary.total_compatible}</span>
                </div>
                <p className="text-[10px] text-gray-400">Aides compatibles</p>
              </div>
              <div>
                <div className="flex items-center gap-1.5 text-orange-600 mb-0.5">
                  <Target className="w-4 h-4" />
                  <span className="text-sm font-bold">{urgentCount}</span>
                </div>
                <p className="text-[10px] text-gray-400">Urgences ≤ 14j</p>
              </div>
            </div>
          </div>
        </div>

        {/* Actions barre */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
          <p className="text-[10px] text-gray-400">
            {project.matched_at
              ? `Matching mis à jour le ${formatDate(project.matched_at)}`
              : "Aucun matching calculé"}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefreshMatch}
              disabled={refreshing}
              className="btn btn-secondary text-xs flex items-center gap-1.5"
            >
              <RotateCcw className={clsx("w-3.5 h-3.5", refreshing && "animate-spin")} />
              Relancer le matching
            </button>
            <button
              onClick={handleDelete}
              className="btn text-xs flex items-center gap-1.5 text-red-600 hover:bg-red-50 border border-red-200"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Supprimer
            </button>
          </div>
        </div>
      </div>

      {/* Body */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Matches column (2/3) */}
        <div className="lg:col-span-2 card p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-700">
              Aides compatibles
              <span className="ml-2 text-xs font-normal text-gray-400">({summary.total_compatible})</span>
            </h2>
            <div className="flex gap-1">
              <button
                onClick={() => setActiveTab("matches")}
                className={clsx(
                  "text-xs px-2.5 py-1 rounded-md font-medium transition-colors",
                  activeTab === "matches"
                    ? "bg-primary-600 text-white"
                    : "text-gray-500 hover:bg-gray-100"
                )}
              >
                Tous ({summary.matches.length})
              </button>
              <button
                onClick={() => setActiveTab("actions")}
                className={clsx(
                  "text-xs px-2.5 py-1 rounded-md font-medium transition-colors",
                  activeTab === "actions"
                    ? "bg-red-500 text-white"
                    : "text-gray-500 hover:bg-gray-100"
                )}
              >
                Urgents ({urgentCount})
              </button>
            </div>
          </div>

          {summary.matches.length === 0 ? (
            <div className="py-10 text-center text-xs text-gray-400">
              Aucune aide compatible trouvée. Affinez les secteurs ou les pays de votre projet.
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {(activeTab === "actions"
                ? summary.matches.filter((m) => m.days_left !== null && m.days_left <= 14)
                : summary.matches
              ).map((m) => (
                <MatchCard key={m.id} match={m} />
              ))}
            </div>
          )}
        </div>

        {/* Side column (1/3) */}
        <div className="space-y-4">
          <NextActions actions={summary.next_actions} />

          {/* Budget */}
          {(project.budget_min || project.budget_max) && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Budget projet</h3>
              <p className="text-sm text-gray-900">
                {project.budget_min
                  ? `${project.budget_min.toLocaleString("fr")} €`
                  : "—"}{" "}
                →{" "}
                {project.budget_max
                  ? `${project.budget_max.toLocaleString("fr")} €`
                  : "sans limite"}
              </p>
            </div>
          )}

          {/* Keywords */}
          {project.keywords.length > 0 && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Mots-clés</h3>
              <div className="flex flex-wrap gap-1.5">
                {project.keywords.map((k) => (
                  <span key={k} className="badge bg-violet-50 text-violet-700 text-[10px]">{k}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
