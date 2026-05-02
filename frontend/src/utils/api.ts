export const getServerApiUrl = () =>
  (process.env.API_URL || process.env.INTERNAL_API_URL || "http://127.0.0.1:8000").trim();

