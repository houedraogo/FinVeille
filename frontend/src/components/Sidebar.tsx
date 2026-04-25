"use client";

import Link from "next/link";
import Image from "next/image";
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
  Wand2,
  ReceiptText,
  LineChart,
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
        label: "Opportunités publiques",
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
        href: "/onboarding",
        label: "Configurer ma veille",
        icon: Wand2,
        activeFn: (pathname: string) => pathname === "/onboarding",
      },
      {
        href: "/recommendations",
        label: "Opportunités recommandées",
        icon: Sparkles,
        activeFn: (pathname: string) => pathname === "/recommendations",
      },
      {
        href: "/match",
        label: "Analyse de document",
        icon: ChevronRight,
        activeFn: (pathname: string) => pathname === "/match",
      },
      { href: "/alerts", label: "Ma veille", icon: Bell },
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

const ADMIN_NAV_GROUPS = [
  {
    label: "Pilotage plateforme",
    items: [
      {
        href: "/admin/workspace",
        label: "Cockpit SaaS",
        icon: ShieldCheck,
        activeFn: (pathname: string) => pathname === "/admin/workspace",
      },
      {
        href: "/admin/clients",
        label: "Clients",
        icon: UsersRound,
        activeFn: (pathname: string) => pathname.startsWith("/admin/clients"),
      },
      {
        href: "/admin/billing",
        label: "Abonnements",
        icon: ReceiptText,
        activeFn: (pathname: string) => pathname === "/admin/billing",
      },
      {
        href: "/admin/data-quality",
        label: "Qualite donnees",
        icon: LineChart,
        activeFn: (pathname: string) => pathname === "/admin/data-quality" || pathname === "/admin",
      },
      {
        href: "/sources",
        label: "Sources publiques",
        icon: Database,
        activeFn: (pathname: string) => pathname === "/sources",
      },
      {
        href: "/sources/private",
        label: "Sources privees",
        icon: Database,
        activeFn: (pathname: string) => pathname === "/sources/private",
      },
    ],
  },
  {
    label: "Catalogue",
    items: [
      {
        href: "/devices",
        label: "Opportunités publiques",
        icon: Landmark,
        activeFn: (pathname: string) => pathname === "/devices",
      },
      {
        href: "/devices/private",
        label: "Fonds & investisseurs",
        icon: TrendingUp,
        activeFn: (pathname: string) => pathname === "/devices/private",
      },
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
      const raw = localStorage.getItem("kafundo_user");
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
    () => {
      const groups = canAccessAdmin(role) ? ADMIN_NAV_GROUPS : NAV_GROUPS;
      return groups.map((group) => ({
        ...group,
        items: group.items.filter((item) => {
          if (item.href.startsWith("/sources")) return canManageSources(role);
          if (item.href.startsWith("/admin")) return canAccessAdmin(role);
          return true;
        }),
      })).filter((group) => group.items.length > 0);
    },
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
      <div className="px-4 py-4 border-b border-primary-700 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5 min-w-0">
          <Image
            src="/brand/kafundo-picto.png"
            alt="Kafundo"
            width={40}
            height={40}
            className="h-10 w-10 rounded-xl object-cover shrink-0"
            priority
          />
          <div className="min-w-0">
            <span className="block text-base font-bold tracking-tight text-white leading-tight">Kafundo</span>
            <span className="block text-[10px] text-primary-300 leading-tight truncate">Trouve tes financements</span>
          </div>
        </Link>
        <button onClick={onClose} className="md:hidden p-1 text-primary-400 hover:text-white shrink-0">
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
            localStorage.removeItem("kafundo_token");
            localStorage.removeItem("kafundo_user");
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
