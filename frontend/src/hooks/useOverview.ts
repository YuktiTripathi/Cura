import { useQuery } from "@tanstack/react-query";
import { getOverview } from "../lib/api";
import { queryKeys } from "../lib/queryClient";

export function useOverview() {
  return useQuery({ queryKey: queryKeys.overview, queryFn: getOverview, staleTime: 5 * 60_000, retry: false });
}
