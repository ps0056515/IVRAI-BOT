from __future__ import annotations

from datetime import datetime

UNIT_KEY_MAP = {"1": "qspiders", "2": "jspiders", "3": "pysiders", "4": "prospiders", "5": "placement", "9": "support"}

COURSE_KEYWORDS = {
    "manual testing": "Manual Testing",
    "selenium": "Selenium Automation",
    "sdet": "SDET",
    "api testing": "API Testing",
    "istqb": "ISTQB Prep",
    "java full stack": "Java Full Stack",
    "core java": "Core Java",
    "j2ee": "Core Java + J2EE",
    "ocjp": "OCJP Track",
    "python full stack": "Python Full Stack",
    "django": "Django Web Development",
    "data science": "Python + Data Science",
    "devops": "DevOps",
}

COUNSELLOR_MAP = {
    "qspiders": {"btm": "Priya S.", "jayanagar": "Karthik R.", "default": "QSpiders Desk"},
    "jspiders": {"rajajinagar": "Anitha M.", "indiranagar": "Vijay K.", "default": "JSpiders Desk"},
    "pysiders": {"hsr": "Madhavi P.", "default": "PySiders Desk"},
    "prospiders": {"default": "ProSpiders Desk"},
    "support": {"default": "Support Queue"},
    "placement": {"default": "Placement Cell"},
}


def detect_unit(transcript: str, ivr_key: str | None) -> str:
    if ivr_key and ivr_key in UNIT_KEY_MAP:
        return UNIT_KEY_MAP[ivr_key]
    text = transcript.lower()
    if "testing" in text or "selenium" in text or "istqb" in text:
        return "qspiders"
    if "java" in text or "j2ee" in text or "ocjp" in text:
        return "jspiders"
    if "python" in text or "django" in text or "data science" in text:
        return "pysiders"
    if "placement" in text:
        return "placement"
    if "support" in text:
        return "support"
    return "qspiders"


def detect_course(transcript: str) -> str | None:
    text = transcript.lower()
    for keyword, course in COURSE_KEYWORDS.items():
        if keyword in text:
            return course
    return None


def detect_student_type(transcript: str) -> str:
    text = transcript.lower()
    if any(k in text for k in ("fresher", "passout", "2024", "2025", "2026", "no experience")):
        return "fresher"
    if any(k in text for k in ("working", "experience", "weekend batch", "job")):
        return "working_professional"
    if any(k in text for k in ("mechanical", "civil", "commerce", "switch", "non-it")):
        return "career_switcher"
    if any(k in text for k in ("existing student", "already enrolled", "support")):
        return "existing_student"
    return "fresher"


def score_and_flags(transcript: str, duration_sec: int, ended_at: str | None) -> tuple[dict[str, bool], int, str]:
    text = transcript.lower()
    flags = {
        "emi_flag": False,
        "referral_flag": False,
        "competitor_flag": False,
        "placement_interest": False,
        "demo_interest": False,
    }
    score = 0

    hour = None
    if ended_at:
        try:
            hour = datetime.fromisoformat(ended_at.replace("Z", "+00:00")).hour
        except ValueError:
            pass
    if hour is not None and (10 <= hour < 12 or 17 <= hour < 19):
        score += 10

    if detect_course(transcript):
        score += 15
    if any(k in text for k in ("my friend", "colleague joined", "someone told me", "batch mate")):
        score += 25
        flags["referral_flag"] = True
    if any(k in text for k in ("emi", "instalment", "installment", "afford", "expensive", "pay in parts")):
        score += 20
        flags["emi_flag"] = True
    if any(k in text for k in ("placement", "companies", "job support", "interview drive")):
        score += 15
        flags["placement_interest"] = True
    if any(k in text for k in ("demo class", "free demo", "walk in")):
        score += 20
        flags["demo_interest"] = True
    if any(k in text for k in ("other institute", "competitor", "niit")):
        score -= 5
        flags["competitor_flag"] = True
    if duration_sec < 60:
        score -= 15

    if score >= 80:
        band = "hot"
    elif score >= 50:
        band = "warm"
    else:
        band = "cold"
    return flags, score, band


def assign_counsellor(unit: str, branch_interest: str | None) -> str:
    branch = (branch_interest or "").lower()
    unit_map = COUNSELLOR_MAP.get(unit, {"default": "Admissions Desk"})
    for key, val in unit_map.items():
        if key != "default" and key in branch:
            return val
    return unit_map.get("default", "Admissions Desk")


def next_action(lead_band: str, emi_flag: bool, demo_interest: bool) -> str:
    if lead_band == "hot":
        return "Immediate callback under 30 minutes and supervisor alert."
    if emi_flag:
        return "Callback within 2 hours and share EMI plan."
    if demo_interest:
        return "Confirm demo attendance today."
    return "Nurture follow-up and callback within 24 hours."


def summary(student_type: str, unit: str, course: str | None, flags: dict[str, bool], score: int, band: str) -> str:
    parts = [f"{student_type.replace('_', ' ').title()} caller for {unit.upper()}"]
    if course:
        parts.append(f"course interest: {course}")
    if flags["emi_flag"]:
        parts.append("EMI discussion captured")
    if flags["referral_flag"]:
        parts.append("referral mention detected")
    if flags["placement_interest"]:
        parts.append("placement query detected")
    parts.append(f"score {score} ({band.upper()})")
    return ". ".join(parts) + "."
