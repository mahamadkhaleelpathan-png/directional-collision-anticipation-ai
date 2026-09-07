"""Multilingual phrase tables and the localized alert builder for the voice
safety assistant.

Design rules:
- The backend risk engine is still the single source of truth. This module
  only formats the same validated threat into a spoken sentence in the
  selected language.
- Every language table is a deterministic set of plain-string segments, so
  the exact wording cannot drift and is unit-testable.
- Phrase generation is fully local (no LLM / translation service), keeping
  threat-to-speech latency low (REAL-TIME, AUTOMATIC, SIMULTANEOUS).
- ``te-IN`` (Telugu) is the default language. ``hi-IN`` (Hindi) and the other
  Indian languages are selectable from the HUD; ``en-IN`` is the safe
  fallback when a requested code is unknown (never silently fake speech — the
  caller surfaces ``fallback_language``).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

# Item 21: supported Indian/Indian-English language codes.
LANGUAGE_CODES: Tuple[str, ...] = (
    "en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "ml-IN",
    "mr-IN", "gu-IN", "bn-IN", "pa-IN", "or-IN", "ur-IN",
)

# Default language (item 21 / HUD "Current Language" default).
DEFAULT_LANGUAGE: str = "te-IN"

_FALLBACK_LANGUAGE: str = "en-IN"

# Native-name labels shown in the HUD language selector (item 21).
LANGUAGE_LABELS: Dict[str, str] = {
    "en-IN": "English (India)",
    "hi-IN": "हिन्दी (Hindi)",
    "te-IN": "తెలుగు (Telugu)",
    "ta-IN": "தமிழ் (Tamil)",
    "kn-IN": "ಕನ್ನಡ (Kannada)",
    "ml-IN": "മലയാളം (Malayalam)",
    "mr-IN": "मराठी (Marathi)",
    "gu-IN": "ગુજરાતી (Gujarati)",
    "bn-IN": "বাংলা (Bengali)",
    "pa-IN": "ਪੰਜਾਬੀ (Punjabi)",
    "or-IN": "ଓଡ଼ିଆ (Odia)",
    "ur-IN": "اردو (Urdu)",
}

# "Test voice" strings per language (item 48).
_TEST_TEXTS: Dict[str, str] = {
    "en-IN": "Voice assistant test successful.",
    "hi-IN": "वॉइस असिस्टेंट परीक्षण सफल रहा।",
    "te-IN": "వాయిస్ అసిస్టెంట్ పరీక్ష విజయవంతంగా పూర్తయింది.",
    "ta-IN": "குரல் உதவியாளர் சோதனை வெற்றிகரமாக முடிந்தது.",
    "kn-IN": "ಧ್ವನಿ ಸಹಾಯಕ ಪರೀಕ್ಷೆ ಯಶಸ್ವಿಯಾಗಿ ಪೂರ್ಣಗೊಂಡಿದೆ.",
    "ml-IN": "വോയിസ് അസിസ്റ്റന്റ് പരീക്ഷണം വിജയകരമായി പൂർത്തിയായി.",
    "mr-IN": "व्हॉइस असिस्टंट चाचणी यशस्वीरित्या पूर्ण झाली.",
    "gu-IN": "વૉઇસ આસિસ્ટન્ટ પરીક્ષણ સફળતાપૂર્વક પૂર્ણ થયું.",
    "bn-IN": "ভয়েস সহকারী পরীক্ষা সফলভাবে সম্পন্ন হয়েছে।",
    "pa-IN": "ਵੌਇਸ ਸਹਾਇਕ ਟੈਸਟ ਸਫਲਤਾਪੂਰਵਕ ਪੂਰਾ ਹੋਇਆ।",
    "or-IN": "ଭଏସ୍ ସହାୟକ ପରୀକ୍ଷା ସଫଳଭାବେ ସମ୍ପନ୍ନ ହେଲା।",
    "ur-IN": "وائس اسسٹنٹ ٹیسٹ کامیابی سے مکمل ہوا۔",
}

# ---------------------------------------------------------------------------
# Segment keys used by the generic composer:
#   head_* / risk_*      : sentence heads + risk noun phrases
#   from_left / from_right / from_ahead / nearby : approach phrases
#   loc_left / loc_right / loc_ahead             : location phrases
#   object_detected      : LOW-level announcement prefix
#   vehicle              : "vehicle #{id}"  -> "{id}" placeholder
#   moving_at            : "{speed}" placeholder (km/h)
#   seconds              : "{ttc}" placeholder (s, one decimal)
#   slowdown_crit / reduce_high : closing imperative
#   safe_clear           : SAFE sentence (item 12 / 46)
#   base_medium/base_high/base_critical : exact per-level sentences (item 12)
# ---------------------------------------------------------------------------

_EN: Dict[str, str] = {
    "head_critical": "Emergency! ",
    "head_high": "Warning. ",
    "head_medium": "Caution. ",
    "risk_critical": "Critical collision risk",
    "risk_high": "High collision risk",
    "risk_medium": "Medium collision risk",
    "from_left": "from your left",
    "from_right": "from your right",
    "from_ahead": "from ahead",
    "nearby": "nearby",
    "loc_left": "on your left",
    "loc_right": "on your right",
    "loc_ahead": "ahead",
    "object_detected": "Object detected",
    "vehicle": "vehicle #{id}",
    "moving_at": "moving at approximately {speed} kilometers per hour",
    "seconds": "in about {ttc} seconds",
    "slowdown_crit": "Slow down immediately.",
    "reduce_high": "Reduce speed.",
    "safe_clear": "Road ahead is clear.",
    "base_medium": "Caution. Medium collision risk detected.",
    "base_high": "Warning. High collision risk detected.",
    "base_critical": "Emergency. Critical collision risk. Slow down immediately.",
}

_TE: Dict[str, str] = {
    "head_critical": "అత్యవసరం! ",
    "head_high": "హెచ్చరిక. ",
    "head_medium": "జాగ్రత్త. ",
    "risk_critical": "క్లిష్టమైన తాకిడి ప్రమాదం",
    "risk_high": "అధిక తాకిడి ప్రమాదం",
    "risk_medium": "మితమైన తాకిడి ప్రమాదం",
    "from_left": "మీ ఎడమ వైపు నుండి",
    "from_right": "మీ కుడి వైపు నుండి",
    "from_ahead": "ముందు నుండి",
    "nearby": "సమీపంలో",
    "loc_left": "మీ ఎడమ వైపు",
    "loc_right": "మీ కుడి వైపు",
    "loc_ahead": "ముందు",
    "object_detected": "ప్రమాదకర వస్తువు కనుగొనబడింది",
    "vehicle": "వాహనం {id}",
    "moving_at": "సుమారు {speed} కిలోమీటర్ల వేగంతో కదులుతోంది",
    "seconds": "సుమారు {ttc} సెకన్లలో",
    "slowdown_crit": "వెంటనే వేగం తగ్గించండి.",
    "reduce_high": "వేగం తగ్గించండి.",
    "safe_clear": "ముందు మార్గం స్పష్టంగా ఉంది.",
    "base_medium": "జాగ్రత్త. మితమైన తాకిడి ప్రమాదం కనుగొనబడింది.",
    "base_high": "హెచ్చరిక. అధిక తాకిడి ప్రమాదం కనుగొనబడింది.",
    "base_critical": "అత్యవసరం! క్లిష్టమైన తాకిడి ప్రమాదం. వెంటనే వేగం తగ్గించండి.",
}

_HI: Dict[str, str] = {
    "head_critical": "आपातकाल! ",
    "head_high": "चेतावनी. ",
    "head_medium": "सावधानी. ",
    "risk_critical": "गंभीर टक्कर जोखिम",
    "risk_high": "उच्च टक्कर जोखिम",
    "risk_medium": "मध्यम टक्कर जोखिम",
    "from_left": "आपकी बाईं ओर से",
    "from_right": "आपकी दाईं ओर से",
    "from_ahead": "सामने से",
    "nearby": "पास में",
    "loc_left": "आपकी बाईं ओर",
    "loc_right": "आपकी दाईं ओर",
    "loc_ahead": "सामने",
    "object_detected": "खतरनाक वस्तु पहचानी गई",
    "vehicle": "वाहन {id}",
    "moving_at": "लगभग {speed} किलोमीटर प्रति घंटे की रफ़्तार से चल रहा है",
    "seconds": "लगभग {ttc} सेकंड में",
    "slowdown_crit": "तुरंत गति कम करें।",
    "reduce_high": "गति कम करें।",
    "safe_clear": "आगे की सड़क साफ़ है।",
    "base_medium": "सावधानी. मध्यम टक्कर जोखिम का पता चला।",
    "base_high": "चेतावनी. उच्च टक्कर जोखिम का पता चला।",
    "base_critical": "आपातकाल! गंभीर टक्कर जोखिम. तुरंत गति कम करें।",
}

_TA: Dict[str, str] = {
    "head_critical": "அவசரம்! ",
    "head_high": "எச்சரிக்கை. ",
    "head_medium": "கவனம். ",
    "risk_critical": "மிகக் கடுமையான மோதல் ஆபத்து",
    "risk_high": "அதிக மோதல் ஆபத்து",
    "risk_medium": "மிதமான மோதல் ஆபத்து",
    "from_left": "உங்கள் இடது பக்கத்திலிருந்து",
    "from_right": "உங்கள் வலது பக்கத்திலிருந்து",
    "from_ahead": "முன்னால் இருந்து",
    "nearby": "அருகில்",
    "loc_left": "உங்கள் இடது பக்கத்தில்",
    "loc_right": "உங்கள் வலது பக்கத்தில்",
    "loc_ahead": "முன்னால்",
    "object_detected": "அபாய வாகனம் கண்டறியப்பட்டது",
    "vehicle": "வாகனம் {id}",
    "moving_at": "தோராயமாக {speed} கிலோமீட்டர் வேகத்தில் செல்கிறது",
    "seconds": "சுமார் {ttc} வினாடிகளில்",
    "slowdown_crit": "உடனடியாக வேகத்தைக் குறைக்கவும்.",
    "reduce_high": "வேகத்தைக் குறைக்கவும்.",
    "safe_clear": "முன்னால் சாலை தெளிவாக உள்ளது.",
    "base_medium": "கவனம். மிதமான மோதல் ஆபத்து கண்டறியப்பட்டது.",
    "base_high": "எச்சரிக்கை. அதிக மோதல் ஆபத்து கண்டறியப்பட்டது.",
    "base_critical": "அவசரம்! மிகக் கடுமையான மோதல் ஆபத்து. உடனடியாக வேகத்தைக் குறைக்கவும்.",
}

_KN: Dict[str, str] = {
    "head_critical": "ತುರ್ತು! ",
    "head_high": "ಎಚ್ಚರಿಕೆ. ",
    "head_medium": "ಎಚ್ಚರ. ",
    "risk_critical": "ಗಂಭೀರ ಘರ್ಷಣೆ ಅಪಾಯ",
    "risk_high": "ಹೆಚ್ಚಿನ ಘರ್ಷಣೆ ಅಪಾಯ",
    "risk_medium": "ಮಧ್ಯಮ ಘರ್ಷಣೆ ಅಪಾಯ",
    "from_left": "ನಿಮ್ಮ ಎಡಭಾಗದಿಂದ",
    "from_right": "ನಿಮ್ಮ ಬಲಭಾಗದಿಂದ",
    "from_ahead": "ಮುಂದೆ ಇಂದ",
    "nearby": "ಹತ್ತಿರ",
    "loc_left": "ನಿಮ್ಮ ಎಡಭಾಗದಲ್ಲಿ",
    "loc_right": "ನಿಮ್ಮ ಬಲಭಾಗದಲ್ಲಿ",
    "loc_ahead": "ಮುಂದೆ",
    "object_detected": "ಅಪಾಯಕಾರಿ ವಸ್ತು ಪತ್ತೆಯಾಗಿದೆ",
    "vehicle": "ವಾಹನ {id}",
    "moving_at": "ಸುಮಾರು {speed} ಕಿಲೋಮೀಟರ್ ವೇಗದಲ್ಲಿ ಚಲಿಸುತ್ತಿದೆ",
    "seconds": "ಸುಮಾರು {ttc} ಸೆಕೆಂಡುಗಳಲ್ಲಿ",
    "slowdown_crit": "ತಕ್ಷಣ ವೇಗವನ್ನು ಕಡಿಮೆ ಮಾಡಿ.",
    "reduce_high": "ವೇಗವನ್ನು ಕಡಿಮೆ ಮಾಡಿ.",
    "safe_clear": "ಮುಂದೆ ರಸ್ತೆ ಸ್ಪಷ್ಟವಾಗಿದೆ.",
    "base_medium": "ಎಚ್ಚರ. ಮಧ್ಯಮ ಘರ್ಷಣೆ ಅಪಾಯ ಪತ್ತೆಯಾಗಿದೆ.",
    "base_high": "ಎಚ್ಚರಿಕೆ. ಹೆಚ್ಚಿನ ಘರ್ಷಣೆ ಅಪಾಯ ಪತ್ತೆಯಾಗಿದೆ.",
    "base_critical": "ತುರ್ತು! ಗಂಭೀರ ಘರ್ಷಣೆ ಅಪಾಯ. ತಕ್ಷಣ ವೇಗವನ್ನು ಕಡಿಮೆ ಮಾಡಿ.",
}

_ML: Dict[str, str] = {
    "head_critical": "അടിയന്തരം! ",
    "head_high": "മുന്നറിയിപ്പ്. ",
    "head_medium": "ശ്രദ്ധിക്കുക. ",
    "risk_critical": "ഗുരുതരമായ കൂട്ടിയിടി അപകടം",
    "risk_high": "ഉയർന്ന കൂട്ടിയിടി അപകടം",
    "risk_medium": "മിതമായ കൂട്ടിയിടി അപകടം",
    "from_left": "നിങ്ങളുടെ ഇടതുവശത്ത് നിന്ന്",
    "from_right": "നിങ്ങളുടെ വലതുവശത്ത് നിന്ന്",
    "from_ahead": "മുന്നിൽ നിന്ന്",
    "nearby": "സമീപത്ത്",
    "loc_left": "നിങ്ങളുടെ ഇടതുവശത്ത്",
    "loc_right": "നിങ്ങളുടെ വലതുവശത്ത്",
    "loc_ahead": "മുന്നിൽ",
    "object_detected": "അപകട വാഹനം കണ്ടെത്തി",
    "vehicle": "വാഹനം {id}",
    "moving_at": "ഏകദേശം {speed} കിലോമീറ്റർ വേഗതയിൽ നീങ്ങുന്നു",
    "seconds": "ഏകദേശം {ttc} സെക്കൻഡിനുള്ളിൽ",
    "slowdown_crit": "ഉടൻ വേഗത കുറയ്ക്കുക.",
    "reduce_high": "വേഗത കുറയ്ക്കുക.",
    "safe_clear": "മുന്നിലെ റോഡ് വ്യക്തമാണ്.",
    "base_medium": "ശ്രദ്ധിക്കുക. മിതമായ കൂട്ടിയിടി അപകടം കണ്ടെത്തി.",
    "base_high": "മുന്നറിയിപ്പ്. ഉയർന്ന കൂട്ടിയിടി അപകടം കണ്ടെത്തി.",
    "base_critical": "അടിയന്തരം! ഗുരുതരമായ കൂട്ടിയിടി അപകടം. ഉടൻ വേഗത കുറയ്ക്കുക.",
}

_MR: Dict[str, str] = {
    "head_critical": "आपत्कालीन! ",
    "head_high": "चेतावणी. ",
    "head_medium": "सावधानता. ",
    "risk_critical": "गंभीर टक्कर धोका",
    "risk_high": "उच्च टक्कर धोका",
    "risk_medium": "मध्यम टक्कर धोका",
    "from_left": "तुमच्या डावीकडून",
    "from_right": "तुमच्या उजवीकडून",
    "from_ahead": "समोरून",
    "nearby": "जवळ",
    "loc_left": "तुमच्या डाव्या बाजूला",
    "loc_right": "तुमच्या उजव्या बाजूला",
    "loc_ahead": "समोर",
    "object_detected": "धोकादायक वस्तू आढळली",
    "vehicle": "वाहन {id}",
    "moving_at": "अंदाजे {speed} किलोमीटर प्रति तास वेगाने जात आहे",
    "seconds": "सुमारे {ttc} सेकंदांत",
    "slowdown_crit": "लगेच वेग कमी करा.",
    "reduce_high": "वेग कमी करा.",
    "safe_clear": "समोरचा रस्ता स्पष्ट आहे.",
    "base_medium": "सावधानता. मध्यम टक्कर धोका आढळला.",
    "base_high": "चेतावणी. उच्च टक्कर धोका आढळला.",
    "base_critical": "आपत्कालीन! गंभीर टक्कर धोका. लगेच वेग कमी करा.",
}

_GU: Dict[str, str] = {
    "head_critical": "કટોકટી! ",
    "head_high": "ચેતવણી. ",
    "head_medium": "સાવધાન. ",
    "risk_critical": "ગંભીર અથડામણ જોખમ",
    "risk_high": "ઉચ્ચ અથડામણ જોખમ",
    "risk_medium": "મધ્યમ અથડામણ જોખમ",
    "from_left": "તમારી ડાબી બાજુથી",
    "from_right": "તમારી જમણી બાજુથી",
    "from_ahead": "સામેથી",
    "nearby": "નજીક",
    "loc_left": "તમારી ડાબી બાજુ",
    "loc_right": "તમારી જમણી બાજુ",
    "loc_ahead": "સામે",
    "object_detected": "જોખમી વસ્તુ શોધાઈ",
    "vehicle": "વાહન {id}",
    "moving_at": "આશરે {speed} કિલોમીટર પ્રતિ કલાકની ઝડપે આગળ વધી રહ્યું છે",
    "seconds": "લગભગ {ttc} સેકન્ડમાં",
    "slowdown_crit": "તરત જ ઝડપ ઓછી કરો.",
    "reduce_high": "ઝડપ ઓછી કરો.",
    "safe_clear": "આગળનો રસ્તો સ્પષ્ટ છે.",
    "base_medium": "સાવધાન. મધ્યમ અથડામણ જોખમ શોધાયું.",
    "base_high": "ચેતવણી. ઉચ્ચ અથડામણ જોખમ શોધાયું.",
    "base_critical": "કટોકટી! ગંભીર અથડામણ જોખમ. તરત જ ઝડપ ઓછી કરો.",
}

_BN: Dict[str, str] = {
    "head_critical": "জরুরি! ",
    "head_high": "সতর্কতা. ",
    "head_medium": "সাবধান. ",
    "risk_critical": "গুরুতর সংঘর্ষের ঝুঁকি",
    "risk_high": "উচ্চ সংঘর্ষের ঝুঁকি",
    "risk_medium": "মাঝারি সংঘর্ষের ঝুঁকি",
    "from_left": "আপনার বাম দিক থেকে",
    "from_right": "আপনার ডান দিক থেকে",
    "from_ahead": "সামনে থেকে",
    "nearby": "কাছাকাছি",
    "loc_left": "আপনার বাম দিকে",
    "loc_right": "আপনার ডান দিকে",
    "loc_ahead": "সামনে",
    "object_detected": "ঝুঁকিপূর্ণ যান শনাক্ত হয়েছে",
    "vehicle": "যানবাহন {id}",
    "moving_at": "প্রায় {speed} কিলোমিটার প্রতি ঘণ্টা গতিতে যাচ্ছে",
    "seconds": "প্রায় {ttc} সেকেন্ডে",
    "slowdown_crit": "অবিলম্বে গতি কমান।",
    "reduce_high": "গতি কমান।",
    "safe_clear": "সামনের রাস্তা পরিষ্কার।",
    "base_medium": "সাবধান. মাঝারি সংঘর্ষের ঝুঁকি শনাক্ত হয়েছে।",
    "base_high": "সতর্কতা. উচ্চ সংঘর্ষের ঝুঁকি শনাক্ত হয়েছে।",
    "base_critical": "জরুরি! গুরুতর সংঘর্ষের ঝুঁকি. অবিলম্বে গতি কমান।",
}

_PA: Dict[str, str] = {
    "head_critical": "ਐਮਰਜੈਂਸੀ! ",
    "head_high": "ਚੇਤਾਵਨੀ. ",
    "head_medium": "ਸਾਵਧਾਨ. ",
    "risk_critical": "ਗੰਭੀਰ ਟੱਕਰ ਦਾ ਖਤਰਾ",
    "risk_high": "ਉੱਚ ਟੱਕਰ ਦਾ ਖਤਰਾ",
    "risk_medium": "ਦਰਮਿਆਨਾ ਟੱਕਰ ਦਾ ਖਤਰਾ",
    "from_left": "ਤੁਹਾਡੇ ਖੱਬੇ ਪਾਸੇ ਤੋਂ",
    "from_right": "ਤੁਹਾਡੇ ਸੱਜੇ ਪਾਸੇ ਤੋਂ",
    "from_ahead": "ਸਾਹਮਣੇ ਤੋਂ",
    "nearby": "ਨੇੜੇ",
    "loc_left": "ਤੁਹਾਡੇ ਖੱਬੇ ਪਾਸੇ",
    "loc_right": "ਤੁਹਾਡੇ ਸੱਜੇ ਪਾਸੇ",
    "loc_ahead": "ਸਾਹਮਣੇ",
    "object_detected": "ਖਤਰਨਾਕ ਵਸਤੂ ਪਛਾਣੀ ਗਈ",
    "vehicle": "ਵਾਹਨ {id}",
    "moving_at": "ਲਗਭਗ {speed} ਕਿਲੋਮੀਟਰ ਪ੍ਰਤੀ ਘੰਟਾ ਦੀ ਰਫ਼ਤਾਰ ਨਾਲ ਜਾ ਰਿਹਾ ਹੈ",
    "seconds": "ਲਗਭਗ {ttc} ਸਕਿੰਟ ਵਿੱਚ",
    "slowdown_crit": "ਤੁਰੰਤ ਰਫ਼ਤਾਰ ਘਟਾਓ।",
    "reduce_high": "ਰਫ਼ਤਾਰ ਘਟਾਓ।",
    "safe_clear": "ਅੱਗੇ ਦਾ ਰਸਤਾ ਸਾਫ਼ ਹੈ।",
    "base_medium": "ਸਾਵਧਾਨ. ਦਰਮਿਆਨਾ ਟੱਕਰ ਦਾ ਖਤਰਾ ਪਛਾਣਿਆ ਗਿਆ।",
    "base_high": "ਚੇਤਾਵਨੀ. ਉੱਚ ਟੱਕਰ ਦਾ ਖਤਰਾ ਪਛਾਣਿਆ ਗਿਆ।",
    "base_critical": "ਐਮਰਜੈਂਸੀ! ਗੰਭੀਰ ਟੱਕਰ ਦਾ ਖਤਰਾ. ਤੁਰੰਤ ਰਫ਼ਤਾਰ ਘਟਾਓ।",
}

_OR: Dict[str, str] = {
    "head_critical": "ଜରୁରୀ! ",
    "head_high": "ସତର୍କତା. ",
    "head_medium": "ସାବଧାନ. ",
    "risk_critical": "ଗମ୍ଭୀର ସଂଘର୍ଷ ବିପଦ",
    "risk_high": "ଉଚ୍ଚ ସଂଘର୍ଷ ବିପଦ",
    "risk_medium": "ମଧ୍ୟମ ସଂଘର୍ଷ ବିପଦ",
    "from_left": "ଆପଣଙ୍କ ବାମ ପାର୍ଶ୍ୱରୁ",
    "from_right": "ଆପଣଙ୍କ ଡାହାଣ ପାର୍ଶ୍ୱରୁ",
    "from_ahead": "ଆଗରୁ",
    "nearby": "ପାଖରେ",
    "loc_left": "ଆପଣଙ୍କ ବାମ ପାର୍ଶ୍ୱରେ",
    "loc_right": "ଆପଣଙ୍କ ଡାହାଣ ପାର୍ଶ୍ୱରେ",
    "loc_ahead": "ଆଗରେ",
    "object_detected": "ଆପଦ ଯାନ ଚିହ୍ନଟ ହେଲା",
    "vehicle": "ଯାନ {id}",
    "moving_at": "ପ୍ରାୟ {speed} କିଲୋମିଟର ପ୍ରତି ଘଣ୍ଟା ଗତିରେ ଚାଲୁଛି",
    "seconds": "ପ୍ରାୟ {ttc} ସେକେଣ୍ଡରେ",
    "slowdown_crit": "ତୁରନ୍ତ ଗତି ହ୍ରାସ କରନ୍ତୁ।",
    "reduce_high": "ଗତି ହ୍ରାସ କରନ୍ତୁ।",
    "safe_clear": "ଆଗରେ ରାସ୍ତା ସ୍ପଷ୍ଟ ଅଛି।",
    "base_medium": "ସାବଧାନ. ମଧ୍ୟମ ସଂଘର୍ଷ ବିପଦ ଚିହ୍ନଟ ହେଲା।",
    "base_high": "ସତର୍କତା. ଉଚ୍ଚ ସଂଘର୍ଷ ବିପଦ ଚିହ୍ନଟ ହେଲା।",
    "base_critical": "ଜରୁରୀ! ଗମ୍ଭୀର ସଂଘର୍ଷ ବିପଦ. ତୁରନ୍ତ ଗତି ହ୍ରାସ କରନ୍ତୁ।",
}

_UR: Dict[str, str] = {
    "head_critical": "ہنگامی! ",
    "head_high": "خبردار. ",
    "head_medium": "احتیاط. ",
    "risk_critical": "شدید تصادم کا خطرہ",
    "risk_high": "زیادہ تصادم کا خطرہ",
    "risk_medium": "درمیانی تصادم کا خطرہ",
    "from_left": "آپ کی بائیں جانب سے",
    "from_right": "آپ کی دائیں جانب سے",
    "from_ahead": "سامنے سے",
    "nearby": "قریب",
    "loc_left": "آپ کی بائیں جانب",
    "loc_right": "آپ کی دائیں جانب",
    "loc_ahead": "سامنے",
    "object_detected": "خطرناک گاڑی پہچان لی گئی",
    "vehicle": "گاڑی {id}",
    "moving_at": "تقریباً {speed} کلومیٹر فی گھنٹہ کی رفتار سے چل رہی ہے",
    "seconds": "تقریباً {ttc} سیکنڈ میں",
    "slowdown_crit": "فوراً رفتار کم کریں۔",
    "reduce_high": "رفتار کم کریں۔",
    "safe_clear": "آگے کی سڑک صاف ہے۔",
    "base_medium": "احتیاط. درمیانی تصادم کا خطرہ پتہ چلا۔",
    "base_high": "خبردار. زیادہ تصادم کا خطرہ پتہ چلا۔",
    "base_critical": "ہنگامی! شدید تصادم کا خطرہ. فوراً رفتار کم کریں۔",
}

_PHRASES: Dict[str, Dict[str, str]] = {
    "en-IN": _EN,
    "hi-IN": _HI,
    "te-IN": _TE,
    "ta-IN": _TA,
    "kn-IN": _KN,
    "ml-IN": _ML,
    "mr-IN": _MR,
    "gu-IN": _GU,
    "bn-IN": _BN,
    "pa-IN": _PA,
    "or-IN": _OR,
    "ur-IN": _UR,
}


def is_supported_language(code: Optional[str]) -> bool:
    """True when ``code`` is one of the supported language tags."""
    return bool(code and code in _PHRASES)


def round_speed(kmh: Optional[float]) -> Optional[int]:
    """Round km/h to the nearest whole number for speech (item 8).

    Returns None for missing/non-finite values so callers can skip the
    speed clause instead of speaking NaN/Infinity.
    """
    try:
        if kmh is None:
            return None
        f = float(kmh)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return int(round(f))


def test_text(language: Optional[str]) -> str:
    """Per-language "Test voice" sentence (item 48)."""
    code = language or DEFAULT_LANGUAGE
    return _TEST_TEXTS.get(code, _TEST_TEXTS[_FALLBACK_LANGUAGE])


def supported_languages() -> List[Dict[str, str]]:
    """Metadata for every supported language (used by the API/HUD)."""
    return [
        {
            "code": code,
            "label": LANGUAGE_LABELS.get(code, code),
            "test": test_text(code),
        }
        for code in LANGUAGE_CODES
    ]


def _resolve_language(language: Optional[str]) -> Dict[str, str]:
    """Phrase table for ``language`` with a safe ``en-IN`` fallback."""
    code = language or DEFAULT_LANGUAGE
    if code in _PHRASES:
        return _PHRASES[code]
    return _PHRASES[_FALLBACK_LANGUAGE]


def _approach(tbl: Dict[str, str], direction: Optional[str]) -> str:
    d = (direction or "AHEAD").upper()
    if d == "LEFT":
        return tbl["from_left"]
    if d == "RIGHT":
        return tbl["from_right"]
    if d == "AHEAD":
        return tbl["from_ahead"]
    return tbl["nearby"]


def _loc(tbl: Dict[str, str], direction: Optional[str]) -> str:
    d = (direction or "AHEAD").upper()
    if d == "LEFT":
        return tbl["loc_left"]
    if d == "RIGHT":
        return tbl["loc_right"]
    if d == "AHEAD":
        return tbl["loc_ahead"]
    return tbl["nearby"]


def build_alert_text_lang(
    risk_level: str,
    direction: Optional[str] = "AHEAD",
    ttc: Optional[float] = None,
    speed_kmh: Optional[float] = None,
    class_name: Optional[str] = None,
    track_id: Optional[int] = None,
    language: str = DEFAULT_LANGUAGE,
    ttc_max_s: float = 10.0,
    include_speed: bool = False,
) -> Tuple[str, str]:
    """Localized sentence builder.

    Returns ``(text, spoken_language)`` where ``spoken_language`` may differ
    from the requested ``language`` when a safe fallback had to be used, so
    the caller can surface the fallback (never fakes multilingual speech).
    ``class_name`` is accepted for API compatibility and not spoken (the
    track number is the stable identity per item 13).
    """
    level = (risk_level or "SAFE").upper()
    tbl = _resolve_language(language)

    if level == "SAFE":
        return tbl["safe_clear"], (language if is_supported_language(language) else _FALLBACK_LANGUAGE)

    approach = _approach(tbl, direction)

    ttc_clause = ""
    if ttc is not None and ttc > 0 and float(ttc) <= ttc_max_s:
        ttc_clause = " " + tbl["seconds"].format(ttc=f"{float(ttc):.1f}")

    speed_clause = ""
    if include_speed and speed_kmh is not None:
        rs = round_speed(speed_kmh)
        if rs is not None and rs > 0:
            veh = tbl["vehicle"].format(id=track_id if track_id is not None else "?")
            sp = tbl["moving_at"].format(speed=rs)
            speed_clause = f", {veh} {sp}"

    has_detail = (direction or "AHEAD").upper() != "AHEAD" or bool(ttc_clause) or bool(speed_clause)

    if level == "CRITICAL":
        if not has_detail:
            return tbl["base_critical"], (language if is_supported_language(language) else _FALLBACK_LANGUAGE)
        return (
            f"{tbl['head_critical']}{tbl['risk_critical']} {approach}{ttc_clause}{speed_clause}."
            f" {tbl['slowdown_crit']}",
            (language if is_supported_language(language) else _FALLBACK_LANGUAGE),
        )
    if level == "HIGH":
        if not has_detail:
            return tbl["base_high"], (language if is_supported_language(language) else _FALLBACK_LANGUAGE)
        return (
            f"{tbl['head_high']}{tbl['risk_high']} {approach}{ttc_clause}{speed_clause}."
            f" {tbl['reduce_high']}",
            (language if is_supported_language(language) else _FALLBACK_LANGUAGE),
        )
    if level == "MEDIUM":
        if not has_detail:
            return tbl["base_medium"], (language if is_supported_language(language) else _FALLBACK_LANGUAGE)
        return (
            f"{tbl['head_medium']}{tbl['risk_medium']} {approach}{ttc_clause}{speed_clause}.",
            (language if is_supported_language(language) else _FALLBACK_LANGUAGE),
        )

    # LOW / any other level: calmly name the location.
    return (
        f"{tbl['object_detected']} {_loc(tbl, direction)}.",
        (language if is_supported_language(language) else _FALLBACK_LANGUAGE),
    )