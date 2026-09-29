import { useEffect, useState } from "react";
import { fallbackMe, getCurrentUser } from "../lib/api";
import type { MeResponse } from "../types/me";

export function useMe(language = "auto") {
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getCurrentUser(language)
      .then((profile) => {
        if (!cancelled) setMe(profile);
      })
      .catch(() => {
        if (!cancelled) setMe(fallbackMe());
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [language]);

  return { me, loading };
}
