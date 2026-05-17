"use client";
import Link from "next/link";
import { FileQuestion, Home, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-6 text-center">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-primary-50">
        <FileQuestion className="h-10 w-10 text-primary-500" />
      </div>

      <h1 className="text-6xl font-bold text-slate-950">404</h1>
      <p className="mt-3 text-xl font-semibold text-slate-700">Page introuvable</p>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
        La page que vous cherchez n'existe pas ou a été déplacée.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-2xl bg-primary-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700"
        >
          <Home className="h-4 w-4" />
          Retour à l'accueil
        </Link>
        <button
          onClick={() => window.history.back()}
          className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
        >
          <ArrowLeft className="h-4 w-4" />
          Page précédente
        </button>
      </div>
    </main>
  );
}
