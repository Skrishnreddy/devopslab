import { useCallback, useEffect, useState } from "react";

/** Fetch on mount, optionally poll; returns data, error and a reload function. */
export function useApi<T>(fn: () => Promise<T>, pollMs?: number) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string>();
  const load = useCallback(() => {
    fn().then((d) => { setData(d); setError(undefined); }).catch((e: Error) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    load();
    if (!pollMs) return;
    const t = setInterval(load, pollMs);
    return () => clearInterval(t);
  }, [load, pollMs]);
  return { data, error, reload: load };
}
