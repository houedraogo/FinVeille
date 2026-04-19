"use client";

import { useState } from "react";
import { Send, UsersRound } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { organizations } from "@/lib/api";

export default function TeamSettingsPage() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [feedback, setFeedback] = useState<string | null>(null);

  const invite = async () => {
    if (!email) return setFeedback("Indique un email.");
    try {
      await organizations.invite({ email, role });
      setFeedback("Invitation envoyee ou enregistree.");
      setEmail("");
    } catch (error: any) {
      setFeedback(error.message || "Impossible d'envoyer l'invitation.");
    }
  };

  return (
    <AppLayout>
      <div className="mb-6">
        <p className="text-sm font-medium text-primary-600">Parametres</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-950">Equipe</h1>
        <p className="mt-2 text-sm text-slate-500">Invite des membres dans ton organisation cliente.</p>
      </div>

      <section className="max-w-2xl rounded-[28px] border border-slate-200 bg-white p-6">
        <UsersRound className="mb-3 h-6 w-6 text-primary-600" />
        <h2 className="text-lg font-semibold text-slate-950">Inviter un membre</h2>
        {feedback && <p className="mt-3 rounded-2xl bg-primary-50 px-4 py-3 text-sm text-primary-800">{feedback}</p>}
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-[1fr_160px]">
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@organisation.com" className="input" />
          <select value={role} onChange={(e) => setRole(e.target.value)} className="input">
            <option value="member">Membre</option>
            <option value="org_admin">Admin org</option>
            <option value="viewer">Lecture seule</option>
          </select>
        </div>
        <button type="button" onClick={invite} className="btn-primary mt-4 text-xs">
          <Send className="h-3.5 w-3.5" />
          Envoyer l'invitation
        </button>
      </section>
    </AppLayout>
  );
}
