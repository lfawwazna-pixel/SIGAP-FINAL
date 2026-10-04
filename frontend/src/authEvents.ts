// Requests from a previous login must not invalidate the new authenticated view.
let generation = 0
export const authGeneration = () => generation
export const nextAuthGeneration = () => ++generation
export function rejectSession(expected: number) {
  if (expected === generation) window.dispatchEvent(new Event('sigap:session-rejected'))
}
