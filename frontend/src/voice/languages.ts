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

export const DEFAULT_VOICE_LANGUAGE: VoiceLanguageCode = 'en-IN';

/** One central client-side table: id, English name, native name (Phase 2). */
export interface VoiceLanguageMeta {
  id: VoiceLanguageCode;
  name: string;
  nativeName: string;
}

export const VOICE_LANGUAGES: VoiceLanguageMeta[] = [
  { id: 'en-IN', name: 'English', nativeName: 'English' },
  { id: 'hi-IN', name: 'Hindi', nativeName: 'हिन्दी' },
  { id: 'te-IN', name: 'Telugu', nativeName: 'తెలుగు' },
  { id: 'ta-IN', name: 'Tamil', nativeName: 'தமிழ்' },
  { id: 'kn-IN', name: 'Kannada', nativeName: 'ಕನ್ನಡ' },
  { id: 'ml-IN', name: 'Malayalam', nativeName: 'മലയാളം' },
  { id: 'mr-IN', name: 'Marathi', nativeName: 'मराठी' },
  { id: 'gu-IN', name: 'Gujarati', nativeName: 'ગુજરાતી' },
  { id: 'bn-IN', name: 'Bengali', nativeName: 'বাংলা' },
  { id: 'pa-IN', name: 'Punjabi', nativeName: 'ਪੰਜਾਬੀ' },
  { id: 'or-IN', name: 'Odia', nativeName: 'ଓଡ଼ିଆ' },
  { id: 'ur-IN', name: 'Urdu', nativeName: 'اردو' },
];

export const VOICE_LANGUAGE_LABELS: Record<VoiceLanguageCode, string> = {
  'en-IN': 'English',
  'hi-IN': 'हिन्दी',
  'te-IN': 'తెలుగు',
  'ta-IN': 'தமிழ்',
  'kn-IN': 'ಕನ್ನಡ',
  'ml-IN': 'മലയാളം',
  'mr-IN': 'मराठी',
  'gu-IN': 'ગુજરાતી',
  'bn-IN': 'বাংলা',
  'pa-IN': 'ਪੰਜਾਬੀ',
  'or-IN': 'ଓଡ଼ିଆ',
  'ur-IN': 'اردو',
};

/** Selector label: native name + English name, e.g. "हिन्दी - Hindi". */
export function languageSelectorLabel(code: VoiceLanguageCode): string {
  const meta = VOICE_LANGUAGES.find((m) => m.id === code);
  if (!meta) return code;
  return meta.nativeName === meta.name
    ? meta.name
    : `${meta.nativeName} - ${meta.name}`;
}

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