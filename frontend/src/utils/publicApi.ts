const DEV_PUBLIC_API_URL = "http://localhost:8000";

const normalizeApiUrl = (value: string | undefined, fallback = DEV_PUBLIC_API_URL) => {
  const raw = (value || fallback).trim().replace(/\/+$/, "");
  try {
    const url = new URL(raw);
    if (!["http:", "https:"].includes(url.protocol)) return fallback;
    return url.toString().replace(/\/+$/, "");
  } catch {
    return fallback;
  }
};

export const getPublicApiUrl = () =>
  normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL);
