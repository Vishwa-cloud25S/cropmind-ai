"use client";

import { useEffect, useRef, useState } from "react";

import { errorMessage, fetchAuthedBlob } from "@/lib/api";

/**
 * Authenticated media loader. Owner-scoped binary routes (stored uploads, thumbnails,
 * Grad-CAM overlays) cannot be reached by a plain <img src> — that navigation carries
 * no Authorization header, so the API answers with the by-design 404 (existence
 * unconfirmed). This component fetches the bytes with the session token attached and
 * renders an object URL. Failures surface the real status as visible text — never a
 * silently broken image, never an invented placeholder.
 */
export default function AuthedImage({
  url,
  alt,
  className,
  hideOnError = false,
  onError,
}: {
  url: string;
  alt: string;
  className?: string;
  hideOnError?: boolean;
  onError?: () => void;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setSrc(null);
    setError(null);
    fetchAuthedBlob(url)
      .then(({ blob }) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch((cause) => {
        if (cancelled) return;
        setError(errorMessage(cause));
        onErrorRef.current?.();
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  if (error) {
    if (hideOnError) return null;
    return (
      <p className="alert-caution" role="note">
        Stored media not available to this session — {error}
      </p>
    );
  }
  if (!src) return <p className="text-xs text-stone-500">Loading stored media…</p>;
  // eslint-disable-next-line @next/next/no-img-element -- authenticated object URL; nothing to optimize
  return <img src={src} alt={alt} className={className} />;
}
