import type { DecisionRequest, NdjsonEvent } from "./types";

export async function streamDecision(
  payload: DecisionRequest,
  signal: AbortSignal,
  onEvent: (event: NdjsonEvent) => void,
): Promise<void> {
  const response = await fetch("/api/decide/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`HTTP ${response.status}`);
  }

  await readNdjson(response.body, onEvent);
}

export async function readNdjson(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: NdjsonEvent) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line) as NdjsonEvent);
    }
  }

  if (buffer.trim()) onEvent(JSON.parse(buffer) as NdjsonEvent);
}
