export type IntegrationLike = {
  provider: string;
  expiresAt: string | null;
};

/** Prefer the newest non-expired OAuth connection for a provider. */
export function selectPreferredIntegration<T extends IntegrationLike>(
  integrations: T[],
  provider: string,
  now = Date.now(),
): T | null {
  const matches = integrations
    .filter((integration) => integration.provider === provider)
    .sort((left, right) => {
      const leftExpiry = left.expiresAt ? Date.parse(left.expiresAt) : 0;
      const rightExpiry = right.expiresAt ? Date.parse(right.expiresAt) : 0;
      const leftReady = leftExpiry > now ? 1 : 0;
      const rightReady = rightExpiry > now ? 1 : 0;
      return rightReady - leftReady || rightExpiry - leftExpiry;
    });
  return matches[0] ?? null;
}
