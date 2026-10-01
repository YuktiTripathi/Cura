import { createContext, useContext, type ReactNode } from "react";

type MarkerPanelApi = {
  /** Whether a marker has an overview entry the panel can show. */
  has: (key: string | null | undefined) => boolean;
  open: (key: string) => void;
};

const NOOP: MarkerPanelApi = { has: () => false, open: () => undefined };
const MarkerPanelContext = createContext<MarkerPanelApi>(NOOP);

export function MarkerPanelProvider({ value, children }: { value: MarkerPanelApi; children: ReactNode }) {
  return <MarkerPanelContext.Provider value={value}>{children}</MarkerPanelContext.Provider>;
}

/** Outside a provider (e.g. isolated tests) cards are simply not clickable. */
export function useMarkerPanel(): MarkerPanelApi {
  return useContext(MarkerPanelContext);
}
