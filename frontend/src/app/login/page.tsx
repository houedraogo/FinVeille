"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import { auth } from "@/lib/api";
import { Chrome } from "lucide-react";

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
  const searchParams = useSearchParams();
  const planParam = searchParams.get("plan"); // ex: "pro", "team"
  const googleButtonRef = useRef<HTMLDivElement | null>(null);
  const manualLoginModeRef = useRef(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [disableGoogleAuth, setDisableGoogleAuth] = useState(false);
  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

  const finishAuth = (result: { access_token: string; user: unknown }) => {
    localStorage.setItem("kafundo_token", result.access_token);
    if (result.user) localStorage.setItem("kafundo_user", JSON.stringify(result.user));
    const user = (result.user || {}) as any;
    // Si un plan est demandé depuis WordPress, rediriger vers le billing pour déclencher le checkout
    if (planParam && planParam !== "free") {
      router.push(`/billing?plan=${planParam}`);
      return;
    }
    const hasOnboarding = localStorage.getItem("kafundo_onboarding_completed") === "1";
    router.push(hasOnboarding || user.platform_role === "super_admin" ? "/" : "/onboarding");
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

  useEffect(() => {
    if (!googleClientId || !googleButtonRef.current || disableGoogleAuth) return;

    const initializeGoogle = () => {
      if (!window.google?.accounts?.id || !googleButtonRef.current) return;

      googleButtonRef.current.innerHTML = "";
      window.google.accounts.id.initialize({
        client_id: googleClientId,
        callback: async ({ credential }) => {
          if (manualLoginModeRef.current) {
            return;
          }
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
        text: "continue_with",
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
  }, [googleClientId, router]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-900 to-primary-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-sm">
        <div className="text-center mb-8">
          <Image
            src="/brand/kafundo-logo-transparent.png"
            alt="Kafundo - Trouve et sécurise tes financements plus facilement"
            width={360}
            height={130}
            className="mx-auto mb-3 h-auto w-full max-w-[280px]"
            priority
          />
          <p className="text-sm text-gray-500">Trouve et sécurise tes financements plus facilement</p>
        </div>

        <div className="mb-5 space-y-3">
          {googleClientId ? (
            <div className="flex flex-col items-center gap-3">
              <div ref={googleButtonRef} className="min-h-[44px] w-full flex justify-center" />
              {googleLoading && <p className="text-xs text-gray-500">Connexion Google en cours...</p>}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
              <div className="flex items-center gap-2 font-medium text-slate-700">
                <Chrome className="h-4 w-4" />
                Connexion Google non configurée
              </div>
              <p className="mt-1 text-xs">
                Ajoute <span className="font-mono">NEXT_PUBLIC_GOOGLE_CLIENT_ID</span> côté front et{" "}
                <span className="font-mono">GOOGLE_CLIENT_ID</span> côté backend pour l’activer.
              </p>
            </div>
          )}
        </div>

        <div className="mb-5 flex items-center gap-3 text-xs uppercase tracking-[0.18em] text-gray-300">
          <div className="h-px flex-1 bg-gray-200" />
          <span>ou</span>
          <div className="h-px flex-1 bg-gray-200" />
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="label">Email</label>
            <input type="email" className="input" placeholder="admin@kafundo.com"
              value={email}
              onChange={e => {
                manualLoginModeRef.current = true;
                setDisableGoogleAuth(true);
                setEmail(e.target.value);
              }}
              required />
          </div>
          <div>
            <label className="label">Mot de passe</label>
            <input type="password" className="input"
              value={password}
              onChange={e => {
                manualLoginModeRef.current = true;
                setDisableGoogleAuth(true);
                setPassword(e.target.value);
              }}
              required />
          </div>
          {error && (
            <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</div>
          )}
          <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
            {loading ? "Connexion..." : "Se connecter"}
          </button>
        </form>
      </div>
    </div>
  );
}
