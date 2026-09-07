/**
 * Client-side mirror of the backend language table (src/voice/languages.py).
 *
 * Kept small and additive: the backend remains the single source of truth for
 * WHAT is spoken; this file only defines what the HUD shows and which local
 * test sentence belongs to which language tag.
 */
export const VOICE_LANGUAGE_CODES = [
  'en-IN',
  'hi-IN',
  'te-IN',
  'ta-IN',
  'kn-IN',
  'ml-IN',
  'mr-IN',
  'gu-IN',
  'bn-IN',
  'pa-IN',
  'or-IN',
  'ur-IN',
] as const;

export type VoiceLanguageCode = (typeof VOICE_LANGUAGE_CODES)[number];

export const DEFAULT_VOICE_LANGUAGE: VoiceLanguageCode = 'te-IN';

export const VOICE_LANGUAGE_LABELS: Record<VoiceLanguageCode, string> = {
  'en-IN': 'English (India)',
  'hi-IN': 'हिन्दी (Hindi)',
  'te-IN': 'తెలుగు (Telugu)',
  'ta-IN': 'தமிழ் (Tamil)',
  'kn-IN': 'ಕನ್ನಡ (Kannada)',
  'ml-IN': 'മലയാളം (Malayalam)',
  'mr-IN': 'मराठी (Marathi)',
  'gu-IN': 'ગુજરાતી (Gujarati)',
  'bn-IN': 'বাংলা (Bengali)',
  'pa-IN': 'ਪੰਜਾਬੀ (Punjabi)',
  'or-IN': 'ଓଡ଼ିଆ (Odia)',
  'ur-IN': 'اردو (Urdu)',
};

/** "Test voice" sentences per language (mirrors backend item 48). */
export const VOICE_TEST_TEXT_BY_LANG: Record<VoiceLanguageCode, string> = {
  'en-IN': 'Voice assistant test successful.',
  'hi-IN': 'वॉइस असिस्टेंट परीक्षण सफल रहा।',
  'te-IN': 'వాయిస్ అసిస్టెంట్ పరీక్ష విజయవంతంగా పూర్తయింది.',
  'ta-IN': 'குரல் உதவியாளர் சோதனை வெற்றிகரமாக முடிந்தது.',
  'kn-IN': 'ಧ್ವನಿ ಸಹಾಯಕ ಪರೀಕ್ಷೆ ಯಶಸ್ವಿಯಾಗಿ ಪೂರ್ಣಗೊಂಡಿದೆ.',
  'ml-IN': 'വോയിസ് അസിസ്റ്റന്റ് പരീക്ഷണം വിജയകരമായി പൂർത്തിയായി.',
  'mr-IN': 'व्हॉइस असिस्टंट चाचणी यशस्वीरित्या पूर्ण झाली.',
  'gu-IN': 'વૉઇસ આસિસ્ટન્ટ પરીક્ષણ સફળતાપૂર્વક પૂર્ણ થયું.',
  'bn-IN': 'ভয়েস সহকারী পরীক্ষা সফলভাবে সম্পন্ন হয়েছে।',
  'pa-IN': 'ਵੌਇਸ ਸਹਾਇਕ ਟੈਸਟ ਸਫਲਤਾਪੂਰਵਕ ਪੂਰਾ ਹੋਇਆ।',
  'or-IN': 'ଭଏସ୍ ସହାୟକ ପରୀକ୍ଷା ସଫଳଭାବେ ସମ୍ପନ୍ନ ହେଲା।',
  'ur-IN': 'وائس اسسٹنٹ ٹیسٹ کامیابی سے مکمل ہوا۔',
};

export function isSupportedLanguage(code: string | undefined | null): code is VoiceLanguageCode {
  return !!code && (VOICE_LANGUAGE_CODES as readonly string[]).includes(code);
}

export function languageLabel(code: string): string {
  return VOICE_LANGUAGE_LABELS[code as VoiceLanguageCode] ?? code;
}