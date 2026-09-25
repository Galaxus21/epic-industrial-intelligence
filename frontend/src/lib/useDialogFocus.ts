/**
 * Keyboard behaviour shared by every modal dialog: focus moves into the dialog when it opens,
 * Tab and Shift+Tab stay inside it, Escape closes it, and focus returns to whatever opened it.
 * Attach the returned ref to the element with role="dialog".
 */
import { useEffect, useRef } from "react";

const focusableSelector =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useDialogFocus<T extends HTMLElement>(onClose: () => void, isOpen = true) {
  const dialogRef = useRef<T>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!isOpen) return;
    const opener = document.activeElement as HTMLElement | null;
    (focusableIn(dialogRef.current)[0] ?? dialogRef.current)?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
      } else if (event.key === "Tab") {
        keepFocusInside(event, dialogRef.current);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      opener?.focus();
    };
  }, [isOpen]);

  return dialogRef;
}

function focusableIn(root: HTMLElement | null): HTMLElement[] {
  if (!root) return [];
  return Array.from(root.querySelectorAll<HTMLElement>(focusableSelector));
}

function keepFocusInside(event: KeyboardEvent, root: HTMLElement | null) {
  const items = focusableIn(root);
  if (!root || items.length === 0) return;
  const first = items[0];
  const last = items[items.length - 1];
  const outside = !root.contains(document.activeElement);
  if (event.shiftKey && (outside || document.activeElement === first)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (outside || document.activeElement === last)) {
    event.preventDefault();
    first.focus();
  }
}
