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
      } catch (err: unknown) {
        // 404 = job not found (server restarted or bad ID) — stop polling
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404 || status === 422) {
          setData({
            job_id: jobId,
            status: "failed",
            tryon_url: null,
            scene_url: null,
            error: "Session expired — please upload your images again.",
          });
          stopPolling();
        }
        // other network errors — keep polling (transient)
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
