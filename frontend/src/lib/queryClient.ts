import { QueryClient } from "@tanstack/react-query";

export const queryKeys = {
  me: ["me"] as const,
  conversations: ["conversations"] as const,
  documents: ["documents"] as const,
  overview: ["overview"] as const,
};

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 1,
        refetchOnWindowFocus: true,
      },
    },
  });
}
