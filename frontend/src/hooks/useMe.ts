import { useQuery } from "@tanstack/react-query";
import { fallbackMe, getCurrentUser } from "../lib/api";
import { queryKeys } from "../lib/queryClient";
import type { MeResponse } from "../types/me";

export function useMe(language = "auto") {
  const query = useQuery<MeResponse>({
    queryKey: queryKeys.me(language),
    queryFn: () => getCurrentUser(language).catch(() => fallbackMe()),
    staleTime: 5 * 60_000,
  });
  return { me: query.data ?? null, loading: query.isPending };
}
