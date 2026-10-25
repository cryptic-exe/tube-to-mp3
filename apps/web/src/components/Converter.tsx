"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  formatDuration,
  type JobStatus,
  type ProbeResult,
  type Quality,
} from "@/lib/types";
import styles from "./Converter.module.css";

const QUALITIES: Quality[] = ["128", "192", "256", "320"];

type Phase = "idle" | "probing" | "ready" | "converting" | "done" | "error";

function extractError(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) =>
          typeof d === "object" && d && "msg" in d
            ? String((d as { msg: unknown }).msg)
            : String(d),
        )
        .join(" ");
    }
  }
  return fallback;
}

export function Converter() {
  const [url, setUrl] = useState("");
  const [quality, setQuality] = useState<Quality>("192");
  const [phase, setPhase] = useState<Phase>("idle");
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit =
    url.trim().length > 8 && phase !== "probing" && phase !== "converting";

  const reset = useCallback(() => {
    setPhase("idle");
    setProbe(null);
    setJob(null);
    setError(null);
    setUrl("");
  }, []);

  const lookUp = useCallback(async () => {
    setError(null);
    setProbe(null);
    setJob(null);
    setPhase("probing");

    try {
      const res = await fetch("/api/probe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setPhase("error");
        setError(extractError(data, "Could not read that YouTube URL."));
        return;
      }
      setProbe(data as ProbeResult);
      setPhase("ready");
    } catch {
      setPhase("error");
      setError("Network error while looking up the video.");
    }
  }, [url]);

  const convert = useCallback(async () => {
    setError(null);
    setJob(null);
    setPhase("converting");

    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), quality }),
      });
      const data = await res.json();
      if (!res.ok) {
        setPhase("error");
        setError(extractError(data, "Could not start conversion."));
        return;
      }
      setJob({
        jobId: data.jobId,
        status: "queued",
        progress: 0,
        title: probe?.title,
      });
    } catch {
      setPhase("error");
      setError("Network error while starting conversion.");
    }
  }, [url, quality, probe?.title]);

  useEffect(() => {
    if (!job?.jobId || phase !== "converting") return;
    if (job.status === "completed" || job.status === "failed") return;

    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch(`/api/jobs/${encodeURIComponent(job.jobId)}`);
        const data = (await res.json()) as JobStatus & { detail?: string };
        if (cancelled) return;
        if (!res.ok) {
          setPhase("error");
          setError(extractError(data, "Lost track of the conversion job."));
          return;
        }
        setJob(data);
        if (data.status === "completed") {
          setPhase("done");
        } else if (data.status === "failed") {
          setPhase("error");
          setError(data.error || "Conversion failed.");
        }
      } catch {
        if (!cancelled) {
          setPhase("error");
          setError("Could not check conversion progress.");
        }
      }
    };

    const id = window.setInterval(tick, 1200);
    void tick();
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [job?.jobId, job?.status, phase]);

  const metaLine = useMemo(() => {
    if (!probe) return null;
    if (probe.is_playlist) {
      return `${probe.entry_count} tracks · Playlist`;
    }
    const duration = formatDuration(probe.duration);
    return duration ? `${duration} · Video` : "Video";
  }, [probe]);

  const progress = job?.progress ?? 0;

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <p className={styles.brand}>Tube to MP3</p>
      </header>

      <section className={styles.hero}>
        <h1 className={styles.title}>Tube to MP3</h1>
        <p className={styles.subtitle}>
          Paste a YouTube link. Convert to clean MP3 — video or playlist.
        </p>

        <form
          className={styles.form}
          onSubmit={(e) => {
            e.preventDefault();
            if (!canSubmit) return;
            if (phase === "ready" || phase === "done" || phase === "error") {
              void convert();
            } else {
              void lookUp();
            }
          }}
        >
          <label className={styles.fieldLabel} htmlFor="yt-url">
            YouTube URL
          </label>
          <input
            id="yt-url"
            className={styles.urlInput}
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="https://www.youtube.com/watch?v=…"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (phase !== "idle" && phase !== "converting") {
                setPhase("idle");
                setProbe(null);
                setJob(null);
                setError(null);
              }
            }}
            disabled={phase === "converting" || phase === "probing"}
          />

          <div className={styles.qualityBlock}>
            <span className={styles.fieldLabel}>Quality</span>
            <div
              className={styles.segments}
              role="radiogroup"
              aria-label="MP3 quality"
            >
              {QUALITIES.map((q) => (
                <button
                  key={q}
                  type="button"
                  role="radio"
                  aria-checked={quality === q}
                  className={`${styles.segment}${quality === q ? ` ${styles.segmentActive}` : ""}`}
                  onClick={() => setQuality(q)}
                  disabled={phase === "converting" || phase === "probing"}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.actions}>
            {phase === "idle" || phase === "probing" ? (
              <button
                type="submit"
                className={`${styles.btn} ${styles.primary}`}
                disabled={!canSubmit}
              >
                {phase === "probing" ? "Looking up…" : "Look up"}
              </button>
            ) : (
              <button
                type="button"
                className={`${styles.btn} ${styles.primary}`}
                disabled={phase === "converting"}
                onClick={() => void convert()}
              >
                {phase === "converting" ? "Converting…" : "Convert"}
              </button>
            )}
            {(phase === "done" || phase === "error" || phase === "ready") && (
              <button
                type="button"
                className={`${styles.btn} ${styles.ghost}`}
                onClick={reset}
              >
                Start over
              </button>
            )}
          </div>
        </form>

        {probe && (
          <div className={styles.preview} aria-live="polite">
            {probe.thumbnail ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                className={styles.thumb}
                src={probe.thumbnail}
                alt=""
                width={160}
                height={90}
              />
            ) : (
              <div className={styles.thumb} aria-hidden />
            )}
            <div className={styles.previewCopy}>
              <p className={styles.previewTitle}>{probe.title}</p>
              {metaLine && <p className={styles.previewMeta}>{metaLine}</p>}
            </div>
          </div>
        )}

        {(phase === "converting" || phase === "done") && (
          <div className={styles.progressBlock} aria-live="polite">
            <div className={styles.progressTrack}>
              <div
                className={styles.progressFill}
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
              />
            </div>
            <p className={styles.progressLabel}>
              {phase === "done"
                ? "Ready"
                : progress > 0
                  ? `${Math.round(progress)}%`
                  : "Starting…"}
            </p>
          </div>
        )}

        {phase === "done" && job?.jobId && (
          <div className={styles.successRow}>
            <a
              className={`${styles.btn} ${styles.primary}`}
              href={`/api/jobs/${encodeURIComponent(job.jobId)}/file`}
              download={job.filename || undefined}
            >
              Download {job.is_playlist ? "ZIP" : "MP3"}
            </a>
          </div>
        )}

        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}
      </section>

      <footer className={styles.footer}>
        <p>
          For personal use with content you have rights to. Not affiliated with
          YouTube.
        </p>
      </footer>
    </main>
  );
}