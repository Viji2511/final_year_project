import axios from "axios";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: BASE, timeout: 30000 });

export const uploadPaper = async (paperId, file) => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(
    `/run?paper_id=${encodeURIComponent(paperId)}`,
    form
  );
  return data;
};

export const getResult = async (paperId) => {
  const { data } = await api.get(`/result/${encodeURIComponent(paperId)}`);
  return data;
};

export const listResults = async () => {
  const { data } = await api.get("/results");
  return data;
};

export const pollResult = (paperId, onUpdate, intervalMs = 3000) => {
  let stopped = false;
  let timer;
  const poll = async () => {
    try {
      const result = await getResult(paperId);
      if (stopped) return;
      onUpdate(result);
      if (result.status === "complete" || result.status === "error") return;
      timer = setTimeout(poll, intervalMs);
    } catch (error) {
      if (!stopped) onUpdate({ status: "error", error: error.message || "Unable to fetch pipeline status." });
    }
  };
  poll();
  return () => { stopped = true; clearTimeout(timer); };
};
