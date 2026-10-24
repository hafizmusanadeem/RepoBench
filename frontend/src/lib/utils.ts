// Create ONLY if src/lib/utils.ts is missing (your .gitignore `lib/` rule may
// have kept it out of git). Same signature Button/Card/Badge already use.
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
