import { useEffect, useRef, useState } from "react";
import { startScene, startTryOn } from "./api/client";
import { ProgressStepper } from "./components/ProgressStepper/ProgressStepper";
import { ScenePreview } from "./components/ResultViewer/ScenePreview";
import { TryOnPreview } from "./components/ResultViewer/TryOnPreview";
import { UploadPanel } from "./components/UploadPanel/UploadPanel";
import { useFileUpload } from "./hooks/useFileUpload";
import { useJobPoller } from "./hooks/useJobPoller";
import type { JobStatus } from "./types";

export default function App() {
  const { jobId, uploading, error: uploadError, upload, reset } = useFileUpload();
  const { status, tryonUrl, sceneUrl, error: jobError } = useJobPoller(jobId);

  const sceneStartedRef = useRef(false);
  const tryonStartedRef = useRef(false);

  // Once upload is done (jobId exists and status is "queued"), kick off try-on
  useEffect(() => {
    if (jobId && status === "queued" && !tryonStartedRef.current) {
      tryonStartedRef.current = true;
      startTryOn(jobId).catch(console.error);
    }
  }, [jobId, status]);

  // Once try-on is done, kick off scene generation
  useEffect(() => {
    if (jobId && status === "tryon_done" && !sceneStartedRef.current) {
      sceneStartedRef.current = true;
      startScene({ job_id: jobId }).catch(console.error);
    }
  }, [jobId, status]);

  const handleUpload = async (personFile: File, dressFile: File) => {
    tryonStartedRef.current = false;
    sceneStartedRef.current = false;
    await upload(personFile, dressFile);
  };

  const handleReset = () => {
    tryonStartedRef.current = false;
    sceneStartedRef.current = false;
    reset();
  };

  const displayStatus: JobStatus | null = jobId ? status : null;
  const isProcessing =
    status === "tryon_processing" ||
    status === "scene_processing" ||
    status === "queued";
  const isFailed = status === "failed";
  const isDone = status === "done";

  return (
    <div className="min-h-screen bg-gradient-to-br from-rose-50 via-white to-amber-50">
      {/* Header */}
      <header className="border-b border-rose-100 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-rose-700 tracking-tight">
              Wedding Virtual Try-On
            </h1>
            <p className="text-xs text-gray-500">AI-powered bridal styling</p>
          </div>
          {jobId && (
            <button
              type="button"
              onClick={handleReset}
              className="text-sm text-rose-500 hover:text-rose-700 font-medium transition-colors"
            >
              Start over
            </button>
          )}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 flex flex-col gap-8">
        {/* Progress stepper */}
        {jobId && (
          <ProgressStepper currentStatus={displayStatus} />
        )}

        {/* Error banner */}
        {(isFailed || uploadError) && (
          <div className="rounded-xl bg-red-50 border border-red-200 px-5 py-4 text-sm text-red-700">
            <strong>Something went wrong:</strong>{" "}
            {jobError ?? uploadError ?? "Unknown error"}
          </div>
        )}

        {/* Upload panel — shown until a job is running or done */}
        {!jobId && (
          <UploadPanel
            onUpload={handleUpload}
            uploading={uploading}
            error={uploadError}
          />
        )}

        {/* Results — shown once try-on has started */}
        {jobId && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <TryOnPreview
              tryonUrl={tryonUrl}
              processing={
                status === "tryon_processing" || status === "queued"
              }
            />
            <ScenePreview
              sceneUrl={sceneUrl}
              processing={status === "scene_processing"}
            />
          </div>
        )}

        {/* Done message */}
        {isDone && (
          <div className="rounded-xl bg-green-50 border border-green-200 px-5 py-4 text-sm text-green-700 text-center">
            Your wedding scene is ready! Download it above or{" "}
            <button
              type="button"
              onClick={handleReset}
              className="underline font-medium hover:text-green-900"
            >
              try another look
            </button>
            .
          </div>
        )}
      </main>
    </div>
  );
}
