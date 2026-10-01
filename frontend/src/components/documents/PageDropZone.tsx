import { useEffect, useRef, useState } from "react";

const hasFiles = (event: DragEvent) => Array.from(event.dataTransfer?.types || []).includes("Files");

/** Drop a PDF anywhere on the page to attach it. Shows a full-window target while dragging files. */
export function PageDropZone({ onFile, disabled = false }: { onFile: (file: File) => void; disabled?: boolean }) {
  const [active, setActive] = useState(false);
  const depth = useRef(0);

  useEffect(() => {
    const enter = (event: DragEvent) => {
      if (!hasFiles(event) || disabled) return;
      event.preventDefault();
      depth.current += 1;
      setActive(true);
    };
    const over = (event: DragEvent) => {
      if (!hasFiles(event) || disabled) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
    };
    const leave = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) setActive(false);
    };
    const drop = (event: DragEvent) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      depth.current = 0;
      setActive(false);
      if (disabled) return;
      const file = event.dataTransfer?.files?.[0];
      if (file) onFile(file);
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
    };
  }, [onFile, disabled]);

  if (!active) return null;
  return (
    <div className="drop-overlay" data-testid="drop-overlay" aria-hidden="true">
      <div className="drop-target">
        <strong>Drop your PDF report</strong>
        <span>Cura will read its values so you can review and ask about them.</span>
      </div>
    </div>
  );
}
