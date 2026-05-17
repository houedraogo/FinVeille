"use client";
import { useState, useRef, useCallback, useEffect } from "react";
import AppLayout from "@/components/AppLayout";
import LimitNotice from "@/components/LimitNotice";
import Link from "next/link";
import {
  Upload, FileText, FileSearch, CheckCircle,
  AlertCircle, ExternalLink, ChevronRight, X, Loader2, ScanText,
} from "lucide-react";
import clsx from "clsx";
import { billing } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MATCH_STORAGE_KEY = "kafundo_match_state";

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

const isMatchResult = (value: unknown): value is MatchResult => {
  const candidate = value as Partial<MatchResult> | null;
  const profile = candidate?.profile as Partial<Profile> | undefined;
  return Boolean(
    candidate
    && profile
    && Array.isArray(candidate.matches)
    && typeof candidate.total === "number"
    && Array.isArray(profile.sectors)
    && Array.isArray(profile.countries)
    && Array.isArray(profile.types)
    && Array.isArray(profile.keywords)
  );
};

const PREMIUM_MATCH_MESSAGE = "L'analyse de document est disponible avec une offre supérieure. Choisissez un plan Pro, Team ou Expert pour en bénéficier.";

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
      setResult(isMatchResult(savedState.result) ? savedState.result : null);
      setError(savedState.error);
      setStep(isMatchResult(savedState.result) ? savedState.step : "idle");
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
      const token = typeof window !== "undefined" ? localStorage.getItem("kafundo_token") : null;
      const res = await fetch(`${API_BASE}/api/v1/match/`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 402 || data.detail?.code === "feature_locked") {
          setMatchingAllowed(false);
          throw new Error(data.detail?.message || PREMIUM_MATCH_MESSAGE);
        }
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
      if (!isMatchResult(data)) {
        throw new Error("L'analyse n'a pas retourné un résultat exploitable. Réessayez avec un document plus détaillé.");
      }
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
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary-100 bg-primary-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-primary-600">
            <ScanText className="w-3.5 h-3.5" />
            Analyse de document
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Importez votre document — obtenez vos financements
          </h1>
          <p className="text-sm leading-6 text-gray-500 max-w-xl">
            Kafundo lit votre pitch deck, note de synthèse ou présentation de projet,
            en extrait le profil clé, puis sélectionne les dispositifs de financement
            les plus adaptés parmi 2 500+ opportunités.
          </p>
        </div>

        {/* Zone d'upload */}
        {!matchingAllowed && (
          <div className="mb-6 space-y-4">
            <LimitNotice
              title="Changez d’offre pour analyser vos documents"
              message="L’analyse de document n’est pas incluse dans votre plan actuel. Passez à une offre Pro, Team ou Expert pour importer un document projet et recevoir les financements les plus pertinents."
            />
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary-600">
                Ce que débloque l’offre Pro
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-sm font-semibold text-slate-900">Lecture automatique du document</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    Kafundo extrait les pays, secteurs, types de financement et besoins de ton projet.
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-sm font-semibold text-slate-900">Sélection des opportunités pertinentes</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    Tu évites de parcourir tout le catalogue et tu vas plus vite vers les meilleures pistes.
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-sm font-semibold text-slate-900">Aide à la priorisation</p>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    Le résultat met en avant les financements à traiter en premier selon ton document.
                  </p>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Link href="/billing" className="btn-primary text-xs">
                  Voir les offres
                </Link>
                <Link href="/recommendations" className="btn-secondary text-xs">
                  Voir mes recommandations actuelles
                </Link>
              </div>
            </div>
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
                <FileSearch className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                <p className="font-semibold text-gray-700 mb-1">Glissez votre document projet ici</p>
                <p className="text-sm text-gray-400">ou cliquez pour sélectionner un fichier</p>
                <p className="text-xs text-gray-300 mt-3">Pitch deck · Note de synthèse · Présentation</p>
                <p className="text-xs text-gray-300 mt-0.5">PDF · PPTX · TXT · MD — max 10 Mo</p>
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
          <div className="mt-4 flex flex-col items-center gap-2">
            <button
              onClick={analyse}
              disabled={loading}
              className="btn-primary px-8 py-3 text-base disabled:opacity-60 flex items-center gap-2"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileSearch className="w-5 h-5" />}
              {loading ? "Analyse en cours…" : "Lancer l'analyse"}
            </button>
            {!loading && (
              <p className="text-xs text-gray-400">Résultats obtenus en quelques secondes</p>
            )}
          </div>
        )}

        {/* Étapes */}
        {loading && (
          <div className="mt-6 flex items-center justify-center gap-10">
            {[
              { key: "extracting", label: "Lecture & extraction du profil" },
              { key: "matching",   label: "Matching des financements" },
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
        {error && matchingAllowed && (
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
                    Profil extrait de votre document
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
              <div>
                <h3 className="font-semibold text-gray-800">
                  {result.total} financement{result.total > 1 ? "s" : ""} identifié{result.total > 1 ? "s" : ""} pour votre projet
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">Classés par score de pertinence — du plus adapté au moins adapté</p>
              </div>
            </div>

            {result.total === 0 && (
              <div className="card p-10 text-center text-gray-400">
                <FileSearch className="w-8 h-8 mx-auto mb-3 opacity-30" />
                <p className="font-medium text-gray-600">Aucun financement identifié</p>
                <p className="text-sm mt-1">
                  Le document ne contient peut-être pas assez d'informations sur le secteur, le pays ou le type de projet.
                  Essayez avec une note plus détaillée.
                </p>
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
                          Analyser <ChevronRight className="w-3 h-3" />
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
