import { useQuery } from "@tanstack/react-query";
import { fallbackMe, getCurrentUser } from "../lib/api";
import { queryKeys } from "../lib/queryClient";
import type { MeResponse } from "../types/me";

export function useMe() {
  const query = useQuery<MeResponse>({
    queryKey: queryKeys.me,
    queryFn: () => getCurrentUser().catch(() => fallbackMe()),
    staleTime: 5 * 60_000,
  });
  return { me: query.data ?? null, loading: query.isPending };
}
