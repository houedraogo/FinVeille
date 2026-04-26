"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Image from "next/image";
import { Menu } from "lucide-react";
import Sidebar from "./Sidebar";
import { auth, relevance } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname();
  const [ready,       setReady]       = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("kafundo_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    // ── Chemin rapide : onboarding déjà validé dans ce navigateur ─────────
    // On vérifie que le token est encore accepté ET que le profil existe.
    const onboardingDone = localStorage.getItem("kafundo_onboarding_completed");
    if (onboardingDone) {
      auth.me()
        .then(async (user: any) => {
          const userRole = user.role === "admin" || user.platform_role === "super_admin"
            ? "admin"
            : "user";
          localStorage.setItem("kafundo_user_role", userRole);

          // Les admins n'ont pas besoin de profil
          if (userRole === "admin") {
            if (pathname === "/") {
              router.replace("/admin");
            } else {
              setReady(true);
            }
            return;
          }

          // Pour les utilisateurs normaux : vérifier que le profil existe en base
          // (le flag localStorage peut être présent sans profil réel si l'onboarding a échoué)
          try {
            const profile = await relevance.getProfile();
            const hasProfile =
              profile &&
              (
                profile.organization_type ||
                profile.countries?.length > 0 ||
                profile.sectors?.length > 0
              );

            if (!hasProfile) {
              // Profil absent → forcer l'onboarding
              localStorage.removeItem("kafundo_onboarding_completed");
              router.replace("/onboarding");
              return;
            }
          } catch {
            // Erreur réseau → laisser passer (ne pas bloquer l'utilisateur)
          }

          setReady(true);
        })
        .catch(() => {
          // Token invalide ou compte supprimé → tout vider et retour login
          ["kafundo_token", "kafundo_onboarding_completed",
           "kafundo_user_role", "kafundo_financing_scope"].forEach(
            (k) => localStorage.removeItem(k)
          );
          router.replace("/login");
        });
      return;
    }

    // ── Chemin API : premier chargement ou nouvel appareil ─────────────────
    auth.me()
      .then(async (user: any) => {
        // 1. L'admin (et super_admin) n'a jamais besoin de faire l'onboarding
        if (user.role === "admin" || user.platform_role === "super_admin") {
          localStorage.setItem("kafundo_onboarding_completed", "1");
          localStorage.setItem("kafundo_user_role", "admin");
          // Rediriger l'admin vers son cockpit s'il arrive sur /
          if (pathname === "/") {
            router.replace("/admin");
          } else {
            setReady(true);
          }
          return;
        }
        // Utilisateur normal
        localStorage.setItem("kafundo_user_role", "user");

        // 2. Utilisateur ayant déjà complété l'onboarding sur un autre appareil
        //    → son profil existe en base de données
        try {
          const profile = await relevance.getProfile();
          const hasProfile =
            profile &&
            (
              profile.organization_type ||
              profile.countries?.length > 0 ||
              profile.sectors?.length > 0
            );

          if (hasProfile) {
            localStorage.setItem("kafundo_onboarding_completed", "1");

            // Restaurer le scope de financement s'il n'est pas en localStorage
            if (!localStorage.getItem("kafundo_financing_scope") && profile.target_funding_types?.length > 0) {
              const hasPrivate = profile.target_funding_types.includes("investissement");
              const hasPublic  = profile.target_funding_types.some((t: string) => t !== "investissement");
              if (hasPrivate && !hasPublic) {
                localStorage.setItem("kafundo_financing_scope", "private");
              } else {
                localStorage.setItem("kafundo_financing_scope", "public");
              }
            }

            setReady(true);
          } else {
            // 3. Nouvel utilisateur sans profil → onboarding obligatoire
            router.replace("/onboarding");
          }
        } catch {
          // Impossible de charger le profil → onboarding par sécurité
          router.replace("/onboarding");
        }
      })
      .catch(() => {
        // Token invalide ou expiré → retour au login
        localStorage.removeItem("kafundo_token");
        router.replace("/login");
      });
  }, [router]);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-500">Chargement...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Overlay mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Contenu principal */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Barre mobile */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-primary-900 text-white sticky top-0 z-10">
          <button onClick={() => setSidebarOpen(true)} className="p-1">
            <Menu className="w-6 h-6" />
          </button>
          <span className="inline-flex items-center gap-2 font-bold text-base">
            <Image src="/brand/kafundo-picto.png" alt="Kafundo" width={28} height={28} className="h-7 w-7 rounded-lg object-cover" />
            Kafundo
          </span>
        </header>

        <main className="flex-1 overflow-auto bg-gray-50">
          <div className="max-w-7xl mx-auto px-4 md:px-6 py-4 md:py-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
