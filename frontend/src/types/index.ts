export type JobStatus =
  | "queued"
  | "tryon_processing"
  | "tryon_done"
  | "scene_processing"
  | "done"
  | "failed";

export type SceneProvider = "mock" | "flux" | "gpt_image" | "sdxl";

export interface UploadResponse {
  job_id: string;
  status: JobStatus;
  message: string;
}

export interface TryOnRequest {
  job_id: string;
}

export interface TryOnResponse {
  job_id: string;
  status: JobStatus;
  message: string;
}

export interface SceneRequest {
  job_id: string;
  provider?: SceneProvider | null;
}

export interface SceneResponse {
  job_id: string;
  status: JobStatus;
  message: string;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  tryon_url: string | null;
  scene_url: string | null;
  error: string | null;
}

export interface ErrorResponse {
  detail: string;
}
