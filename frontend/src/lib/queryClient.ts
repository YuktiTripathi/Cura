import { QueryClient } from "@tanstack/react-query";

export const queryKeys = {
  me: ["me"] as const,
  conversations: ["conversations"] as const,
  documents: ["documents"] as const,
  overview: ["overview"] as const,
  bodySystems: (reportId: string | null) => ["body-systems", reportId] as const,
  healthOverview: ["health-overview"] as const,
  healthView: (subject: string) => ["health-view", subject] as const,
  healthCategory: (id: string) => ["health-overview", id] as const,
  riskOverview: (reportId: string | null) => ["bio-ai-risks", reportId] as const,
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
