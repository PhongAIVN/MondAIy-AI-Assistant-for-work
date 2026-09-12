export function resolveConnectionCallbackMessage(backendMessage: string | null, fallbackMessage: string): string {
  return backendMessage?.trim() || fallbackMessage;
}
