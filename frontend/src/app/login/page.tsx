"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { auth, security, relevance } from "@/lib/api";
import { isStoredAdmin } from "@/lib/auth";
import { Chrome, Eye, EyeOff, CheckCircle2 } from "lucide-react";

declare global {
  interface Window {
    google?: {
      accounts?: {
        id?: {
          initialize: (options: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: {
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "large" | "medium" | "small";
              shape?: "rectangular" | "pill";
              text?: "signin_with" | "signup_with" | "continue_with";
              width?: string | number;
            }
          ) => void;
        };
      };
    };
  }
}

export default function LoginPage() {
  const router = useRouter();
  const googleButtonRef = useRef<HTMLDivElement | null>(null);
  const manualLoginModeRef = useRef(false);

  const [mode, setMode] = useState<"login" | "register" | "forgot">("login");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [disableGoogleAuth, setDisableGoogleAuth] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);

  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

  // Lire ?plan= et ?mode= côté client (évite useSearchParams et son Suspense requis au build)
  const getPlanParam = () => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("plan");
  };

  // Ouvrir directement l'onglet inscription si ?mode=register dans l'URL
  useEffect(() => {
    if (typeof window === "undefined") return;
    const m = new URLSearchParams(window.location.search).get("mode");
    if (m === "register") setMode("register");
  }, []);

  const finishAuth = async (result: { access_token: string; user: unknown }) => {
    localStorage.setItem("kafundo_token", result.access_token);
    if (result.user) localStorage.setItem("kafundo_user", JSON.stringify(result.user));
    const user = (result.user || {}) as any;
    const isAdmin = isStoredAdmin(user);
    if (isAdmin) {
      localStorage.setItem("kafundo_onboarding_completed", "1");
      localStorage.setItem("kafundo_user_role", "admin");
    }
    const planParam = getPlanParam();
    if (planParam && planParam !== "free") {
      router.push(`/billing?plan=${planParam}`);
      return;
    }
    if (isAdmin) {
      router.push("/admin");
      return;
    }
    // Vérifier si le profil existe en base (cas d'un autre appareil ou cache vidé)
    // pour ne pas envoyer à l'onboarding un utilisateur qui a déjà complété son profil.
    try {
      const profile = await relevance.getProfile();
      const hasProfile = profile && (
        profile.organization_type ||
        profile.countries?.length > 0 ||
        profile.sectors?.length > 0
      );
      if (hasProfile) {
        localStorage.setItem("kafundo_onboarding_completed", "1");
        router.push("/");
        return;
      }
    } catch {
      // Erreur réseau → se fier au localStorage
    }
    const hasOnboarding = localStorage.getItem("kafundo_onboarding_completed") === "1";
    router.push(hasOnboarding ? "/" : "/onboarding");
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    manualLoginModeRef.current = true;
    setDisableGoogleAuth(true);
    setLoading(true);
    setError("");
    try {
      const result = await auth.login(email, password);
      finishAuth(result);
    } catch (e: any) {
      setError(e.message || "Identifiants incorrects");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas");
      return;
    }
    if (password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await auth.register(email, password, fullName);
      finishAuth(result);
    } catch (e: any) {
      setError(e.message || "Erreur lors de la création du compte");
    } finally {
      setLoading(false);
    }
  };

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) { setError("Entrez votre adresse email."); return; }
    setLoading(true);
    setError("");
    try {
      await security.forgotPassword(email);
      setForgotSent(true);
    } catch {
      setForgotSent(true); // toujours afficher le succès (sécurité)
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (newMode: "login" | "register" | "forgot") => {
    setMode(newMode);
    setError("");
    setPassword("");
    setConfirmPassword("");
    setForgotSent(false);
  };

  useEffect(() => {
    if (!googleClientId || !googleButtonRef.current || disableGoogleAuth) return;

    const initializeGoogle = () => {
      if (!window.google?.accounts?.id || !googleButtonRef.current) return;
      googleButtonRef.current.innerHTML = "";
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: async ({ credential }) => {
          if (manualLoginModeRef.current) return;
          setGoogleLoading(true);
          setError("");
          try {
            const result = await auth.googleLogin(credential);
            finishAuth(result);
          } catch (e: any) {
            setError(e.message || "Impossible de se connecter avec Google.");
          } finally {
            setGoogleLoading(false);
          }
        },
      });
      window.google.accounts.id.renderButton(googleButtonRef.current, {
        theme: "outline",
        size: "large",
        shape: "pill",
        text: mode === "register" ? "signup_with" : "continue_with",
        width: 320,
      });
    };

    if (window.google?.accounts?.id) {
      initializeGoogle();
      return;
    }

    const existingScript = document.querySelector<HTMLScriptElement>('script[data-google-identity="true"]');
    if (existingScript) {
      existingScript.addEventListener("load", initializeGoogle, { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.dataset.googleIdentity = "true";
    script.addEventListener("load", initializeGoogle, { once: true });
    document.head.appendChild(script);
  }, [googleClientId, router, disableGoogleAuth, mode]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-900 to-primary-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm overflow-hidden">

        {/* Logo */}
        <div className="px-8 pt-8 pb-4 text-center">
          <Image
            src="/brand/kafundo-logo-white-bg.png"
            alt="Kafundo"
            width={400}
            height={140}
            className="mx-auto h-auto w-full max-w-[260px] object-contain"
            priority
          />
        </div>

        {/* Tabs Connexion / Inscription */}
        {mode !== "forgot" && (
          <div className="flex border-b border-gray-100 mx-6">
            <button
              onClick={() => switchMode("login")}
              className={`flex-1 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                mode === "login"
                  ? "border-primary-600 text-primary-700"
                  : "border-transparent text-gray-400 hover:text-gray-600"
              }`}
            >
              Se connecter
            </button>
            <button
              onClick={() => switchMode("register")}
              className={`flex-1 py-2.5 text-sm font-medium transition-colors border-b-2 ${
                mode === "register"
                  ? "border-primary-600 text-primary-700"
                  : "border-transparent text-gray-400 hover:text-gray-600"
              }`}
            >
              S'inscrire
            </button>
          </div>
        )}

        <div className="px-8 py-6 space-y-5">
          {/* Google OAuth — masqué en mode "oublié" */}
          {mode !== "forgot" && (
            <>
              {googleClientId ? (
                <div className="flex flex-col items-center gap-2">
                  <div ref={googleButtonRef} className="min-h-[44px] w-full flex justify-center" />
                  {googleLoading && <p className="text-xs text-gray-400">Connexion Google en cours...</p>}
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                  <div className="flex items-center gap-2 font-medium text-slate-600">
                    <Chrome className="h-4 w-4" />
                    Google non configuré
                  </div>
                </div>
              )}
              <div className="flex items-center gap-3 text-xs text-gray-300">
                <div className="h-px flex-1 bg-gray-100" />
                <span className="uppercase tracking-widest">ou</span>
                <div className="h-px flex-1 bg-gray-100" />
              </div>
            </>
          )}

          {/* ── FORMULAIRE CONNEXION ── */}
          {mode === "login" && (
            <form onSubmit={handleLogin} className="space-y-3">
              <div>
                <label className="label">Email</label>
                <input
                  type="email" className="input" placeholder="vous@exemple.com"
                  value={email}
                  onChange={e => {
                    manualLoginModeRef.current = true;
                    setDisableGoogleAuth(true);
                    setEmail(e.target.value);
                  }}
                  required
                />
              </div>
              <div>
                <label className="label">Mot de passe</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    className="input pr-10"
                    placeholder="••••••••"
                    value={password}
                    onChange={e => {
                      manualLoginModeRef.current = true;
                      setDisableGoogleAuth(true);
                      setPassword(e.target.value);
                    }}
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
              {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
              <button type="submit" disabled={loading} className="btn-primary w-full justify-center mt-1">
                {loading ? "Connexion…" : "Se connecter"}
              </button>
              <p className="text-center">
                <button
                  type="button"
                  onClick={() => switchMode("forgot")}
                  className="text-xs text-slate-400 hover:text-primary-600 underline"
                >
                  Mot de passe oublié ?
                </button>
              </p>
            </form>
          )}

          {/* ── MOT DE PASSE OUBLIÉ ── */}
          {mode === "forgot" && (
            <div className="space-y-4">
              <div>
                <p className="text-sm font-semibold text-slate-800">Mot de passe oublié</p>
                <p className="text-xs text-slate-500 mt-1">
                  Entrez votre email. Si un compte existe, vous recevrez un lien valable 2 heures.
                </p>
              </div>
              {forgotSent ? (
                <div className="flex items-start gap-3 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                  <p className="text-sm text-emerald-800">
                    Si ce compte existe, un email de réinitialisation vient d'être envoyé. Vérifiez vos spams.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleForgot} className="space-y-3">
                  <div>
                    <label className="label">Adresse email</label>
                    <input
                      type="email"
                      className="input"
                      placeholder="vous@exemple.com"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      required
                    />
                  </div>
                  {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
                  <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
                    {loading ? "Envoi…" : "Envoyer le lien"}
                  </button>
                </form>
              )}
              <p className="text-center">
                <button
                  type="button"
                  onClick={() => switchMode("login")}
                  className="text-xs text-slate-400 hover:text-slate-600 underline"
                >
                  Retour à la connexion
                </button>
              </p>
            </div>
          )}

          {/* ── FORMULAIRE INSCRIPTION ── */}
          {mode === "register" && (
            <form onSubmit={handleRegister} className="space-y-3">
              <div>
                <label className="label">Nom complet</label>
                <input
                  type="text" className="input" placeholder="Marie Dupont"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="label">Email</label>
                <input
                  type="email" className="input" placeholder="vous@exemple.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="label">Mot de passe <span className="text-gray-400 font-normal">(8 caractères min.)</span></label>
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
              {error && <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
              <button type="submit" disabled={loading} className="btn-primary w-full justify-center mt-1">
                {loading ? "Création du compte…" : "Créer mon compte"}
              </button>
              <p className="text-xs text-center text-gray-400">
                En créant un compte, vous acceptez nos{" "}
                <a href="/legal/terms" className="underline hover:text-gray-600">CGU</a>{" "}
                et notre{" "}
                <a href="/legal/privacy" className="underline hover:text-gray-600">politique de confidentialité</a>.
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
