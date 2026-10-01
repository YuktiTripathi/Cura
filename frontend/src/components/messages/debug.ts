export function debugMode(): boolean {
  return import.meta.env.VITE_CURA_DEBUG === "true";
}
