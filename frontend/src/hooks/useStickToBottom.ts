import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

const NEAR_BOTTOM_PX = 120;

/**
 * Keep a scroll container pinned to its newest content while the reader is already at the bottom,
 * and jump there when they send something. Reading earlier messages is never interrupted.
 */
export function useStickToBottom(ref: RefObject<HTMLElement>, contentKey: unknown, forceKey: unknown) {
  const pinned = useRef(true);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = () => {
      pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [ref]);

  useLayoutEffect(() => {
    pinned.current = true;
  }, [forceKey]);

  useLayoutEffect(() => {
    const el = ref.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [ref, contentKey, forceKey]);
}
