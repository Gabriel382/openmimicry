// SPDX-License-Identifier: MIT
//
// Minimal WebSocket client for the OpenMimicry Unity bridge.
//
// Reads JSON frames from the configured backend endpoint and forwards
// them to subscribers (typically `AvatarController`). Acks every
// `avatar.directive` so the Python adapter can implement backpressure.
//
// The implementation uses `System.Net.WebSockets.ClientWebSocket` so
// it works in standalone player builds without third-party packages.
// In the Editor the WS thread runs on a background task; messages are
// marshalled back to the main thread via a thread-safe queue.

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace OpenMimicry
{
    public delegate void FrameHandler(string type, string json);

    public class WSClient : MonoBehaviour
    {
        [Tooltip("WebSocket URL of the OpenMimicry backend, e.g. ws://127.0.0.1:8765")]
        public string url = "ws://127.0.0.1:8765";

        [Tooltip("Reconnect delay in seconds (initial value, doubles up to maxBackoffSeconds).")]
        public float initialBackoffSeconds = 0.5f;

        [Tooltip("Maximum reconnect backoff in seconds.")]
        public float maxBackoffSeconds = 5f;

        [Tooltip("If true, the client emits a telemetry frame every telemetryIntervalSeconds.")]
        public bool emitTelemetry = true;

        [Tooltip("Interval between telemetry frames, in seconds.")]
        public float telemetryIntervalSeconds = 1f;

        private readonly List<FrameHandler> _subscribers = new();
        private readonly ConcurrentQueue<string> _inbound = new();
        private readonly ConcurrentQueue<string> _outbound = new();
        private CancellationTokenSource _cts;
        private Task _runTask;
        private ClientWebSocket _ws;
        private float _backoff;
        private float _telemetryTimer;
        private string _lastAnimState = "Idle";

        public void Subscribe(FrameHandler handler)
        {
            if (handler == null) return;
            _subscribers.Add(handler);
        }

        public void Send(string json)
        {
            _outbound.Enqueue(json);
        }

        public void SetAnimState(string state)
        {
            _lastAnimState = state ?? "Idle";
        }

        // -------------------------------------------------------------------
        // Lifecycle
        // -------------------------------------------------------------------

        private void OnEnable()
        {
            _cts = new CancellationTokenSource();
            _backoff = Mathf.Max(0.1f, initialBackoffSeconds);
            _runTask = Task.Run(() => RunAsync(_cts.Token));
        }

        private void OnDisable()
        {
            _cts?.Cancel();
            try
            {
                _ws?.Abort();
                _ws?.Dispose();
            }
            catch (Exception) { /* ignore on teardown */ }
            _ws = null;
            _runTask = null;
        }

        private void Update()
        {
            while (_inbound.TryDequeue(out var raw))
            {
                DispatchFrame(raw);
            }
            if (!emitTelemetry) return;
            _telemetryTimer += Time.unscaledDeltaTime;
            if (_telemetryTimer >= telemetryIntervalSeconds)
            {
                _telemetryTimer = 0f;
                Send(TelemetryFrame.Make(1f / Mathf.Max(Time.unscaledDeltaTime, 1e-3f), _lastAnimState));
            }
        }

        // -------------------------------------------------------------------
        // Background worker
        // -------------------------------------------------------------------

        private async Task RunAsync(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                try
                {
                    _ws = new ClientWebSocket();
                    await _ws.ConnectAsync(new Uri(url), token);
                    Debug.Log($"[OpenMimicry] connected to {url}");
                    _backoff = Mathf.Max(0.1f, initialBackoffSeconds);

                    var sendTask = PumpOutboundAsync(_ws, token);
                    await PumpInboundAsync(_ws, token);
                    await sendTask;
                }
                catch (OperationCanceledException)
                {
                    return;
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[OpenMimicry] WS error: {ex.Message}");
                }
                finally
                {
                    try { _ws?.Dispose(); } catch { /* ignore */ }
                    _ws = null;
                }

                // Exponential backoff before retrying.
                await Task.Delay(TimeSpan.FromSeconds(_backoff), token).ContinueWith(_ => { });
                _backoff = Mathf.Min(maxBackoffSeconds, _backoff * 2f);
            }
        }

        private async Task PumpInboundAsync(ClientWebSocket ws, CancellationToken token)
        {
            var buffer = new byte[8192];
            var sb = new StringBuilder();
            while (ws.State == WebSocketState.Open && !token.IsCancellationRequested)
            {
                WebSocketReceiveResult result;
                sb.Clear();
                do
                {
                    var segment = new ArraySegment<byte>(buffer);
                    result = await ws.ReceiveAsync(segment, token);
                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "bye", token);
                        return;
                    }
                    sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                } while (!result.EndOfMessage);
                _inbound.Enqueue(sb.ToString());
            }
        }

        private async Task PumpOutboundAsync(ClientWebSocket ws, CancellationToken token)
        {
            while (ws.State == WebSocketState.Open && !token.IsCancellationRequested)
            {
                if (_outbound.TryDequeue(out var raw))
                {
                    var bytes = Encoding.UTF8.GetBytes(raw);
                    await ws.SendAsync(
                        new ArraySegment<byte>(bytes),
                        WebSocketMessageType.Text,
                        endOfMessage: true,
                        token);
                }
                else
                {
                    await Task.Delay(20, token);
                }
            }
        }

        // -------------------------------------------------------------------
        // Dispatch + ack
        // -------------------------------------------------------------------

        private void DispatchFrame(string raw)
        {
            string type = TypeOf(raw);
            if (string.IsNullOrEmpty(type)) return;
            foreach (var sub in _subscribers)
            {
                try
                {
                    sub.Invoke(type, raw);
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"[OpenMimicry] subscriber error: {ex.Message}");
                }
            }
            if (type == "avatar.directive")
            {
                Send(AckFrame.Make("avatar.directive"));
            }
        }

        private static string TypeOf(string raw)
        {
            try
            {
                var env = JsonUtility.FromJson<Envelope>(raw);
                return env?.type ?? string.Empty;
            }
            catch (Exception)
            {
                return string.Empty;
            }
        }
    }
}
