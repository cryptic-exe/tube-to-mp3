export type Quality = "128" | "192" | "256" | "320";

export type ProbeResult = {
  title: string;
  duration: number | null;
  thumbnail: string | null;
  is_playlist: boolean;
  entry_count: number;
  webpage_url: string;
};

export type JobStatus = {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | "expired" | string;
  progress: number;
  title?: string | null;
  is_playlist?: boolean;
  entry_count?: number;
  error?: string | null;
  ready?: boolean;
  filename?: string | null;
};

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds)) return "";
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}