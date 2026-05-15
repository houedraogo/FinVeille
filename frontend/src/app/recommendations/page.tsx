"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RefreshCw, Sparkles, ArrowRight, AlertCircle, Clock, CheckCircle2 } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import DeviceCard from "@/components/DeviceCard";
import { relevance } from "@/lib/api";
import type { Device, RecommendationItem } from "@/lib/types";

function toRecommendedDevice(item: RecommendationItem): Device {
  return {
    ...item.device,
    relevance_label: item.relevance.relevance_label,
    relevance_reasons: item.relevance.reason_texts,
    priority_level: item.relevance.priority_level,
    eligibility_confidence: item.relevance.eligibility_confidence,
    decision_hint: item.relevance.decision_hint,
  };
}

export default function RecommendationsPage() {
  const [items, setItems] = useState<RecommendationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRecommendations = async () => {
    try {
      setError(null);
      const data = await relevance.recommendations({ page_size: 24 });
      setItems(Array.isArray(data?.items) ? data.items : []);
    } catch (err: any) {
      setError(err?.message || "Impossible de charger les recommandations.");
      setItems([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadRecommendations();
  }, []);

  const recommendedDevices = useMemo(() => items.map(toRecommendedDevice), [items]);
  const highPriorityCount = items.filter((item) => item.relevance.priority_level?.toLowerCase().includes("haute")).length;
  const mediumPriorityCount = items.filter((item) => item.relevance.priority_level?.toLowerCase().includes("moyenne")).length;
  const quickActionCount = items.filter((item) => item.relevance.decision_hint?.toLowerCase().includes("semaine")).length;

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await relevance.refreshRecommendations({ page_size: 24 });
    } catch {
      // On recharge quand meme la vue ensuite.
    }
    await loadRecommendations();
  };

  return (
    <AppLayout>
      <div className="space-y-6">
        <section
          className="relative overflow-hidden rounded-[30px] border border-blue-300/25 px-6 py-6 text-white shadow-[0_24px_70px_-34px_rgba(15,23,42,0.65)]"
          style={{
            background: "linear-gradient(135deg, #071a46 0%, #123da3 48%, #0369a1 100%)",
          }}
        >
          <div className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-white/14 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-28 left-1/3 h-56 w-80 rounded-full bg-cyan-300/18 blur-3xl" />

          <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white/85">
                <Sparkles className="h-3.5 w-3.5" />
                Recommandations
              </div>
              <h1 className="mt-4 text-3xl font-bold tracking-[-0.03em] text-white">
                Les meilleures opportunités pour votre profil
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-7 text-white/78">
                Kafundo met en avant les opportunités les plus cohérentes avec votre structure, vos secteurs et vos priorités.
                L’objectif n’est pas d’en voir plus, mais de décider plus vite sur les bonnes pistes.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleRefresh}
                disabled={refreshing}
                className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-primary-700 shadow-sm transition hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
                Actualiser
              </button>
              <Link
                href="/onboarding"
                className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-4 py-3 text-sm font-semibold text-white transition hover:bg-white/15"
              >
                Ajuster mon profil
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          <div className="relative mt-6 grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-white/20 bg-white/14 px-4 py-4 backdrop-blur-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70">Priorité haute</p>
              <p className="mt-2 text-2xl font-bold">{highPriorityCount}</p>
              <p className="mt-1 text-sm text-white/75">À regarder en premier cette semaine.</p>
            </div>
            <div className="rounded-2xl border border-white/20 bg-white/14 px-4 py-4 backdrop-blur-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70">Bonnes pistes</p>
              <p className="mt-2 text-2xl font-bold">{mediumPriorityCount}</p>
              <p className="mt-1 text-sm text-white/75">Pertinentes mais avec quelques points à confirmer.</p>
            </div>
            <div className="rounded-2xl border border-white/20 bg-white/14 px-4 py-4 backdrop-blur-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/70">Actions rapides</p>
              <p className="mt-2 text-2xl font-bold">{quickActionCount}</p>
              <p className="mt-1 text-sm text-white/75">Demandent une décision ou une vérification très prochainement.</p>
            </div>
          </div>
        </section>

        {error ? (
          <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-semibold">Impossible de charger les recommandations</p>
              <p className="mt-1">{error}</p>
            </div>
          </div>
        ) : null}

        <section className="grid gap-3 lg:grid-cols-3">
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-emerald-900">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="text-sm font-semibold">Bonne nouvelle : vos opportunités sont déjà triées</p>
                <p className="mt-1 text-sm leading-6 text-emerald-800">
                  Chaque fiche met en avant les raisons de pertinence et une action conseillée pour vous aider à arbitrer plus vite.
                </p>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-amber-900">
            <div className="flex items-start gap-3">
              <Clock className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="text-sm font-semibold">Attention : vérifiez les échéances</p>
                <p className="mt-1 text-sm leading-6 text-amber-800">
                  Une opportunité recommandée ne veut pas dire qu’elle est simple à saisir. Confirmez toujours les conditions et la date limite sur la source officielle.
                </p>
              </div>
            </div>
          </div>
          <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-4 text-blue-900">
            <div className="flex items-start gap-3">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="text-sm font-semibold">Conseil : gardez votre profil à jour</p>
                <p className="mt-1 text-sm leading-6 text-blue-800">
                  Plus votre profil est précis, plus les recommandations sont utiles et priorisées correctement.
                </p>
              </div>
            </div>
          </div>
        </section>

        {loading ? (
          <div className="flex min-h-[260px] items-center justify-center">
            <RefreshCw className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        ) : recommendedDevices.length === 0 ? (
          <div className="rounded-[26px] border border-slate-200 bg-white px-6 py-12 text-center shadow-sm">
            <p className="text-lg font-semibold text-slate-900">Aucune recommandation forte pour le moment</p>
            <p className="mx-auto mt-2 max-w-2xl text-sm leading-7 text-slate-500">
              Complétez votre profil, vos secteurs et vos zones d’intérêt pour que Kafundo vous propose des opportunités plus ciblées.
            </p>
            <div className="mt-5">
              <Link href="/onboarding" className="btn-primary">
                Configurer mon profil
              </Link>
            </div>
          </div>
        ) : (
          <section className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">Opportunités recommandées</h2>
                <p className="mt-1 text-sm text-slate-500">
                  {recommendedDevices.length} opportunité{recommendedDevices.length > 1 ? "s" : ""} classée{recommendedDevices.length > 1 ? "s" : ""} selon votre profil.
                </p>
              </div>
              <Link href="/opportunities/now" className="text-sm font-medium text-primary-600 hover:text-primary-700">
                Voir les opportunités à saisir
              </Link>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              {recommendedDevices.map((device) => (
                <DeviceCard key={device.id} device={device} fromParam="recommendations" />
              ))}
            </div>
          </section>
        )}
      </div>
    </AppLayout>
  );
}
