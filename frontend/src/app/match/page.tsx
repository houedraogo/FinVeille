"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import AppLayout from "@/components/AppLayout";
import LimitNotice from "@/components/LimitNotice";
import Link from "next/link";
import {
  Upload, FileText, Search, CheckCircle,
  AlertCircle, ExternalLink, ChevronRight, X, Loader2,
} from "lucide-react";
import clsx from "clsx";
import { billing } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MATCH_STORAGE_KEY = "finveille_match_state";

const DEVICE_TYPE_LABELS: Record<string, string> = {
  subvention: "Subvention", pret: "Prêt", aap: "Appel à projets",
  accompagnement: "Accompagnement", garantie: "Garantie", concours: "Concours",
  investissement: "Investissement", autre: "Autre",
};

const SCORE_COLOR = (score: number) =>
  score >= 70 ? "text-green-600 bg-green-50 border-green-200"
  : score >= 40 ? "text-orange-600 bg-orange-50 border-orange-200"
  : "text-gray-500 bg-gray-50 border-gray-200";

interface Profile {
  sectors: string[];
  countries: string[];
  types: string[];
  amount_min: number | null;
  amount_max: number | null;
  keywords: string[];
  summary: string;
}

interface MatchDevice {
  id: string;
  title: string;
  description_courte: string | null;
  device_type: string;
  country: string;
  sectors: string[] | null;
  amount_min: number | null;
  amount_max: number | null;
  source_url: string;
  close_date: string | null;
  match_score: number;
}

interface MatchResult {
  profile: Profile;
  matches: MatchDevice[];
  total: number;
}

interface MatchPageState {
  fileName: string | null;
  fileSize: number | null;
  result: MatchResult | null;
  error: string | null;
  step: "idle" | "extracting" | "matching" | "done";
  updatedAt?: string | null;
}

export default function MatchPage() {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"idle" | "extracting" | "matching" | "done">("idle");
  const [matchingAllowed, setMatchingAllowed] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  const persistMatchState = useCallback((nextState: MatchPageState | null) => {
    if (!nextState || (!nextState.fileName && !nextState.result && !nextState.error && nextState.step === "idle")) {
      localStorage.removeItem(MATCH_STORAGE_KEY);
      return;
    }
    localStorage.setItem(MATCH_STORAGE_KEY, JSON.stringify(nextState));
  }, []);

  useEffect(() => {
    billing.subscription()
      .then((subscription: any) => setMatchingAllowed(!!subscription?.features?.matching_ai))
      .catch(() => setMatchingAllowed(true));

    const rawState = localStorage.getItem(MATCH_STORAGE_KEY);
    if (!rawState) return;

    try {
      const savedState = JSON.parse(rawState) as MatchPageState;
      setFileName(savedState.fileName);
      setFileSize(savedState.fileSize);
      setResult(savedState.result);
      setError(savedState.error);
      setStep(savedState.step);
    } catch {
      localStorage.removeItem(MATCH_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (loading) return;

    const stateToPersist: MatchPageState = {
      fileName,
      fileSize,
      result,
      error,
      step,
      updatedAt: new Date().toISOString(),
    };

    persistMatchState(stateToPersist);
  }, [fileName, fileSize, result, error, step, loading, persistMatchState]);

  const handleFile = (f: File) => {
    setFile(f);
    setFileName(f.name);
    setFileSize(f.size);
    setResult(null);
    setError(null);
    setStep("idle");
  };

  const resetMatch = () => {
    setFile(null);
    setFileName(null);
    setFileSize(null);
    setResult(null);
    setError(null);
    setStep("idle");
    localStorage.removeItem(MATCH_STORAGE_KEY);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const analyse = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);

    setStep("extracting");
    await new Promise(r => setTimeout(r, 500));
    setStep("matching");

    const form = new FormData();
    form.append("file", file);

    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("finveille_token") : null;
      const res = await fetch(`${API_BASE}/api/v1/match/`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg = typeof data.detail === "string"
          ? data.detail
          : data.detail?.message
            ? data.detail.message
          : Array.isArray(data.detail)
            ? data.detail.map((d: any) => d.msg).join(", ")
            : `Erreur ${res.status}`;
        throw new Error(msg);
      }

      const data: MatchResult = await res.json();
      persistMatchState({
        fileName: file.name,
        fileSize: file.size,
        result: data,
        error: null,
        step: "done",
        updatedAt: new Date().toISOString(),
      });
      setResult(data);
      setError(null);
      setStep("done");
    } catch (e: any) {
      setError(e.message || "Erreur inattendue.");
      setStep("idle");
    } finally {
      setLoading(false);
    }
  };

  const formatAmount = (n: number | null) =>
    n == null ? null
    : n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)} M€`
    : `${(n / 1000).toFixed(0)} k€`;

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <Search className="w-6 h-6 text-primary-500" />
            <h1 className="text-2xl font-bold text-gray-900">Matching de projet</h1>
          </div>
          <p className="text-sm text-gray-500">
            Importez votre pitch ou présentation — FinVeille analyse votre document et identifie
            les dispositifs de financement les plus adaptés à votre projet.
          </p>
        </div>

        {/* Zone d'upload */}
        {!matchingAllowed && (
          <div className="mb-6">
            <LimitNotice
              title="Matching IA reserve aux plans Pro"
              message="Le matching de document est disponible avec les offres Pro, Team et Enterprise."
            />
          </div>
        )}

        {!result && matchingAllowed && (
          <div
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => !file && inputRef.current?.click()}
            className={clsx(
              "border-2 border-dashed rounded-2xl p-10 text-center transition-all",
              dragging ? "border-primary-400 bg-primary-50" : "border-gray-200 hover:border-primary-300 hover:bg-gray-50",
              !file && "cursor-pointer"
            )}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.pptx,.ppt,.txt,.md"
              className="hidden"
              onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
            />

            {!file ? (
              <>
                <Upload className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                <p className="font-medium text-gray-700 mb-1">Glissez votre document ici</p>
                <p className="text-sm text-gray-400">ou cliquez pour parcourir</p>
                <p className="text-xs text-gray-300 mt-3">PDF · PPTX · TXT — max 10 Mo</p>
              </>
            ) : (
              <div className="flex items-center justify-center gap-3">
                <FileText className="w-8 h-8 text-primary-500 flex-shrink-0" />
                <div className="text-left">
                  <p className="font-medium text-gray-800">{fileName}</p>
                  <p className="text-xs text-gray-400">{fileSize ? `${(fileSize / 1024).toFixed(0)} Ko` : ""}</p>
                </div>
                <button
                  onClick={e => { e.stopPropagation(); resetMatch(); }}
                  className="ml-4 text-gray-400 hover:text-red-400"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}

        {/* Bouton analyser */}
        {file && !result && (
          <div className="mt-4 flex justify-center">
            <button
              onClick={analyse}
              disabled={loading}
              className="btn-primary px-8 py-3 text-base disabled:opacity-60 flex items-center gap-2"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Search className="w-5 h-5" />}
              {loading ? "Analyse en cours…" : "Trouver les financements correspondants"}
            </button>
          </div>
        )}

        {/* Étapes */}
        {loading && (
          <div className="mt-6 flex items-center justify-center gap-10">
            {[
              { key: "extracting", label: "Lecture du document" },
              { key: "matching",   label: "Recherche des dispositifs" },
            ].map(({ key, label }, i) => {
              const order = ["extracting", "matching"];
              const current = order.indexOf(step);
              const mine = order.indexOf(key);
              const done = current > mine;
              const active = current === mine;
              return (
                <div key={key} className="flex items-center gap-2 text-sm">
                  <div className={clsx(
                    "w-7 h-7 rounded-full flex items-center justify-center border-2 transition-all",
                    done   ? "bg-green-500 border-green-500 text-white"
                    : active ? "border-primary-500 text-primary-500 animate-pulse"
                    : "border-gray-200 text-gray-300"
                  )}>
                    {done ? <CheckCircle className="w-4 h-4" /> : <span className="text-xs font-bold">{i + 1}</span>}
                  </div>
                  <span className={done ? "text-green-600" : active ? "text-primary-600 font-medium" : "text-gray-400"}>
                    {label}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Erreur */}
        {error && (
          <div className="mt-4 flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 rounded-xl p-4">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">Erreur d'analyse</p>
              <p className="text-sm">{error}</p>
            </div>
          </div>
        )}

        {/* Résultats */}
        {result && (
          <div className="mt-6 space-y-5">
            {/* Profil détecté */}
            <div className="card p-4 bg-primary-50/40 border-primary-100">
              <div className="flex items-start justify-between gap-2 mb-3">
                <div>
                  <p className="text-xs font-semibold text-primary-600 uppercase tracking-wide mb-1">
                    Profil détecté dans votre document
                  </p>
                  {result.profile.summary && (
                    <p className="text-sm text-gray-600 line-clamp-2">{result.profile.summary}</p>
                  )}
                </div>
                <button
                  onClick={resetMatch}
                  className="text-gray-400 hover:text-gray-600 flex-shrink-0"
                  title="Nouvelle analyse"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs">
                {result.profile.sectors.map(s => (
                  <span key={s} className="badge bg-blue-100 text-blue-700 capitalize">{s}</span>
                ))}
                {result.profile.countries.map(p => (
                  <span key={p} className="badge bg-green-100 text-green-700">{p}</span>
                ))}
                {result.profile.types.map(t => (
                  <span key={t} className="badge bg-purple-100 text-purple-700">{DEVICE_TYPE_LABELS[t] ?? t}</span>
                ))}
                {(result.profile.amount_min || result.profile.amount_max) && (
                  <span className="badge bg-gray-100 text-gray-600">
                    {[formatAmount(result.profile.amount_min), formatAmount(result.profile.amount_max)]
                      .filter(Boolean).join(" – ")}
                  </span>
                )}
                {result.profile.keywords.slice(0, 5).map(k => (
                  <span key={k} className="badge bg-gray-50 text-gray-400 border border-gray-200">{k}</span>
                ))}
              </div>
            </div>

            {/* Header résultats */}
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-800">
                {result.total} dispositif{result.total > 1 ? "s" : ""} correspondant{result.total > 1 ? "s" : ""}
              </h3>
              <p className="text-xs text-gray-400">Classés par pertinence</p>
            </div>

            {result.total === 0 && (
              <div className="card p-10 text-center text-gray-400">
                <Search className="w-8 h-8 mx-auto mb-3 opacity-30" />
                <p className="font-medium">Aucun dispositif trouvé</p>
                <p className="text-sm mt-1">Essayez avec un document plus détaillé sur le projet, le secteur ou la géographie.</p>
              </div>
            )}

            {/* Liste */}
            <div className="space-y-3">
              {result.matches.map((d) => (
                <div key={d.id} className="card p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-start gap-3">
                    {/* Score */}
                    <div className={clsx(
                      "flex-shrink-0 w-12 h-12 rounded-xl border-2 flex flex-col items-center justify-center",
                      SCORE_COLOR(d.match_score)
                    )}>
                      <span className="text-lg font-bold leading-none">{d.match_score}</span>
                      <span className="text-[9px] opacity-60">/ 99</span>
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h4 className="font-medium text-gray-900 text-sm leading-snug">{d.title}</h4>
                        <a href={d.source_url} target="_blank" rel="noopener noreferrer"
                          className="flex-shrink-0 text-gray-400 hover:text-primary-600" title="Source">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>

                      {d.description_courte && (
                        <p className="text-xs text-gray-500 line-clamp-2 mb-2">{d.description_courte}</p>
                      )}

                      <div className="flex flex-wrap items-center gap-1.5 text-xs">
                        {d.device_type && (
                          <span className="badge bg-blue-50 text-blue-700">
                            {DEVICE_TYPE_LABELS[d.device_type] ?? d.device_type}
                          </span>
                        )}
                        {d.country && <span className="badge bg-gray-100 text-gray-600">{d.country}</span>}
                        {(d.amount_min || d.amount_max) && (
                          <span className="badge bg-gray-100 text-gray-600">
                            {[formatAmount(d.amount_min), formatAmount(d.amount_max)].filter(Boolean).join(" – ")}
                          </span>
                        )}
                        {d.close_date && (
                          <span className="badge bg-orange-50 text-orange-600">
                            Clôture {new Date(d.close_date).toLocaleDateString("fr-FR")}
                          </span>
                        )}
                        <Link href={`/devices/${d.id}?from=match`}
                          onClick={() => persistMatchState({
                            fileName,
                            fileSize,
                            result,
                            error,
                            step,
                          })}
                          className="ml-auto flex items-center gap-1 text-primary-600 hover:text-primary-700 font-medium">
                          Voir la fiche <ChevronRight className="w-3 h-3" />
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
