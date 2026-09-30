export type PackageActionKind = "package" | "test_group";

export function supershyftPackageHref(kind: PackageActionKind | null | undefined, packageId: string): string {
  const base = (import.meta.env.VITE_SUPERSHYFT_APP_URL || "").replace(/\/$/, "");
  const template =
    kind === "test_group"
      ? import.meta.env.VITE_SUPERSHYFT_TEST_GROUP_PATH || "/diagnostics/test-groups/{id}"
      : import.meta.env.VITE_SUPERSHYFT_PACKAGE_PATH || "/diagnostics/packages/{id}";
  const path = template.replace("{id}", encodeURIComponent(packageId));
  return base ? `${base}${path}` : path;
}

export function openSuperShyftPackage(kind: PackageActionKind | null | undefined, packageId: string) {
  const detail = { type: "cura:open_package", package_id: packageId, kind: kind || "package" };
  window.dispatchEvent(new CustomEvent("cura:open_package", { detail }));
  if (window.parent && window.parent !== window) {
    window.parent.postMessage(detail, "*");
  }
  const href = supershyftPackageHref(kind, packageId);
  const absolute = /^https?:\/\//i.test(href);
  if (absolute) {
    window.open(href, "_blank", "noopener,noreferrer");
    return;
  }
  if (import.meta.env.VITE_SUPERSHYFT_APP_URL) {
    window.open(href, "_blank", "noopener,noreferrer");
  }
}
