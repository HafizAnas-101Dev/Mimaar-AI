"""Strings for the measurement-only report in English, Urdu and Arabic.

Muse Spark writes the live summary in the chosen language; these templates cover
mock mode and the fallback when the model output is invalid.
"""

LANGUAGE_NAMES = {"en": "English", "ur": "Urdu", "ar": "Arabic"}

DISCLAIMERS = {
    "en": "Estimate only; not an engineering or safety assessment.",
    "ur": "یہ صرف ایک تخمینہ ہے؛ یہ انجینئرنگ یا حفاظتی جائزہ نہیں ہے۔",
    "ar": "هذا تقدير فقط، وليس تقييمًا هندسيًا أو تقييمًا للسلامة.",
}

ELEMENT_NAMES = {
    "ur": {"wall": "دیوار", "floor": "فرش", "ceiling": "چھت", "door": "دروازہ", "window": "کھڑکی", "fixture": "لائٹ فکسچر"},
    "ar": {"wall": "جدار", "floor": "أرضية", "ceiling": "سقف", "door": "باب", "window": "نافذة", "fixture": "وحدة إضاءة"},
}

DEFECT_NAMES = {
    "en": {"crack": "crack", "damp": "damp stain", "peeling": "peeling paint", "misalignment": "misalignment", "other": "defect"},
    "ur": {"crack": "دراڑ", "damp": "نمی کا دھبہ", "peeling": "اکھڑتا پینٹ", "misalignment": "بے ترتیبی", "other": "نقص"},
    "ar": {"crack": "شق", "damp": "بقعة رطوبة", "peeling": "تقشر الطلاء", "misalignment": "عدم استواء", "other": "عيب"},
}

VERTICAL = {
    "en": ("upper", "middle", "lower"),
    "ur": ("اوپری", "درمیانی", "نچلے"),
    "ar": ("العلوي", "الأوسط", "السفلي"),
}
HORIZONTAL = {
    "en": ("left", "centre", "right"),
    "ur": ("بائیں", "درمیانی", "دائیں"),
    "ar": ("الأيسر", "الأوسط", "الأيمن"),
}


def element_parts(counts: list[tuple[str, int]], lang: str) -> str:
    if lang == "en":
        return ", ".join(f"{n} {t}{'s' if n != 1 else ''}" for t, n in counts) or "no elements"
    names = ELEMENT_NAMES[lang]
    return "، ".join(f"{names[t]}: {n}" for t, n in counts) or "—"


ROLE_NAMES = {
    "en": {"floor": "Floor", "ceiling": "Ceiling", "wall": "Wall"},
    "ur": {"floor": "فرش", "ceiling": "چھت", "wall": "دیوار"},
    "ar": {"floor": "الأرضية", "ceiling": "السقف", "wall": "الجدار"},
}


def photo_label(roles: list[str | None], index: int, lang: str) -> str | None:
    """The room slot a photo came from, as the app names it: "Floor", "Wall 2"…"""
    role = roles[index] if 0 <= index < len(roles) else None
    if role is None:
        return None
    name = ROLE_NAMES[lang][role]
    if role == "wall" and roles.count("wall") > 1:
        return f"{name} {roles[: index + 1].count('wall')}"
    return name


def location(row: int, col: int, lang: str, photo: int | None = None, roles: list[str | None] | None = None) -> str:
    """Where a defect is: "Wall 2 · upper left of the photo" in a room, or just the area otherwise."""
    label = photo_label(roles, photo, lang) if roles and photo is not None else None
    if label:
        return f"{label} · {location(row, col, lang)}"
    v, h = VERTICAL[lang][row], HORIZONTAL[lang][col]
    if lang == "ur":
        text = f"تصویر کے {v} {h} حصے میں"
        return f"{text} (تصویر {photo + 1})" if photo is not None else text
    if lang == "ar":
        text = f"في الجزء {v} {h} من الصورة"
        return f"{text} (الصورة {photo + 1})" if photo is not None else text
    text = f"{v} {h} of the photo"
    return f"{text} (photo {photo + 1})" if photo is not None else text


def defect_why(kind: str, share: float, lang: str) -> str:
    name = DEFECT_NAMES[lang][kind]
    if lang == "ur":
        return f"تجزیے نے تصویر کے {share:.2%} حصے پر {name} کی نشاندہی کی۔"
    if lang == "ar":
        return f"رصد التحليل {name} يغطي {share:.2%} من الصورة."
    return f"Segmentation flagged a {name} region covering {share:.2%} of the photo."


def summary(parts: str, defects: int, cost: tuple[float, float, str] | None, photos: int, lang: str) -> str:
    if lang == "ur":
        text = f"تصویر میں یہ عناصر ملے: {parts}۔ {defects} ممکنہ نقائص مزید جانچ کے لیے نشان زد کیے گئے ہیں۔"
        if photos > 1:
            text = f"{photos} تصاویر کا مجموعی جائزہ۔ " + text
        if cost:
            text += f" تخمینی فنشنگ لاگت: {cost[0]:,.0f} سے {cost[1]:,.0f} {cost[2]}۔"
        return text
    if lang == "ar":
        text = f"العناصر المرصودة: {parts}. تم تحديد {defects} من العيوب المحتملة لمزيد من الفحص."
        if photos > 1:
            text = f"تقرير مجمع من {photos} صور. " + text
        if cost:
            text += f" التكلفة التقريبية للتشطيب: من {cost[0]:,.0f} إلى {cost[1]:,.0f} {cost[2]}."
        return text
    text = f"Detected {parts}. {defects} possible defect(s) flagged for a closer look."
    if photos > 1:
        text = f"Combined view of {photos} photos. " + text
    if cost:
        text += f" Rough finishing cost: {cost[0]:,.0f} to {cost[1]:,.0f} {cost[2]}."
    return text
