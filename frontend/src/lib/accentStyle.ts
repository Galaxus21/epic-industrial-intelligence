/**
 * Text in a data-driven colour (a status, risk or health colour chosen at runtime).
 * Pair the returned style with the `text-accent` class: the dark theme shows the colour as is, and the light
 * theme darkens it (globals.css), because the bright shades that read well on black fall below 3:1 on white.
 */
import type { CSSProperties } from "react";

export const accentClass = "text-accent";

export function accentStyle(color: string): CSSProperties {
  return { "--accent": color } as CSSProperties;
}
