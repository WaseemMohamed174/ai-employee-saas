import { useEffect, useRef } from "react";

/**
 * Re-runs a data fetch on a fixed interval while the tab is visible (S5).
 * Keeps dashboard pages live without a manual refresh or section-switching.
 * Skips ticks when the tab is hidden or the previous fetch is still in flight.
 */
export function useAutoRefresh(fn: () => void, intervalMs = 5000, deps: unknown[] = []) {
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const busyRef = useRef(false);
  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState !== "visible" || busyRef.current) return;
      busyRef.current = true;
      try {
        Promise.resolve(fnRef.current()).finally(() => {
          busyRef.current = false;
        });
      } catch {
        busyRef.current = false;
      }
    }, intervalMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps]);
}
