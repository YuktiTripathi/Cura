import { useQuery } from "@tanstack/react-query";
import { getHealthCategory, getHealthOverview } from "../lib/api";
import { queryKeys } from "../lib/queryClient";

/** One snapshot of blood results and Bio-AI risks, grouped by health category. */
export function useHealthOverview() {
  return useQuery({ queryKey: queryKeys.healthOverview, queryFn: getHealthOverview, staleTime: 5 * 60_000, retry: false });
}

/** The same cached wording as the overview, so opening a category makes no extra model request. */
export function useHealthCategory(categoryId: string | null) {
  return useQuery({
    queryKey: queryKeys.healthCategory(categoryId ?? ""),
    queryFn: () => getHealthCategory(categoryId as string),
    enabled: Boolean(categoryId),
    staleTime: 5 * 60_000,
    retry: false,
  });
}
