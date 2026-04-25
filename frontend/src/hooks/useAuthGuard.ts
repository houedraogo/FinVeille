"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export function useAuthGuard() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("kafundo_token");
    if (!token) {
      router.replace("/login");
    } else {
      // Display current user email in sidebar if available
      try {
        const user = JSON.parse(localStorage.getItem("kafundo_user") || "{}");
        const el = document.getElementById("sidebar-user-email");
        if (el && user.email) el.textContent = user.email;
      } catch {}
      setReady(true);
    }
  }, [router]);

  return ready;
}
