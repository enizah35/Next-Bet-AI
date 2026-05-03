const DEV_SERVER_API_URL = "http://127.0.0.1:8000";

const normalizeApiUrl = (value: string | undefined, fallback = DEV_SERVER_API_URL) => {
  const raw = (value || fallback).trim().replace(/\/+$/, "");
  try {
    const url = new URL(raw);
    if (!["http:", "https:"].includes(url.protocol)) return fallback;
    return url.toString().replace(/\/+$/, "");
  } catch {
    return fallback;
  }
};

export const getServerApiUrl = () =>
  normalizeApiUrl(process.env.API_URL || process.env.INTERNAL_API_URL);
