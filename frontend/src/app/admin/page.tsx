"use client";
import { useEffect, useState } from "react";
import AppLayout from "@/components/AppLayout";
import RoleGate from "@/components/RoleGate";
import { admin } from "@/lib/api";
import DeviceCard from "@/components/DeviceCard";
import {
  AlertTriangle, CheckCircle, Clock, RefreshCw,
  ShieldCheck, Zap, XCircle, Users, Mail, Send, Sparkles,
  Copy, Trash2, ChevronDown, ChevronUp, Star,
} from "lucide-react";

export default function AdminPage() {
  const [quality, setQuality] = useState<any>(null);
  const [pending, setPending] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState("");
  const [actionType, setActionType] = useState<"success" | "error">("success");
  const [emailStatus, setEmailStatus] = useState<any>(null);
  const [emailTesting, setEmailTesting] = useState(false);
  const [dedupData, setDedupData] = useState<any>(null);
  const [dedupLoading, setDedupLoading] = useState(false);
  const [dedupMerging, setDedupMerging] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [mergingGroup, setMergingGroup] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [q, p, es] = await Promise.all([admin.quality(), admin.pending(), admin.emailStatus()]);
      setQuality(q);
      setPending(p);
      setEmailStatus(es);
    } catch (e: any) {
      const msg = e.message || "Erreur inconnue";
      if (msg.includes("401") || msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("not authenticated")) {
        setError("Session expirée. Veuillez vous reconnecter.");
      } else if (msg.includes("403") || msg.toLowerCase().includes("forbidden")) {
        setError("Accès refusé. Cette page est réservée aux administrateurs et éditeurs.");
      } else {
        setError(`Erreur lors du chargement : ${msg}`);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleFixExpired = async () => {
    try {
      const result = await admin.fixExpired() as { message?: string };
      setActionMsg(result.message || "Opportunités expirées corrigées !");
      setActionType("success");
      fetchData();
    } catch (e: any) {
      setActionMsg(`Erreur : ${e.message}`);
      setActionType("error");
    }
  };

  const handleCollectAll = async () => {
    try {
      await admin.collectAll();
      setActionMsg("Collecte globale déclenchée ! Les sources sont en cours de traitement.");
      setActionType("success");
    } catch (e: any) {
      setActionMsg(`Erreur : ${e.message}`);
      setActionType("error");
    }
  };

  const handleEnrich = async () => {
    try {
      const result = await admin.enrich(50) as { message?: string };
      setActionMsg(result.message || "Enrichissement lancé !");
      setActionType("success");
    } catch (e: any) {
      setActionMsg(`Erreur : ${e.message}`);
      setActionType("error");
    }
  };

  const [rewriting, setRewriting] = useState(false);
  const handleBulkRewrite = async () => {
    setRewriting(true);
    try {
      const result = await admin.rewrite(20, "pending") as {
        processed?: number; succeeded?: number; failed?: number; skipped?: number; message?: string;
      };
      setActionMsg(result.message || `${result.succeeded}/${result.processed} fiches reformulées.`);
      setActionType((result.failed ?? 0) > 0 && (result.succeeded ?? 0) === 0 ? "error" : "success");
      fetchData();
    } catch (e: any) {
      setActionMsg(`Erreur reformulation : ${e.message}`);
      setActionType("error");
    } finally {
      setRewriting(false);
    }
  };

  const handleDetectDuplicates = async () => {
    setDedupLoading(true);
    try {
      const result = await admin.dedup() as any;
      setDedupData(result);
      setExpandedGroups(new Set());
    } catch (e: any) {
      setActionMsg(`Déduplication : ${e.message}`);
      setActionType("error");
    } finally {
      setDedupLoading(false);
    }
  };

  const handleMergeAll = async () => {
    setDedupMerging(true);
    try {
      const result = await admin.dedupMergeAll() as { message?: string };
      setActionMsg(result.message || "Fusion terminée !");
      setActionType("success");
      setDedupData(null);
      fetchData();
    } catch (e: any) {
      setActionMsg(`Erreur fusion : ${e.message}`);
      setActionType("error");
    } finally {
      setDedupMerging(false);
    }
  };

  const handleMergeGroup = async (group: any) => {
    const canonicalId = group.canonical_id;
    const dupIds = group.devices
      .filter((d: any) => !d.is_canonical)
      .map((d: any) => d.id);
    setMergingGroup(group.key);
    try {
      const result = await admin.dedupMergeGroup(canonicalId, dupIds) as { message?: string };
      setActionMsg(result.message || "Groupe fusionné !");
      setActionType("success");
      setDedupData((prev: any) => prev
        ? { ...prev, groups: prev.groups.filter((g: any) => g.key !== group.key),
            total_groups: prev.total_groups - 1,
            total_duplicates: prev.total_duplicates - dupIds.length }
        : null
      );
    } catch (e: any) {
      setActionMsg(`Erreur : ${e.message}`);
      setActionType("error");
    } finally {
      setMergingGroup(null);
    }
  };

  const toggleGroup = (key: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const handleTestEmail = async () => {
    setEmailTesting(true);
    try {
      const result = await admin.testEmail() as { message?: string };
      setActionMsg(result.message || "Email de test envoyé !");
      setActionType("success");
    } catch (e: any) {
      setActionMsg(`Email : ${e.message}`);
      setActionType("error");
    } finally {
      setEmailTesting(false);
    }
  };

  const [sendingDigest, setSendingDigest] = useState(false);
  const handleSendDigest = async () => {
    setSendingDigest(true);
    try {
      const result = await admin.sendDigest() as {
        sent?: number; failed?: number; users_targeted?: number; message?: string;
      };
      setActionMsg(result.message || `Digest envoyé à ${result.sent ?? 0} utilisateur(s).`);
      setActionType((result.failed ?? 0) > 0 && (result.sent ?? 0) === 0 ? "error" : "success");
    } catch (e: any) {
      setActionMsg(`Digest : ${e.message}`);
      setActionType("error");
    } finally {
      setSendingDigest(false);
    }
  };

  const [sendingReminders, setSendingReminders] = useState(false);
  const handleSendDeadlineReminders = async () => {
    setSendingReminders(true);
    try {
      const result = await admin.sendDeadlineReminders(7) as {
        sent?: number; failed?: number; users_targeted?: number; reminders_sent?: number; message?: string;
      };
      setActionMsg(result.message || `Rappels J-7 envoyés (${result.reminders_sent ?? 0} rappel(s)).`);
      setActionType((result.failed ?? 0) > 0 && (result.sent ?? 0) === 0 ? "error" : "success");
    } catch (e: any) {
      setActionMsg(`Rappels : ${e.message}`);
      setActionType("error");
    } finally {
      setSendingReminders(false);
    }
  };

  return (
    <RoleGate
      allow={["admin"]}
      title="Administration réservée"
      message="Cette zone est réservée au profil super admin."
      backHref="/workspace"
    >
      <AppLayout>
      {/* En-tête */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Administration</h1>
          <p className="text-sm text-gray-500">Qualité des données et gestion des sources</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchData} disabled={loading}
            className="btn-secondary text-xs flex items-center gap-1.5">
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            Actualiser
          </button>
          <button onClick={handleFixExpired} className="btn-secondary text-xs flex items-center gap-1.5">
            <Clock className="w-3 h-3" /> Corriger expirés
          </button>
          <button onClick={handleCollectAll} className="btn-primary text-xs flex items-center gap-1.5">
            <Zap className="w-3 h-3" /> Collecte globale
          </button>
          <button onClick={handleEnrich} className="btn-secondary text-xs flex items-center gap-1.5">
            <Sparkles className="w-3 h-3" /> Enrichir fiches
          </button>
          <button onClick={handleBulkRewrite} disabled={rewriting} className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
            {rewriting ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
            {rewriting ? "Reformulation…" : "Reformuler IA (20)"}
          </button>
          <button onClick={handleSendDigest} disabled={sendingDigest} className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
            {sendingDigest ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Mail className="w-3 h-3" />}
            {sendingDigest ? "Envoi digest…" : "Digest hebdo"}
          </button>
          <button onClick={handleSendDeadlineReminders} disabled={sendingReminders} className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50">
            {sendingReminders ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
            {sendingReminders ? "Envoi rappels…" : "Rappels J-7"}
          </button>
        </div>
      </div>

      {/* Message d'action */}
      {actionMsg && (
        <div className={`mb-4 px-4 py-3 rounded-lg text-sm border flex items-center gap-2
          ${actionType === "success"
            ? "bg-green-50 text-green-700 border-green-200"
            : "bg-red-50 text-red-700 border-red-200"}`}>
          {actionType === "success"
            ? <CheckCircle className="w-4 h-4 flex-shrink-0" />
            : <XCircle className="w-4 h-4 flex-shrink-0" />}
          {actionMsg}
          <button onClick={() => setActionMsg("")} className="ml-auto text-xs opacity-60 hover:opacity-100">✕</button>
        </div>
      )}

      {/* Erreur */}
      {error && (
        <div className="mb-6 px-5 py-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3">
          <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-700">{error}</p>
            <button onClick={fetchData}
              className="mt-2 text-xs text-red-600 underline hover:no-underline">
              Réessayer
            </button>
          </div>
        </div>
      )}

      {/* Chargement */}
      {loading && !error && (
        <div className="flex items-center justify-center py-16 text-gray-400">
          <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Chargement du rapport qualité...
        </div>
      )}

      {/* Rapport qualité */}
      {!loading && quality && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
            {[
              { label: "Fiches incomplètes", value: quality.incomplete_devices, icon: AlertTriangle, color: "text-orange-500", bg: "bg-orange-50", border: "border-orange-100" },
              { label: "Expirés encore ouverts", value: quality.expired_still_open, icon: Clock, color: "text-red-500", bg: "bg-red-50", border: "border-red-100" },
              { label: "En attente validation", value: quality.pending_validation, icon: ShieldCheck, color: "text-yellow-600", bg: "bg-yellow-50", border: "border-yellow-100" },
              { label: "Faible confiance", value: quality.low_confidence, icon: AlertTriangle, color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-100" },
              { label: "Complétion moy.", value: `${quality.avg_completeness}%`, icon: CheckCircle, color: "text-green-600", bg: "bg-green-50", border: "border-green-100" },
              { label: "Confiance moy.", value: `${quality.avg_confidence}%`, icon: CheckCircle, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-100" },
            ].map(({ label, value, icon: Icon, color, bg, border }) => (
              <div key={label} className={`card p-4 text-center border ${border}`}>
                <div className={`w-9 h-9 rounded-full ${bg} flex items-center justify-center mx-auto mb-2`}>
                  <Icon className={`w-4 h-4 ${color}`} />
                </div>
                <div className="text-2xl font-bold text-gray-900">{value}</div>
                <div className="text-xs text-gray-400 leading-tight mt-0.5">{label}</div>
              </div>
            ))}
          </div>

          {/* Configuration Email */}
          {emailStatus && (
            <div className="card p-5 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-700 flex items-center gap-2">
                  <Mail className="w-4 h-4 text-blue-500" />
                  Configuration email
                </h2>
                <button
                  onClick={handleTestEmail}
                  disabled={emailTesting || !emailStatus.reachable}
                  className="btn-secondary text-xs flex items-center gap-1.5 disabled:opacity-50"
                  title={!emailStatus.reachable ? "SMTP non joignable" : "Envoyer un email de test"}
                >
                  {emailTesting
                    ? <RefreshCw className="w-3 h-3 animate-spin" />
                    : <Send className="w-3 h-3" />}
                  {emailTesting ? "Envoi..." : "Envoyer un test"}
                </button>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                  emailStatus.reachable
                    ? "bg-green-100 text-green-700"
                    : emailStatus.configured
                    ? "bg-red-100 text-red-700"
                    : "bg-gray-100 text-gray-500"
                }`}>
                  {emailStatus.reachable
                    ? <><CheckCircle className="w-3 h-3" /> SMTP connecté</>
                    : emailStatus.configured
                    ? <><XCircle className="w-3 h-3" /> SMTP inaccessible</>
                    : <><AlertTriangle className="w-3 h-3" /> Non configuré</>}
                </span>
                {emailStatus.host && (
                  <span className="text-gray-500 font-mono text-xs">
                    {emailStatus.host}:{emailStatus.port}
                    {emailStatus.auth_required ? " (avec auth)" : " (sans auth — dev)"}
                  </span>
                )}
                {!emailStatus.reachable && (
                  <span className="text-xs text-gray-400">{emailStatus.message}</span>
                )}
              </div>
              {!emailStatus.configured && (
                <p className="mt-2 text-xs text-gray-400">
                  Configurez <code className="bg-gray-100 px-1 rounded">SMTP_HOST</code> dans le fichier <code className="bg-gray-100 px-1 rounded">.env</code> pour activer les notifications email.
                </p>
              )}
            </div>
          )}

          {/* Déduplication */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold text-gray-700 flex items-center gap-2">
                <Copy className="w-4 h-4 text-purple-500" />
                Doublons
                {dedupData && (
                  <span className="text-sm font-normal text-gray-400">
                    ({dedupData.total_duplicates} doublon{dedupData.total_duplicates > 1 ? "s" : ""} dans {dedupData.total_groups} groupe{dedupData.total_groups > 1 ? "s" : ""})
                  </span>
                )}
              </h2>
              <div className="flex gap-2">
                <button
                  onClick={handleDetectDuplicates}
                  disabled={dedupLoading}
                  className="btn-secondary text-xs flex items-center gap-1.5"
                >
                  {dedupLoading
                    ? <RefreshCw className="w-3 h-3 animate-spin" />
                    : <Copy className="w-3 h-3" />}
                  {dedupLoading ? "Analyse..." : "Détecter"}
                </button>
                {dedupData && dedupData.total_duplicates > 0 && (
                  <button
                    onClick={handleMergeAll}
                    disabled={dedupMerging}
                    className="btn-primary text-xs flex items-center gap-1.5 bg-purple-600 hover:bg-purple-700"
                  >
                    {dedupMerging
                      ? <RefreshCw className="w-3 h-3 animate-spin" />
                      : <Trash2 className="w-3 h-3" />}
                    {dedupMerging ? "Fusion..." : `Fusionner tout (${dedupData.total_duplicates})`}
                  </button>
                )}
              </div>
            </div>

            {!dedupData ? (
              <div className="text-center py-10 bg-white rounded-xl border border-gray-100 text-gray-400">
                <Copy className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Cliquez sur "Détecter" pour analyser les doublons</p>
              </div>
            ) : dedupData.total_groups === 0 ? (
              <div className="text-center py-10 bg-white rounded-xl border border-gray-100 text-gray-400">
                <CheckCircle className="w-8 h-8 mx-auto mb-2 text-green-400" />
                <p className="font-medium text-gray-600">Aucun doublon détecté !</p>
                <p className="text-sm">Toutes les fiches sont uniques.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {dedupData.groups.map((group: any) => (
                  <div key={group.key} className="bg-white rounded-xl border border-purple-100 overflow-hidden">
                    {/* En-tête du groupe */}
                    <div
                      className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-purple-50 transition-colors"
                      onClick={() => toggleGroup(group.key)}
                    >
                      <div className="flex items-center gap-3">
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-purple-100 text-purple-700 text-xs font-bold">
                          {group.count}
                        </span>
                        <div>
                          <p className="text-sm font-medium text-gray-800 line-clamp-1">
                            {group.devices[0]?.title || "—"}
                          </p>
                          <p className="text-xs text-gray-400">
                            {group.devices[0]?.organism || "—"} · {group.devices[0]?.country || "—"}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleMergeGroup(group); }}
                          disabled={mergingGroup === group.key}
                          className="text-xs px-2.5 py-1 rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 flex items-center gap-1"
                        >
                          {mergingGroup === group.key
                            ? <RefreshCw className="w-3 h-3 animate-spin" />
                            : <Trash2 className="w-3 h-3" />}
                          Fusionner
                        </button>
                        {expandedGroups.has(group.key)
                          ? <ChevronUp className="w-4 h-4 text-gray-400" />
                          : <ChevronDown className="w-4 h-4 text-gray-400" />}
                      </div>
                    </div>

                    {/* Détail des fiches */}
                    {expandedGroups.has(group.key) && (
                      <div className="border-t border-purple-50 divide-y divide-gray-50">
                        {group.devices.map((device: any) => (
                          <div key={device.id} className={`px-4 py-3 flex items-start gap-3 text-sm
                            ${device.is_canonical ? "bg-green-50" : "bg-white"}`}>
                            <div className="mt-0.5">
                              {device.is_canonical
                                ? <Star className="w-4 h-4 text-green-500" />
                                : <Copy className="w-4 h-4 text-gray-300" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-gray-800 truncate">{device.title}</p>
                              <p className="text-xs text-gray-500 truncate">{device.source_url || "—"}</p>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              <span className={`px-2 py-0.5 rounded-full text-xs font-medium
                                ${device.is_canonical ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                                {device.is_canonical ? "À conserver" : "Doublon"}
                              </span>
                              <span className="text-xs text-gray-400">{device.completeness_score}%</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Opportunités en attente de validation */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold text-gray-700 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-yellow-500" />
                En attente de validation
                {pending && (
                  <span className="text-sm font-normal text-gray-400">({pending.total})</span>
                )}
              </h2>
            </div>

            {!pending || pending?.items?.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-xl border border-gray-100 text-gray-400">
                <CheckCircle className="w-10 h-10 mx-auto mb-2 text-green-400" />
                <p className="font-medium text-gray-600">Tout est validé !</p>
                <p className="text-sm">Aucune opportunité en attente de validation</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {pending?.items?.map((device: any) => (
                  <DeviceCard key={device.id} device={device} />
                ))}
              </div>
            )}
          </div>
        </>
      )}
      </AppLayout>
    </RoleGate>
  );
}
