"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Eye, EyeOff, CheckCircle2, AlertCircle } from "lucide-react";
import { security } from "@/lib/api";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const t = new URLSearchParams(window.location.search).get("token") || "";
      setToken(t);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }
    if (password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères.");
      return;
    }
    if (!token) {
      setError("Lien invalide ou expiré. Demandez un nouveau lien.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await security.resetPassword(token, password);
      setSuccess(true);
    } catch (e: any) {
      setError(e.message || "Lien invalide ou expiré. Demandez un nouveau lien.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-900 to-primary-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm overflow-hidden">
        <div className="px-8 pt-8 pb-4 text-center">
          <Image
            src="/brand/kafundo-logo-white-bg.png"
            alt="Kafundo"
            width={400}
            height={140}
            className="mx-auto h-auto w-full max-w-[200px] object-contain"
            priority
          />
        </div>

        <div className="px-8 py-6">
          <h1 className="text-lg font-semibold text-slate-900 mb-1">Nouveau mot de passe</h1>
          <p className="text-sm text-slate-500 mb-5">Choisissez un mot de passe sécurisé pour votre compte.</p>

          {success ? (
            <div className="space-y-4">
              <div className="flex items-start gap-3 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                <p className="text-sm text-emerald-800">
                  Mot de passe mis à jour avec succès. Vous pouvez maintenant vous connecter.
                </p>
              </div>
              <button
                onClick={() => router.push("/login")}
                className="btn-primary w-full justify-center"
              >
                Se connecter
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">Nouveau mot de passe <span className="text-gray-400 font-normal">(8 car. min.)</span></label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="input pr-10"
                    placeholder="••••••••"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    minLength={8}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="label">Confirmer le mot de passe</label>
                <input
                  type={showPassword ? "text" : "password"}
                  className="input"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  required
                />
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-100 px-3 py-2">
                  <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
                {loading ? "Mise à jour…" : "Définir le mot de passe"}
              </button>

              <p className="text-center">
                <button
                  type="button"
                  onClick={() => router.push("/login")}
                  className="text-sm text-slate-400 hover:text-slate-600 underline"
                >
                  Retour à la connexion
                </button>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
