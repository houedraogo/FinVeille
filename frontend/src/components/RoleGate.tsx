"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { ShieldAlert } from "lucide-react";

import AppLayout from "@/components/AppLayout";
import { getCurrentRole, type AppRole } from "@/lib/auth";

export default function RoleGate({
  allow,
  title = "Accès réservé",
  message = "Cette fonctionnalité n'est pas disponible pour votre profil utilisateur.",
  backHref = "/workspace",
  children,
}: {
  allow: AppRole[];
  title?: string;
  message?: string;
  backHref?: string;
  children: ReactNode;
}) {
  const [role, setRole] = useState<AppRole | null>(null);

  useEffect(() => {
    setRole(getCurrentRole());
  }, []);

  if (!role) {
    return (
      <AppLayout>
        <div className="flex min-h-[40vh] items-center justify-center text-sm text-slate-400">
          Vérification des droits...
        </div>
      </AppLayout>
    );
  }

  if (!allow.includes(role)) {
    return (
      <AppLayout>
        <div className="mx-auto mt-10 max-w-xl rounded-[28px] border border-slate-200 bg-white p-8 text-center shadow-[0_14px_40px_-28px_rgba(15,23,42,0.25)]">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-amber-600">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <h1 className="mt-4 text-xl font-semibold text-slate-950">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">{message}</p>
          <Link href={backHref} className="btn-secondary mt-5 inline-flex text-xs">
            Retour
          </Link>
        </div>
      </AppLayout>
    );
  }

  return <>{children}</>;
}
