import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { getHealthCategory, getHealthOverview, getHealthView } from "../lib/api";
import { queryKeys } from "../lib/queryClient";
import { useMe } from "./useMe";

function subjectKey(userId: string | number | null | undefined): string {
  return userId == null || userId === "" ? "session" : String(userId);
}

/** Prefetch the member health view. A 404 means the snapshot flag is off. */
export function useHealthView() {
  const { me, loading } = useMe();
  const subject = subjectKey(me?.user_id);
  const client = useQueryClient();
  useEffect(() => {
    client.removeQueries({
      predicate: (query) => query.queryKey[0] === "health-view" && query.queryKey[1] !== subject,
    });
  }, [client, subject]);
  return useQuery({
    queryKey: queryKeys.healthView(subject),
    queryFn: getHealthView,
    enabled: !loading,
    staleTime: 5 * 60_000,
    retry: false,
    gcTime: 5 * 60_000,
  });
}

/** One snapshot of blood results and Bio-AI risks, grouped by health category. */
export function useHealthOverview() {
  const view = useHealthView();
  const fallback = useQuery({
    queryKey: queryKeys.healthOverview,
    queryFn: getHealthOverview,
    enabled: view.isFetched && view.data == null && !view.isError,
    staleTime: 5 * 60_000,
    retry: false,
  });
  if (view.data) {
    return { data: view.data.overview, isLoading: false, isError: false, isPending: false, refetch: view.refetch };
  }
  if (view.isPending || view.isLoading) {
    return { data: undefined, isLoading: true, isError: false, isPending: true, refetch: view.refetch };
  }
  return fallback;
}

/** Category detail from the warm view, otherwise one compatibility request. */
export function useHealthCategory(categoryId: string | null) {
  const view = useHealthView();
  const cached = categoryId && view.data ? view.data.categories[categoryId] : undefined;
  const query = useQuery({
    queryKey: queryKeys.healthCategory(categoryId ?? ""),
    queryFn: () => getHealthCategory(categoryId as string),
    enabled: Boolean(categoryId) && view.isFetched && view.data == null && !view.isError,
    staleTime: 5 * 60_000,
    retry: false,
  });
  if (cached) {
    return { data: cached, isLoading: false, isError: false, isPending: false, refetch: view.refetch };
  }
  if (categoryId && view.data && !cached) {
    return { data: undefined, isLoading: false, isError: true, isPending: false, refetch: view.refetch };
  }
  return query;
}
