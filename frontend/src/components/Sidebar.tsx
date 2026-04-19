"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  LayoutDashboard,
  Database,
  Bell,
  Settings,
  LogOut,
  TrendingUp,
  Building2,
  Landmark,
  ChevronRight,
  Sparkles,
  X,
  FolderSearch,
  ShieldCheck,
  UserRound,
  CreditCard,
  KeyRound,
  UsersRound,
} from "lucide-react";
import clsx from "clsx";

import { canAccessAdmin, canManageSources, getCurrentRole, type AppRole } from "@/lib/auth";

const NAV_GROUPS = [
  {
    label: null,
    items: [{ href: "/", label: "Dashboard", icon: LayoutDashboard, exact: true }],
  },
  {
    label: "Financement Public",
    items: [
      {
        href: "/devices",
        label: "Dispositifs publics",
        icon: Landmark,
        activeFn: (pathname: string, _sp: URLSearchParams) => pathname === "/devices",
      },
      {
        href: "/sources",
        label: "Sources & Collecte",
        icon: Database,
        activeFn: (pathname: string) => pathname === "/sources",
      },
    ],
  },
  {
    label: "Financement Privé",
    items: [
      {
        href: "/devices/private",
        label: "Fonds & Investisseurs",
        icon: TrendingUp,
        activeFn: (pathname: string) => pathname === "/devices/private",
      },
      {
        href: "/sources/private",
        label: "Sources & Collecte",
        icon: Database,
        activeFn: (pathname: string) => pathname === "/sources/private",
      },
    ],
  },
  {
    label: "Outils",
    items: [
      {
        href: "/workspace",
        label: "Mon espace",
        icon: FolderSearch,
        activeFn: (pathname: string) => pathname === "/workspace",
      },
      {
        href: "/match",
        label: "Matching IA",
        icon: Sparkles,
        activeFn: (pathname: string) => pathname === "/match",
      },
      { href: "/alerts", label: "Mes alertes", icon: Bell },
      {
        href: "/profile",
        label: "Profil",
        icon: UserRound,
        activeFn: (pathname: string) => pathname === "/profile",
      },
      {
        href: "/billing",
        label: "Abonnement",
        icon: CreditCard,
        activeFn: (pathname: string) => pathname === "/billing",
      },
      {
        href: "/settings/security",
        label: "Securite",
        icon: KeyRound,
        activeFn: (pathname: string) => pathname === "/settings/security",
      },
      {
        href: "/settings/team",
        label: "Equipe",
        icon: UsersRound,
        activeFn: (pathname: string) => pathname === "/settings/team",
      },
      {
        href: "/admin/workspace",
        label: "Espace super admin",
        icon: ShieldCheck,
        activeFn: (pathname: string) => pathname === "/admin/workspace",
      },
      { href: "/admin", label: "Administration", icon: Settings },
    ],
  },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export default function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [userEmail, setUserEmail] = useState<string>("Connecté");
  const [role, setRole] = useState<AppRole>("reader");

  useEffect(() => {
    try {
      const raw = localStorage.getItem("finveille_user");
      if (raw) {
        const user = JSON.parse(raw);
        setUserEmail(user.email || user.name || "Connecté");
      }
    } catch {
      // ignore
    }
    setRole(getCurrentRole());
  }, []);

  const visibleGroups = useMemo(
    () =>
      NAV_GROUPS.map((group) => ({
        ...group,
        items: group.items.filter((item) => {
          if (item.href.startsWith("/sources")) return canManageSources(role);
          if (item.href.startsWith("/admin")) return canAccessAdmin(role);
          return true;
        }),
      })).filter((group) => group.items.length > 0),
    [role]
  );

  const isActive = (item: any) => {
    if (item.activeFn) return item.activeFn(pathname, searchParams);
    if (item.exact) return pathname === item.href;
    return pathname === item.href || pathname.startsWith(item.href + "/");
  };

  return (
    <aside
      className={clsx(
        "w-64 bg-primary-900 text-white flex flex-col min-h-screen shrink-0 z-30",
        "md:relative md:translate-x-0 md:flex",
        "fixed inset-y-0 left-0 transition-transform duration-200",
        isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
      )}
    >
      <div className="px-5 py-5 border-b border-primary-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="text-lg font-bold tracking-tight">FinVeille</span>
            <p className="text-xs text-primary-400 leading-none">France & Afrique</p>
          </div>
        </div>
        <button onClick={onClose} className="md:hidden p-1 text-primary-400 hover:text-white">
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-5 overflow-y-auto">
        {visibleGroups.map((group, gi) => (
          <div key={gi}>
            {group.label && (
              <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-primary-400">
                {group.label}
              </p>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const active = isActive(item);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onClose}
                    className={clsx(
                      "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group",
                      active
                        ? "bg-primary-700 text-white shadow-sm"
                        : "text-primary-300 hover:bg-primary-800 hover:text-white"
                    )}
                  >
                    <item.icon
                      className={clsx(
                        "w-4 h-4 flex-shrink-0 transition-colors",
                        active ? "text-primary-200" : "text-primary-400 group-hover:text-primary-200"
                      )}
                    />
                    <span className="flex-1">{item.label}</span>
                    {active && <ChevronRight className="w-3 h-3 text-primary-400" />}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-primary-700 space-y-1">
        <div className="px-3 py-2 text-xs text-primary-500 flex items-center gap-2">
          <Building2 className="w-3 h-3" />
          <span className="truncate">{userEmail}</span>
        </div>
        <button
          onClick={() => {
            localStorage.removeItem("finveille_token");
            localStorage.removeItem("finveille_user");
            window.location.href = "/login";
          }}
          className="flex items-center gap-3 px-3 py-2 w-full rounded-lg text-sm text-primary-300 hover:bg-primary-800 hover:text-white transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Déconnexion
        </button>
      </div>
    </aside>
  );
}
