export function speakWithBrowserVoice(text: string): boolean {
  if (!("speechSynthesis" in window) || !text.trim()) return false;

  const utter = new SpeechSynthesisUtterance(text);
  const voices = window.speechSynthesis.getVoices();
  const picked =
    voices.find((v) => /en|fr|pt/i.test(v.lang)) ?? voices[0];

  if (picked) utter.voice = picked;

  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
  return true;
}