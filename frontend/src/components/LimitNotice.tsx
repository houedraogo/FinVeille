"use client";

import Link from "next/link";
import { Lock, Sparkles } from "lucide-react";

interface LimitNoticeProps {
  title?: string;
  message?: string;
  compact?: boolean;
}

export default function LimitNotice({
  title = "Limite atteinte",
  message = "Passez a une offre superieure pour continuer a utiliser cette fonctionnalite.",
  compact = false,
}: LimitNoticeProps) {
  return (
    <div className={`rounded-2xl border border-amber-200 bg-amber-50 ${compact ? "p-3" : "p-5"}`}>
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700">
          <Lock className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-amber-950">{title}</p>
          <p className="mt-1 text-sm leading-6 text-amber-800">{message}</p>
          <Link href="/billing" className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-amber-900 hover:text-amber-700">
            <Sparkles className="h-3.5 w-3.5" />
            Voir les plans
          </Link>
        </div>
      </div>
    </div>
  );
}
