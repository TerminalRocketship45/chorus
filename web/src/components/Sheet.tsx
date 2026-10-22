import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { overlayRoot } from "./Overlay";

/** A small, calm bottom sheet (iOS style) with a scrim. Escape, the scrim and Done close it. */
export function Sheet({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const doneRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    doneRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [onClose]);

  return createPortal(
    <div className="sheet-layer">
      <div className="sheet-scrim" onClick={onClose} aria-hidden="true" />
      <div className="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
        <div className="sheet__grab" aria-hidden="true" />
        <h2 className="sheet__title" id="sheet-title">
          {title}
        </h2>
        <div className="sheet__body">{children}</div>
        <button type="button" className="btn btn--tinted btn--block" ref={doneRef} onClick={onClose}>
          Done
        </button>
      </div>
    </div>,
    overlayRoot()
  );
}
