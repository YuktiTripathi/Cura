import { useEffect, useRef } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";

/** Invalidate `queryKey` whenever `signal` changes after mount (the initial fetch already covers mount). */
export function useRefetchOnChange(queryKey: QueryKey, signal: unknown) {
  const client = useQueryClient();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    void client.invalidateQueries({ queryKey });
    // queryKey is a stable constant at call sites; only the signal should retrigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, signal]);
}
