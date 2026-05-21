/**
 * OpenMimicry External-protocol echo server (M12).
 *
 * A 50-ish-line WS server you can point the
 * `ExternalAvatarAdapter` at to verify the wire flow during
 * development. Every inbound frame is pretty-printed to stdout; the
 * server replies with `ack` for `avatar.directive` frames and emits a
 * `ready` frame the moment a client connects.
 *
 * Run:
 *     pnpm --filter @openmimicry/external-echo start
 *     # or directly:
 *     pnpm tsx src/server.ts
 */

import { WebSocketServer, type WebSocket } from "ws";

const PORT = Number.parseInt(process.env["OM_EXTERNAL_PORT"] ?? "8765", 10);
const HOST = process.env["OM_EXTERNAL_HOST"] ?? "127.0.0.1";

const wss = new WebSocketServer({ host: HOST, port: PORT });

console.log(`[external-echo] listening on ws://${HOST}:${PORT}`);

wss.on("connection", (ws: WebSocket, req) => {
  const peer = `${req.socket.remoteAddress}:${req.socket.remotePort}`;
  console.log(`[external-echo] connection from ${peer}`);
  ws.send(JSON.stringify({ type: "ready" }));

  ws.on("message", (raw: Buffer | ArrayBuffer | Buffer[]) => {
    let text: string;
    if (Buffer.isBuffer(raw)) text = raw.toString("utf8");
    else if (Array.isArray(raw)) text = Buffer.concat(raw).toString("utf8");
    else text = Buffer.from(raw).toString("utf8");

    let frame: { type?: string } & Record<string, unknown>;
    try {
      frame = JSON.parse(text);
    } catch (err) {
      console.warn(`[external-echo] malformed frame: ${(err as Error).message}`);
      ws.send(JSON.stringify({ type: "error", message: "malformed JSON" }));
      return;
    }

    const kind = String(frame.type ?? "");
    console.log(`[external-echo] ${peer} <- ${kind}: ${shortPreview(frame)}`);

    if (kind === "avatar.directive") {
      ws.send(JSON.stringify({ type: "ack", for: "avatar.directive" }));
    } else if (kind === "shutdown") {
      ws.send(JSON.stringify({ type: "ack", for: "shutdown" }));
      ws.close(1000, "bye");
    }
  });

  ws.on("close", (code) => {
    console.log(`[external-echo] ${peer} closed (code=${code})`);
  });

  ws.on("error", (err) => {
    console.warn(`[external-echo] ${peer} error: ${err.message}`);
  });
});

function shortPreview(frame: Record<string, unknown>): string {
  const copy = { ...frame };
  if (typeof copy["directive"] === "object" && copy["directive"] !== null) {
    const d = copy["directive"] as Record<string, unknown>;
    copy["directive"] = {
      state: d["state"],
      emotion: d["emotion"],
      speaking: d["speaking"],
    };
  }
  const text = JSON.stringify(copy);
  return text.length > 200 ? `${text.slice(0, 197)}...` : text;
}
