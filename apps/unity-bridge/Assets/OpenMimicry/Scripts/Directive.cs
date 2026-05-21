// SPDX-License-Identifier: MIT
//
// Wire-protocol DTOs for the OpenMimicry Unity bridge.
//
// Mirrors `docs/contracts.md` §9 (Unity additive amendment) and
// `packages/openmimicry-avatar/src/openmimicry/avatar/runtimes/unity/transports.py`.
//
// Unity ships `JsonUtility`, which is happy with public fields on
// `[Serializable]` classes. We keep one class per inbound frame
// `type` and a small envelope that pulls only the `type` field out.

using System;
using UnityEngine;

namespace OpenMimicry
{
    [Serializable]
    public class Envelope
    {
        public string type;
    }

    [Serializable]
    public class Directive
    {
        public string state;
        public string emotion;
        public string animation;
        public bool speaking;
        public string text;
        public string next_state;
        public int duration_ms;
        public float intensity;
        public string gesture;
        public string gaze;
    }

    [Serializable]
    public class AvatarDirectiveFrame
    {
        public string type;
        public string runtime;
        public Directive directive;
        public bool speaking;
        public string text;
    }

    [Serializable]
    public class LoadCharacterFrame
    {
        public string type;
        public string id;
        public string asset_url;
    }

    [Serializable]
    public class SetVisibilityFrame
    {
        public string type;
        public bool visible;
    }

    [Serializable]
    public class BubbleTextFrame
    {
        public string type;
        public string text;
        public bool complete;
    }

    // Outbound (Unity -> backend) frames.

    [Serializable]
    public class AckFrame
    {
        public string type;
        public string @for;

        public static string Make(string forType)
        {
            return JsonUtility.ToJson(new AckFrame { type = "ack", @for = forType });
        }
    }

    [Serializable]
    public class TelemetryFrame
    {
        public string type;
        public float fps;
        public string anim_state;

        public static string Make(float fps, string animState)
        {
            return JsonUtility.ToJson(new TelemetryFrame
            {
                type = "telemetry",
                fps = fps,
                anim_state = animState,
            });
        }
    }
}
