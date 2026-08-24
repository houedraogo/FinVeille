"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import clsx from "clsx";
import { Plus, FolderOpen, RefreshCw, Zap, TrendingUp, Target, ChevronRight, X } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { projects } from "@/lib/api";
import {
  UserProject,
  PROJECT_STAGE_LABELS,
  PROJECT_STAGE_COLORS,
  ProjectStage,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Modal création projet
// ---------------------------------------------------------------------------

const STAGES: ProjectStage[] = ["ideation", "mvp", "croissance", "expansion", "maturite"];

function CreateModal({ onClose, onCreate }: { onClose: () => void; onCreate: (p: UserProject) => void }) {
  const [form, setForm] = useState({
    name: "",
    description: "",
    sectors: "",
    countries: "",
    stage: "ideation" as ProjectStage,
    budget_max: "",
    keywords: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const created = await projects.create({
        name: form.name.trim(),
        description: form.description.trim() || null,
        sectors: form.sectors.split(",").map((s) => s.trim()).filter(Boolean),
        countries: form.countries.split(",").map((s) => s.trim()).filter(Boolean),
        stage: form.stage,
        budget_max: form.budget_max ? parseFloat(form.budget_max) : null,
        keywords: form.keywords.split(",").map((s) => s.trim()).filter(Boolean),
      });
      onCreate(created);
    } catch (err: any) {
      setError(err.message || "Erreur lors de la création");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold text-gray-900">Nouveau projet</h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Nom du projet *</label>
            <input
              className="input w-full"
              placeholder="ex : Développement IA, Expansion Afrique…"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
            <textarea
              className="input w-full resize-none"
              rows={2}
              placeholder="Objectif, contexte, besoin de financement…"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Secteurs</label>
              <input
                className="input w-full"
                placeholder="IA, Industrie, Santé…"
                value={form.sectors}
                onChange={(e) => setForm({ ...form, sectors: e.target.value })}
              />
              <p className="text-[10px] text-gray-400 mt-0.5">Séparés par des virgules</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Pays cibles</label>
              <input
                className="input w-full"
                placeholder="France, Sénégal…"
                value={form.countries}
                onChange={(e) => setForm({ ...form, countries: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Maturité</label>
              <select
                className="input w-full"
                value={form.stage}
                onChange={(e) => setForm({ ...form, stage: e.target.value as ProjectStage })}
              >
                {STAGES.map((s) => (
                  <option key={s} value={s}>{PROJECT_STAGE_LABELS[s]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Budget max (€)</label>
              <input
                className="input w-full"
                type="number"
                placeholder="500000"
                value={form.budget_max}
                onChange={(e) => setForm({ ...form, budget_max: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Mots-clés complémentaires</label>
            <input
              className="input w-full"
              placeholder="robotique, export, décarbonation…"
              value={form.keywords}
              onChange={(e) => setForm({ ...form, keywords: e.target.value })}
            />
          </div>

          {error && <p className="text-xs text-red-600">{error}</p>}

          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} className="btn btn-secondary text-sm">
              Annuler
            </button>
            <button type="submit" disabled={loading} className="btn btn-primary text-sm">
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : "Créer & analyser"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Project card
// ---------------------------------------------------------------------------

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-gray-400">—</span>;
  const color =
    score >= 60 ? "text-emerald-600 bg-emerald-50" :
    score >= 35 ? "text-orange-600 bg-orange-50" :
    "text-gray-500 bg-gray-50";
  return (
    <span className={clsx("text-xs font-bold px-2 py-0.5 rounded-full", color)}>
      {Math.round(score)}%
    </span>
  );
}

function MaturityBar({ stage }: { stage: ProjectStage }) {
  const steps = STAGES;
  const idx = steps.indexOf(stage);
  return (
    <div className="flex gap-0.5 items-center">
      {steps.map((_, i) => (
        <div
          key={i}
          className={clsx(
            "h-1.5 flex-1 rounded-full",
            i <= idx ? "bg-primary-500" : "bg-gray-200"
          )}
        />
      ))}
    </div>
  );
}

function ProjectCard({ project }: { project: UserProject }) {
  const matchCount = project.cached_matches?.length ?? 0;
  const potentialFunding = project.cached_matches
    ?.slice(0, 5)
    .reduce((sum, m) => sum + (m.amount_max ?? 0), 0) ?? 0;

  return (
    <Link
      href={`/projects/${project.id}`}
      className="card p-5 hover:shadow-md transition-shadow flex flex-col gap-4 group"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-900 line-clamp-1 group-hover:text-primary-600 transition-colors">
            {project.name}
          </h3>
          {project.description && (
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{project.description}</p>
          )}
        </div>
        <ScoreBadge score={project.match_score} />
      </div>

      {/* Tags */}
      {(project.sectors.length > 0 || project.countries.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {project.sectors.slice(0, 3).map((s) => (
            <span key={s} className="badge bg-blue-50 text-blue-700 text-[10px]">{s}</span>
          ))}
          {project.countries.slice(0, 2).map((c) => (
            <span key={c} className="badge bg-gray-100 text-gray-600 text-[10px]">{c}</span>
          ))}
        </div>
      )}

      {/* Maturité */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[10px] text-gray-500">
          <span>Maturité</span>
          <span className={clsx("px-1.5 py-0.5 rounded font-medium text-[10px]", PROJECT_STAGE_COLORS[project.stage])}>
            {PROJECT_STAGE_LABELS[project.stage]}
          </span>
        </div>
        <MaturityBar stage={project.stage} />
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-2 pt-1 border-t border-gray-100">
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-emerald-600 mb-0.5">
            <TrendingUp className="w-3 h-3" />
            <span className="text-xs font-bold">
              {potentialFunding >= 1_000_000
                ? `${(potentialFunding / 1_000_000).toFixed(1)}M€`
                : potentialFunding >= 1_000
                ? `${Math.round(potentialFunding / 1_000)}k€`
                : potentialFunding > 0 ? `${potentialFunding}€` : "—"}
            </span>
          </div>
          <p className="text-[10px] text-gray-400">Financement potentiel</p>
        </div>
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-blue-600 mb-0.5">
            <Zap className="w-3 h-3" />
            <span className="text-xs font-bold">{matchCount}</span>
          </div>
          <p className="text-[10px] text-gray-400">Aides compatibles</p>
        </div>
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-orange-600 mb-0.5">
            <Target className="w-3 h-3" />
            <span className="text-xs font-bold">
              {project.cached_matches?.filter((m) => m.days_left !== null && m.days_left <= 14).length ?? 0}
            </span>
          </div>
          <p className="text-[10px] text-gray-400">Actions urgentes</p>
        </div>
      </div>

      <div className="flex justify-end">
        <span className="text-xs text-primary-600 font-medium flex items-center gap-1 group-hover:gap-2 transition-all">
          Voir le projet <ChevronRight className="w-3 h-3" />
        </span>
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ProjectsPage() {
  const [list, setList] = useState<UserProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    projects.list()
      .then((data) => setList(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  function handleCreated(p: UserProject) {
    setList((prev) => [p, ...prev]);
    setShowModal(false);
  }

  return (
    <AppLayout>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Mes projets</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {list.length} projet{list.length !== 1 ? "s" : ""} · aides associées automatiquement
          </p>
        </div>
        <button onClick={() => setShowModal(true)} className="btn btn-primary flex items-center gap-2 text-sm">
          <Plus className="w-4 h-4" />
          Nouveau projet
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <RefreshCw className="w-5 h-5 text-gray-400 animate-spin" />
        </div>
      ) : list.length === 0 ? (
        <div className="text-center py-20">
          <FolderOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <h3 className="text-sm font-medium text-gray-700 mb-1">Aucun projet pour l'instant</h3>
          <p className="text-xs text-gray-400 mb-5">
            Créez votre premier projet pour découvrir les aides et investisseurs compatibles.
          </p>
          <button onClick={() => setShowModal(true)} className="btn btn-primary text-sm">
            Créer mon premier projet
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {list.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}

      {showModal && (
        <CreateModal onClose={() => setShowModal(false)} onCreate={handleCreated} />
      )}
    </AppLayout>
  );
}
