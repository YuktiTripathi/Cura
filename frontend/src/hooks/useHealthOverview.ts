import { useQuery } from "@tanstack/react-query";
import { getHealthCategory, getHealthOverview } from "../lib/api";
import { queryKeys } from "../lib/queryClient";

/** One snapshot of blood results and Bio-AI risks, grouped by health category. */
export function useHealthOverview() {
  return useQuery({ queryKey: queryKeys.healthOverview, queryFn: getHealthOverview, staleTime: 5 * 60_000, retry: false });
}

/** Category detail and its evidence-bound explanation. */
export function useHealthCategory(categoryId: string | null) {
  return useQuery({
    queryKey: queryKeys.healthCategory(categoryId ?? ""),
    queryFn: () => getHealthCategory(categoryId as string),
    enabled: Boolean(categoryId),
    staleTime: 5 * 60_000,
    retry: false,
  });
}
