"use client";

import { useEffect, useRef, useState } from "react";
import { Send, UsersRound } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { organizations } from "@/lib/api";
import { clearTenantWorkspaceData } from "@/lib/sensitive-storage";

export default function TeamSettingsPage() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [invitationFeedback, setInvitationFeedback] = useState<string | null>(null);
  const accepting = useRef(false);

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("invitation_token");
    if (!token || !localStorage.getItem("kafundo_token") || accepting.current) return;
    accepting.current = true;
    setInvitationFeedback("Acceptation de l'invitation en cours…");
    void (async () => {
      try {
        const membership = await organizations.acceptInvitation(token);
        await organizations.select(membership.organization_id);
        clearTenantWorkspaceData();
        const user = JSON.parse(localStorage.getItem("kafundo_user") || "{}");
        localStorage.setItem("kafundo_user", JSON.stringify({
          ...user, default_organization_id: membership.organization_id,
        }));
        window.location.replace("/workspace");
      } catch (error: any) {
        setInvitationFeedback(error.message || "Invitation invalide ou expirée.");
      }
    })();
  }, []);

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
        <p className="text-sm font-medium text-primary-600">Paramètres</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-950">Équipe</h1>
        <p className="mt-2 text-sm text-slate-500">Invite des membres dans ton organisation cliente.</p>
      </div>

      <section className="max-w-2xl rounded-[28px] border border-slate-200 bg-white p-6">
        {invitationFeedback && <p role="status" className="mb-4 rounded-2xl bg-primary-50 px-4 py-3 text-sm text-primary-800">{invitationFeedback}</p>}
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
