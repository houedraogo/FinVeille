"use client";
import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-6 text-center">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-red-50">
        <AlertTriangle className="h-10 w-10 text-red-500" />
      </div>

      <h1 className="text-6xl font-bold text-slate-950">500</h1>
      <p className="mt-3 text-xl font-semibold text-slate-700">Une erreur est survenue</p>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
        Quelque chose s'est mal passé de notre côté. Notre équipe a été notifiée.
      </p>

      {error?.digest && (
        <p className="mt-2 font-mono text-xs text-slate-400">Référence : {error.digest}</p>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <button
          onClick={reset}
          className="inline-flex items-center gap-2 rounded-2xl bg-primary-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700"
        >
          <RefreshCw className="h-4 w-4" />
          Réessayer
        </button>
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
        >
          <Home className="h-4 w-4" />
          Retour à l'accueil
        </Link>
      </div>
    </main>
  );
}
