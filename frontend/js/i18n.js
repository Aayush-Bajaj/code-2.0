/**
 * i18n.js — Lightweight UI Internationalization (English & Hindi)
 * Note: Official carbon reports remain in English per audit standards.
 * Hindi labels are marked for review in documentation.
 */

export const translations = {
  en: {
    app_title: "Carbon Passport",
    tagline: "Turn factory bills and videos into verified carbon numbers",
    demo_badge: "MSME Demo",
    estimate_warning: "⚠️ Estimate based on operational inputs, not a certified regulatory audit.",
    start_hero_title: "Prove your factory's carbon footprint in minutes",
    start_hero_subtitle: "Designed for Indian MSME suppliers and exporters facing buyer carbon disclosures (CBAM & BRSR). Every number links directly to its source evidence.",
    btn_demo: "Try Demo Factory (Sharma Auto MIDC)",
    btn_upload: "Start With Your Factory Files",
    step1_title: "1. Upload Evidence",
    step1_desc: "Electricity statements, fuel invoices, and short video clips of your machinery running.",
    step2_title: "2. Review & Fill Hours",
    step2_desc: "Confirm OCR extracted amounts and enter typical operating hours per month.",
    step3_title: "3. Export Buyer Report",
    step3_desc: "Get an evidence-backed report and explore digital twin decarbonisation savings.",
    nav_start: "Start",
    nav_upload: "Upload",
    nav_review: "Review",
    nav_results: "Results",
    nav_twin: "Digital Twin",
    nav_report: "Report",
    nav_methods: "Data & Methods",
    scope1_label: "Scope 1 (Direct Fuel)",
    scope2_label: "Scope 2 (Electricity)",
    scope3_label: "Scope 3 (Freight)",
    total_footprint: "Total Carbon Footprint",
    monthly_view: "Monthly View",
    yearly_view: "Per Year",
    data_confidence: "Data Confidence Score",
    btn_view_evidence: "View Evidence",
    evidence_drawer_title: "7-Step Evidence Chain",
    close: "Close",
    theme_light: "Light",
    theme_dark: "Dark",
    theme_projector: "Projector Mode",
  },
  hi: {
    app_title: "कार्बन पासपोर्ट",
    tagline: "फैक्ट्री बिल और वीडियो को सत्यापित कार्बन आंकड़ों में बदलें",
    demo_badge: "एमएसएमई डेमो",
    estimate_warning: "⚠️ परिचालन इनपुट पर आधारित अनुमान, प्रमाणित नियामक ऑडिट नहीं।",
    start_hero_title: "मिनटों में अपनी फैक्ट्री का कार्बन फुटप्रिंट जानें",
    start_hero_subtitle: "भारतीय एमएसएमई आपूर्तिकर्ताओं और निर्यातकों के लिए डिज़ाइन किया गया। प्रत्येक संख्या सीधे अपने मूल साक्ष्य से जुड़ी है।",
    btn_demo: "डेमो फैक्ट्री आज़माएं (शर्मा ऑटो एमआईडीसी)",
    btn_upload: "अपनी फैक्ट्री फ़ाइलों से शुरू करें",
    step1_title: "1. साक्ष्य अपलोड करें",
    step1_desc: "बिजली बिल, ईंधन इनवॉइस और चलती हुई मशीनरी के छोटे वीडियो क्लिप।",
    step2_title: "2. समीक्षा करें और घंटे भरें",
    step2_desc: "निकाली गई राशियों की पुष्टि करें और प्रति माह सामान्य परिचालन घंटे दर्ज करें।",
    step3_title: "3. रिपोर्ट निर्यात करें",
    step3_desc: "साक्ष्य-समर्थित रिपोर्ट प्राप्त करें और डिजिटल ट्विन बचत विकल्पों का पता लगाएं।",
    nav_start: "प्रारंभ",
    nav_upload: "अपलोड",
    nav_review: "समीक्षा",
    nav_results: "परिणाम",
    nav_twin: "डिजिटल ट्विन",
    nav_report: "रिपोर्ट",
    nav_methods: "डेटा और विधियाँ",
    scope1_label: "स्कोप 1 (प्रत्यक्ष ईंधन)",
    scope2_label: "स्कोप 2 (खरीदी गई बिजली)",
    scope3_label: "स्कोप 3 (परिवहन)",
    total_footprint: "कुल कार्बन फुटप्रिंट",
    monthly_view: "मासिक दृश्य",
    yearly_view: "प्रति वर्ष",
    data_confidence: "डेटा विश्वास स्कोर",
    btn_view_evidence: "साक्ष्य देखें",
    evidence_drawer_title: "7-चरणीय साक्ष्य श्रृंखला",
    close: "बंद करें",
    theme_light: "लाइट",
    theme_dark: "डार्क",
    theme_projector: "प्रोजेक्टर मोड",
  }
};

let currentLang = "en";

export function getLang() {
  return currentLang;
}

export function setLang(lang) {
  if (translations[lang]) {
    currentLang = lang;
  }
}

export function t(key) {
  const dict = translations[currentLang] || translations.en;
  return dict[key] || translations.en[key] || key;
}
