"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Download, KeyRound, ShieldCheck, Trash2 } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { security } from "@/lib/api";

export default function SecuritySettingsPage() {
  const searchParams = useSearchParams();
  const resetToken = searchParams.get("reset_token") || "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  const requestReset = async () => {
    const rawUser = localStorage.getItem("finveille_user");
    const userEmail = email || (rawUser ? JSON.parse(rawUser).email : "");
    if (!userEmail) return setFeedback("Indique un email.");
    const response = await security.forgotPassword(userEmail);
    setFeedback(response.message || "Email envoye si le compte existe.");
  };

  const resetPassword = async () => {
    if (!resetToken || password.length < 8) return setFeedback("Token manquant ou mot de passe trop court.");
    const response = await security.resetPassword(resetToken, password);
    setFeedback(response.message || "Mot de passe mis a jour.");
  };

  const exportData = async () => {
    const response = await security.createDataExport();
    setFeedback(`Export RGPD prepare. Token : ${response.download_token}`);
  };

  const deleteAccount = async () => {
    if (!confirm("Confirmer la demande de suppression de compte ?")) return;
    const response = await security.requestDeletion(reason);
    setFeedback(`Demande enregistree. Suppression prevue : ${response.scheduled_for || "a planifier"}`);
  };

  return (
    <AppLayout>
      <div className="mb-6">
        <p className="text-sm font-medium text-primary-600">Parametres</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-950">Securite et donnees</h1>
        <p className="mt-2 text-sm text-slate-500">Mot de passe, export RGPD et demande de suppression.</p>
      </div>

      {feedback && <div className="mb-5 rounded-2xl border border-primary-100 bg-primary-50 px-4 py-3 text-sm text-primary-800">{feedback}</div>}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <section className="rounded-[28px] border border-slate-200 bg-white p-6">
          <KeyRound className="mb-3 h-6 w-6 text-primary-600" />
          <h2 className="text-lg font-semibold text-slate-950">Reset password</h2>
          <p className="mt-1 text-sm text-slate-500">Envoie un lien de reinitialisation sur ton email.</p>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@exemple.com" className="input mt-4" />
          <button type="button" onClick={requestReset} className="btn-primary mt-3 text-xs">Envoyer le lien</button>
        </section>

        <section className="rounded-[28px] border border-slate-200 bg-white p-6">
          <ShieldCheck className="mb-3 h-6 w-6 text-emerald-600" />
          <h2 className="text-lg font-semibold text-slate-950">Nouveau mot de passe</h2>
          <p className="mt-1 text-sm text-slate-500">Utilise cette zone apres ouverture d'un lien de reset.</p>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="8 caracteres minimum" className="input mt-4" />
          <button type="button" onClick={resetPassword} className="btn-secondary mt-3 text-xs">Mettre a jour</button>
        </section>

        <section className="rounded-[28px] border border-slate-200 bg-white p-6">
          <Download className="mb-3 h-6 w-6 text-blue-600" />
          <h2 className="text-lg font-semibold text-slate-950">Export RGPD</h2>
          <p className="mt-1 text-sm text-slate-500">Prepare un export des donnees rattachees a ton compte.</p>
          <button type="button" onClick={exportData} className="btn-secondary mt-4 text-xs">Generer mon export</button>
        </section>

        <section className="rounded-[28px] border border-red-100 bg-red-50/70 p-6 xl:col-span-3">
          <Trash2 className="mb-3 h-6 w-6 text-red-600" />
          <h2 className="text-lg font-semibold text-red-950">Suppression du compte</h2>
          <p className="mt-1 text-sm text-red-700">Cree une demande de suppression avec delai de securite.</p>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Raison facultative" className="input mt-4 min-h-[100px]" />
          <button type="button" onClick={deleteAccount} className="btn-secondary mt-3 border-red-200 text-xs text-red-700">Demander la suppression</button>
        </section>
      </div>
    </AppLayout>
  );
}
