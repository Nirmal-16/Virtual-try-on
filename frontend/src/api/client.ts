import axios from "axios";
import type {
  JobStatusResponse,
  SceneRequest,
  SceneResponse,
  TryOnRequest,
  TryOnResponse,
  UploadResponse,
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 30_000,
});

export async function uploadImages(
  personFile: File,
  dressFile: File
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("person_image", personFile);
  form.append("dress_image", dressFile);
  const { data } = await api.post<UploadResponse>("/api/upload", form);
  return data;
}

export async function startTryOn(jobId: string): Promise<TryOnResponse> {
  const body: TryOnRequest = { job_id: jobId };
  const { data } = await api.post<TryOnResponse>("/api/tryon", body);
  return data;
}

export async function startScene(req: SceneRequest): Promise<SceneResponse> {
  const { data } = await api.post<SceneResponse>("/api/scene", req);
  return data;
}

export async function getStatus(jobId: string): Promise<JobStatusResponse> {
  const { data } = await api.get<JobStatusResponse>(`/api/status/${jobId}`);
  return data;
}

export function imageUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  return `${base}${path}`;
}
