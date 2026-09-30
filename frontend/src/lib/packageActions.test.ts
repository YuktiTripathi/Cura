import { afterEach, describe, expect, it, vi } from "vitest";
import { openSuperShyftPackage, supershyftPackageHref } from "./packageActions";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("packageActions", () => {
  it("builds a SuperShyft path from catalog id without inventing a booking URL", () => {
    expect(supershyftPackageHref("test_group", "31")).toBe("/diagnostics/test-groups/31");
    expect(supershyftPackageHref("package", "12")).toBe("/diagnostics/packages/12");
  });

  it("opens a package through a clickable event rather than markdown text", () => {
    const handler = vi.fn();
    const onOpen = (event: Event) => handler((event as CustomEvent).detail);
    window.addEventListener("cura:open_package", onOpen);
    openSuperShyftPackage("test_group", "31");
    expect(handler).toHaveBeenCalledWith({
      type: "cura:open_package",
      package_id: "31",
      kind: "test_group",
    });
    window.removeEventListener("cura:open_package", onOpen);
  });
});
