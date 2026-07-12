import { useCallback, useEffect, useState } from "react";

export const SUCCESS_DISMISS_MS = 3000;

type SuccessState = {
  message: string | null;
  revision: number;
};

export function useTransientSuccess(): readonly [string | null, (message: string | null) => void] {
  const [state, setState] = useState<SuccessState>({ message: null, revision: 0 });
  const setMessage = useCallback((message: string | null) => {
    setState((current) => ({ message, revision: current.revision + 1 }));
  }, []);

  useEffect(() => {
    if (state.message === null) return;
    const timer = window.setTimeout(() => {
      setState((current) => current.revision === state.revision
        ? { message: null, revision: current.revision }
        : current);
    }, SUCCESS_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [state]);

  return [state.message, setMessage] as const;
}
