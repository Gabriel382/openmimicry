// SPDX-License-Identifier: MIT
//
// Bridges OpenMimicry directives into Unity Animator parameters.
//
// Attach this to the GameObject that owns your character's `Animator`.
// Wire a `WSClient` into the same GameObject (or expose it via the
// `wsClient` field). For each inbound `avatar.directive` frame the
// controller:
//
//   * sets the `State` and `Emotion` integer parameters,
//   * sets the `Speaking` bool,
//   * fires the `Gesture` trigger when the frame carries a gesture,
//   * forwards `intensity` to the `Intensity` float parameter,
//   * exposes the gaze hint as a string parameter (`GazeTarget`) on a
//     companion component if you wire one in.
//
// The Unity-side state-machine layout is intentionally generic — any
// Animator with these parameters works.

using UnityEngine;

namespace OpenMimicry
{
    [RequireComponent(typeof(Animator))]
    public class AvatarController : MonoBehaviour
    {
        [Tooltip("The WSClient on the same GameObject (or any other in the scene).")]
        public WSClient wsClient;

        [Tooltip("Optional Renderer toggled by set.visibility frames.")]
        public Renderer visibilityTarget;

        [Tooltip("Optional TextMesh / UI label that mirrors bubble.text frames.")]
        public UnityEngine.UI.Text bubbleLabel;

        private Animator _animator;

        // Animator parameter IDs (resolved once for speed).
        private int _stateId;
        private int _emotionId;
        private int _speakingId;
        private int _gestureId;
        private int _intensityId;

        private void Awake()
        {
            _animator = GetComponent<Animator>();
            _stateId = Animator.StringToHash("State");
            _emotionId = Animator.StringToHash("Emotion");
            _speakingId = Animator.StringToHash("Speaking");
            _gestureId = Animator.StringToHash("Gesture");
            _intensityId = Animator.StringToHash("Intensity");
        }

        private void OnEnable()
        {
            if (wsClient == null)
            {
                wsClient = GetComponent<WSClient>();
            }
            if (wsClient != null)
            {
                wsClient.Subscribe(OnFrame);
            }
        }

        private void OnFrame(string type, string json)
        {
            switch (type)
            {
                case "avatar.directive":
                    ApplyDirective(json);
                    break;
                case "load.character":
                    OnLoad(json);
                    break;
                case "set.visibility":
                    OnVisibility(json);
                    break;
                case "bubble.text":
                    OnBubble(json);
                    break;
            }
        }

        private void ApplyDirective(string json)
        {
            var frame = JsonUtility.FromJson<AvatarDirectiveFrame>(json);
            if (frame?.directive == null) return;

            _animator.SetInteger(_stateId, StateToInt(frame.directive.state));
            _animator.SetInteger(_emotionId, EmotionToInt(frame.directive.emotion));
            _animator.SetBool(_speakingId, frame.directive.speaking);
            _animator.SetFloat(_intensityId, Mathf.Clamp01(frame.directive.intensity > 0
                ? frame.directive.intensity
                : 1f));

            if (!string.IsNullOrEmpty(frame.directive.gesture))
            {
                _animator.SetTrigger(_gestureId);
            }

            wsClient?.SetAnimState(frame.directive.state);
        }

        private void OnLoad(string json)
        {
            var frame = JsonUtility.FromJson<LoadCharacterFrame>(json);
            if (frame == null) return;
            Debug.Log($"[OpenMimicry] load.character id={frame.id} url={frame.asset_url}");
            // Production projects would fetch the asset_url and swap the
            // mesh here. The sample scene keeps the placeholder model in
            // place; the log is enough to verify the bridge.
        }

        private void OnVisibility(string json)
        {
            var frame = JsonUtility.FromJson<SetVisibilityFrame>(json);
            if (visibilityTarget != null)
            {
                visibilityTarget.enabled = frame != null && frame.visible;
            }
        }

        private void OnBubble(string json)
        {
            var frame = JsonUtility.FromJson<BubbleTextFrame>(json);
            if (bubbleLabel != null && frame != null)
            {
                bubbleLabel.text = frame.text ?? string.Empty;
            }
        }

        // ----- mappings to Animator integers --------------------------------

        private static int StateToInt(string state)
        {
            switch (state)
            {
                case "idle": return 0;
                case "listening": return 1;
                case "thinking": return 2;
                case "speaking": return 3;
                case "happy": return 4;
                case "error": return 5;
                default: return 0;
            }
        }

        private static int EmotionToInt(string emotion)
        {
            switch (emotion)
            {
                case "neutral": return 0;
                case "happy": return 1;
                case "sad": return 2;
                case "angry": return 3;
                case "confused": return 4;
                case "focused": return 5;
                case "worried": return 6;
                default: return 0;
            }
        }
    }
}
