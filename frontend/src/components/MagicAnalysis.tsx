"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import {
  X, Sparkles, ArrowRight, CheckCircle2, Circle, Loader2,
  TrendingUp, Zap, Target, ChevronRight, ExternalLink,
} from "lucide-react";

import { projects } from "@/lib/api";
import { DEVICE_TYPE_LABELS, ProjectMatch, ProjectMatchSummary } from "@/lib/types";
import { formatAmount, estimateEffort } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTOR_TAGS = [
  "IA", "Numérique", "Industrie", "Santé", "Agriculture",
  "Énergie", "Transport", "Environnement", "R&D", "Export",
  "Innovation", "Agroalimentaire", "Culture", "Éducation",
];

const COUNTRY_TAGS = ["France", "Sénégal", "Maroc", "Côte d'Ivoire", "Tunisie", "Cameroun"];

const PROGRESS_STEPS = [
  "Analyse du profil projet",
  "Identification des secteurs et mots-clés",
  "Recherche des aides compatibles",
  "Calcul du financement potentiel",
  "Priorisation des opportunités",
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Step = "form" | "loading" | "results";

interface AnalysisResult {
  projectId: string;
  projectName: string;
  summary: ProjectMatchSummary;
}

interface Props {
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildFinancePlan(matches: ProjectMatch[]) {
  const byType: Record<string, { count: number; total: number }> = {};
  for (const m of matches) {
    if (!byType[m.device_type]) byType[m.device_type] = { count: 0, total: 0 };
    byType[m.device_type].count++;
    byType[m.device_type].total += m.amount_max ?? 0;
  }
  return Object.entries(byType)
    .sort(([, a], [, b]) => b.total - a.total)
    .slice(0, 4)
    .map(([type, data]) => ({ type, ...data }));
}

function formatFunding(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} M€`;
  if (n >= 1_000) return `${Math.round(n / 1_000)} k€`;
  return n > 0 ? `${Math.round(n)} €` : "—";
}

const SCORE_COLOR = (s: number) =>
  s >= 70 ? "bg-emerald-500" : s >= 50 ? "bg-blue-500" : s >= 35 ? "bg-yellow-400" : "bg-gray-300";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TagSelector({
  tags,
  selected,
  onToggle,
  placeholder,
}: {
  tags: string[];
  selected: string[];
  onToggle: (t: string) => void;
  placeholder?: string;
}) {
  const [custom, setCustom] = useState("");

  function addCustom() {
    const val = custom.trim();
    if (val && !selected.includes(val)) onToggle(val);
    setCustom("");
  }

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {tags.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => onToggle(t)}
            className={clsx(
              "rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
              selected.includes(t)
                ? "bg-primary-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {t}
          </button>
        ))}
      </div>
      {selected.filter((s) => !tags.includes(s)).map((s) => (
        <span key={s} className="inline-flex items-center gap-1 mr-1 mb-1 rounded-full bg-primary-600 px-2.5 py-1 text-xs font-medium text-white">
          {s}
          <button type="button" onClick={() => onToggle(s)} className="opacity-70 hover:opacity-100">×</button>
        </span>
      ))}
      <div className="flex gap-2 mt-1">
        <input
          className="input flex-1 text-xs py-1.5"
          placeholder={placeholder ?? "Ajouter…"}
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCustom())}
        />
        <button type="button" onClick={addCustom} className="btn btn-secondary text-xs px-3">
          +
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step components
// ---------------------------------------------------------------------------

function StepForm({
  onAnalyse,
}: {
  onAnalyse: (name: string, description: string, sectors: string[], countries: string[]) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [sectors, setSectors] = useState<string[]>([]);
  const [countries, setCountries] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  function toggle<T>(arr: T[], val: T): T[] {
    return arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val];
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-gradient-to-br from-primary-700 to-blue-600 px-8 pt-8 pb-6 text-white">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles className="w-5 h-5 text-primary-200" />
          <span className="text-xs font-semibold uppercase tracking-widest text-primary-200">
            Analyse IA
          </span>
        </div>
        <h2 className="text-2xl font-bold">Analyser mon projet</h2>
        <p className="mt-1 text-sm text-primary-100">
          Obtenez en 30 secondes votre shortlist personnalisée, un plan de financement et vos priorités.
        </p>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-5">
        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">Nom du projet *</label>
          <input
            ref={inputRef}
            className="input w-full"
            placeholder="ex : Développement IA, Expansion Afrique, Industrialisation R&D…"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && name.trim() && onAnalyse(name, description, sectors, countries)}
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">Décrivez votre projet</label>
          <textarea
            className="input w-full resize-none"
            rows={3}
            placeholder="Objectif, besoin de financement, stade actuel du projet… Plus c'est précis, meilleure est l'analyse."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">Secteurs concernés</label>
          <TagSelector
            tags={SECTOR_TAGS}
            selected={sectors}
            onToggle={(t) => setSectors(toggle(sectors, t))}
            placeholder="Autre secteur…"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-gray-700 mb-1.5">Pays cibles</label>
          <TagSelector
            tags={COUNTRY_TAGS}
            selected={countries}
            onToggle={(t) => setCountries(toggle(countries, t))}
            placeholder="Autre pays…"
          />
        </div>
      </div>

      {/* Footer CTA */}
      <div className="px-8 py-5 border-t border-gray-100">
        <button
          onClick={() => name.trim() && onAnalyse(name, description, sectors, countries)}
          disabled={!name.trim()}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-6 py-3.5 text-sm font-bold text-white shadow-lg shadow-primary-200 transition-all hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Sparkles className="w-4 h-4" />
          Lancer l'analyse
          <ArrowRight className="w-4 h-4 ml-auto" />
        </button>
        <p className="text-center text-[10px] text-gray-400 mt-2">
          Un projet sera créé dans votre espace — modifiable à tout moment.
        </p>
      </div>
    </div>
  );
}

function StepLoading({ projectName }: { projectName: string }) {
  const [doneCount, setDoneCount] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setDoneCount((c) => {
        if (c >= PROGRESS_STEPS.length - 1) { clearInterval(timer); return c; }
        return c + 1;
      });
    }, 700);
    return () => clearInterval(timer);
  }, []);

  const pct = Math.round(((doneCount + 1) / PROGRESS_STEPS.length) * 100);

  return (
    <div className="flex flex-col items-center justify-center h-full bg-gradient-to-b from-gray-950 to-gray-900 text-white px-10 py-12">
      <div className="w-16 h-16 rounded-2xl bg-primary-500/20 flex items-center justify-center mb-6 shadow-lg shadow-primary-900/40">
        <Sparkles className="w-8 h-8 text-primary-300 animate-pulse" />
      </div>

      <h2 className="text-xl font-bold mb-1">Analyse en cours…</h2>
      <p className="text-sm text-gray-400 mb-8">
        Analyse de <span className="text-white font-medium">"{projectName}"</span>
      </p>

      {/* Steps */}
      <div className="w-full max-w-sm space-y-3 mb-8">
        {PROGRESS_STEPS.map((step, i) => {
          const done = i < doneCount;
          const active = i === doneCount;
          return (
            <div key={step} className="flex items-center gap-3">
              {done ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              ) : active ? (
                <Loader2 className="w-4 h-4 text-primary-400 flex-shrink-0 animate-spin" />
              ) : (
                <Circle className="w-4 h-4 text-gray-600 flex-shrink-0" />
              )}
              <span className={clsx(
                "text-sm transition-colors",
                done ? "text-emerald-400" : active ? "text-white font-medium" : "text-gray-600"
              )}>
                {step}
              </span>
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="w-full max-w-sm">
        <div className="flex justify-between text-xs text-gray-500 mb-1.5">
          <span>Progression</span>
          <span className="text-primary-400 font-medium">{pct}%</span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-gray-800 overflow-hidden">
          <div
            className="h-full rounded-full bg-primary-500 transition-all duration-700"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function StepResults({
  result,
  onClose,
}: {
  result: AnalysisResult;
  onClose: () => void;
}) {
  const { summary, projectId, projectName } = result;
  const plan = buildFinancePlan(summary.matches);
  const topMatches = summary.matches.slice(0, 5);
  const maxScore = topMatches[0]?.score ?? 100;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-gradient-to-br from-emerald-700 to-green-600 px-8 pt-6 pb-5 text-white flex-shrink-0">
        <div className="flex items-center gap-2 mb-1">
          <CheckCircle2 className="w-4 h-4 text-emerald-200" />
          <span className="text-xs font-semibold uppercase tracking-widest text-emerald-200">
            Analyse terminée
          </span>
        </div>
        <h2 className="text-xl font-bold line-clamp-1">"{projectName}"</h2>

        {/* KPIs */}
        <div className="grid grid-cols-3 gap-3 mt-4">
          <div className="bg-white/10 rounded-xl px-3 py-2.5 text-center">
            <div className="text-lg font-bold">{formatFunding(summary.potential_funding)}</div>
            <div className="text-[10px] text-emerald-100 mt-0.5">💰 Financement potentiel</div>
          </div>
          <div className="bg-white/10 rounded-xl px-3 py-2.5 text-center">
            <div className="text-lg font-bold">{summary.total_compatible}</div>
            <div className="text-[10px] text-emerald-100 mt-0.5">📈 Aides compatibles</div>
          </div>
          <div className="bg-white/10 rounded-xl px-3 py-2.5 text-center">
            <div className="text-lg font-bold">{summary.next_actions.length}</div>
            <div className="text-[10px] text-emerald-100 mt-0.5">🎯 Actions à lancer</div>
          </div>
        </div>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-8 py-5 space-y-6">

        {/* Shortlist */}
        {topMatches.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">
              Top opportunités
            </h3>
            <div className="space-y-2.5">
              {topMatches.map((m) => (
                <Link
                  key={m.id}
                  href={`/devices/${m.id}`}
                  onClick={onClose}
                  className="flex items-center gap-3 group"
                >
                  {/* Score bar */}
                  <div className="w-20 flex-shrink-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[10px] font-bold text-gray-600">{Math.round(m.score)}%</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className={clsx("h-full rounded-full", SCORE_COLOR(m.score))}
                        style={{ width: `${(m.score / maxScore) * 100}%` }}
                      />
                    </div>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-gray-900 line-clamp-1 group-hover:text-primary-700 transition-colors">
                      {m.title}
                    </p>
                    <p className="text-[10px] text-gray-400">
                      {DEVICE_TYPE_LABELS[m.device_type] || m.device_type} · {m.organism}
                      {m.amount_max ? ` · ${formatFunding(m.amount_max)}` : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {m.days_left !== null && m.days_left <= 14 && (
                      <span className="text-[10px] font-semibold text-red-600 bg-red-50 px-1.5 py-0.5 rounded">
                        J-{m.days_left}
                      </span>
                    )}
                    <span className="text-[10px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded hidden sm:inline">
                      ⏱ {estimateEffort(m.device_type)}
                    </span>
                    <ChevronRight className="w-3 h-3 text-gray-300 group-hover:text-primary-500 transition-colors" />
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Plan de financement */}
        {plan.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">
              Plan de financement
            </h3>
            <div className="space-y-2">
              {plan.map(({ type, count, total }) => (
                <div key={type} className="flex items-center gap-3 py-2 px-3 rounded-xl bg-gray-50">
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-800">
                      {DEVICE_TYPE_LABELS[type] || type}
                    </p>
                    <p className="text-[10px] text-gray-400">
                      {count} aide{count > 1 ? "s" : ""} · effort {estimateEffort(type)}
                    </p>
                  </div>
                  <div className="text-sm font-bold text-gray-900">
                    {total > 0 ? formatFunding(total) : "Récurrent"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Prochaines actions */}
        {summary.next_actions.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3">
              Prochaines actions recommandées
            </h3>
            <div className="space-y-2">
              {summary.next_actions.map((a, i) => (
                <Link
                  key={i}
                  href={a.href}
                  onClick={onClose}
                  className={clsx(
                    "flex items-start gap-2.5 rounded-xl px-3 py-2.5 text-xs font-medium transition-colors group",
                    a.priority === "high"
                      ? "bg-red-50 text-red-700 hover:bg-red-100"
                      : "bg-blue-50 text-blue-700 hover:bg-blue-100"
                  )}
                >
                  <span className="mt-0.5 flex-shrink-0">{a.priority === "high" ? "⚠️" : "→"}</span>
                  <span className="line-clamp-2">{a.label}</span>
                  <ChevronRight className="w-3 h-3 flex-shrink-0 mt-0.5 ml-auto group-hover:translate-x-0.5 transition-transform" />
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer CTAs */}
      <div className="px-8 py-5 border-t border-gray-100 flex gap-3 flex-shrink-0">
        <Link
          href={`/projects/${projectId}`}
          onClick={onClose}
          className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-primary-600 px-4 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-primary-700"
        >
          <TrendingUp className="w-4 h-4" />
          Voir l'analyse complète
          <ArrowRight className="w-4 h-4 ml-auto" />
        </Link>
        <button
          onClick={onClose}
          className="rounded-xl border border-gray-200 px-4 py-3 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
        >
          Fermer
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main modal
// ---------------------------------------------------------------------------

export default function MagicAnalysis({ onClose }: Props) {
  const [step, setStep] = useState<Step>("form");
  const [projectName, setProjectName] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Minimum loading display — don't show results before 3.5s for "wow" effect
  const minLoadDoneRef = useRef(false);
  const apiDoneRef = useRef<AnalysisResult | null>(null);

  // Prevent body scroll while modal is open
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  async function handleAnalyse(
    name: string,
    description: string,
    sectors: string[],
    countries: string[]
  ) {
    setProjectName(name);
    setStep("loading");
    setError(null);
    minLoadDoneRef.current = false;
    apiDoneRef.current = null;

    // Minimum display time for the "wow" loading screen
    setTimeout(() => {
      minLoadDoneRef.current = true;
      if (apiDoneRef.current) {
        setResult(apiDoneRef.current);
        setStep("results");
      }
    }, 3600);

    try {
      const created = await projects.create({
        name,
        description: description.trim() || null,
        sectors,
        countries,
        stage: "ideation",
        keywords: [],
      });

      const summary: ProjectMatchSummary = created.match_summary ?? {
        matches: created.cached_matches ?? [],
        global_score: created.match_score ?? 0,
        total_compatible: (created.cached_matches ?? []).length,
        potential_funding: (created.cached_matches ?? [])
          .slice(0, 5)
          .reduce((s: number, m: any) => s + (m.amount_max ?? 0), 0),
        next_actions: [],
      };

      const res: AnalysisResult = {
        projectId: created.id,
        projectName: name,
        summary,
      };

      apiDoneRef.current = res;
      if (minLoadDoneRef.current) {
        setResult(res);
        setStep("results");
      }
    } catch (err: any) {
      setError(err.message || "Erreur lors de l'analyse");
      setStep("form");
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4"
      onClick={(e) => e.target === e.currentTarget && step === "form" && onClose()}
    >
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden flex flex-col"
        style={{ maxHeight: "90vh", minHeight: "500px" }}>

        {/* Close button */}
        {step !== "loading" && (
          <button
            onClick={onClose}
            className="absolute top-4 right-4 z-10 p-1.5 rounded-full bg-white/80 text-gray-500 hover:text-gray-800 hover:bg-white transition-colors shadow-sm"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {/* Error */}
        {error && (
          <div className="absolute top-0 inset-x-0 z-20 bg-red-500 text-white text-xs text-center py-2 px-4">
            {error} — <button className="underline" onClick={() => setError(null)}>Réessayer</button>
          </div>
        )}

        {/* Steps */}
        {step === "form" && <StepForm onAnalyse={handleAnalyse} />}
        {step === "loading" && <StepLoading projectName={projectName} />}
        {step === "results" && result && <StepResults result={result} onClose={onClose} />}
      </div>
    </div>
  );
}
