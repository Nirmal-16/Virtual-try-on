import { useState } from "react";
import { uploadImages } from "../api/client";

interface UploadState {
  jobId: string | null;
  uploading: boolean;
  error: string | null;
}

interface UseFileUploadReturn extends UploadState {
  upload: (personFile: File, dressFile: File) => Promise<string | null>;
  reset: () => void;
}

export function useFileUpload(): UseFileUploadReturn {
  const [state, setState] = useState<UploadState>({
    jobId: null,
    uploading: false,
    error: null,
  });

  const upload = async (
    personFile: File,
    dressFile: File
  ): Promise<string | null> => {
    setState({ jobId: null, uploading: true, error: null });
    try {
      const response = await uploadImages(personFile, dressFile);
      setState({ jobId: response.job_id, uploading: false, error: null });
      return response.job_id;
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Upload failed. Please try again.";
      setState({ jobId: null, uploading: false, error: message });
      return null;
    }
  };

  const reset = () =>
    setState({ jobId: null, uploading: false, error: null });

  return { ...state, upload, reset };
}
