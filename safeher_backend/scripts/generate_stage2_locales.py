#!/usr/bin/env python3
"""Generate Stage-2 Hindi + Marathi string overlays (critical UX paths)."""

from pathlib import Path

RES = Path(__file__).resolve().parents[2] / "safeher_android" / "app" / "src" / "main" / "res"

# Critical user-facing strings for SOS / auth / errors / contacts / offline.
# Remaining keys fall back to values/strings.xml (English).
HI = {
    "app_name": "SafeHer",
    "login_title": "वापसी पर स्वागत है",
    "login_button": "लॉग इन",
    "register_title": "खाता बनाएँ",
    "register_button": "रजिस्टर",
    "field_phone": "फ़ोन नंबर",
    "field_password": "पासवर्ड",
    "field_name": "पूरा नाम",
    "otp_title": "फ़ोन सत्यापित करें",
    "otp_subtitle": "%1$s पर भेजा गया 6-अंकों का कोड दर्ज करें",
    "otp_resend": "OTP फिर भेजें",
    "session_expired_title": "सत्र समाप्त",
    "session_expired_message": "आपका सत्र समाप्त हो गया है। जारी रखने के लिए फिर से लॉग इन करें।",
    "session_expired_login": "फिर से लॉग इन करें",
    "logout": "लॉग आउट",
    "action_sos": "एसओएस",
    "action_contacts": "आपातकालीन संपर्क",
    "error_offline_title": "इंटरनेट कनेक्शन नहीं",
    "error_offline_banner": "आप ऑफ़लाइन हैं",
    "error_network": "नेटवर्क त्रुटि। अपना कनेक्शन जाँचें।",
    "action_retry": "फिर कोशिश करें",
    "contacts_empty_title": "कोई आपातकालीन संपर्क नहीं",
    "contacts_empty_message": "आपातकाल में सूचित किए जाने वाले अधिकतम 5 भरोसेमंद संपर्क जोड़ें।",
    "contacts_add_title": "आपातकालीन संपर्क जोड़ें",
    "contacts_save": "संपर्क सहेजें",
    "sos_title": "आपातकालीन एसओएस",
    "sos_subtitle": "अपने संपर्कों को आपातकालीन अलर्ट भेजने के लिए नीचे बटन दबाकर रखें।",
    "sos_countdown_title": "एसओएस भेजा जा रहा है…",
    "sos_countdown_subtitle": "आपके आपातकालीन संपर्कों को सूचित किया जाएगा। रोकने के लिए रद्द करें टैप करें।",
    "sos_countdown_cancel": "एसओएस रद्द करें",
    "sos_active_title": "अलर्ट सक्रिय",
    "sos_active_message": "आपके आपातकालीन संपर्कों को सूचित कर दिया गया है। सुरक्षित रहें — मदद आ रही है।",
    "sos_cancel_button": "एसओएस अलर्ट रद्द करें",
    "sos_cancel_title": "आपातकालीन अलर्ट रद्द करें?",
    "sos_cancel_message": "इससे आपके संपर्कों को बताया जाएगा कि आप सुरक्षित हैं। क्या आप सुनिश्चित हैं?",
    "sos_cancel_confirm": "हाँ, मैं सुरक्षित हूँ",
    "sos_offline_queued": "एसओएस कतार में है। ऑनलाइन होने पर आपका अलर्ट अपने आप भेजा जाएगा।",
    "sos_preflight_title": "एसओएस तत्परता",
    "sos_preflight_network": "इंटरनेट कनेक्शन",
    "sos_preflight_network_hint": "ऑफ़लाइन में कतार लग सकती है, लेकिन डिलीवरी के लिए कनेक्शन ज़रूरी है।",
    "sos_preflight_notifications": "सूचनाएँ",
    "sos_preflight_notifications_hint": "फ़ोरग्राउंड एसओएस और लोकेशन सेवा अलर्ट के लिए आवश्यक।",
    "sos_preflight_location": "लोकेशन अनुमति",
    "sos_location_unavailable_warning": "लोकेशन उपलब्ध नहीं — अलर्ट फिर भी भेजा जाएगा, लेकिन निर्देशांक नहीं मिल सकते।",
    "location_permission_required_title": "लोकेशन एक्सेस आवश्यक",
    "location_permission_required_message": "एसओएस के दौरान आपातकालीन संपर्कों से अपनी स्थिति साझा करने के लिए SafeHer को लोकेशन चाहिए।",
    "ai_audio_permission_required": "ऑडियो संकट पहचान के लिए माइक्रोफ़ोन एक्सेस आवश्यक है।",
}

MR = {
    "app_name": "SafeHer",
    "login_title": "पुन्हा स्वागत आहे",
    "login_button": "लॉग इन",
    "register_title": "खाते तयार करा",
    "register_button": "नोंदणी",
    "field_phone": "फोन नंबर",
    "field_password": "पासवर्ड",
    "field_name": "पूर्ण नाव",
    "otp_title": "फोन पडताळा",
    "otp_subtitle": "%1$s वर पाठवलेला ६-अंकी कोड टाका",
    "otp_resend": "OTP पुन्हा पाठवा",
    "session_expired_title": "सत्र संपले",
    "session_expired_message": "तुमचे सत्र संपले आहे. पुढे जाण्यासाठी पुन्हा लॉग इन करा.",
    "session_expired_login": "पुन्हा लॉग इन करा",
    "logout": "लॉग आउट",
    "action_sos": "SOS",
    "action_contacts": "आपत्कालीन संपर्क",
    "error_offline_title": "इंटरनेट कनेक्शन नाही",
    "error_offline_banner": "तुम्ही ऑफलाइन आहात",
    "error_network": "नेटवर्क त्रुटी. कनेक्शन तपासा.",
    "action_retry": "पुन्हा प्रयत्न करा",
    "contacts_empty_title": "आपत्कालीन संपर्क नाहीत",
    "contacts_empty_message": "आपत्कालीन स्थितीत सूचित करण्यासाठी जास्तीत जास्त ५ विश्वासू संपर्क जोडा.",
    "contacts_add_title": "आपत्कालीन संपर्क जोडा",
    "contacts_save": "संपर्क जतन करा",
    "sos_title": "आपत्कालीन SOS",
    "sos_subtitle": "संपर्कांना आपत्कालीन सूचना पाठवण्यासाठी खालील बटण दाबा आणि धरून ठेवा.",
    "sos_countdown_title": "SOS पाठवत आहे…",
    "sos_countdown_subtitle": "तुमच्या आपत्कालीन संपर्कांना कळवले जाईल. थांबवण्यासाठी रद्द करा टॅप करा.",
    "sos_countdown_cancel": "SOS रद्द करा",
    "sos_active_title": "अलर्ट सक्रिय",
    "sos_active_message": "तुमच्या आपत्कालीन संपर्कांना कळवले आहे. सुरक्षित रहा — मदत येत आहे.",
    "sos_cancel_button": "SOS अलर्ट रद्द करा",
    "sos_cancel_title": "आपत्कालीन अलर्ट रद्द करायचा?",
    "sos_cancel_message": "यामुळे संपर्कांना कळेल की तुम्ही सुरक्षित आहात. खात्री आहे का?",
    "sos_cancel_confirm": "होय, मी सुरक्षित आहे",
    "sos_offline_queued": "SOS रांगेत आहे. ऑनलाइन झाल्यावर अलर्ट आपोआप पाठवला जाईल.",
    "sos_preflight_title": "SOS तयारी",
    "sos_preflight_network": "इंटरनेट कनेक्शन",
    "sos_preflight_network_hint": "ऑफलाइन रांग शक्य आहे, पण डिलिव्हरीसाठी कनेक्शन आवश्यक.",
    "sos_preflight_notifications": "सूचना",
    "sos_preflight_notifications_hint": "फोरग्राउंड SOS आणि लोकेशन सेवा सूचनांसाठी आवश्यक.",
    "sos_preflight_location": "लोकेशन परवानगी",
    "sos_location_unavailable_warning": "लोकेशन उपलब्ध नाही — अलर्ट तरीही जाईल, पण निर्देशांक मिळणार नाहीत.",
    "location_permission_required_title": "लोकेशन प्रवेश आवश्यक",
    "location_permission_required_message": "SOS दरम्यान आपत्कालीन संपर्कांना स्थान शेअर करण्यासाठी SafeHer ला लोकेशन हवे.",
    "ai_audio_permission_required": "ऑडिओ संकट ओळखीसाठी मायक्रोफोन प्रवेश आवश्यक आहे.",
}


def write_locale(folder: str, mapping: dict[str, str]) -> None:
    out_dir = RES / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<resources>"]
    for key, value in mapping.items():
        safe = (
            value.replace("&", "&amp;")
            .replace("'", "\\'")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        lines.append(f'    <string name="{key}">{safe}</string>')
    lines.append("</resources>")
    (out_dir / "strings.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(mapping)} strings -> {out_dir / 'strings.xml'}")


if __name__ == "__main__":
    write_locale("values-hi", HI)
    write_locale("values-mr", MR)
