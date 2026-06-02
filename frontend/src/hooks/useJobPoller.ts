import { useCallback, useEffect, useRef, useState } from "react";
import { getStatus } from "../api/client";
import type { JobStatus, JobStatusResponse } from "../types";

const TERMINAL_STATES: JobStatus[] = ["done", "failed"];
const POLL_INTERVAL_MS = 2000;

interface UseJobPollerReturn {
  status: JobStatus | null;
  tryonUrl: string | null;
  sceneUrl: string | null;
  error: string | null;
  isPolling: boolean;
}

export function useJobPoller(jobId: string | null): UseJobPollerReturn {
  const [data, setData] = useState<JobStatusResponse | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  useEffect(() => {
    if (!jobId) {
      stopPolling();
      setData(null);
      return;
    }

    setIsPolling(true);

    const poll = async () => {
      try {
        const result = await getStatus(jobId);
        setData(result);
        if (TERMINAL_STATES.includes(result.status)) {
          stopPolling();
        }
      } catch {
        // transient network error — keep polling
      }
    };

    poll();
    timerRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => stopPolling();
  }, [jobId, stopPolling]);

  return {
    status: data?.status ?? null,
    tryonUrl: data?.tryon_url ?? null,
    sceneUrl: data?.scene_url ?? null,
    error: data?.error ?? null,
    isPolling,
  };
}
