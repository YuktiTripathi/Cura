import { afterEach, describe, expect, it, vi } from "vitest";
import {
  THEME_STORAGE_KEY,
  applyTheme,
  nextThemePreference,
  readThemePreference,
  writeThemePreference,
} from "./theme";

function mockSystemDark(dark: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: dark && query.includes("dark"),
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

describe("theme", () => {
  afterEach(() => {
    window.localStorage.clear();
    vi.unstubAllGlobals();
    delete document.documentElement.dataset.theme;
  });

  it("defaults to system and cycles system → light → dark", () => {
    expect(readThemePreference()).toBe("system");
    expect(nextThemePreference("system")).toBe("light");
    expect(nextThemePreference("light")).toBe("dark");
    expect(nextThemePreference("dark")).toBe("system");
  });

  it("persists explicit choices and clears storage for system", () => {
    writeThemePreference("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(readThemePreference()).toBe("dark");
    writeThemePreference("system");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
  });

  it("resolves system preference onto the root element", () => {
    mockSystemDark(true);
    expect(applyTheme("system")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(applyTheme("light")).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
