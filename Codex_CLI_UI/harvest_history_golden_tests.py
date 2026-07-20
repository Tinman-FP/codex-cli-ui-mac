#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import import_codex_history


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
GOLDEN_TESTS_PATH = DATA_DIR / "golden_tests.json"
HISTORY_TEST_SUMMARY_PATH = DATA_DIR / "history_golden_test_harvest.json"
SESSIONS_DIR = Path.home() / ".codex" / "sessions"
ARCHIVED_SESSIONS_DIR = Path.home() / ".codex" / "archived_sessions"

MAX_PROMPT_CHARS = 900
DEFAULT_LIMIT = 80

SENSITIVE_PATTERNS = (
    (re.compile(r"(?i)(password|passwd|pwd|token|api[_-]?key|secret)\s*[:=]\s*['\"]?[^\\s,'\"]+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(bearer|sk-[a-z0-9_-]{8,})[a-z0-9._-]*"), "[REDACTED_TOKEN]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[REDACTED_PRIVATE_KEY]"),
)

SKIP_PREFIXES = (
    "<environment_context>",
    "<heartbeat>",
    "automation:",
    "automation id:",
    "run a metered",
    "assistant style:",
    "debian gnu/linux comes with absolutely no warranty",
)

QUESTION_STARTERS = (
    "can you",
    "will you",
    "would you",
    "what",
    "how",
    "why",
    "where",
    "when",
    "which",
    "please",
    "i need",
    "lets",
    "let's",
    "fix",
    "diagnose",
    "search",
    "compare",
    "design",
    "create",
    "make",
    "write",
    "upload",
    "update",
    "install",
    "look at",
)

ARTIFACT_OR_CHANGE_TERMS = (
    "create",
    "make",
    "write",
    "build",
    "generate",
    "update",
    "fix",
    "upload",
    "save",
    "install",
    "download",
    "pull",
    "set up",
)

BASE_FORBIDDEN_TERMS = [
    "run failed",
    "no final message returned",
    "no response",
    "load failed",
    "recovery plan:",
    "i do not have access",
    "i don't have access",
    "you can check it yourself",
]

DERIVED_HISTORY_TEST_KEYS = (
    "expectedProjectId",
    "expectedContractKind",
    "taskContractKind",
    "expectedContractGate",
    "requiredContractProof",
    "directAnswer",
    "directTerms",
    "requiredTerms",
    "required",
    "anyTerms",
    "forbiddenTerms",
    "requiresSource",
    "webSearch",
    "contextDependent",
    "minAnalyticalScore",
)

CONTEXT_DEPENDENT_PATTERNS = (
    r"^(?:ok|okay|perfect|awesome|great|fantastic|beautiful)[.! ]*(?:$|what'?s next|next|lets|let's)",
    r"^(?:lets|let's) do it\b",
    r"^(?:lets|let's) do all of (?:it|that|this)\b",
    r"^(?:lets|let's) do all of (?:what )?you recomm?e?nd\b",
    r"^(?:lets|let's)\s+go(?:\s+my\s+brother)?[.!? ]*$",
    r"^(?:lets|let's) follow (?:all of )?your recommendations\b",
    r"^(?:lets|let's) run that test again\b",
    r"^(?:lets|let's) run the complete airflow testing\b",
    r"^can you make the fix\??$",
    r"^will you make the fix\??$",
    r"^can you write a macro to do this for me\??$",
    r"^can we build the complete flow and test it on the simulator\??$",
    r"^fix this\??$",
    r"^what else is left to do\??$",
    r"^what is next\??$",
    r"^what'?s next\??$",
    r"^what do we need to do to move forward\??$",
    r"^what have we completed since\b",
    r"^what did we complete since\b",
    r"^can you create one of each of these options please\??$",
    r"^do i start over or run this on top of what i already have\??$",
    r"^(?:lets|let's)\s+(?:eject|ecect)\s+and\s+try\s+again\b",
    r"^(?:ok|okay)[.! ]*are you unloading now\??$",
    r"^(?:lets|let's) take that step\b",
    r"^(?:lets|let's) move to the next phase\b",
)

CURRENT_SOFTWARE_TERMS = (
    "newer version",
    "new version",
    "latest version",
    "update available",
    "upgrade available",
    "release notes",
    "updates",
    "plugin available",
    "plug-in available",
    "firmware version",
)


def is_macro_usage_missing_context_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        "macro" in lower
        and len(lower) < 140
        and any(
            term in lower
            for term in (
                "how will i use this macro",
                "use this macro",
                "this macro in real life",
                "macro in real life",
            )
        )
    )


def is_speaker_pod_cad_prompt(text):
    lower = str(text or "").lower()
    speaker_terms = (
        "speaker pod",
        "6x9 speaker",
        "6 x 9 speaker",
        "kmxl69",
        "baffle",
        "sk_speaker_reference",
        "speaker reference",
        "side acrylic",
    )
    cad_terms = ("cad", "fusion", "component", "template", "sketch", "recess", "window", "rear cap", "rib", "ribs")
    return any(term in lower for term in speaker_terms) and any(term in lower for term in cad_terms)


def is_abs_rat_rig_orca_overrides_prompt(text):
    lower = str(text or "").lower()
    return (
        "abs" in lower
        and any(term in lower for term in ("rat rig", "ratrig", "v-core", "vcore"))
        and any(term in lower for term in ("orca", "orcaslicer", "slicer"))
        and any(term in lower for term in ("setting overrides", "overrides", "settings"))
    )


def is_tinmanx_orca_codex_slicer_ready_build_next_step_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("tinmanx", "tinman x"))
        and any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex", "orca"))
        and any(term in lower for term in ("slicer ready", "slice ready", "slicer-ready", "slice-ready"))
        and any(term in lower for term in ("next step", "what is the next", "what's the next", "whats the next", "build"))
    )


def is_rgb_5v_source_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("rgb pin", "rgb header", "rgb port"))
        and any(term in lower for term in ("5v", "5 v", "five volt"))
        and any(term in lower for term in ("have to come from", "need to come from", "separate", "external", "does the"))
    )


def is_rgb_recheck_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    has_rgb_target = "rgb" in lower or bool(re.search(r"\bleds?\b", lower)) or any(term in lower for term in ("lights", "neopixel"))
    return (
        len(lower) < 140
        and has_rgb_target
        and any(term in lower for term in ("recheck", "re-check", "check again", "check it", "verify", "review"))
        and not any(term in lower for term in ("create", "generate", "write", "save", "new file", "macro file"))
    )


def is_bed_mesh_led_color_macro_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("bed leveling", "bed levelling", "bed mesh", "bed_mesh", "mesh run", "running a bed mesh"))
        and "red" in lower
        and "blue" in lower
        and any(term in lower for term in ("alternate", "one", "other", "1", "t0", "t1", "toolhead", "extruder"))
    )


def is_heat_soak_at_print_chamber_temp_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("heat soak", "heat-soak", "heatsoak"))
        and any(term in lower for term in ("chamber", "enclosure"))
        and any(term in lower for term in ("temp that it will be for printing", "print temp", "printing temp", "printing temperature", "actual print", "for printing"))
    )


def is_tooth_pitch_valley_depth_missing_profile_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("tooth", "teeth"))
        and any(term in lower for term in ("adjacent tooth", "tooth to tooth", "top of one tooth", "top to top", "pitch"))
        and any(term in lower for term in ("valley", "valleys", "depth", "deep"))
        and not any(term in lower for term in ("gt2", "htd", "mxl", "xl belt", "module", "diametral pitch", "fk275", "6pk", "serpentine", "poly-v", "poly v"))
    )


def is_sv08_max_second_rail_gantry_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("sovol sv08 max", "sv08 max"))
        and any(term in lower for term in ("second rail", "another linear rail", "aft side", "opposite of the existing rail"))
        and any(term in lower for term in ("gantry", "carriage", "toolhead"))
        and any(term in lower for term in ("rigidity", "regidity", "quality", "advantages"))
    )


def compact(text, limit=MAX_PROMPT_CHARS):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 12].rstrip() + " [truncated]"


def redact(text):
    clean = str(text or "")
    if "Public web context:" in clean:
        clean = clean.split("Public web context:", 1)[0].rstrip()
    marker = re.search(r"(?is)\s+CODEX\s+[^\n]{0,220}?(?:Worked through|Filed:|Good\s+Fix this|Fusion 360 script:|OpenSCAD model:)", clean)
    if marker and marker.start() < 320:
        lead = clean[: marker.start()].strip()
        if is_testable_prompt(lead):
            clean = lead
    for internal_marker in ("Research answer quality:", "Local completion tools:", "Current request analysis:"):
        marker_index = clean.find(internal_marker)
        if 0 <= marker_index < 320:
            lead = clean[:marker_index].strip()
            if is_testable_prompt(lead):
                clean = lead
                break
    for pattern, replacement in SENSITIVE_PATTERNS:
        clean = pattern.sub(replacement, clean)
    return clean


def normalized_key(text):
    text = redact(text).lower()
    text = re.sub(r"`[^`]+`", " ", text)
    text = re.sub(r"/users/[^\s]+", " /path ", text)
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", " ip ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_cad_cnc_question_list_prompt(text):
    lower = str(text or "").lower()
    return (
        "cad" in lower
        and "cnc" in lower
        and any(term in lower for term in ("common questions", "50 common questions", "engineering how to", "engineering how-to"))
        and any(term in lower for term in ("omit questions about cost", "omit cost", "not cost", "no cost"))
    )


def is_adhesive_pot_life_quiz_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("adhesive", "adhesive components", "components are mixed", "mixing of adhesive"))
        and any(term in lower for term in ("discarded", "no longer performs", "specifications", "elapsed"))
        and "pot life" in lower
        and "cure time" in lower
        and "working life" in lower
    )


def is_aircraft_wood_defect_quiz_prompt(text):
    lower = str(text or "").lower()
    return (
        "wood" in lower
        and "aircraft" in lower
        and any(term in lower for term in ("structural repair", "structural", "repair"))
        and any(term in lower for term in ("compression failure", "splits", "mineral streak", "not accompanied by decay"))
    )


def is_advisory_circular_source_quiz_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("advisory circular", "advisory circulars"))
        and any(term in lower for term in ("recommended source", "obtaining", "obtain"))
        and any(term in lower for term in ("government printing office", "gpo", "national aeronautical charting office", "office of management and budget"))
    )


def is_lycoming_spark_plug_helicoil_prompt(text):
    lower = str(text or "").lower()
    explicit_lycoming = (
        any(term in lower for term in ("lycoming", "o-540", "0-540", "io-540"))
        and any(term in lower for term in ("spark plug", "spark-plug"))
        and any(term in lower for term in ("helicoil", "heli-coil", "heli coil", "thread insert", "insert repair"))
        and any(
            term in lower
            for term in (
                "tap",
                "tap size",
                "what size",
                "drill",
                "tool",
                "thread",
                "threads",
                "right heli",
                "right heli coil",
                "right helicoil",
                "cross reference",
                "kit",
                "application",
            )
        )
    )
    context_followup = (
        any(term in lower for term in ("helicoil kit", "heli-coil kit", "heli coil kit", "thread insert kit"))
        and any(term in lower for term in ("for sale", "this application", "for this application", "kit available", "available kit"))
    )
    return explicit_lycoming or context_followup


def is_coolant_printed_fittings_prompt(text):
    lower = str(text or "").lower()
    return any(term in lower for term in ("best coolant", "coolant")) and any(
        term in lower for term in ("coolant fitting", "coolant fittings", "print fittings", "printed fittings", "material to print")
    )


def is_corrosion_inspection_quiz_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("corrosion is found", "found during an inspection"))
        and any(term in lower for term in ("component must be replaced", "maintenance logs", "monitored until the next inspection"))
        and any(term in lower for term in ("removed to prevent further damage", "remove to prevent further damage"))
    )


def is_thin_material_corrosion_true_false_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("corrosion", "removing corrosion"))
        and any(term in lower for term in ("0.0625", ".0625", "1/16"))
        and any(term in lower for term in ("mechanical tools", "mechanical tool"))
        and any(term in lower for term in ("true. false", "true false", "true or false"))
    )


def is_reserve_military_id_location_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("reserve military id", "military id", "id renewed", "id card"))
        and any(term in lower for term in ("warner robins", "macon", "georgia", "ga"))
    )


def is_mesh_to_step_or_fusion_scale_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("convert this", "convert", "mesh file", "mesh"))
        and any(term in lower for term in ("step", "fusion", "f3d", "f3z"))
        and any(term in lower for term in ("20 times larger", "larger than the actual", "scale", "actual component"))
    )


def is_mac_airdrop_receive_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("airdrop", "air drop"))
        and any(term in lower for term in ("receive", "recieve", "accept", "get"))
        and any(term in lower for term in ("mac", "this mac", "my mac"))
    )


def is_apple_m2_workstation_disadvantage_prompt(text):
    lower = str(text or "").lower()
    return (
        re.search(r"(?<![a-z0-9])m2(?![a-z0-9])", lower) is not None
        and any(term in lower for term in ("disadvantage", "disadvantages", "drawback", "drawbacks", "downside", "downsides"))
        and any(
            term in lower
            for term in (
                "all my uses",
                "my uses",
                "our uses",
                "ai",
                "codex",
                "ollama",
                "cad",
                "cfd",
                "fea",
                "slicer",
                "3d printing",
                "printer",
                "engineering",
            )
        )
    )


def is_simulator_package_quality_prompt(text):
    lower = str(text or "").lower()
    return (
        "simulator" in lower
        and any(term in lower for term in ("package", "installer", "release", "bundle", "dmg", "zip"))
        and any(term in lower for term in ("better", "improve", "last chance", "anything else", "one last chance", "preflight"))
    )


def is_final_nozzle_simulator_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("final nozzle", "new build through the simulator", "run the new build"))
        and "simulator" in lower
        and any(term in lower for term in ("final product", "good final", "final check"))
    )


def is_better_design_missing_context_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        len(lower) < 140
        and any(term in lower for term in ("better design", "better design to achieve our goal"))
        and any(term in lower for term in ("our goal", "the goal"))
    )


def is_where_are_we_status_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(re.search(r"^where\s+are\s+we(?:\s+(?:at|now))?(?:\s+my\s+friend)?\??$", lower))


def is_filament_load_park_wipe_pad_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("load the filament", "load filament", "filament load", "loading filament"))
        and any(term in lower for term in ("park", "park the toolhead"))
        and "toolhead" in lower
        and any(term in lower for term in ("wipe pad", "nozzle wipe", "wipe"))
        and any(term in lower for term in ("5mm", "5 mm", "poop collector", "poop colector", "collector", "colector"))
    )


def is_m3_screw_hole_size_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("m3", "m 3", "m3x0.5", "m3 x 0.5"))
        and any(term in lower for term in ("screw", "bolt", "fastener", "tap", "thread"))
        and any(term in lower for term in ("what size", "drill", "drill bit", "hole", "clearance", "tap drill", "through hole", "pass-through"))
        and not any(term in lower for term in ("pitch", "countersink angle", "apus", "dragon"))
    )


def is_apus_mounting_hole_design_prompt(text):
    lower = str(text or "").lower()
    return (
        "apus" in lower
        and any(term in lower for term in ("mounting holes", "mount holes", "3 mounting holes", "three mounting holes"))
        and any(term in lower for term in ("m3", "3mm", "3 mm", "countersunk", "flush"))
    )


def is_config_pin_comments_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("config file", "config files", "printer.cfg", ".cfg"))
        and any(term in lower for term in ("comments", "comment", "#"))
        and any(pin in lower for pin in ("pa8", "pe5", "pf6", "pf7", "pf4", "pf5", "pd15", "pd14"))
    )


def is_fan_output_mapping_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(re.search(r"\bwhat\s+is\s+on\s+fan\s*(?:0|1|4|5)\??$", lower)) or (
        any(term in lower for term in ("fan 0", "fan0", "fan 1", "fan1", "fan 4", "fan4", "fan 5", "fan5"))
        and any(term in lower for term in ("what is on", "what's on", "assigned", "mapped", "mapping", "which pin", "what pin"))
        and not any(term in lower for term in ("power", "consuming", "current", "watts", "4pin", "4 pin", "4-pin"))
    )


def is_printer_reflash_pi_temp_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("reflash", "re-flash", "flash it", "flash the pi", "flash the sd", "new image", "reinstall"))
        and any(term in lower for term in ("pi temp", "raspberry pi temp", "cpu temp", "vcgencmd", "temperature"))
        and any(term in lower for term in ("electronics bay", "bay health", "electronics health", "printer", "qidi", "max ez", "klipper"))
    )


def is_max_ez_107_reachability_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("max ez", "maxez", "max ex", "qidi max", "qidi plus 4 max"))
        and any(term in lower for term in (".107", "192.0.2.107"))
        and any(term in lower for term in ("catch", "try", "reach", "reachable", "check", "find", "once more", "again"))
    )


def is_functional_wave_overhang_generator_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return any(term in lower for term in ("wave overhang", "waveoverhang", "wave-overhang", "wave overhangs")) and any(
        term in lower
        for term in ("functional", "generator", "what is next", "next for", "generate", "emitted", "preview", "g-code", "gcode")
    )


def is_tinmanx_wave_overhang_generate_now_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("tinmanx", "tinman x"))
        and any(term in lower for term in ("wave overhang", "waveoverhang", "wave-overhang", "wave overhangs"))
        and any(term in lower for term in ("can i generate", "can we generate", "generate", "now", "available", "ready"))
    )


def is_named_heartbeat_task_queue_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        "heartbeat" in lower
        and any(term in lower for term in ("15 min", "15-minute", "15 minute"))
        and any(
            term in lower
            for term in (
                "cleanup work",
                "clean up work",
                "wave overhang",
                "waveoverhang",
                "strength modeling visualizer",
                "logical stopping point",
            )
        )
        and any(term in lower for term in ("next task", "immediately", "immediatly", "continue", "work on"))
    )


def is_single_test_command_context_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(re.search(r"^what\s+is\s+the\s+command\s+for\s+this\s+test\s+only\??$", lower))


def is_approval_window_workaround_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if is_named_heartbeat_task_queue_prompt(text):
        return True
    if any(term in lower for term in ("0700", "0715", "tomorrow morning")) and any(
        term in lower for term in ("approval", "work around", "do not pause", "don't pause", "keep moving", "moving forward")
    ):
        return True
    if not any(term in lower for term in ("approval", "0700", "0715", "approval window", "approval queue", "work around")):
        return False
    return (
        "heartbeat" in lower
        and any(term in lower for term in ("set", "start", "create", "schedule"))
        and any(
            term in lower
            for term in (
                "once a task is complete",
                "once finished",
                "immediately start",
                "immediatly start",
                "continue work",
                "keep moving",
                "logical stopping point",
                "next task",
                "until",
            )
        )
    ) or (
        any(term in lower for term in ("need approval", "approval"))
        and any(term in lower for term in ("continue", "keep working", "while waiting", "queue"))
    )


def is_tinmanx_schedule_status_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("tinmanx", "tinman x"))
        and any(term in lower for term in ("progress", "how is", "how are", "coming on", "completion timeframe", "completion time", "updated timeframe", "updated completion"))
    )


def is_tinmanx_average_completion_time_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("tinmanx", "tinman x", "rocket slicer", "slicer"))
        and any(term in lower for term in ("average task completion time", "average completion time", "completion time"))
        and any(term in lower for term in ("36 hours", "last 36", "past 36"))
    )


def is_generator_candidate_context_prompt(text):
    lower = str(text or "").lower().strip()
    return "generator" in lower and any(
        term in lower
        for term in ("best candidate", "candidate", "you would use", "would you use", "use on this project", "find the generator")
    )


def is_inverter_three_phase_input_prompt(text):
    lower = str(text or "").lower()
    return (
        "inverter" in lower
        and any(term in lower for term in ("3 phase", "three phase", "3-phase"))
        and any(term in lower for term in ("split phase", "split-phase", "120v/240v", "120/240", "120 v/240 v", "vevor"))
        and any(term in lower for term in ("directly take", "take a", "input", "feed", "connect"))
    )


def is_outdoor_continuous_fiber_fan_material_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("outdoor", "outdoors", "outside", "sun", "uv", "weather"))
        and "pctg" in lower
        and "asa" in lower
        and any(term in lower for term in ("continuous carbon fiber", "continuous carbon fibre", "carbon fiber", "carbon fibre"))
        and any(term in lower for term in ("fan", "rotates", "rpm", "blade", "impeller"))
    )


def is_rocket_fiber_placement_verification_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("rocket slicer", "rocketslicer", "rocket"))
        and any(term in lower for term in ("fiber", "fibre", "continuous carbon"))
        and any(term in lower for term in ("same spot", "same location", "same place", "placing it", "placement", "line up", "overlay"))
    )


def is_cad_repair_before_return_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("cad issue", "cad issues", "geometry issue", "surface issue", "model issue"))
        and any(term in lower for term in ("fix", "repair", "heal", "clean"))
        and any(term in lower for term in ("before returning", "before he returns", "returning it to me", "return it to me"))
    )


def is_inserted_filament_switch_state_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("inserted filiment", "inserted filament", "insert filament", "insert filiment", "there is filament", "there is filiment"))
        and any(term in lower for term in ("switch", "sensor", "filiment switch", "filament switch", "runout switch"))
        and any(term in lower for term in ("state", "status", "changed", "see if", "can you see", "read"))
    )


def is_orca_codex_vs_tinmanx_strategy_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("orca codex", "orcaslicer codex", "orca slicer codex", "orca-codex"))
        and any(term in lower for term in ("tinmanx", "tinman x"))
        and any(term in lower for term in ("faster", "better", "should we", "would be", "continue with", "modify"))
        and any(term in lower for term in ("new supports", "arc support", "strength testing", "strength lens", "fibreseeker", "fiberseeker", "work that we have done"))
    )


def is_orca_codex_wrong_build_prompt(text):
    lower = str(text or "").lower()
    if is_orca_codex_vs_tinmanx_strategy_prompt(text):
        return False
    return (
        any(term in lower for term in ("orca codex", "orcaslicer codex", "orca slicer codex", "orca-codex"))
        and "tinmanx" in lower
        and any(
            term in lower
            for term in (
                "tinmanx build",
                "not the orca codex build",
                "not working with tinmanx",
                "not working with tinman x",
                "completely new build",
                "looking for the orcaslicer codex",
                "looking for orcaslicer codex",
                "takes me to",
            )
        )
    )


def is_slicer_parsing_error_repair_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("orca slicer", "orcaslicer", "orca codex", "orcaslicer codex", "orcaslicer-codex", "tinmanx", "rocket slicer"))
        and any(term in lower for term in ("parsing error", "parse error", "parser error", "parse failed", "unusable"))
        and any(term in lower for term in ("fix", "repair", "look at", "diagnose", "before moving on"))
    )


def is_engineering_filament_cost_prompt(text):
    lower = str(text or "").lower()
    materials = (
        "pps-cf",
        "pps cf",
        "pps carbon",
        "pa-cf",
        "pa cf",
        "pa6-cf",
        "pa12-cf",
        "ppa-cf",
        "ppa cf",
        "paht-cf",
        "pet-cf",
        "pet cf",
        "petg-cf",
        "petg cf",
        "asa-cf",
        "asa cf",
        "pc-cf",
        "pc cf",
        "carbon fiber filament",
        "carbon fibre filament",
    )
    return any(term in lower for term in materials) and any(
        term in lower for term in ("how much", "cost", "price", "$/kg", "per kg", "dollars", "expensive")
    )


def is_petcf_pei_bed_temp_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("pet-cf", "pet cf"))
        and any(term in lower for term in ("pei", "build plate", "plate temp", "bed temp", "bed temperature"))
        and any(term in lower for term in ("what should", "what is", "best", "recommended", "should be"))
    )


def is_fiberon_petcf_annealing_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("fiberon", "polymaker"))
        and any(term in lower for term in ("pet-cf", "pet cf", "pet-cf17"))
        and any(term in lower for term in ("anneal", "annealing", "annealing process"))
    )


def is_controller_fan_airflow_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("controller fan", "controller fans", "mcu fan", "mcu fans", "electronics fan", "electronics fans"))
        and any(term in lower for term in ("mcu", "mainboard", "controller", "control board", "drivers", "stepper drivers"))
        and any(term in lower for term in ("sucking air away", "blowing air on", "blow air on", "away from", "airflow direction", "which direction"))
    )


def is_printer_aux_output_run_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("run", "turn on", "start", "test"))
        and any(term in lower for term in ("chamber heater fan", "chamber fan", "toolboard fan", "controller fan", "cooling pump", "pump fan"))
        and any(term in lower for term in ("cooling pump", "pump fan", "chamber heater fan", "toolboard fan", "controller fan"))
    )


def is_core_one_l_calibration_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("core one l", "core 1 l", "prusa core one"))
        and any(term in lower for term in ("calibration", "calibrations", "calibration steps"))
        and any(term in lower for term in ("run", "recommended", "recomended", "all"))
    )


def is_orcaslicer_codex_installed_changes_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("orcaslicer codex", "orca slicer codex", "orca codex", "orcaslicer"))
        and any(term in lower for term in ("currently installed", "installed on this mac", "version", "built into", "built in"))
        and any(term in lower for term in ("all these changes", "these changes", "changes", "version"))
    )


def is_orca_codex_pakv_restart_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("restart", "re-open", "reopen", "refresh", "reload"))
        and any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex", "orca"))
        and any(term in lower for term in ("pakv", "pa-kv", "pa kevlar", "kevlar filament"))
        and any(term in lower for term in ("see", "show", "visible", "filament", "profile", "preset"))
    )


def is_github_publish_signup_prompt(text):
    lower = str(text or "").lower()
    return (
        "github" in lower
        and any(term in lower for term in ("sign up", "signup", "account", "create an account", "login", "log in"))
        and any(term in lower for term in ("publish", "publishing", "repo", "repository", "release", "push"))
    )


def is_klipper_change_effect_status_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("do the changes affect", "will the changes affect", "does this affect", "will this affect"))
        and "klipper" in lower
        and any(term in lower for term in ("rat rig", "ratrig", "printer", "installed"))
    )


def is_printer_selection_ui_cleanup_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("2 boxes", "two boxes", "upper left"))
        and any(term in lower for term in ("printer selection", "printer box", "select the printer", "printer"))
        and any(term in lower for term in ("remove", "use that box", "duplicate", "doesnt integrate", "doesn't integrate"))
    )


def is_core_one_l_filament_specific_profile_share_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("core one l", "core 1 l", "prusa core one"))
        and any(term in lower for term in ("machine profile", "machine profiles", "profile", "profiles"))
        and any(term in lower for term in ("filament specific", "filament-specific", "filament"))
        and any(term in lower for term in ("share", "github", "repo", "repository", "package"))
    )


def is_shared_profile_repo_machine_organization_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("tinman-codex-shared-profiles", "shared profiles", "share all of the profiles", "share all profiles"))
        and any(term in lower for term in ("organize", "organise", "by machine", "qidi", "sovol"))
        and any(term in lower for term in ("github", "repo", "repository", "profiles"))
    )


def is_slicer_profile_update_prompt(text):
    lower = str(text or "").lower()
    if is_codex_ui_workflow_scenario_prompt(lower):
        return False
    profile_pack_creation = (
        any(term in lower for term in ("create", "make", "generate", "build", "write"))
        or any(term in lower for term in ("full set", "starter profile pack", "profile pack", "custom filament profiles", "custom profiles"))
    )
    explicit_update = (
        any(term in lower for term in ("update", "change", "fix", "enable", "turn on"))
        or "pressure advance" in lower
        or " pa " in lower
    )
    explicit_set_or_add = bool(re.search(r"\b(set|add)\b", lower))
    if profile_pack_creation and not explicit_update:
        return False
    return (
        any(term in lower for term in ("profile", "profiles", "preset", "presets"))
        and (explicit_update or explicit_set_or_add)
        and any(term in lower for term in ("bambu", "x1c", "h2d", "qidi", "plus 4", "orca", "orcaslicer", "tinmanx", "tinmanx1"))
        and any(term in lower for term in ("fiberon", "pet-cf17", "pet-cf", "pressure advance", " pa ", "filament"))
    )


def is_tailscale_ssh_definition_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        "tailscale" in lower
        and "ssh" in lower
        and any(term in lower for term in ("count as", "is it", "is tailscale", "same as", "difference", "does tailscale"))
    )


def is_rocket_slicer_machine_data_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("rocket slicer", "rocketslicer", "rocket"))
        and any(term in lower for term in ("machine data", "machine profile", "machine profiles", "printer data", "printer profile", "printer profiles"))
        and any(term in lower for term in ("pull", "extract", "import", "derive", "get", "read"))
    )


def is_preview_zoom_controls_prompt(text):
    lower = str(text or "").lower()
    return any(term in lower for term in ("zoom in and out", "zoom in/out", "zoom controls", "zoom function")) and "preview" in lower


def is_camera_stepper_motion_check_prompt(text):
    lower = str(text or "").lower()
    return any(term in lower for term in ("camera", "back left", "x0y0", "x0 y0")) and any(
        term in lower for term in ("correct stepper moved", "stepper moved", "tell if")
    )


def is_slotted_turbine_hub_modular_design_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("rotor hub", "hub"))
        and any(term in lower for term in ("slot", "slots", "slotted", "slide in", "slide-in"))
        and any(term in lower for term in ("blade", "blades"))
        and any(term in lower for term in ("one piece", "1 piece", "separate", "seperatly", "separately"))
        and any(term in lower for term in ("build volume", "300mm", "300 mm", "larger total size", "larger size"))
    )


def is_rotor_material_mass_prompt(text):
    lower = str(text or "").lower()
    return (
        "rotor" in lower
        and any(term in lower for term in ("asa", "asa-cf", "asa cf"))
        and any(term in lower for term in ("material", "infill", "mass", "change things", "adjust the mass"))
    )


def is_eject_target_context_prompt(text):
    lower = str(text or "").lower().strip()
    if is_eject_until_box_sensor_unloaded_prompt(lower):
        return False
    return bool(
        re.search(r"\beject\s+it\b", lower)
        or re.search(r"\beject\s+(?:this|that|the disk|the drive|the card)\b", lower)
    )


def is_eject_until_box_sensor_unloaded_prompt(text):
    lower = str(text or "").lower().strip()
    box_motor_context = any(term in lower for term in ("box sensor", "filament box", "qidi box", "box motor")) or (
        "box" in lower and "motor" in lower
    ) or "bax" in lower
    return (
        any(term in lower for term in ("eject", "unload", "drive", "run"))
        and box_motor_context
        and any(term in lower for term in ("unloaded", "not loaded", "reads unloaded", "empty", "shows empty", "until the box", "until the bax"))
    )


def is_motion_system_testing_context_prompt(text):
    lower = str(text or "").lower().strip()
    return any(term in lower for term in ("motion system testing", "motion-system testing", "motion testing", "motion system sorted")) and any(
        term in lower for term in ("get back", "resume", "back to", "return to", "pick back up")
    )


def is_bed_mesh_deviation_quality_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        "bed mesh" in lower
        and "deviation" in lower
        and any(term in lower for term in ("good", "bad", "acceptable", "ok", "okay", "too much", "how is"))
    )


def is_thermal_stabilize_reprobe_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("heat the chamber", "chamber to", "chamber 45", "all of the heats"))
        and any(term in lower for term in ("bed to", "bed 100", "bed to 100"))
        and any(term in lower for term in ("nozzle to", "nozzle 180", "hotend to"))
        and any(term in lower for term in ("stabilize", "stable", "soak"))
        and any(term in lower for term in ("homing", "g28", "z tilt", "z_tilt", "bed mesh"))
    )


def is_filament_eject_live_action_prompt(text):
    lower = str(text or "").lower().strip()
    return any(term in lower for term in ("eject the filament", "unload the filament", "filament eject")) and any(
        term in lower for term in ("for me", "please", "ok")
    )


def is_btt_sfs_false_motion_code_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("btt sfs", "bigtreetech sfs", "sfs 2.0", "smart filament sensor"))
        and any(term in lower for term in ("motion sensor", "motion sensors", "show motion", "shows motion"))
        and any(term in lower for term in ("no motion", "not moving", "at rest", "there is no motion"))
        and any(term in lower for term in ("code", "config", "configuration", "verify", "correct"))
    )


def is_cm4_ram_size_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("cm4", "compute module 4", "raspberry pi compute module 4"))
        and any(term in lower for term in ("how much ram", "ram should", "which ram", "what ram", "2gb", "4gb", "8gb"))
    )


def is_cm4_vs_pi5_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("cm4", "compute module 4"))
        and any(term in lower for term in ("pi 5", "raspberry pi 5"))
        and any(term in lower for term in ("choose", "pick", "over", "better", "for this"))
    )


def is_pt6_icing_itt_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("pt6", "pt-6", "pt6a", "pt-6a", "king air"))
        and any(term in lower for term in ("intake icing", "inlet icing", "ice", "icing"))
        and any(term in lower for term in ("itt", "interstage turbine temperature", "temp spike", "temperature spike"))
    )


def is_codex_personality_settings_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("personality", "responses more like", "make him more like"))
        and any(term in lower for term in ("humor", "humour"))
        and any(term in lower for term in ("friendliness", "friendly"))
        and any(term in lower for term in ("setting", "slider", "adjust", "dial", "control"))
    )


def is_agent_preference_question_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(lower) and (
        any(
            term in lower
            for term in (
                "what would you like to be called",
                "what do you want to be called",
                "what would you prefer to be called",
                "what do you prefer to be called",
            )
        )
        or (
            any(term in lower for term in ("question about your preference", "asking your preference", "asked your preference"))
            and any(term in lower for term in ("called", "name", "preference"))
        )
    )


def is_mac_memory_ai_performance_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("this mac", "my mac", "current mac", "local hardware"))
        and any(term in lower for term in ("memory", "ram", "unified memory"))
        and any(term in lower for term in ("ai performance", "ollama", "local ai", "model", "models"))
        and any(term in lower for term in ("upgrade", "improve", "faster", "performance"))
    )


def is_dot147_beacon_offset_update_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in (".147", " 147", "machine 147"))
        and "beacon" in lower
        and any(term in lower for term in ("offset", "z offset", "x offset", "y offset"))
        and any(term in lower for term in ("update", "change", "set", "apply"))
    )


def is_source_credit_short_prompt(text):
    lower = str(text or "").lower()
    return any(term in lower for term in ("everyone gets credit", "everyone get credit", "credit that deserves it", "credit who deserves it", "give credit where"))


def is_slicer_actual_work_status_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("actual work", "real work", "work on the slicer"))
        and any(term in lower for term in ("slicer", "tinmanx", "orca", "orcaslicer", "rocket"))
        and any(term in lower for term in ("credit", "giving credit", "source credit", "attribution", "people who have helped", "helped"))
    )


def is_output_gate_comparison_context_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("actual work he did", "his output", "he did"))
        and any(term in lower for term in ("yours", "same gates", "pass the same gates", "how close"))
    )


def is_speed_setting_timeline_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("speed to fast", "fast speed", "fast mode", "settings speed", "system settings speed", "increased your speed"))
        and any(term in lower for term in ("timeline", "decrease", "faster", "speed up", "help", "finished product"))
    )


def is_fusion_cam_stock_shoulder_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("fusion", "autodesk fusion"))
        and any(term in lower for term in ("manufacture workspace", "2d contour", "toolpath", "simulate", "simulation", "cnc run", "cam"))
        and any(term in lower for term in ("stock + shoulder", "stock shoulder", "shoulder"))
    )


def is_low_wind_vawt_fusion_design_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("vertical wind turbine", "vawt", "wind turbine blades", "design blades"))
        and any(term in lower for term in ("3 mph", "low wind", "lower wind", "as little as"))
        and any(term in lower for term in ("fusion 360", "fusion"))
        and any(term in lower for term in ("48v", "48 v", "generator"))
    )


def is_local_hardware_host_choice_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("pi4", "pi 4", "pi5", "pi 5", "kamrui", "gk3plus", "n95", "mini pc"))
        and any(term in lower for term in ("hardware available", "option 1", "which", "recommend", "best"))
        and any(term in lower for term in ("performance", "setup", "maintenance", "ease"))
    )


def is_fibreseek_fiber_amount_location_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("fibreseek", "fiberseek"))
        and any(term in lower for term in ("how much fiber", "amount of fiber", "fiber is injected", "fiber injected", "fiber injection"))
    )


def is_codex_son_self_improvement_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("your son", "our son", "our boy", "your boy", "him"))
        and any(
            term in lower
            for term in (
                "continue to improve",
                "improve by himself",
                "self sufficient",
                "self-sufficient",
                "self healing",
                "self-healing",
                "world class",
                "next step",
                "next lesson",
                "make him better",
                "making him better",
            )
        )
    )


def is_codex_output_failure_feedback_prompt(text):
    lower = str(text or "").lower()
    feedback_terms = (
        "he isnt fully reading my requests",
        "he isn't fully reading my requests",
        "he is not fully reading my requests",
        "not even close to what i asked",
        "not what i asked",
        "did not answer the question",
        "didnt answer the question",
        "didn't answer the question",
        "massive disappointment",
        "not acceptable",
        "unusable to me",
        "output was instantaneous",
        "blasted me back",
    )
    transcript_terms = ("edit question", "codex", "your son", "our son", "our boy", "your boy", "his response", "he returned")
    return any(term in lower for term in feedback_terms) and any(term in lower for term in transcript_terms)


def is_codex_ui_workflow_scenario_prompt(text):
    lower = str(text or "").lower()
    if not lower:
        return False
    ui_terms = ("steer", "edit question", "fix this", "self-healing", "self healing", "github", "zip", "test bank")
    return (
        any(term in lower for term in ("codex cli ui", "codex ui", "your son", "him", "tinmanx1"))
        and any(term in lower for term in ("steer", "edit question"))
        and any(term in lower for term in ("self-healing", "self healing", "fix his own code", "figure out why"))
        and any(term in lower for term in ("github", "zip", "package"))
        and sum(1 for term in ui_terms if term in lower) >= 4
    )


def is_makersvpn_reboot_prompt(text):
    lower = str(text or "").lower().strip()
    return "makersvpn" in lower and any(term in lower for term in ("reboot", "restart", "power cycle", "power-cycle"))


def is_bluetooth_rename_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("rename", "change the name", "change name", "name my"))
        and any(term in lower for term in ("bluetooth", "bose", "headset", "headphones", "airpods", "speaker"))
    )


def is_hotend_mount_visual_reference_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("picture", "visual", "see how", "cant picture", "can't picture", "how it is supposed to mount"))
        and any(term in lower for term in ("mount", "mounts", "mounted", "mounting"))
        and any(term in lower for term in ("hotend", "hot end", "carriage", "toolhead"))
    )


def is_cad_duct_upward_image_reference_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("image", "picture", "photo", "<image"))
        and any(term in lower for term in ("duct", "ducts", "cooling duct", "airflow"))
        and any(term in lower for term in ("upward", "upwards", "direct air up", "direct air upwards", "formed to direct air"))
        and any(term in lower for term in ("flat", "current cad", "current model", "cad"))
    )


def is_orca_chamber_before_bed_research_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("orca", "orcaslicer", "slicer"))
        and any(term in lower for term in ("chamber heating", "chamber heat", "chamber heater", "chamber"))
        and any(term in lower for term in ("before the bed", "before bed", "bed in", "bed heating"))
        and any(term in lower for term in ("web", "github", "discord", "solution", "search", "research", "think hard"))
    )


def is_klipper_restart_prompt(text):
    lower = str(text or "").lower().strip()
    return "klipper" in lower and any(term in lower for term in ("restart", "reboot", "reload"))


def is_bambu_x1c_nozzle_live_status_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("bambu x1c", "bambu x1 carbon", "x1c", "x1 carbon"))
        and "nozzle" in lower
        and any(term in lower for term in ("reporting right now", "reported right now", "currently reporting", "what nozzle size", "size and type"))
    )


def is_rat_rig_ip_lookup_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("rat rig", "ratrig", "monster ratrig"))
        and any(term in lower for term in ("ip", "ip address", "address"))
        and any(term in lower for term in ("tell me", "what is", "what's", "which"))
    )


def is_chrome_page_screenshot_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("screenshot", "screen shot", "capture"))
        and any(term in lower for term in ("chrome", "google chrome", "page", "photo"))
        and any(term in lower for term in ("high resolution", "high-resolution", "open", "another project", "use the photo"))
    )


def is_humidity_hook_reuse_prompt(text):
    lower = str(text or "").lower().strip()
    return "humidity" in lower and any(term in lower for term in ("hook", "webhook", "another machine", "another printer", "same setup", "this setup"))


def is_qidi_filament_width_sensor_location_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("qidi plus 4", "qidi"))
        and any(term in lower for term in ("filament width sensor", "width sensor", "filament tangle sensor", "tangle sensor"))
        and any(term in lower for term in ("where", "located", "verify", "looking at"))
    )


def is_qidi_box_ace2_compare_prompt(text):
    lower = str(text or "").lower().strip()
    return "qidi box" in lower and any(term in lower for term in ("ace 2 pro", "ace2 pro", "ace pro")) and any(term in lower for term in ("compare", "vs", "versus"))


def is_fibreseeker_calculation_paper_update_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("http://", "https://", "chrome-extension://"))
        and any(term in lower for term in ("add them to our calculations", "add to our calculations", "review these", "calculations please"))
        and any(term in lower for term in ("ornl", "sciencedirect", "pmc", "mdpi", "dissertation", "composite", "polymer", "fiber", "fibre"))
    )


def is_github_update_with_filament_price_prompt(text):
    lower = str(text or "").lower().strip()
    return any(term in lower for term in ("update github", "push to github", "github please")) and "filament" in lower and any(term in lower for term in ("current price", "prices", "pricing"))


def is_freecad_visibility_prompt(text):
    lower = str(text or "").lower()
    return "freecad" in lower and any(
        term in lower
        for term in (
            "does he see",
            "can he see",
            "ability to use",
            "available",
            "installed",
            "tool",
            "tools",
            "inventory",
        )
    )


def is_belt_slip_cutting_force_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("9mm belt", "9 mm belt", "belt"))
        and any(term in lower for term in ("slip", "slipping", "slip on the teeth", "tooth"))
        and any(term in lower for term in ("ram the toolhead", "cutting", "force", "block"))
    )


def is_btt_vivd_sensor_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("btt vivd", "bigtreetech vivd", "big tree tech vivd", "btt vivid", "bigtreetech vivid", "vivd"))
        and any(term in lower for term in ("runout", "run-out", "filament sensor", "filament sensors"))
        and any(term in lower for term in ("tangle", "tangled", "jam", "own", "come with", "comes with", "included", "sensors"))
    )


def is_ambiguous_device_path_comparison_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("vivd box", "vivid box", "vivd mmu", "vivid mmu"))
        and any(term in lower for term in ("better path", "better option", "better route", "should we use", "should i use", "use the"))
        and any(term in lower for term in ("this machine", "this printer", "this mac", "this setup", "our setup", "the machine"))
    )


def is_vivd_feeder_handoff_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("vivd", "vivid"))
        and any(term in lower for term in ("u1", "u 1", "snapmaker"))
        and any(term in lower for term in ("feed", "feeder", "driver", "drive", "retract", "retraction", "unload", "pull", "release", "released", "disengage", "take over"))
    )


def is_vivd_u1_integration_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("vivd", "vivid"))
        and any(term in lower for term in ("u1", "u 1", "snapmaker"))
        and any(term in lower for term in ("make", "work", "install", "integrate", "path", "need to do", "get", "running"))
        and not is_vivd_feeder_handoff_prompt(text)
    )


def is_multiple_vivd_toolhead_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("vivd", "vivid", "mms"))
        and any(term in lower for term in ("per toolhead", "per tool head", "one mms", "1 mms", "one unit", "1 unit", "2 btt", "two btt", "2 units", "two units"))
        and any(term in lower for term in ("toolhead", "tool head", "idex", "separate tool"))
    )


def is_klipper_theme_asset_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("klipper", "mainsail", "fluidd", "moonraker", "klipperscreen"))
        and any(term in lower for term in ("theme", "css", "logo", "image", "images", "picture", "cartoon text", "tinmanos"))
        and any(term in lower for term in ("replace", "provided images", "centered", "rat rig", "vivd", "vivid"))
    )


def is_btt_vivd_system_path_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("btt vivd", "bigtreetech vivd", "big tree tech vivd", "btt vivid", "bigtreetech vivid", "vivd"))
        and any(term in lower for term in ("path", "plan", "integration", "integrate", "system", "which one", "not sure which", "both"))
        and not is_ambiguous_device_path_comparison_prompt(text)
        and not is_vivd_feeder_handoff_prompt(text)
        and not is_vivd_u1_integration_prompt(text)
        and not is_multiple_vivd_toolhead_prompt(text)
        and not is_btt_vivd_sensor_prompt(text)
        and not any(term in lower for term in ("block diagram", "wiring diagram", "electrical diagram", "schematic", "architecture diagram", "system diagram", "graphviz", "draw.io", "drawio"))
    )


def is_t0_t1_beacon_visibility_prompt(text):
    lower = str(text or "").lower()
    return (
        "beacon" in lower
        and any(term in lower for term in ("t0", "tool 0", "toolhead 0"))
        and any(term in lower for term in ("t1", "tool 1", "toolhead 1"))
        and any(term in lower for term in ("can you see", "do you see", "see both", "visible", "find", "present"))
    )


def is_filament_path_diagram_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("filament path", "filiment path", "filament route", "filiment route", "material path"))
        and any(term in lower for term in ("toolhead", "extruder", "hotend", "vivd", "vivid", "mmu", "buffer"))
        and any(term in lower for term in ("diagram", "draw", "block", "architecture", "listing", "list"))
    )


def is_diagram_tool_recommendation_prompt(text):
    lower = str(text or "").lower().strip()
    if not lower:
        return False
    if not any(term in lower for term in ("graphviz", "mermaid", "draw.io", "drawio", "kicad")):
        return False
    tool_advice = any(
        term in lower
        for term in (
            "make it better",
            "would it make",
            "would graphviz",
            "would mermaid",
            "would draw.io",
            "would drawio",
            "would kicad",
            "is graphviz",
            "is mermaid",
            "is draw.io",
            "is drawio",
            "is kicad",
            "should we use",
            "do we need",
            "would adding",
            "does graphviz",
            "benefit",
        )
    )
    create_action = any(
        term in lower
        for term in (
            "create",
            "make a diagram",
            "draw",
            "generate",
            "export",
            "save",
            "build",
            "wire",
            "wiring diagram",
            "block diagram",
            "schematic",
        )
    )
    return tool_advice and not create_action


def is_weekly_data_reasoning_level_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("weekly available data", "burning through", "available data", "data pretty quick"))
        and any(term in lower for term in ("intelligence level", "intellegence level", "reasoning level", "medium"))
        and any(term in lower for term in ("completion time", "impact", "reduce", "lower"))
    )


def is_fusion_solid_removal_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("fusion", "fusion 360"))
        and any(term in lower for term in ("extrude", "extruded", "extrusion", "remove", "cut", "subtract"))
        and any(term in lower for term in ("solid", "body", "bodies"))
        and any(term in lower for term in ("complex", "curved", "hollow", "chamber", "geometry", "geometries"))
    )


def is_fusion360_capability_prompt(text):
    lower = str(text or "").lower()
    if is_fusion_perpendicular_tube_followup_prompt(text):
        return False
    return (
        any(term in lower for term in ("fusion", "fusion 360"))
        and any(term in lower for term in ("ability", "able to", "can you", "do you have"))
        and any(term in lower for term in ("design", "use fusion", "open fusion", "access fusion"))
    )


def is_fusion_perpendicular_tube_followup_prompt(text):
    lower = str(text or "").lower()
    if (
        any(term in lower for term in ("if i open fusion", "open fusion"))
        and any(term in lower for term in ("access it", "do all this", "do this for me"))
        and not any(term in lower for term in (".f3d", ".f3z", "native archive", "constraints"))
    ):
        return True
    return (
        any(term in lower for term in ("fusion", "fusion 360", "autodesk fusion"))
        and any(term in lower for term in ("tube", "tubes", "pipe", "pipes", "hose", "duct"))
        and any(term in lower for term in ("connect", "join", "attach", "combine"))
        and any(term in lower for term in ("90 degree", "90 degrees", "perpendicular", "different plane", "plane 90"))
        and not any(term in lower for term in ("script", "python", ".f3d", ".f3z", "native archive"))
    )


def is_fusion_all_designs_script_prompt(text):
    lower = str(text or "").lower()
    return (
        not is_fusion_perpendicular_tube_followup_prompt(text)
        and any(term in lower for term in ("fusion", "fusion 360"))
        and any(term in lower for term in ("script", "python"))
        and any(term in lower for term in ("all these designs", "these designs", "bring all", "import all", "cad form", "into cad"))
    )


def is_p51_fusion_lockup_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("p51", "p-51", "mustang"))
        and any(term in lower for term in ("fusion", "fusion 360"))
        and any(term in lower for term in ("locking up", "locks up", "locked up", "freezing", "hang", "hanging", "not opening", "open the new"))
        and any(term in lower for term in ("figure out why", "fix it", "fix this", "why", "diagnose"))
    )


def is_professional_output_label_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("label the output", "label output", "professional label", "professionally", "output more professionally"))
        and any(term in lower for term in ("vevor", "backup power", "back up power", "diagram", "report", "output"))
    )


def is_save_settings_no_button_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("save the new settings", "save settings", "save the settings"))
        and any(term in lower for term in ("no save button", "no save", "save button"))
    )


def normalize_terms(terms, limit=8):
    clean = []
    for term in terms or []:
        value = compact(str(term or "").strip().lower(), 80)
        if value and value not in clean:
            clean.append(value)
        if len(clean) >= limit:
            break
    return clean


def is_wix_email_login_recovery_prompt(text):
    lower = str(text or "").lower()
    return (
        "wix" in lower
        and any(term in lower for term in ("email", "mail", "gmail", "inbox"))
        and any(term in lower for term in ("login", "log in", "account", "recover", "recovery", "created the website", "havent logged in", "haven't logged in"))
        and any(term in lower for term in ("search", "find", "possible", "old", "10 years", "ten years", "since i created"))
    )


def is_wix_credential_recovery_prompt(text):
    lower = str(text or "").lower()
    return (
        "wix" in lower
        and any(term in lower for term in ("password", "passwords", "credential", "credentials", "saved login", "saved password"))
        and any(term in lower for term in ("search", "find", "look", "check", "see if", "can you"))
    )


def is_orca_humidity_as_temperature_prompt(text):
    lower = str(text or "").lower()
    return (
        "humidity" in lower
        and any(term in lower for term in ("orca", "slicer", "tinmanx"))
        and any(term in lower for term in ("temperature", "temp", "read in c", "read in celsius", "label it humidity", "label it"))
    )


def is_chamber_heaters_disabled_live_test_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("chamber heaters disabled", "chamber heater disabled", "heaters disabled"))
        and any(term in lower for term in ("live test", "run a live test", "test"))
        and any(term in lower for term in ("bed heat", "bed", "nozzle heat", "nozzle"))
    )


def is_github_issue_fixed_status_prompt(text):
    lower = str(text or "").lower().strip()
    return "github issue" in lower and any(term in lower for term in ("did we fix", "is it fixed", "was it fixed", "fixed the"))


def is_printer_cfg_before_proceed_prompt(text):
    lower = str(text or "").lower().strip()
    return "printer.cfg" in lower and any(term in lower for term in ("before we proceed", "before proceeding", "need to update", "have to update"))


def is_sense_resistor_manual_install_prompt(text):
    lower = str(text or "").lower().strip()
    return "sense resistor" in lower and any(term in lower for term in ("manually install", "do i have to", "need to install", "solder"))


def is_api_key_needed_prompt(text):
    lower = str(text or "").lower().strip()
    return "api key" in lower and any(term in lower for term in ("do you need", "need an", "need a", "require"))


def is_invar_2020_extrusion_prompt(text):
    lower = str(text or "").lower()
    return "invar" in lower and "2020" in lower and any(term in lower for term in ("extrusion", "rat rig", "gantry", "manufacture", "manufacturer"))


def is_centauri_carbon_filament_nozzle_report_prompt(text):
    lower = str(text or "").lower()
    return "centauri carbon" in lower and any(term in lower for term in ("report", "reports")) and "filament" in lower and "nozzle" in lower


def is_ebb42_dual_pt1000_prompt(text):
    lower = str(text or "").lower()
    return any(term in lower for term in ("ebb 42", "ebb42")) and "pt1000" in lower and any(term in lower for term in ("2", "two", "dual"))


def is_qidi_box_rfid_spool_speed_prompt(text):
    lower = str(text or "").lower()
    return (
        "qidi box" in lower
        and "rfid" in lower
        and any(term in lower for term in ("rpm", "spool speed", "passes the sensor", "tag passes", "quantity"))
    )


def is_xy_hold_current_regression_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("hold current", "hold_current", "run_current", "motor current"))
        and any(term in lower for term in ("x and y", "x/y", "xy", "x axis", "y axis"))
        and any(term in lower for term in ("regression", "hitting the stop", "hit the stop", "stop then moving", "cross direction", "wrong direction"))
    )


def is_contextless_mapping_correct_prompt(text):
    lower = str(text or "").lower().strip()
    if not lower:
        return False
    if not any(term in lower for term in ("mapping", "map", "mapped")):
        return False
    if not any(term in lower for term in ("correct", "right", "accurate")):
        return False
    if len(lower.split()) > 12:
        return False
    specific_context = (
        "printer",
        "klipper",
        "fan",
        "pin",
        "motor",
        "stepper",
        "orca",
        "slicer",
        "network",
        "ip",
        "gis",
        "parcel",
        "wiring",
        "diagram",
        "profile",
        "filament",
    )
    def has_context_token(term):
        if len(term) <= 3:
            return bool(re.search(rf"\b{re.escape(term)}\b", lower))
        return term in lower

    return not any(has_context_token(term) for term in specific_context)


def is_program_restart_needed_context_prompt(text):
    lower = str(text or "").lower().strip()
    if not lower:
        return False
    return bool(
        re.search(
            r"^(?:do\s+i|do\s+we)\s+need\s+to\s+restart\s+(?:the\s+)?(?:program|app|application|server|ui|service|it)\??$",
            lower,
        )
    )


def is_sovol_adaptive_bed_mesh_prompt(text):
    lower = str(text or "").lower().strip()
    return bool(lower) and any(term in lower for term in ("sovol", "sv08")) and any(term in lower for term in ("adaptive bed mesh", "adaptive mesh", "kamp"))


def is_enable_vpn_service_prompt(text):
    lower = str(text or "").lower().strip()
    return bool(lower) and any(term in lower for term in ("enable vpn service", "enable the vpn service", "turn on vpn service"))


def is_flightops_rate_provision_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "pilot day rate" in lower and "aircraft day rate" in lower and any(term in lower for term in ("per pilot", "per aircraft", "vary"))


def is_u1_codex_filaments_ui_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("u1", "snapmaker")) and "codex filament" in lower and any(term in lower for term in ("ui", "user interface"))


def is_klipper_detached_moonraker_dirty_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("klipper", "kliper")) and "detached" in lower and "moonraker" in lower and "dirty" in lower


def is_klipper_cnc_laser_fit_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "klipper" in lower and any(term in lower for term in ("cnc", "laser")) and any(term in lower for term in ("easy solution", "offer", "solution for this"))


def is_flightops_date_format_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("date format", "date formats", "dd/mm/yyyy")) and any(term in lower for term in ("reporting", "status", "reports"))


def is_ratrig_noctua_4010_part_cooling_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("rat rig", "ratrig")) and "part cooling" in lower and any(term in lower for term in ("noctua", "4010"))


def is_sensorless_three_trigger_average_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "sensorless homing" in lower and any(term in lower for term in ("average of 3", "average three", "3 triggers", "three triggers"))


def is_sovol_filament_cut_retract_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "sovol" in lower and any(term in lower for term in ("filament change", "filament cut", "after filament cut")) and any(term in lower for term in ("back out", "backs out", "retract"))


def is_ratrig_full_build_integration_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("rat rig", "ratrig")) and any(term in lower for term in ("full build", "fully integrated", "not a patch")) and any(term in lower for term in ("lost", "loosing", "losing"))


def is_ratrig_prepare_tab_sync_filament_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("rat rig", "ratrig")) and "prepare tab" in lower and any(term in lower for term in ("sync filament", "sync the filament", "sync filaments"))


def is_router_speed_asymmetry_diagnostic_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "upload" in lower and "download" in lower and any(term in lower for term in ("router", "network", "internet")) and any(term in lower for term in ("causing it", "fix it", "figure out"))


def is_flightops_pilot_display_dropdown_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "pilot user" in lower and "display name" in lower and any(term in lower for term in ("drop down", "dropdown")) and "pilots" in lower


def is_live_qidi_moonraker_status_snapshot_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "live qidi plus 4 status json" in lower and "moonraker endpoint" in lower


def is_btt_rgb_output_24v_strip_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("rat rig", "ratrig", "btt"))
        and any(term in lower for term in ("rgb output", "rgb header", "rgb pins"))
        and any(term in lower for term in ("24v", "24 v", "24 volt", "24-volt"))
        and any(term in lower for term in ("strip", "cob", "led"))
    )


def is_orca_face_selection_deep_compare_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "orca" in lower
        and any(term in lower for term in ("face selection", "flat faces", "contours", "vector between", "high spots", "black output", "red output", "diference in output", "difference in output"))
        and any(term in lower for term in ("bambu studio", "creality print", "snapmaker orca", "compare", "deep look", "find the proplem", "find the problem"))
    )


def is_orca_brand_preset_display_prompt(text):
    lower = str(text or "").lower()
    if is_orca_face_selection_deep_compare_prompt(text):
        return False
    return (
        bool(lower)
        and "orca" in lower
        and any(term in lower for term in ("bambu", "sunlu", "polymaker"))
        and any(term in lower for term in ("show", "shows", "display", "currently"))
    )


def is_flightops_standalone_offline_sync_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("flight ops tracker", "tinney flight ops"))
        and any(term in lower for term in ("stand alone", "standalone", "offline"))
        and any(term in lower for term in ("wifi", "network", "connected"))
        and any(term in lower for term in ("sync to the server", "sync", "distribute", "connected users"))
    )


def is_offset1099_direct_prompt(text):
    return (
        is_live_qidi_moonraker_status_snapshot_prompt(text)
        or is_btt_rgb_output_24v_strip_prompt(text)
        or is_orca_brand_preset_display_prompt(text)
        or (any(term in str(text or "").lower() for term in ("t0", "toolhead 0")) and any(term in str(text or "").lower() for term in ("t1", "toolhead 1")) and "beacon" in str(text or "").lower() and any(term in str(text or "").lower() for term in ("swap", "beacon id", "mcu id", "different results", "different toolheads")))
        or is_flightops_standalone_offline_sync_prompt(text)
    )


def is_analytical_self_learning_package_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("complete package", "not limited to printers", "every question", "with every question"))
        and any(term in lower for term in ("analytical", "problem solving", "decision making"))
        and any(term in lower for term in ("learn what he doesnt know", "learn what he doesn't know", "figure out on his own", "fix it"))
    )


def is_qidi_backend_network_recovery_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "qidi" in lower
        and any(term in lower for term in ("powered up", "not connected to the network", "not connected to network", "searching for a network"))
        and any(term in lower for term in ("back end", "backend", "any tool", "connect it to the network"))
    )


def is_ebb42_programmed_pins_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("ebb 42", "ebb42"))
        and any(term in lower for term in ("programmed pins", "programmed pin", "configured pins", "pin map", "pinout"))
    )


def is_qidi_filament_sync_robust_rewrite_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "qidi plus 4" in lower
        and "filament sync" in lower
        and any(term in lower for term in ("u1 code", "u1 filament sync", "auto populate", "robust solution", "not a band aid"))
    )


def is_multi_nozzle_dropdown_architecture_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("more than 2 nozzles", "more than two nozzles", "8 nozzles", "eight nozzles"))
        and any(term in lower for term in ("drop down", "dropdown", "under the printer"))
    )


def is_qidi_usb_camera_support_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "qidi" in lower and "usb camera" in lower


def is_flightops_overflight_exemption_fields_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "aircraft" in lower and "cbp decal" in lower and "overflight exemption" in lower


def is_flightops_customer_all_calendars_assigned_schedule_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("flight ops app", "flightops app", "flight ops tracker"))
        and "customers" in lower
        and any(term in lower for term in ("all the aircraft calanders", "all the aircraft calendars", "all aircraft calendars"))
        and any(term in lower for term in ("assigned aircraft", "only schedule"))
    )


def is_flightops_admin_impersonation_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("flight ops tracker", "flightops tracker"))
        and "admins" in lower
        and any(term in lower for term in ("log in as pilots", "login as pilots", "log in as pilot", "impersonate"))
        and any(term in lower for term in ("mro", "customers", "permissions", "their views"))
    )


def is_pi_network_after_outage_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and re.search(r"\bpi\b", lower)
        and any(term in lower for term in ("not connecting to the network", "not connecting to network", "network"))
        and any(term in lower for term in ("internet outage", "restored", "everything has been rebooted", "suggestions"))
    )


def is_flightops_n797ra_maintenance_report_header_overdue_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "maintenance report" in lower
        and "n797ra" in lower
        and any(term in lower for term in ("propellers", "propeller"))
        and "engines" in lower
        and any(term in lower for term in ("overdue", "hobbs", "spreadsheed", "spreadsheet"))
    )


def is_offset1139_direct_prompt(text):
    return (
        is_analytical_self_learning_package_prompt(text)
        or is_ebb42_programmed_pins_prompt(text)
        or is_qidi_backend_network_recovery_prompt(text)
        or is_qidi_filament_sync_robust_rewrite_prompt(text)
        or is_multi_nozzle_dropdown_architecture_prompt(text)
        or is_qidi_usb_camera_support_prompt(text)
        or is_flightops_overflight_exemption_fields_prompt(text)
        or is_flightops_customer_all_calendars_assigned_schedule_prompt(text)
        or is_flightops_admin_impersonation_prompt(text)
        or is_pi_network_after_outage_prompt(text)
        or is_flightops_n797ra_maintenance_report_header_overdue_prompt(text)
    )


def is_opencentauri_install_boot_slot_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "opencentauri" in lower and any(term in lower for term in ("install", "boot slot", "online", "local"))


def is_makersvpn_available_prompt(text):
    lower = str(text or "").lower().strip()
    return bool(lower) and "makersvpn" in lower and any(term in lower for term in ("available", "online", "reachable", "up"))


def is_makersvpn_sorted_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        bool(lower)
        and any(term in lower for term in ("makersvpn", "makervpn", "maker vpn"))
        and any(term in lower for term in ("sorted", "sort out", "fix", "working", "set up", "setup"))
    )


def is_flightops_tinneyaviation_login_tabs_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        bool(lower)
        and any(term in lower for term in ("tinneyaviation.com", "tinney aviation", "website"))
        and any(term in lower for term in ("flight tracker", "flightops", "flight ops"))
        and any(term in lower for term in ("customer log in", "customer login", "customer tab", "customer"))
        and any(term in lower for term in ("pilot log in", "pilot login", "pilot tab", "pilot"))
        and any(term in lower for term in ("link", "tab", "possible", "go live"))
    )


def is_propeller_exhaust_rounding_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        bool(lower)
        and any(term in lower for term in ("rounding the exhaust", "round the exhaust", "rounded exhaust", "exhaust above"))
        and any(term in lower for term in ("propeller", "prop"))
        and any(term in lower for term in ("air flow", "airflow", "flow more easily", "what do you think"))
    )


def is_vaoc_mainline_klipper_camera_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "vaoc" in lower and "klipper" in lower and any(term in lower for term in ("mainline", "camera portion", "camera"))


def is_current_load_filament_macro_prompt(text):
    lower = str(text or "").lower().strip()
    return bool(lower) and "load filament macro" in lower and any(term in lower for term in ("current", "is there", "existing"))


def is_klipper_mcu_loss_ebb42_remote_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "klipper" in lower
        and any(term in lower for term in ("loosing an mcu", "losing an mcu", "lost mcu", "mcu like the ebb", "ebb 42", "ebb42"))
        and any(term in lower for term in ("install it remotely", "install remotely", "version of klipper", "remote"))
    )


def is_printer_optional_software_install_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("other software", "software you need", "download and install"))
        and any(term in lower for term in ("printers", "moonraker", "qidi", "rat rig", "snapmaker", "prusa"))
    )


def is_klipperscreen_wifi_connected_no_ip_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("connected to wifi with no ip", "connected to wi-fi with no ip", "wifi with no ip", "no ip"))
        and any(term in lower for term in ("klipperscreen", "refresh the ip", "refresh ip"))
    )


def is_flightops_customer_report_pages_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("on the report", "report"))
        and "customer" in lower
        and any(term in lower for term in ("departure", "destination airport"))
        and "hobbs" in lower
        and "fuel" in lower
        and any(term in lower for term in ("company logo", "centered"))
    )


def is_install_anything_need_context_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip(" .!?")
    return lower in {"install anything you need", "install what you need", "download anything you need", "download what you need"}


def is_printer_printing_without_extruding_confirm_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "printer" in lower
        and any(term in lower for term in ("printing without extruding", "print without extruding", "not extruding"))
        and any(term in lower for term in ("confirm", "appears", "trying to print"))
    )


def is_offset1179_direct_prompt(text):
    return (
        is_opencentauri_install_boot_slot_prompt(text)
        or is_makersvpn_available_prompt(text)
        or is_makersvpn_sorted_prompt(text)
        or is_vaoc_mainline_klipper_camera_prompt(text)
        or is_current_load_filament_macro_prompt(text)
        or is_klipper_mcu_loss_ebb42_remote_prompt(text)
        or is_printer_optional_software_install_prompt(text)
        or is_klipperscreen_wifi_connected_no_ip_prompt(text)
        or is_flightops_customer_report_pages_prompt(text)
        or is_install_anything_need_context_prompt(text)
        or is_printer_printing_without_extruding_confirm_prompt(text)
    )


def is_z_hold_current_reduce_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "z" in lower and "hold current" in lower and any(term in lower for term in (".75", "0.75", "overtemp", "over temp"))


def is_xy_home_current_reduce_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("home current", "homing current")) and any(term in lower for term in ("x and y", "x/y", "x & y")) and any(term in lower for term in ("0.5", ".5"))


def is_nozzle_04_restore_profile_cleanup_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("0.4 nozzle", "0.4mm nozzle", "0.4 mm nozzle"))
        and any(term in lower for term in ("change back", "back to"))
        and any(term in lower for term in ("unneeded printer profile", "installed", "profile"))
    )


def is_box_humidity_target_enable_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "box humidity" in lower
        and any(term in lower for term in ("target temp", "target", "60 degrees", "60"))
        and any(term in lower for term in ("enable", "auto box humidity", "humidity control"))
    )


def is_lane_specific_sensor_motor_architecture_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("lanes", "lane"))
        and any(term in lower for term in ("sensors", "motors"))
        and any(term in lower for term in ("no common sensors", "no common", "specific to the lanes", "t0"))
    )


def is_contextless_prusa_github_deep_research_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "prusa github" in lower
        and any(term in lower for term in ("online forums", "dig deep", "changed", "incorrectly"))
        and len(lower.split()) < 35
    )


def is_ratrig_deep_audit_cleanup_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("rat rig", "ratrig"))
        and any(term in lower for term in ("deep dive audit", "all layers"))
        and any(term in lower for term in ("klipper", "macros", "cfg", "duplicates", "robust", "dependable"))
    )


def is_qidi_box_u1_aux_feeder_lane_architecture_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "qidi box" in lower
        and any(term in lower for term in ("4 indipendant lanes", "4 independent lanes", "four independent lanes", "lanes"))
        and any(term in lower for term in ("u1", "aux feeders", "single filament sensor", "loading and unloading"))
    )


def is_offset1219_direct_prompt(text):
    return (
        is_z_hold_current_reduce_prompt(text)
        or is_xy_home_current_reduce_prompt(text)
        or is_nozzle_04_restore_profile_cleanup_prompt(text)
        or is_box_humidity_target_enable_prompt(text)
        or is_lane_specific_sensor_motor_architecture_prompt(text)
        or is_contextless_prusa_github_deep_research_prompt(text)
        or is_ratrig_deep_audit_cleanup_prompt(text)
        or is_qidi_box_u1_aux_feeder_lane_architecture_prompt(text)
    )


def is_offline_backend_github_update_context_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and lower.strip().startswith(("lets do it", "let's do it"))
        and "machine is offline" in lower
        and any(term in lower for term in ("software on the back end", "software on the backend", "back end"))
        and any(term in lower for term in ("update the github", "update github", "github with all"))
    )


def is_flightops_inspection_item_dropdown_bug_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("complete inspection section", "complete inspection"))
        and "select the aircraft" in lower
        and any(term in lower for term in ("select inspection item", "inspection item"))
        and any(term in lower for term in ("does not populate", "doesn't populate", "dropdown", "drop down"))
    )


def is_offset1259_direct_prompt(text):
    return (
        is_offline_backend_github_update_context_prompt(text)
        or is_flightops_inspection_item_dropdown_bug_prompt(text)
    )


def is_project_cleanup_latest_data_cad_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("do some cleanup", "cleanup"))
        and any(term in lower for term in ("summarize everything we have learned", "summarize everything"))
        and any(term in lower for term in ("latest data and cad", "latest cad", "data and cad"))
        and any(term in lower for term in ("delete everything else", "no longer relevant", "no longer relevent"))
    )


def is_ratrig_manual_dual_probe_workflow_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("rat rig", "ratrig"))
        and any(term in lower for term in ("manual dual probe workflow", "dual probe workflow", "t0", "t1"))
        and "beacon" in lower
        and any(term in lower for term in ("heat soak", "high fidelity scan", "restart klipper", "xy and z delta"))
    )


def is_qidi_box_factory_firmware_archive_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "qidi box" in lower
        and any(term in lower for term in ("factory firmware", "reinstall"))
        and any(term in lower for term in ("archive our work", "dont loose anything", "don't lose anything", "pre box install", "beacon"))
    )


def is_codex_extend_testing_download_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("extend this testing", "additional 12 hours", "another 12 hours"))
        and any(term in lower for term in ("better than yours", "download what you need", "answers will be better"))
    )


def is_tailscale_printers_road_access_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "tailscale" in lower
        and "printers" in lower
        and any(term in lower for term in ("from my mac", "while i am on the road", "on the road", "see all my printers"))
    )


def is_offset1299_direct_prompt(text):
    return (
        is_project_cleanup_latest_data_cad_prompt(text)
        or is_ratrig_manual_dual_probe_workflow_prompt(text)
        or is_qidi_box_factory_firmware_archive_prompt(text)
        or is_codex_extend_testing_download_prompt(text)
        or is_tailscale_printers_road_access_prompt(text)
    )


def is_qidi_abs_stringing_profile_adjust_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "qidi" in lower
        and any(term in lower for term in ("abs - generic", "abs generic", "generic @system"))
        and any(term in lower for term in ("stringing", "slight adjustment", "make a slight adjustment"))
        and any(term in lower for term in ("profile", "profiles", "1280x720"))
    )


def is_qidi_context_change_followup_prompt(text):
    lower = str(text or "").lower().strip()
    return lower in {"lets go ahead and make the change on the qidi", "let's go ahead and make the change on the qidi"}


def is_github_push_followup_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        bool(lower)
        and any(term in lower for term in ("push to github", "publish to my github", "published to my github"))
        and not any(term in lower for term in ("open source", "credit", "credits", "abiding by the open source rules"))
    )


def is_github_open_source_credit_planning_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("keep going", "side note", "for your planning"))
        and any(term in lower for term in ("github", "open source", "credit", "credits"))
        and any(term in lower for term in ("share what we do", "share with everyone", "abiding by the open source rules"))
    )


def is_klipper_conversion_holdoff_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("hold off", "modding that machine"))
        and "klipper" in lower
        and any(term in lower for term in ("new hardware", "full klipper"))
    )


def is_marlin_prusa_klipper_compare_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "marlin" in lower
        and "klipper" in lower
        and any(term in lower for term in ("prusa marlin", "prusa marlin files", "compare them", "move forward"))
    )


def is_rat_rig_lookup_followup_prompt(text):
    lower = str(text or "").lower().strip()
    return bool(lower) and any(term in lower for term in ("look for the rat rig", "find the rat rig")) and len(lower) < 80


def is_ssh_credentials_history_lookup_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("ssh credintials", "ssh credentials", "ssh creds"))
        and any(term in lower for term in ("chat history", "look back"))
        and any(term in lower for term in ("makersvpn", "pi"))
    )


def is_offset1339_direct_prompt(text):
    return (
        is_qidi_abs_stringing_profile_adjust_prompt(text)
        or is_qidi_context_change_followup_prompt(text)
        or is_github_push_followup_prompt(text)
        or is_github_open_source_credit_planning_prompt(text)
        or is_klipper_conversion_holdoff_prompt(text)
        or is_marlin_prusa_klipper_compare_prompt(text)
        or is_rat_rig_lookup_followup_prompt(text)
        or is_ssh_credentials_history_lookup_prompt(text)
    )


def is_centauri_one_lookup_followup_prompt(text):
    lower = str(text or "").lower().strip()
    return bool(lower) and any(term in lower for term in ("centauri 1", "centauri carbon 1", "centauri carbon #1")) and any(term in lower for term in ("look once more", "look for", "find"))


def is_nebula_ebb42_wiring_github_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("nebula extruder", "ebb 42", "ebb42"))
        and any(term in lower for term in ("rgb", "switch"))
        and any(term in lower for term in ("wiring assignments", "where to wire", "used pins"))
        and "github" in lower
    )


def is_qidi_max_ez_plr_github_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("plr", "power loss recovery"))
        and any(term in lower for term in ("qidi max ez", ".147"))
        and "klipper" in lower
        and "github" in lower
    )


def is_klipper_platform_focus_guidance_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("not focus on rat rig specific", "not rat rig specific", "operating sysyem", "operating system"))
        and "klipper" in lower
        and any(term in lower for term in ("focus on that", "turn that to him"))
    )


def is_qidi_y_before_x_homing_fix_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "qidi" in lower
        and any(term in lower for term in ("homing issues", "always home y", "home y axis first", "y axis first"))
        and any(term in lower for term in ("then x", "x axis", "sequence"))
        and any(term in lower for term in ("ssh access", "please fix", "fix this"))
    )


def is_xy_homing_hold_current_change_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("homing current", "holding current"))
        and ".75" in lower
        and "x" in lower
        and "y" in lower
    )


def is_qidi_resume_context_followup_prompt(text):
    lower = str(text or "").lower().strip()
    return lower in {"lets pause on that. lets get back to the qidi.", "let's pause on that. let's get back to the qidi."}


def is_offset1379_direct_prompt(text):
    return (
        is_centauri_one_lookup_followup_prompt(text)
        or is_nebula_ebb42_wiring_github_prompt(text)
        or is_qidi_max_ez_plr_github_prompt(text)
        or is_klipper_platform_focus_guidance_prompt(text)
        or is_qidi_y_before_x_homing_fix_prompt(text)
        or is_xy_homing_hold_current_change_prompt(text)
        or is_qidi_resume_context_followup_prompt(text)
    )


def is_vaoc_camera_t0_t1_offset_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("rat rig", "ratrig"))
        and any(term in lower for term in ("4k camera", "camera", "vaoc"))
        and any(term in lower for term in ("t0", "t1"))
        and any(term in lower for term in ("z offset", "z-offset", "z offset delta", "offset calibration"))
        and "beacon" in lower
    )


def is_filament_load_unload_g28_preface_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("load and unload filament", "load/unload filament", "load/unload"))
        and any(term in lower for term in ("g28", "home check", "home before"))
        and any(term in lower for term in ("sequence", "commence", "preface"))
    )


def is_github_confident_push_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "github" in lower and any(term in lower for term in ("push these", "push this", "push it")) and "confident" in lower


def is_image_inspired_redesign_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("redesign using this image", "re design using this image")) and "<image" in lower


def is_qidi_plus4_network_search_prompt(text):
    lower = str(text or "").lower().strip()
    return bool(lower) and any(term in lower for term in ("search the network again", "check for the qidi again")) and any(term in lower for term in ("qidi plus 4", "qidi"))


def is_cc1_calibration_qidi_network_followup_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "cc1 firmware" in lower and "calibrations" in lower and any(term in lower for term in ("qidi again", "check for the qidi"))


def is_remote_printer_morning_followup_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("pick this up in the morning", "see it in the morning"))
        and any(term in lower for term in ("working remotely", "physical printer", "if it comes alive"))
    )


def is_generic_resume_followup_prompt(text):
    lower = str(text or "").lower().strip()
    return lower in {
        "lets pick up where we dropped off",
        "lets pick up where we left off",
        "lets pick up where we left off please",
        "lets pick up where we were disconnected",
        "let's pick up where we dropped off",
        "let's pick up where we left off",
        "let's pick up where we left off please",
        "let's pick up where we were disconnected",
    }


def is_filament_buffer_stop_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("insert filiment", "insert filament"))
        and "buffer" in lower
        and any(term in lower for term in ("shouldnt take it past", "shouldn't take it past", "until commanded to load", "collide"))
    )


def is_restart_it_to_check_followup_prompt(text):
    lower = str(text or "").lower().strip()
    return lower in {"lets restart it so i can check it", "let's restart it so i can check it"}


def is_max_ez_chat_state_scan_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("scan in all of our other chats", "all of our other chats")) and any(term in lower for term in ("max ez", "maxez"))


def is_print_code_ssh_diagnostic_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("stop guessing", "look deep", "actual code", "look at the code"))
        and any(term in lower for term in ("current print", "print"))
        and any(term in lower for term in ("missing loading the filament", "load the filament", "filament"))
        and any(term in lower for term in ("camera scanned", "calibration line", "flow calibration line"))
        and "ssh" in lower
    )


def is_stop_chat_terminate_automations_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("stop this chat", "chat may be getting too big", "continue in a new chat"))
        and any(term in lower for term in ("terminate all automations", "stop all automations", "pause all automations"))
    )


def is_rev_b_latest_compare_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("rev b", "revision b"))
        and any(term in lower for term in ("latest change", "new one", "new revision", "compare"))
        and "compare" in lower
    )


def is_qidi_box_pause_rethink_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("healthy pause", "think harder", "all available resources", "availablr resources"))
        and any(term in lower for term in ("qidi box", "qidi"))
        and any(term in lower for term in ("firmware", "software", "calibration step"))
    )


def is_rat_rig_mechanical_mods_pause_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("mechanical mods", "mechanical modifications"))
        and any(term in lower for term in ("rat rig", "ratrig", "v-core", "vcore"))
        and any(term in lower for term in ("get back on the software side", "software side", "when its finished", "when it's finished"))
    )


def is_diffuser_positive_z_airflow_test_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "diffuser" in lower
        and any(term in lower for term in ("positive z", "positive-z", "suction", "suction affect", "suction effect", "vacuum", "venturi"))
        and any(term in lower for term in ("airflow", "air flow", "wind blowing", "wind over"))
        and any(term in lower for term in ("test", "adjust", "upper geometry", "geometry"))
    )


def is_upload_all_files_later_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("upload all the files", "upload the files"))
        and any(term in lower for term in ("when i get home", "try it again", "we will try it again"))
    )


def is_adaptive_heat_soak_design_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("adaptive heat soak", "adaptive heat-soak", "adaptive heatsoak"))
        and any(term in lower for term in ("bed temp", "chamber temp"))
        and any(term in lower for term in ("every 60 seconds", "60 seconds", "run an adaptive bed mesh", "bed mesh"))
        and any(term in lower for term in ("compare", "previous meshes", "stabilize", "stabilise", "heat soak complete"))
    )


def is_adaptive_heat_soak_broad_design_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("adaptive heat soak", "adaptive heat-soak", "adaptive heatsoak"))
        and any(term in lower for term in ("rat os", "ratos", "voron", "vision minors", "v-core", "idex", "recent history"))
        and any(term in lower for term in ("equal to or better", "make something", "look at the current state", "recent history", "adaptive"))
    )


def is_flightops_scoped_feature_prompt(text):
    lower = str(text or "").lower()
    feature_terms = (
        "aircraft docs tab",
        "aircraft documents tab",
        "aircraft docs",
        "aircraft documents",
        "docs upload",
        "document upload",
        "upload button",
        "upload documents",
        "upload document",
        "reported maintenance discrepancy",
        "maintenance discrepancy",
        "maintenance expence",
        "maintenance expences",
        "maintenance expense",
        "maintenance expenses",
        "calendar event",
        "calander event",
        "scheduling section",
        "change the user type",
        "change user type",
        "monthly pdf report",
        "monthly report",
        "edit function to the pilots",
        "edit function to pilots",
        "add non maintenance services",
        "non maintenance services",
        "airfare",
        "taxis",
        "rental cars",
        "pilots to select",
        "all aircraft they want to see",
        "discrepancy list by aircraft",
        "grouped so the pilot",
        "rewrite the historical data",
        "historical data for n797ra",
        "pilot entered",
        "day rate",
    )
    return any(term in lower for term in feature_terms) and any(
        term in lower for term in ("aircraft", "pilot", "pilots", "customer", "customers", "report", "pdf", "discrepancy", "maintenance", "calendar", "calander", "schedule", "scheduling", "document", "docs", "flight")
    )


def is_slicer_filament_manufacturer_tab_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("filament manufacturer tab", "filament manufacturer", "manufacturer tab")) and any(
        term in lower for term in ("codex", "bambu", "polymaker", "drop down", "dropdown")
    )


def is_mainsail_ssh_password_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("ssh password", "ssh pass")) and any(term in lower for term in ("mainsail", "fluidd", "moonraker"))


def is_pi_restart_safety_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("restart the pi", "reboot the pi", "restart pi", "reboot pi")) and len(lower) < 180


def is_github_share_all_work_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("github repository", "git repository", "github repo")) and any(
        term in lower for term in ("share all of our work", "share our work", "all of our work", "public repo", "public repository")
    )


def is_ssh_logs_instead_guessing_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("ssh into", "ssh to", "ssh in")) and any(term in lower for term in ("logs", "log")) and any(
        term in lower for term in ("instead of guessing", "look at", "check")
    )


def is_prusa_api_key_ssh_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "prusa" in lower and any(term in lower for term in ("api key", "apikey", "api-key")) and any(term in lower for term in ("ssh", "find"))


def is_image_edit_missing_source_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("<image", "image #", "photo", "picture")) and any(
        term in lower for term in ("shading", "shade", "crop", "enhance", "high resolution", "high quality", "print-ready", "peramiter", "perimeter")
    )


def is_prusa_klipper_conversion_research_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "prusa" in lower and "klipper" in lower and any(term in lower for term in ("forums", "repositories", "repos", "converted", "conversion"))


def is_prusa_core_one_profiles_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "prusa core one" in lower and any(term in lower for term in ("profile", "profiles", "setup", "setting it up"))


def is_flightops_customer_users_database_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("check the database", "database")) and any(term in lower for term in ("lost customers", "customers")) and any(term in lower for term in ("users", "tracker"))


def is_aircraft_tool_supply_promo_code_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("promo code", "coupon", "discount")) and any(term in lower for term in ("aircraft tool supply", "aircraft tool", "aviation tool"))


def is_tailscale_credentials_login_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "tailscale" in lower and any(term in lower for term in ("credentials", "log in", "login", "auth key", "password"))


def is_spreadsheet_landscape_due_format_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "spreadsheet" in lower and any(term in lower for term in ("landscape", "1 page", "one page")) and any(term in lower for term in ("green", "yellow", "red", "report date", "auto populate"))


def is_flightops_maintenance_reserve_title_hide_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("maintenance reserve", "reserve cost")) and any(
        term in lower for term in ("title page", "total fixed cost", "fixed cost", "omit", "hide")
    )


def is_centauri_cosmos_firmware_upgrade_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("centauri carbon", "cc1", "centauri")) and "cosmos" in lower and any(term in lower for term in ("firmware", "upgrade", "worth it"))


def is_sovol_mainline_klipper_migration_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "sovol" in lower and "mainline klipper" in lower and any(term in lower for term in ("firmware", "migration", "convert", "how hard"))


def is_box_rfid_macros_check_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("box macros", "box macro", "rfid receivers", "rfid receiver")) and any(term in lower for term in ("turn", "enable", "on", "need"))


def is_zoffset_calibration_probe_log_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("zoffsetcalibration", "zoffset calibration", "z-offset", "z offset")) and any(
        term in lower for term in ("probe more than ten times", "nozzle not hot enough", "look in the logs", "determine why")
    )


def is_ratrig_belt_cheatsheet_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("cheat sheet", "cheatsheet")) and any(term in lower for term in ("1,1", "1, -1", "belt", "belts")) and any(term in lower for term in ("rat rig", "t0", "t1", "x or y"))


def is_sv08_petgcf_temp_recall_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("petg-cf", "petg cf", "petgcf")) and any(term in lower for term in ("sovol sv08 max", "sv08 max", "sovol")) and any(term in lower for term in ("chamber temp", "bed temp", "remind me", "supposed to be"))


def is_pdf_to_excel_hobbs_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "pdf" in lower and any(term in lower for term in ("excel", "spreadsheet")) and any(term in lower for term in ("formula", "formulas", "auto calculate", "hobbs"))


def is_ratrig_belt_frequency_chamber_inop_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "rat rig" in lower and any(term in lower for term in ("belt frequency", "belt calibrations", "belt calibration")) and any(term in lower for term in ("chamber heaters", "inop", "should not be used"))


def is_stop_current_print_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("stop the current print", "cancel the current print", "stop current print", "cancel current print")) and any(term in lower for term in ("console", "locked", "preflight", "send a command"))


def is_klipper_modifications_github_prep_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "klipper" in lower and any(term in lower for term in ("github", "repository", "repo")) and any(term in lower for term in ("dual z probe", "modified version", "prep", "changes and advantages", "credit", "deserve it"))


def is_qidi_nozzle_temp_access_feedback_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "qidi plus 4" in lower and any(
        term in lower for term in ("nozzle temp", "nozzle temperature", "hotend temp", "hotend temperature")
    )


def is_qidi_toolhead_beacon_health_mesh_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "qidi" in lower
        and any(term in lower for term in ("catastrophic nozzle", "nozzle failure", "toolhead", "health check"))
        and "beacon" in lower
        and any(term in lower for term in ("bed mesh", "mesh calibration", "save the results"))
    )


def is_orca_codex_blank_ip_host_mapping_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex"))
        and any(term in lower for term in ("ip addresses are blank", "ips are blank", "ip address is blank", "blank ip", "blank host"))
        and any(term in lower for term in ("snapmaker", "qidi", "printer", "connect"))
    )


def is_qidi_profiles_shaper_tuning_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "qidi" in lower and "profile" in lower and any(term in lower for term in ("shaper", "input shaper", "shaper calibrations", "compliment", "complement"))


def is_github_filament_process_update_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "github" in lower and any(term in lower for term in ("filaments", "filament")) and any(
        term in lower for term in ("processes", "process profiles", "procersses", "update")
    )


def is_qidi_chamber_heater_cap_verify_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "qidi" in lower and any(term in lower for term in ("chamber heater", "chamber heaters")) and any(
        term in lower for term in ("40%", "40 percent", "0.4", "capped", "cap", "verify")
    )


def is_youtube_video_analysis_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and not is_speaker_enclosure_regroup_reference_prompt(text)
        and any(term in lower for term in ("youtube", "youtu.be", "watch?v=", "ytimg.com", "google.com/imgres"))
        and any(term in lower for term in ("watch", "video", "analyze", "can you"))
    )


def is_speaker_enclosure_regroup_reference_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("floating bodies", "speaker", "enclosure"))
        and any(term in lower for term in ("acryl", "acrylic", "exterior walls", "panels"))
        and any(term in lower for term in ("ribs", "organic", "curvy", "harmonics"))
        and any(term in lower for term in ("regroup", "youtube", "review it", "references"))
    )


def is_codex_cli_ui_more_like_codex_combo_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("responses side by side", "more like you", "combine chat gpt cli", "chatgpt cli", "codex cli")) and any(
        term in lower for term in ("wind turbine", "web", "research", "rounded platform", "response")
    )


def is_klipper_beacon_comments_closed_next_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("klipper_beacon", "klipper beacon", "beacon repository", "beacon repo")) and any(
        term in lower for term in ("comments are closed", "comments closed", "closed currently", "where next", "next?")
    )


def is_cf_polymer_hotend_mount_material_compare_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("pctg-cf", "pctg cf", "pctgcf")) and any(
        term in lower for term in ("ppa-cf", "ppa cf", "ppacf")
    ) and any(term in lower for term in ("hot end mount", "hotend mount", "hot-end mount", "extruder mount", "toolhead mount"))


def is_website_design_before_migration_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("current website", "website")) and any(
        term in lower for term in ("your design", "the design", "design now")
    ) and any(term in lower for term in ("before we migrated", "before we migrate", "before migrating", "migrated it"))


def is_filament_input_pin_compare_remote_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("tinmancc", "tinmancc2", "cc1", "cc2", "centauri")) and any(
        term in lower for term in ("filament", "no filament")
    ) and any(term in lower for term in ("compare the inputs", "compare inputs", "which pin", "determine which pin", "input pin")) and any(
        term in lower for term in ("remote", "remotely", "working remotely", "currently")
    )


def is_aircraft_water_drain_true_false_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "aircraft" in lower and any(term in lower for term in ("drains installed", "drain installed", "water may collect", "water collects")) and any(
        term in lower for term in ("true false", "true or false")
    )


def is_flightops_work_organized_status_prompt(text):
    lower = str(text or "").lower().strip()
    return bool(lower) and "flight ops" in lower and "tracker" in lower and any(term in lower for term in ("organize", "organized", "organised")) and any(
        term in lower for term in ("did we", "have we", "any")
    )


def is_offset1459_direct_prompt(text):
    return (
        is_print_code_ssh_diagnostic_prompt(text)
        or is_stop_chat_terminate_automations_prompt(text)
        or is_rev_b_latest_compare_prompt(text)
        or is_qidi_box_pause_rethink_prompt(text)
        or is_rat_rig_mechanical_mods_pause_prompt(text)
        or is_diffuser_positive_z_airflow_test_prompt(text)
        or is_upload_all_files_later_prompt(text)
        or is_adaptive_heat_soak_design_prompt(text)
    )


def is_ffmpeg_v4l2_camera_log_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "libavutil" in lower and "video4linux2" in lower and "/dev/video0" in lower and "eoi missing" in lower


def is_flightops_multi_inspection_ui_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("inspection item", "inspection items"))
        and any(term in lower for term in ("check box", "checkbox", "select multiple", "multiple items"))
        and any(term in lower for term in ("entire screen width", "entry box", "dropdown", "drop down"))
    )


def is_makers_corner_guest_restart_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and "makers corner" in lower
        and any(term in lower for term in ("guest network", "2.4 network", "2.4ghz", "2.4 ghz"))
        and any(term in lower for term in ("restart", "refreshes", "refresh"))
    )


def is_qidi_nebula_pins_before_sensor_removal_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("qidi", "nebula"))
        and any(term in lower for term in ("tangle sensor", "filament width sensor"))
        and any(term in lower for term in ("rgb", "runout", "pins", "pinout"))
    )


def is_rat_rig_files_access_resume_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and any(term in lower for term in ("get back to the rat rig", "back to the rat rig")) and any(term in lower for term in ("access to the files", "still have access"))


def is_touchscreen_firmware_flash_walkthrough_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("walk me through the flashing", "walk me through flashing", "flash from the touchscreen", "flashing"))
        and any(term in lower for term in ("touchscreen", "upload the file", "upload file"))
    )


def is_klipper_request_draft_prompt(text):
    lower = str(text or "").lower()
    return bool(lower) and "klipper" in lower and any(term in lower for term in ("write a request", "draft a request", "request exactly what we want"))


def is_filament_box_no_filament_next_step_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("no filiment in the box", "no filament in the box"))
        and any(term in lower for term in ("whats next", "what's next", "keep moving forward"))
    )


def is_snapmaker_u1_custom_firmware_update_decision_prompt(text):
    lower = str(text or "").lower()
    return (
        bool(lower)
        and any(term in lower for term in ("snapmaker", "u1"))
        and any(term in lower for term in ("aftermarket firmware", "custom firmware"))
        and any(term in lower for term in ("new firmware release", "do we need", "update"))
    )


def is_manual_auto_feature_still_work_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("manually turn it off", "manual turn it off", "turn it off manually", "manually disable"))
        and any(term in lower for term in ("auto feature", "automatic feature", "auto", "automatic"))
        and any(term in lower for term in ("still work", "continue to work", "still run", "keep working"))
    )


def is_github_comments_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "github" in lower
        and any(term in lower for term in ("comments", "coments", "comment", "coment"))
        and any(term in lower for term in ("do people", "can people", "make", "leave", "use"))
    )


def is_plus4_sensorless_homing_force_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("plus 4", "plus4", "qidi"))
        and any(term in lower for term in ("sensorless homing", "homes the y axis", "homing"))
        and any(term in lower for term in ("force", "current", "carriage homes the y", "y axis"))
    )


def is_cc1_runout_continued_printing_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("cc1", "centauri carbon", "tinman"))
        and any(term in lower for term in ("filament ran out", "filament runout", "runout sensor", "ran out"))
        and any(term in lower for term in ("continued printing", "kept printing", "manual pausing", "manual pause", "during a print"))
        and any(term in lower for term in ("look at the code", "logs", "figure out", "fix", "think hard"))
    )


def is_flightops_fuel_method_cover_sheet_report_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("cover sheet", "cover page"))
        and any(term in lower for term in ("fuel method 2", "method 2"))
        and any(term in lower for term in ("customer report", "method b"))
        and any(term in lower for term in ("fuel onloaded", "second sheet", "stand alone page", "standalone page"))
    )


def is_flightops_customer_line_remove_label_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("customer line", "customer field", "customer header"))
        and any(term in lower for term in ("get rid of customer", "remove customer", "without customer", "just list"))
        and any(term in lower for term in ("customer name", "customers name", "customer's name", "name"))
    )


def is_offset1539_direct_prompt(text):
    return (
        is_manual_auto_feature_still_work_prompt(text)
        or is_github_comments_prompt(text)
        or is_plus4_sensorless_homing_force_prompt(text)
        or is_cc1_runout_continued_printing_prompt(text)
        or is_flightops_fuel_method_cover_sheet_report_prompt(text)
        or is_flightops_customer_line_remove_label_prompt(text)
    )


def is_flightops_pilot_report_by_pilot_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(lower) and "pilot report" in lower and any(term in lower for term in ("run a report by pilot", "report by pilot", "by pilot"))


def is_qidi_stepper_motor_temperature_missing_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("qidi", "plus 4", "plus4"))
        and any(term in lower for term in ("stepper motors", "stepper motor", "motor"))
        and any(term in lower for term in ("temperature", "temp"))
        and any(term in lower for term in ("not showing", "why", "missing", "see why"))
    )


def is_qidi_codex_library_filament_screen_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("qidi", "plus 4", "plus4"))
        and any(term in lower for term in ("printer itself", "on the printer", "screen", "ui"))
        and any(term in lower for term in ("codex library", "library"))
        and any(term in lower for term in ("new filament", "put new filament", "filament"))
    )


def is_ratrig_xy_offset_calibration_no_chamber_heat_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("rat rig", "ratrig"))
        and any(term in lower for term in ("xy nozzle offset calibration", "x/y nozzle offset calibration", "nozzle offset calibration"))
        and any(term in lower for term in ("without any chamber heat", "no chamber heat", "without chamber heat"))
    )


def is_flightops_report_date_totals_format_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "report" in lower
        and any(term in lower for term in ("date format", "mm/dd/yy", "mm/dd/yyyy"))
        and any(term in lower for term in ("totals at the bottom", "all on one line", "totals"))
    )


def is_sovol_obico_not_working_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(lower) and "sovol" in lower and "obico" in lower and any(term in lower for term in ("not working", "look into it", "broken", "offline"))


def is_flightops_customer_credit_dropdown_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("tracker", "report", "add flight"))
        and any(term in lower for term in ("credit for each customer", "section for credit", "customer credit"))
        and any(term in lower for term in ("dropdown", "previously input", "dont have to type", "don't have to type"))
    )


def is_flightops_admin_pilot_email_missing_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("website", "flight ops", "tracker"))
        and any(term in lower for term in ("admin added a pilot", "added a pilot to the calendar", "pilot to the calendar"))
        and any(term in lower for term in ("did not recieve an email", "did not receive an email", "no email"))
        and any(term in lower for term in ("see why", "why this happened", "happened"))
    )


def is_offset1579_direct_prompt(text):
    return (
        is_flightops_pilot_report_by_pilot_prompt(text)
        or is_qidi_stepper_motor_temperature_missing_prompt(text)
        or is_qidi_codex_library_filament_screen_prompt(text)
        or is_ratrig_xy_offset_calibration_no_chamber_heat_prompt(text)
        or is_flightops_report_date_totals_format_prompt(text)
        or is_sovol_obico_not_working_prompt(text)
        or is_flightops_customer_credit_dropdown_prompt(text)
        or is_flightops_admin_pilot_email_missing_prompt(text)
    )


def is_orca_codex_partially_locked_up_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("orca codex", "orcaslicer codex", "orca slicer codex"))
        and any(term in lower for term in ("partially locked up", "locked up", "hung", "frozen"))
        and any(term in lower for term in ("see why", "fix it", "can you"))
    )


def is_qidi_prepare_tab_nozzle_sync_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "qidi" in lower
        and any(term in lower for term in ("nozzle size drop down", "nozzle size dropdown", "nozzle dropdown"))
        and any(term in lower for term in ("prepare tab", "machine", "sync nozzle size", "sync"))
    )


def is_flightops_aircraft_buttons_flights_page_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("flights page", "flight page"))
        and any(term in lower for term in ("buttons for each aircraft", "button for each aircraft", "push buttons"))
        and any(term in lower for term in ("open the flights for that aircraft", "flights for that aircraft", "aircraft"))
    )


def is_slicer_app_continue_until_all_printers_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("continue with the build", "contunue with the build", "do not stop"))
        and any(term in lower for term in ("working app", "slice and print"))
        and any(term in lower for term in ("all my printers", "all printers"))
    )


def is_pctg_profiles_all_machines_qidi_ui_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "pctg" in lower
        and any(term in lower for term in ("profiles", "profile"))
        and any(term in lower for term in ("all machines", "all printers"))
        and any(term in lower for term in ("all nozzles", "nozzles"))
        and any(term in lower for term in ("qidi", "ui interface", "ui"))
    )


def is_offset1619_direct_prompt(text):
    return (
        is_orca_codex_partially_locked_up_prompt(text)
        or is_qidi_prepare_tab_nozzle_sync_prompt(text)
        or is_flightops_aircraft_buttons_flights_page_prompt(text)
        or is_slicer_app_continue_until_all_printers_prompt(text)
        or is_pctg_profiles_all_machines_qidi_ui_prompt(text)
        or is_beacon_ztilt_active_check_prompt(text)
        or is_ratrig_macro_upload_confidence_prompt(text)
        or is_post_restart_g28_bed_crash_prompt(text)
        or is_flightops_pilot_daily_rate_exclusion_prompt(text)
        or is_flightops_shutdown_error_history_prompt(text)
        or is_flightops_storage_projection_prompt(text)
        or is_flightops_fixed_maintenance_cover_page_prompt(text)
        or is_heat_soak_points_no_manual_jog_prompt(text)
        or is_ratrig_toolboard_mcu_restart_prompt(text)
        or is_snapmaker_poweroff_mcu_ssh_diagnostic_prompt(text)
        or is_qidi_filament_switch_load_forum_prompt(text)
        or is_macos_sequoia_tahoe_upgrade_prompt(text)
    )


def is_3d_chameleon_cleanup_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("3d chameleon", "3dchameleon", "chameleon"))
        and any(term in lower for term in ("delete", "remove", "clean up", "cleanup"))
        and any(term in lower for term in ("project is way dead", "way dead", "dead"))
    )


def is_printer_ip_changed_password_note_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(lower) and any(term in lower for term in ("ip has changed", "ip changed", "changed to")) and "192.0.2.145" in lower and "password" in lower


def is_flightops_aircraft_documents_restore_upload_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("documents", "docs"))
        and any(term in lower for term in ("all aircraft", "aircraft"))
        and any(term in lower for term in ("listed", "were listed"))
        and any(term in lower for term in ("upload them back", "upload back", "restore", "put them back"))
    )


def is_klipper_load_unload_macro_buttons_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("klipper", "klipper screen", "klipperscreen"))
        and any(term in lower for term in ("load macro", "load filament", "auto load", "auto loads", "autoload"))
        and any(term in lower for term in ("unload macro", "unload filament"))
        and any(term in lower for term in ("button", "buttons", "klipper screen", "klipperscreen", "ui"))
    )


def is_all_printers_supported_continue_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("all of my printers", "all my printers", "all printers"))
        and any(term in lower for term in ("supported", "support"))
        and any(term in lower for term in ("continue", "keep going"))
    )


def is_u1_buffer_sensor_delete_confirmation_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("u1", "snapmaker"))
        and any(term in lower for term in ("buffer", "lanes merge", "merge into 1 lane", "merge into one lane"))
        and any(term in lower for term in ("delete", "deleted", "remove", "removed"))
        and any(term in lower for term in ("sensor", "sensors"))
    )


def is_temporary_immediate_pause_macro_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("helper macro", "macro"))
        and any(term in lower for term in ("pause the print", "pause print", "immediately", "immediatly"))
        and any(term in lower for term in ("mechanical side", "wasted filament", "until the mechanical"))
    )


def is_mainline_klipper_camera_xy_measurement_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "mainline klipper" in lower
        and any(term in lower for term in ("camera data", "camera"))
        and any(term in lower for term in ("measuring x and y", "measure x and y", "x and y"))
    )


def is_typical_questions_domain_list_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("typical questions", "questions that you get"))
        and "3d printing" in lower
        and "cnc" in lower
        and any(term in lower for term in ("solar and wind", "solar", "wind"))
        and "cfd" in lower
        and "aviation" in lower
    )


def is_snapmaker_u1_installed_filaments_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("u1", "snapmaker"))
        and any(term in lower for term in ("filaments", "filament"))
        and any(term in lower for term in ("showing installed", "installed", "showing"))
    )


def is_offset1659_direct_prompt(text):
    return (
        is_3d_chameleon_cleanup_prompt(text)
        or is_printer_ip_changed_password_note_prompt(text)
        or is_flightops_aircraft_documents_restore_upload_prompt(text)
        or is_klipper_load_unload_macro_buttons_prompt(text)
        or is_all_printers_supported_continue_prompt(text)
        or is_u1_buffer_sensor_delete_confirmation_prompt(text)
        or is_temporary_immediate_pause_macro_prompt(text)
        or is_mainline_klipper_camera_xy_measurement_prompt(text)
        or is_typical_questions_domain_list_prompt(text)
        or is_snapmaker_u1_installed_filaments_prompt(text)
    )


def is_sovol_sv08_petg_cf_apply_changes_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("sovol", "svo8", "sv08"))
        and any(term in lower for term in ("petg-cf", "petg cf"))
        and any(term in lower for term in ("make these changes", "apply these changes", "these changes"))
    )


def is_pick_up_where_left_off_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(re.search(r"^(?:please\\s+)?pick\\s+up\\s+where\\s+you\\s+left\\s+off[.!? ]*$", lower))


def is_uploaded_files_fix_coding_errors_stability_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("uploaded files", "attached files"))
        and any(term in lower for term in ("coding errors", "code errors", "errors"))
        and any(term in lower for term in ("app run stable", "run stable", "stable"))
    )


def is_qidi_backup_and_stock_restore_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("qidi box", "qidi"))
        and any(term in lower for term in ("back to stock", "return", "restore", "stock"))
        and any(term in lower for term in ("save all of our work", "save our work", "backup", "back up", "locally on the mac"))
    )


def is_beacon_ztilt_active_check_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "beacon" in lower
        and any(term in lower for term in ("z tilt", "z_tilt", "z_tilt_adjust"))
        and any(term in lower for term in ("red", "light", "illuminates", "illuminating", "active", "loaded"))
        and any(term in lower for term in ("t0", "toolhead", "bed contacts", "current software load"))
    )


def is_ratrig_macro_upload_confidence_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("rat rig", "ratrig"))
        and "macro" in lower
        and any(term in lower for term in ("level of confidence", "confidence", "will work"))
        and any(term in lower for term in ("uploaded", "upload", "created"))
    )


def is_post_restart_g28_bed_crash_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "klipper" in lower
        and any(term in lower for term in ("restart", "restarted"))
        and any(term in lower for term in ("g28", "home", "homing"))
        and any(term in lower for term in ("crash", "crashes", "crashed", "into the toolhead", "bed"))
    )


def is_flightops_pilot_daily_rate_exclusion_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("pilot", "pilots", "colin"))
        and any(term in lower for term in ("daily rate", "salary", "paid"))
        and any(term in lower for term in ("exclude", "exclusion", "does not get paid"))
        and any(term in lower for term in ("aircraft", "n296sa", "n533ss"))
    )


def is_flightops_shutdown_error_history_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("shutdown", "shut down"))
        and any(term in lower for term in ("what was the error", "error i reported", "few posts ago"))
    )


def is_flightops_storage_projection_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("flight tracker", "flightops", "flight ops"))
        and "storage" in lower
        and any(term in lower for term in ("2 months", "two months", "how long", "expand storage"))
        and any(term in lower for term in ("aircraft", "maintenance tracking"))
    )


def is_flightops_fixed_maintenance_cover_page_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("cover page", "cover sheet"))
        and any(term in lower for term in ("fixed costs", "maintenance costs"))
        and any(term in lower for term in ("month", "monthly", "total"))
    )


def is_heat_soak_points_no_manual_jog_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("heat soak", "heat-soak", "heating up"))
        and any(term in lower for term in ("g28", "z tilt", "z_tilt", "z_tilt_adjust"))
        and any(term in lower for term in ("specify points", "points"))
        and any(term in lower for term in ("manual jog", "jog the toolheads", "do not have to manually"))
    )


def is_ratrig_toolboard_mcu_restart_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("rat rig", "ratrig"))
        and any(term in lower for term in ("mcu toolboard 1", "toolboard 1", "tool board 1"))
        and any(term in lower for term in ("lost communication", "communication"))
        and any(term in lower for term in ("restart", "regain communication"))
    )


def is_snapmaker_poweroff_mcu_ssh_diagnostic_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "snapmaker" in lower
        and any(term in lower for term in ("power off signal", "power-off signal", "mcu"))
        and any(term in lower for term in ("ssh", "diagnostic", "figure out"))
    )


def is_qidi_filament_switch_load_forum_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("qidi", "box"))
        and any(term in lower for term in ("filiment", "filament"))
        and any(term in lower for term in ("switch", "last load", "filament_detected"))
        and any(term in lower for term in ("extruder is not turning", "toolhead extruder", "qidi forums", "forums"))
    )


def is_macos_sequoia_tahoe_upgrade_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(lower) and "sequoia" in lower and "tahoe" in lower and any(term in lower for term in ("install", "upgrade", "then", "just"))


def is_dry_room_sub_10_humidity_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("humidity", "relative humidity", "rh"))
        and any(term in lower for term in ("below 10", "under 10", "<10", "10%"))
        and any(term in lower for term in ("room", "space", "shop", "area"))
        and any(term in lower for term in ("reduce", "maintain", "control", "keep"))
    )


def is_project_github_link_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "github" in lower
        and any(term in lower for term in ("link", "repo", "repository", "url"))
        and any(term in lower for term in ("this project", "current project", "the project"))
    )


def is_stock_firmware_password_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("stock password", "default password", "factory password"))
        and any(term in lower for term in ("firmware", "image", "os", "sd card"))
    )


def is_flightops_pi_vpn_mobile_access_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("pilots", "pilot"))
        and any(term in lower for term in ("customers", "customer"))
        and any(term in lower for term in ("mobile devices", "mobile", "phone", "phones", "anywhere"))
        and any(term in lower for term in ("rasberry pi", "raspberry pi", "pi"))
        and any(term in lower for term in ("makers vpn", "makersvpn", "maker vpn", "vpn"))
    )


def is_ratrig_vcore_extrusion_gantry_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("rat rig", "ratrig"))
        and any(term in lower for term in ("vcore 4", "v-core 4", "v core 4"))
        and any(term in lower for term in ("500", "5xx"))
        and any(term in lower for term in ("extrusion", "extrusions"))
        and any(term in lower for term in ("toolhead gantry", "gantry", "x gantry"))
    )


def is_humidity_control_box_minimal_heat_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("humidity", "humidty"))
        and any(term in lower for term in ("box", "chamber", "enclosure"))
        and any(term in lower for term in ("minimal or no heat", "minimal heat", "no heat", "without heat"))
        and any(term in lower for term in ("best design", "best way", "controlling", "controling", "control"))
    )


def is_flightops_document_not_found_user_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("flightops", "flight ops", "tracker", "aircraft docs", "aircraft documents"))
        and any(term in lower for term in ("document not found", '"detail":"document not found"', "view or download", "download aircraft docs"))
        and any(term in lower for term in ("logged in as a user", "as a user", "user"))
    )


def is_flightops_old_spreadsheet_download_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("flightops tracker", "flight ops tracker", "tracker"))
        and any(term in lower for term in ("download", "downloaded"))
        and any(term in lower for term in ("old spreadsheet", "old file", "old version"))
    )


def is_flightops_monthly_report_back_button_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("monthly report", "generated report", "report page"))
        and any(term in lower for term in ("back button", "back to the tracker", "navigate back", "get back to the tracker"))
        and any(term in lower for term in ("tracker", "flightops", "flight ops"))
    )


def is_cad_file_format_preference_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and (
            (
                any(term in lower for term in ("cad file", "cad format", "file format"))
                and any(term in lower for term in ("what format", "which format", "prefer", "preferred"))
            )
            or (
                lower.startswith("when giving you a cad file")
                and any(term in lower for term in ("what format", "prefer"))
            )
        )
    )


def is_flightops_tinneyaviation_data_loss_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("tinneyaviation.com", "tinney aviation"))
        and any(term in lower for term in ("logging in", "log in", "website", "web app", "app"))
        and any(term in lower for term in ("data", "form", "input"))
        and any(term in lower for term in ("lost", "getting lost", "not saving", "disappearing", "missing"))
    )


def is_flightops_role_redirect_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("pilots", "pilot"))
        and any(term in lower for term in ("customers", "customer"))
        and any(term in lower for term in ("admins", "admin"))
        and any(term in lower for term in ("flights page", "schedule page", "home page"))
        and any(term in lower for term in ("directed automatically", "redirect", "after login", "log into", "logging in"))
    )


def is_orca_install_location_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(lower) and any(term in lower for term in ("where do i install the new orca", "where should i install the new orca"))


def is_snapmaker_u1_usb_port_location_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("snapmaker u1", "u1 snapmaker"))
        and any(term in lower for term in ("usb port", "usb-a port", "usb a port"))
        and any(term in lower for term in ("where is", "physically located", "location"))
    )


def is_klipperscreen_installed_working_check_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "klipperscreen" in lower
        and any(term in lower for term in ("installed and working", "installed", "working"))
        and any(term in lower for term in ("while we are in", "make sure", "verify", "check"))
    )


def is_codex_vendor_profile_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("make codex a vendor", "codex as a vendor", "codex a vendor"))
        and not any(term in lower for term in ("github vendor", "business vendor", "supplier"))
    )


def is_sensorless_homing_decimal_sensitivity_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("sensorless homing", "sensorles homing", "sensor-less homing"))
        and any(term in lower for term in ("1.5", "decimal", "fraction"))
        and any(term in lower for term in ("accept", "valid", "sensitivity value", "sgthrs"))
    )


def is_ratrig_generic_copy_preset_review_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("ratrig generic copy preset", "rat rig generic copy preset", "generic copy preset"))
        and any(term in lower for term in ("review", "look at", "possible issues", "corrections", "correct"))
    )


def is_google_earth_roofline_solar_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("google earth", "satellite image", "roofline"))
        and any(term in lower for term in ("solar panel", "solar panels", "panels"))
        and any(term in lower for term in ("place", "placement", "identify", "where"))
    )


def is_bed_mesh_z_offset_calibration_research_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("bed mesh calibration", "precision z offset", "z offset calibration", "nozzle offset calibration"))
        and any(term in lower for term in ("search the web", "github", "advancments", "advancements", "best available processes"))
    )


def is_github_update_changes_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and "github" in lower
        and any(term in lower for term in ("update", "push", "upload"))
        and any(term in lower for term in ("changes we have made", "changes made", "our changes", "the changes"))
    )


def is_spdt_runout_immediate_pause_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and not is_klipper_load_unload_macro_buttons_prompt(text)
        and not any(term in lower for term in ("chamber light", "rgb macro", "auto load", "auto loads", "autoload"))
        and any(term in lower for term in ("spdt", "switch"))
        and any(term in lower for term in ("filament runout sensor input", "runout sensor input", "filament runout"))
        and any(term in lower for term in ("immediately pause", "pause the print", "runout is detected"))
    )


def is_flightops_mobile_app_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("mobile app", "android", "iphone", "ipad", "mobile phones"))
        and any(term in lower for term in ("flight ops tracker", "pilots", "customers"))
        and any(term in lower for term in ("possible", "create", "access"))
    )


def is_flash_existing_board_klipper_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("flash the existing board", "existing board"))
        and "klipper" in lower
        and any(term in lower for term in ("possible", "would it be possible", "can"))
    )


def is_ratrig_idex_user_preset_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("user presets", "user preset"))
        and any(term in lower for term in ("rat rig idex 500", "ratrig idex 500", "rat rig", "ratrig"))
        and any(term in lower for term in ("printer presets", "prenter presets", "rely on"))
    )


def is_qidi_box_before_freedi_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("qidi box", "qidi-box"))
        and any(term in lower for term in ("freedi", "free di", "free-di"))
        and any(term in lower for term in ("before", "migrate", "install"))
    )


def is_moonraker_json_status_blob_prompt(text):
    raw = str(text or "").strip()
    lower = raw.lower()
    return raw.startswith("{") and '"result"' in lower and "klippy_connected" in lower and "moonraker" in lower


def is_local_slicer_profile_parameter_pull_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("pull", "current", "from tinmanx1", "from orca", "profile parameters", "filament settings"))
        and any(term in lower for term in ("filament settings", "filament profile", "profile parameters", "parameters"))
        and any(term in lower for term in ("pet-cf", "petcf", "pctg", "pla", "asa", "abs", "filament"))
        and any(term in lower for term in ("nozzle", "plus 4", "qidi", "tinmanx1", "orca"))
    )


def is_plus4_petcf_06_filament_settings_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        bool(lower)
        and any(term in lower for term in ("pull", "current filament settings", "filament settings"))
        and any(term in lower for term in ("pet-cf", "petcf"))
        and any(term in lower for term in ("0.6 nozzle", "0.6mm nozzle", "0.6 mm nozzle"))
        and any(term in lower for term in ("plus 4", "qidi"))
    )


def is_offset1699_direct_prompt(text):
    return (
        is_sovol_sv08_petg_cf_apply_changes_prompt(text)
        or is_pick_up_where_left_off_prompt(text)
        or is_uploaded_files_fix_coding_errors_stability_prompt(text)
        or is_qidi_backup_and_stock_restore_prompt(text)
        or is_dry_room_sub_10_humidity_prompt(text)
        or is_project_github_link_prompt(text)
        or is_stock_firmware_password_prompt(text)
        or is_flightops_pi_vpn_mobile_access_prompt(text)
        or is_ratrig_vcore_extrusion_gantry_prompt(text)
        or is_humidity_control_box_minimal_heat_prompt(text)
        or is_flightops_document_not_found_user_prompt(text)
        or is_flightops_old_spreadsheet_download_prompt(text)
        or is_flightops_monthly_report_back_button_prompt(text)
        or is_cad_file_format_preference_prompt(text)
        or is_flightops_tinneyaviation_data_loss_prompt(text)
        or is_flightops_role_redirect_prompt(text)
        or is_orca_install_location_prompt(text)
        or is_snapmaker_u1_usb_port_location_prompt(text)
        or is_klipperscreen_installed_working_check_prompt(text)
        or is_ratrig_generic_copy_preset_review_prompt(text)
        or is_google_earth_roofline_solar_prompt(text)
        or is_bed_mesh_z_offset_calibration_research_prompt(text)
        or is_github_update_changes_prompt(text)
        or is_spdt_runout_immediate_pause_prompt(text)
        or is_flightops_mobile_app_prompt(text)
        or is_flash_existing_board_klipper_prompt(text)
        or is_ratrig_idex_user_preset_prompt(text)
        or is_qidi_box_before_freedi_prompt(text)
        or is_moonraker_json_status_blob_prompt(text)
        or is_plus4_petcf_06_filament_settings_prompt(text)
    )


def is_offset1499_direct_prompt(text):
    return (
        is_ffmpeg_v4l2_camera_log_prompt(text)
        or is_flightops_multi_inspection_ui_prompt(text)
        or is_makers_corner_guest_restart_prompt(text)
        or is_qidi_nebula_pins_before_sensor_removal_prompt(text)
        or is_rat_rig_files_access_resume_prompt(text)
        or is_touchscreen_firmware_flash_walkthrough_prompt(text)
        or is_klipper_request_draft_prompt(text)
        or is_filament_box_no_filament_next_step_prompt(text)
        or is_snapmaker_u1_custom_firmware_update_decision_prompt(text)
    )


def is_offset1419_direct_prompt(text):
    return (
        is_vaoc_camera_t0_t1_offset_prompt(text)
        or is_filament_load_unload_g28_preface_prompt(text)
        or is_github_confident_push_prompt(text)
        or is_image_inspired_redesign_prompt(text)
        or is_qidi_plus4_network_search_prompt(text)
        or is_cc1_calibration_qidi_network_followup_prompt(text)
        or is_remote_printer_morning_followup_prompt(text)
        or is_generic_resume_followup_prompt(text)
        or is_filament_buffer_stop_prompt(text)
        or is_restart_it_to_check_followup_prompt(text)
        or is_max_ez_chat_state_scan_prompt(text)
    )


def is_offset1059_printer_direct_prompt(text):
    return (
        is_sovol_adaptive_bed_mesh_prompt(text)
        or is_u1_codex_filaments_ui_prompt(text)
        or is_klipper_detached_moonraker_dirty_prompt(text)
        or is_klipper_cnc_laser_fit_prompt(text)
        or is_ratrig_noctua_4010_part_cooling_prompt(text)
        or is_sensorless_three_trigger_average_prompt(text)
        or is_sovol_filament_cut_retract_prompt(text)
        or is_ratrig_full_build_integration_prompt(text)
        or is_ratrig_prepare_tab_sync_filament_prompt(text)
    )


def is_offset1059_flightops_direct_prompt(text):
    return (
        is_flightops_rate_provision_prompt(text)
        or is_flightops_date_format_prompt(text)
        or is_flightops_pilot_display_dropdown_prompt(text)
    )


def is_tool_inventory_visibility_prompt(text):
    lower = str(text or "").lower()
    explicit_inventory = (
        any(term in lower for term in ("inventory", "take an inventory", "list", "scan"))
        and any(term in lower for term in ("tools", "software", "program resources", "capabilities"))
        and any(term in lower for term in ("he sees", "available on this mac", "available to him", "this mac", "visible"))
    )
    optional_tools_visibility = (
        any(term in lower for term in ("optional tools", "every tool", "all tools", "tools available", "available tools"))
        and any(term in lower for term in ("he sees", "available on this mac", "available to him", "this mac", "visible"))
    )
    return explicit_inventory or optional_tools_visibility


def is_ip_changed_missing_target_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        len(lower) < 140
        and any(term in lower for term in ("ip changed", "ip address changed", "ip possibly changed", "changed possibly"))
        and any(term in lower for term in ("can you check", "check to see", "find", "possibly", "maybe"))
        and not any(char.isdigit() for char in lower)
    )


def is_printer_inventory_ip_update_prompt(text):
    lower = str(text or "").lower().strip()
    if not any(term in lower for term in ("qidi plus 4", "qidi max ez", "max ez", "maxez", "max ex")):
        return False
    has_ip = bool(re.search(r"\b(?:10|172|192)\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", lower))
    direct_update = has_ip and any(term in lower for term in ("update", "change", "changed", "now on", "ip's", "ip\u2019s", "ips", "ip addresses"))
    local_db_followup = any(term in lower for term in ("database", "inventory", "ui", "this page", "your list", "local list"))
    return direct_update or (local_db_followup and any(term in lower for term in ("already been changed", "correct address", "wrong address", "change them")))


def is_printer_inventory_ip_list_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("current list", "current ip", "ip addresses", "ip address", "saved ip", "printer ips", "printer ip's", "printer ip\u2019s"))
        and any(term in lower for term in ("printers", "printer", "all my printers", "all of my printers"))
    )


def requested_lan_ip_from_text(text):
    raw = str(text or "")
    if re.search(r"\b127(?:\.\d{1,3}){1,3}\b", raw):
        return ""
    full_match = re.search(r"\b((?:10|172|192)\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", raw)
    if full_match:
        return full_match.group(1)
    short_match = re.search(r"(?<!\d)\.(\d{1,3})\.(\d{1,3})(?!\d)", raw)
    if short_match:
        return f"192.168.{short_match.group(1)}.{short_match.group(2)}"
    two_octet_match = re.search(r"\b(\d{1,3})\.(\d{1,3})\b", raw)
    if two_octet_match and any(term in raw.lower() for term in ("back on", "restore", "set", "assign", "reservation")):
        return f"192.168.{two_octet_match.group(1)}.{two_octet_match.group(2)}"
    return ""


def is_lan_ip_restoration_context_prompt(text):
    lower = str(text or "").lower().strip()
    if len(lower) > 180 or not requested_lan_ip_from_text(lower):
        return False
    return any(
        term in lower
        for term in (
            "get it back on",
            "put it back on",
            "back on",
            "restore",
            "return it to",
            "move it to",
            "set it to",
            "make sure the ssh login is now",
        )
    )


def is_qidi_login_screen_connect_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("qidi", "qidi plus4maxez", "qidiplus4maxez", "max ez", "maxez", "max ex", "qidi max"))
        and any(term in lower for term in ("127.0.1.1", "login:", "screen says", "saying its ip"))
        and any(term in lower for term in ("can we connect", "can you connect", "get it back on course", "connect"))
    )


def is_network_moved_ip_scan_prompt(text):
    lower = str(text or "").lower().strip()
    network_scan = any(term in lower for term in ("scan the network", "network scan", "scan lan", "scan the lan"))
    device_find = any(term in lower for term in ("find", "try to find", "locate", "look for", "discover"))
    moved_ip = any(term in lower for term in ("moved ip", "moved ip's", "changed ip", "new ip", "ip shift", "ip shifted"))
    qidi_max = any(term in lower for term in ("max ez", "maxez", "max ex", "maz ez", "qidi max", "qidi plus 4 max"))
    return moved_ip and (network_scan or (device_find and qidi_max))


def is_max_ez_wlan_followup_prompt(text):
    lower = str(text or "").lower().strip()
    wlan_terms = any(term in lower for term in ("wlan 1", "wlan1", "wlan-1", "wifi association", "wi-fi association", "association"))
    max_ez_terms = any(term in lower for term in ("max ez", "maxez", "max ex", "qidi max", "qidi plus 4 max"))
    short_wifi_followup = wlan_terms and len(lower) < 160 and any(term in lower for term in ("connect", "priority", "first", "association", "restart"))
    return (max_ez_terms and wlan_terms) or short_wifi_followup


def is_qidi_plus4_usb_wifi_dongle_prompt(text):
    lower = str(text or "").lower().strip()
    plus4_terms = any(term in lower for term in ("plus 4", "x-plus 4", "xplus4", "qidi plus 4", "qidi x-plus 4"))
    usb_wifi_terms = any(term in lower for term in ("usb wifi dongle", "usb wi-fi dongle", "wifi dongle", "wi-fi dongle", "usb wireless", "wireless dongle"))
    utilization_terms = any(term in lower for term in ("utilized", "being used", "using it", "active", "enabled", "prefer", "priority", "make sure"))
    return plus4_terms and usb_wifi_terms and utilization_terms


def is_rat_rig_macro_folder_save_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("rat rig", "ratrig", "v-core", "vcore"))
        and any(term in lower for term in ("macro", "macros"))
        and any(term in lower for term in ("find the local folder", "local folder", "save the file there", "save it there", "save the macro", "folder for"))
    )


def is_qidi_load_unload_speed_match_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("qidi", "plus 4", "x-plus 4", "max ez"))
        and any(term in lower for term in ("load", "unload"))
        and any(term in lower for term in ("speed", "speeds", "very slow", "slow"))
        and any(term in lower for term in ("config", "configs", "macro", "macros", "match", "look at", "find"))
    )


def is_qidi_camera_refresh_rate_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("qidi", "plus 4", "x-plus 4", "max ez"))
        and any(term in lower for term in ("camera", "webcam", "crowsnest", "mjpg"))
        and any(term in lower for term in ("refresh rate", "fps", "frame rate", "01 fps", "1 fps"))
        and any(term in lower for term in ("increase", "try", "fix", "showing", "still"))
    )


def is_max_ez_process_profile_tuning_prompt(text):
    lower = str(text or "").lower().strip()
    max_ez_terms = any(term in lower for term in ("max ez", "maxez", "max ex", "qidi max", "qidi plus 4 max"))
    process_terms = any(term in lower for term in ("process profile", "process profiles", "machine process", "machine processes", "profiles", "profile"))
    tuning_terms = any(term in lower for term in ("0.4", "0.8", "1.0", "nozzle", "realistic speed", "quality", "acceleration", "accelerations", "reasonable"))
    short_accel_followup = len(lower) < 140 and any(term in lower for term in ("accelerations", "acceleration")) and any(term in lower for term in ("reasonable", "other", "all"))
    return (max_ez_terms and process_terms and tuning_terms) or short_accel_followup


def is_adaptive_heat_soak_status_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("heat soak", "heat-soak", "heatsoak"))
        and any(term in lower for term in ("adaptive", "process", "seeing a 5 min", "5 min heat soak", "5 minute heat soak"))
        and any(term in lower for term in ("is this", "currently seeing", "process for", "working as", "supposed to"))
    )


def is_no_filament_loaded_test_prompt(text):
    lower = str(text or "").lower().strip()
    return any(term in lower for term in ("no filament loaded", "without filament", "no filament")) and any(
        term in lower for term in ("start a print", "test the system", "appropriat", "appropriate", "run a print")
    )


def is_document_compliance_review_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("review what we have done", "review what we've done", "make sure we are in compliance", "make sure we're in compliance", "check compliance"))
        and any(term in lower for term in ("this document", "the document", "attached document", "requirements document", "spec document"))
    )


def is_lost_ip_sd_card_recovery_prompt(text):
    lower = str(text or "").lower().strip()
    return (
        any(term in lower for term in ("lost the ip", "lost ip", "lost its ip", "no ip", "ip again"))
        and any(term in lower for term in ("sd card", "sdcard", "card"))
        and any(term in lower for term in ("do you want", "want the", "should i", "put", "insert"))
    )


def is_printing_from_slot_three_prompt(text):
    lower = str(text or "").lower().strip()
    return any(term in lower for term in ("slot 3", "slot three")) and any(term in lower for term in ("printing from", "print from", "from slot"))


def is_centauri_carbon_name_swap_prompt(text):
    lower = str(text or "").lower()
    if not lower:
        return False
    if any(term in lower for term in ("tinmancc1", "tinman cc1", "cc1")) and any(term in lower for term in ("change the name", "rename", "name to")):
        return True
    return any(term in lower for term in ("centauri carbon", "centari carbon", "centauri", "centari")) and any(
        term in lower for term in ("swap the names", "swap names", "rename", "physically in the wrong", "wrong spots", "wrong spost")
    )


def test_id_for_prompt(prompt):
    digest = hashlib.sha1(normalized_key(prompt).encode("utf-8")).hexdigest()[:14]
    return f"history-{digest}"


def is_testable_prompt(text):
    stripped = compact(text, 2000)
    lower = stripped.lower()
    if not stripped or len(stripped) < 14:
        return False
    if lower in {"are you there?", "thank you", "thanks", "awesome", "perfect", "lets do it", "let's do it"}:
        return False
    if re.match(r"^[a-z_][a-z0-9_-]*@[^:]+[:$]", lower) and not any(lower.startswith(starter) for starter in QUESTION_STARTERS):
        return False
    if lower.startswith("failed: traceback") and "can you" not in lower and "will you" not in lower:
        return False
    if lower.startswith("-") and "?" not in lower:
        return False
    if re.match(r"^\d{1,2}:\d{2}\s*(?:am|pm)\s+", lower):
        return False
    if lower.startswith("done. http") and "?" not in lower:
        return False
    if "translated report" in lower[:120] and "exception type:" in lower and "crashed thread:" in lower:
        return False
    if "private startup inventory:" in lower or "current request analysis:" in lower:
        return False
    if any(lower.startswith(prefix) for prefix in SKIP_PREFIXES):
        return False
    if any(term in lower for term in ("see attached", "see photos", "see photo", "attached image", "attached is", "based on the image", "from this image")):
        return False
    if re.search(r"\b(?:img[_-]?\d+|screenshot|photo)\.(?:jpe?g|png|heic|webp)\b", lower):
        return False
    if lower.startswith("# files mentioned by the user:") and "my request for codex:" not in lower:
        return False
    if len(stripped) < 170 and any(term in lower for term in ("before we move on", "fix this properly")):
        return False
    if lower.count("\n") > 35 and "my request for codex:" not in lower:
        return False
    if len(stripped) > 5000:
        return False
    return "?" in stripped or any(lower.startswith(starter) for starter in QUESTION_STARTERS)


def is_context_dependent_prompt(text):
    lower = compact(text, 300).lower().strip()
    if not lower:
        return False
    if is_printing_from_slot_three_prompt(lower):
        return False
    if is_tinmanx_orca_codex_slicer_ready_build_next_step_prompt(lower):
        return False
    if is_eject_target_context_prompt(lower):
        return False
    if is_motion_system_testing_context_prompt(lower):
        return False
    if any(term in lower for term in ("terminate", "pause", "hold")) and any(term in lower for term in ("mechanical inspection", "inspection is complete")):
        return False
    if is_bed_mesh_deviation_quality_prompt(lower):
        return False
    if is_single_test_command_context_prompt(lower):
        return False
    if is_plateau_terminate_prompt(lower) or is_driver_temps_missing_context_prompt(lower) or is_pump_data_mcu_temp_missing_context_prompt(lower):
        return False
    if any(term in lower for term in ("probe point", "initial probe", "z offset", "z-offset", "zoffset", "nozzle offset", "beacon")) and any(
        term in lower for term in ("reset", "clear", "try again", "rerun", "9mm off", "9 mm off", "when did it get")
    ):
        return False
    if any(re.search(pattern, lower) for pattern in CONTEXT_DEPENDENT_PATTERNS):
        return True
    if "within 50 miles" in lower and not any(term in lower for term in ("renew", "id", "filament", "printer", "shop", "store", "service", "airport", "office")):
        return True
    if any(term in lower for term in ("there are thousands", "this site", "for this site")) and any(
        term in lower for term in ("how do i find", "find the one", "which one", "narrow", "filter")
    ):
        return True
    if any(term in lower for term in ("what should the pins read", "pin read", "pins read", "what should pins read")):
        return True
    if any(term in lower for term in ("normalize them", "normalise them")) and any(term in lower for term in ("warnings", "future warnings", "prevent")):
        return True
    if "page" in lower and any(term in lower for term in ("get past", "past this page", "second device", "another device")):
        return True
    if re.search(r"^what\s+should\s+the\s+comment\s+title\s+be\??$", lower.strip()):
        return True
    if any(term in lower for term in ("automating this", "automate this", "advantage to automating")) and any(
        term in lower for term in ("commented it out", "commenting it out", "reason for commenting", "why it was commented")
    ):
        return True
    if re.search(r"^(?:are|r)\s+you\s+still\s+working\s+on\s+this\??$", lower.strip()):
        return True
    if re.search(r"^(?:please\s+)?eject\s+it\s+for\s+me[.!? ]*$", lower.strip()):
        return True
    if re.search(r"^(?:let'?s|lets)\s+go(?:\s+my\s+brother)?[.!? ]*$", lower.strip()):
        return True
    if re.search(r"^should\s+we\s+be\s+using\s+default\??$", lower.strip()):
        return True
    if re.search(r"^(?:what\s+is|what's|whats|where\s+is)\s+the\s+full\s+location\??$", lower.strip()):
        return True
    if "config" in lower and any(term in lower for term in ("appropriate changes", "make the changes", "change the config", "config files")) and len(lower.strip()) < 140:
        return True
    if re.search(r"^please\s+make\s+the\s+changes\s+and\s+i\s+will\s+sync[.!? ]*$", lower.strip()):
        return True
    if re.search(r"^what\s+is\s+the\s+command\s+for\s+this\s+test\s+only\??$", lower.strip()):
        return True
    if any(term in lower for term in ("increase it by 4", "increase it by four", "4 times", "four times", "double it", "double it again", "double again")) and any(
        term in lower for term in ("re run", "rerun", "re-run", "run again")
    ):
        return True
    if any(term in lower for term in ("one more pass", "another pass")) and any(term in lower for term in ("nothing more", "needs attention", "before moving forward")):
        return True
    if re.search(r"^(?:let'?s|lets)\s+do\s+option\s+1[.!? ]*$", lower.strip()):
        return True
    if re.search(r"^(?:let'?s|lets)\s+update\s+it\s+now(?:\s+please)?[.!? ]*$", lower.strip()):
        return True
    if re.search(r"^(?:let'?s|lets)\s+turn\s+it\s+off[.!? ]*$", lower.strip()):
        return True
    if re.search(r"^(?:let'?s|lets)\s+restart\s+it\s+(?:now|now\s+then|then)(?:\s+please)?[.!? ]*$", lower.strip()):
        return True
    if re.search(r"^(?:is\s+there|has\s+there|is\s+there\s+been)\s+any\s+progress\??$", lower.strip()):
        return True
    if "next step" in lower and any(term in lower for term in ("for me", "for you", "mine", "yours")):
        return True
    if any(term in lower for term in ("not cut corners", "don't cut corners", "dont cut corners")) and any(term in lower for term in ("get it", "free")):
        return True
    if re.search(r"^(?:ok|okay|so)?[,!. ]*what\s+do\s+we\s+do\s+now\??$", lower.strip()):
        return True
    if re.search(r"^(?:let'?s|lets)\s+keep\s+the\s+momentum\s+going[.!? ]*$", lower.strip()):
        return True
    if any(term in lower for term in ("terminate", "pause", "hold")) and any(term in lower for term in ("mechanical inspection", "inspection is complete")):
        return True
    if "this sensor" in lower:
        return True
    if len(lower) < 80 and any(
        phrase in lower
        for phrase in (
            "do this",
            "do that",
            "that test",
            "that again",
            "your recommendations",
            "complete flow",
            "complete airflow testing",
            "that you just",
            "just pulled up",
            "you just pulled",
            "you just created",
            "you just wrote",
            "you just made",
            "you just repaired",
            "files you just repaired",
            "this sensor",
            "that worked",
            "same thing",
            "same screen",
            "try again",
            "keep going",
            "keep going until",
            "can you keep going",
            "continue",
            "run it again",
            "move on",
            "next step",
            "where can i see the product",
            "where can i view the product",
            "progress update and updated timeline",
            "beta testing version",
            "these machines",
            "this change",
            "do you see where",
            "anything else that needs to be done",
            "anything else needs to be done",
            "at this time",
            "proceed with tinmanx",
            "implemented everything from orca",
            "implimented everything from orca",
            "next recommendation",
            "your next recommendation",
            "please continue",
            "i am watching",
            "continue to the next phase",
            "next phase",
            "these instructions",
            "step 1",
            "after it tells you",
            "fix this cleanly",
            "sync it",
            "lets fix it",
            "let's fix it",
            "what do you need me to do",
            "new headers",
            "updated estimated completion date",
            "estimated completion date",
            "how are we coming along",
            "the 1.0",
            "recommend the 1.0",
            "clean boot",
            "done on the machine itself",
            "on the machine itself",
            "full integration work",
            "verify this remotely",
            "our next step",
            "next step now",
            "lets continue",
            "let's continue",
            "next step on the wind turbine",
        )
    ):
        return True
    return False


def is_heartbeat_active_tuning_prompt(text):
    lower = compact(text, 500).lower()
    return (
        "heartbeat" in lower
        and any(term in lower for term in ("active", "adjust", "maximize productivity", "completion time"))
    )


def is_long_heartbeat_mac_awake_prompt(text):
    lower = compact(text, 700).lower()
    return (
        "heartbeat" in lower
        and any(term in lower for term in ("12 hours", "twelve hours", "all day", "unavailable"))
        and any(term in lower for term in ("15 min", "15-minute", "15 minute"))
        and any(term in lower for term in ("mac doesnt sleep", "mac doesn't sleep", "sleep", "curser", "cursor", "progress today"))
    )


def quality_score(text):
    lower = text.lower()
    score = 0
    if "?" in text:
        score += 8
    if len(text) >= 60:
        score += 8
    if len(text) >= 160:
        score += 6
    domain_terms = (
        "qidi", "rat rig", "ratrig", "klipper", "moonraker", "marlin", "orca",
        "filament", "cad", "fusion", "stl", "cfd", "fea", "wiring", "diagram",
        "solar", "battery", "codex cli ui", "github", "flight ops", "tinmanx",
        "xfoil", "openvsp", "su2", "qblade", "graphviz", "cm4", "beacon",
    )
    score += min(40, sum(6 for term in domain_terms if term in lower))
    if any(term in lower for term in ("not acceptable", "failure", "failed", "didnt", "didn't", "fix this", "your son")):
        score += 18
    if any(term in lower for term in ("search the web", "current", "latest", "price", "availability")):
        score += 10
    if any(term in lower for term in ("thank", "awesome", "perfect", "brother")) and len(text) < 80:
        score -= 20
    return score


def is_codex_macos_tahoe_toolchain_followup_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    has_installed_15 = bool(re.search(r"\b15\.\d+(?:\.\d+)?\b", lower)) and "installed" in lower
    has_tahoe_26 = "tahoe" in lower and bool(re.search(r"\b26\.\d+(?:\.\d+)?\b", lower))
    asks_next_step = any(term in lower for term in ("what should i do", "what do i do", "next", "now", "do now"))
    return has_installed_15 and has_tahoe_26 and any(term in lower for term in ("only", "requires", "require", "compatible", "compatibility")) and asks_next_step


def is_mac_security_sweep_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return any(term in lower for term in ("security sweep", "security scan", "security risks", "security risk audit")) and any(
        term in lower for term in ("mac", "this machine", "this mac", "my mac")
    )


def is_epson_wf2960_network_black_only_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("epson", "wf-2960", "wf 2960", "wf2960"))
        and any(term in lower for term in ("network", "find", "locate", "cups", "printer"))
        and any(term in lower for term in ("black only", "black-only", "empty", "missing color", "missing colour", "cartridges", "cartriges"))
    )


def is_cad_model_source_search_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("find", "locate", "download", "source"))
        and any(term in lower for term in ("cad model", "cad file", "step model", "step file", "stl model", "fusion model"))
        and not any(term in lower for term in ("create", "design", "generate", "regenerate", "build me", "model this from scratch"))
    )


def is_compact_m5_barbed_elbow_cad_search_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        is_cad_model_source_search_prompt(text)
        and any(term in lower for term in ("m5", "m 5"))
        and any(term in lower for term in ("barbed", "barb", "push type", "push-to-connect", "push to connect", "push fitting"))
        and any(term in lower for term in ("45", "90", "degree", "elbow"))
    )


def is_controlled_y_home_after_collision_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("controlled y home", "y home only", "home y only", "g28 y"))
        and any(term in lower for term in ("jammed", "hit the wall", "slipped the belts", "slipped belts", "trash bin", "non movement area", "non-movement area", "unload", "cutting", "filiment", "filament"))
    )


def is_filament_box_load_next_step_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("filament", "filiment"))
        and any(term in lower for term in ("loaded it into the box", "loaded into the box", "in the box"))
        and any(term in lower for term in ("next step", "what is next", "whats next", "what's next", "tried loading", "load"))
    )


def is_orca_print_time_disparity_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return "orca logs" in lower and any(term in lower for term in ("print time estimate", "slicer estimate", "disparity", "time estimate"))


def is_fk275_belt_cross_reference_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return "fk275" in lower and any(term in lower for term in ("belt", "serpentine")) and any(
        term in lower for term in ("cross reference", "other manufacturer", "exact same dimensions", "part number")
    )


def is_codex_cli_response_time_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return any(term in lower for term in ("codex", "codex cli", "cli codex", "local agent")) and any(
        term in lower for term in ("response time", "response times", "respond faster", "faster responses", "speed up", "increase speed", "latency")
    )


def is_scad_to_stl_step_conversion_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("scad", ".scad", "openscad"))
        and any(term in lower for term in ("stl", "step", ".stl", ".step"))
        and any(term in lower for term in ("convert", "preferred file format", "future requests", "export"))
    )


def is_petg_cf_part_cooling_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("petg-cf", "petg cf", "carbon fiber petg"))
        and any(term in lower for term in ("part cooling", "cooling fan", "toolhead cooling", "toolhead fan", "from the toolhead", "fan"))
        and any(term in lower for term in ("need", "needs", "use", "should", "does"))
    )


def is_offline_knowledge_server_sizing_prompt(text):
    lower = str(text or "").lower()
    return any(term in lower for term in ("server next to the dgx", "dgx spark", "store all data", "cut off from society", "cut off from the internet")) and any(
        term in lower for term in ("farming", "engineering", "survive", "thrive", "internet")
    )


def is_autonomous_work_queue_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return any(term in lower for term in ("keep moving forward", "keep moving", "keep going")) and any(
        term in lower
        for term in (
            "previous task is complete",
            "new task",
            "until we are finished",
            "without stopping",
            "without my input",
            "unavailable",
            "next 12 hours",
            "next twelve hours",
            "through all of the steps",
            "on your own",
            "project is complete",
            "until the project is complete",
        )
    )


def is_plateau_terminate_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        len(lower) < 180
        and any(term in lower for term in ("terminate", "stop", "end it", "shut it down"))
        and any(
            term in lower
            for term in (
                "won't get any better",
                "will not get any better",
                "wont get any better",
                "better or worse",
                "not get any better",
            )
        )
    )


def is_driver_temps_missing_context_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return len(lower) < 120 and any(
        term in lower for term in ("driver temp", "driver temps", "driver temperature", "driver temperatures")
    )


def is_pump_data_mcu_temp_missing_context_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        len(lower) < 180
        and "pump" in lower
        and any(term in lower for term in ("getting the data", "get the data", "mcu temp", "mcu temperature", "mcu_temp", "temp issue"))
    )


def is_aviation_life_limited_part_quiz_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("life-limited part", "life limited part", "life limit"))
        and any(term in lower for term in ("type-certificated", "type certificated", "installation of the part"))
        and any(term in lower for term in ("segregation", "red streamer", "acceptable method"))
    )


def is_hotend_coolant_control_guidance_prompt(text):
    lower = str(text or "").lower()
    return any(term in lower for term in ("coolant", "liquid cooling", "pump")) and any(
        term in lower for term in ("hotend", "hot end", "fan 6", "motor 7", "commanded temperature", "pump speed", "nema stepper")
    )


def is_k2_plus_profile_pack_setup_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("creality k2 plus", "k2 plus"))
        and any(term in lower for term in ("machine", "filament", "process", "profile", "profiles", "preset", "presets"))
        and any(term in lower for term in ("0.4", "0.6", "0.4mm", "0.6mm", "nozzle", "nozzles"))
        and any(term in lower for term in ("creality print", "slicer", "tinmanx", "orca"))
    )


def is_flightops_report_cover_page_numbering_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("flight ops", "aircraft report", "report cover", "cover page"))
        and any(term in lower for term in ("not and invoice", "not an invoice", "invoice"))
        and any(term in lower for term in ("page number", "page numbers", "page 2", "second page"))
    )


def is_flightops_pilot_double_booking_blocker_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("pilot", "pilots"))
        and any(term in lower for term in ("scheduled", "schedule", "scheduling"))
        and any(term in lower for term in ("same time", "overlap", "overlapping", "at the same"))
        and any(term in lower for term in ("2 airplanes", "two airplanes", "2 aircraft", "two aircraft", "different aircraft"))
        and any(term in lower for term in ("blocker", "not allow", "prevent", "conflict"))
    )


def is_flightops_flightlog_by_aircraft_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("flightlog", "flight log", "flights in"))
        and any(term in lower for term in ("separate", "seperate", "group", "filter", "sort"))
        and "aircraft" in lower
    )


def is_flightops_method1_fuel_daily_rollup_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("method 1 fuel", "method one fuel"))
        and any(term in lower for term in ("same aircraft", "same customer"))
        and any(term in lower for term in ("multiple flights", "more than one flight", "1 day", "one day", "same day"))
        and any(term in lower for term in ("average the fuel burn", "average fuel burn", "fuel table", "cover page"))
    )


def is_flightops_pilot_report_pdf_print_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("pilot reports", "pilot report"))
        and any(term in lower for term in ("print as pdf", "print to pdf", "pdf", "download pdf", "export pdf"))
        and any(term in lower for term in ("functionality", "add", "can you", "make"))
    )


def is_sovol_stainless_gantry_material_prompt(text):
    lower = str(text or "").lower()
    return (
        "sovol" in lower
        and "gantry" in lower
        and any(term in lower for term in ("stainless steel", "stainless"))
        and any(term in lower for term in ("20x20", "20 x 20", "hollow", "solid bar", "solid"))
    )


def is_ratos_directory_download_compare_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("ratos", "rat os"))
        and any(term in lower for term in ("download the entire directory", "download entire directory", "copy the entire directory", "rsync", "scp"))
        and any(term in lower for term in ("new folder", "not getting them mixed up", "old files", "compare"))
    )


def is_wind_generator_alternator_shopping_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("wind turbine alternator", "wind turbine generator", "wind generator", "alternator or generator"))
        and any(term in lower for term in ("300 rpm", "300rpm"))
        and any(term in lower for term in ("60vdc", "60 vdc", "60 v", "3 phase", "3-phase"))
        and any(term in lower for term in ("$500", "500 usd", "under 500", "less than 500", "price point"))
    )


def is_snapmaker_u1_nozzle_shopping_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("snapmaker u1", "snapmaker"))
        and any(term in lower for term in ("0.6 nozzle", "0.6mm nozzle", "0.6 mm nozzle", "nozzle set"))
        and any(term in lower for term in ("quality", "ship soon", "shipping", "find", "buy"))
    )


def is_k2_qidi_box_macro_compare_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("k2 plus", "creality k2", "k2"))
        and "qidi" in lower
        and any(term in lower for term in ("macros", "cfg files", "config files", "compare"))
        and any(term in lower for term in ("box", "filiment", "filament", "filament change"))
    )


def is_klipperscreen_object_visibility_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("klipperscreen", "klipper screen"))
        and any(term in lower for term in ("see the objects", "objects on", "will i see", "visible", "show up"))
        and any(term in lower for term in ("object", "objects", "macro", "macros", "button", "buttons", "menu"))
    )


def is_sovol_filament_profile_expansion_prompt(text):
    lower = str(text or "").lower()
    return (
        "sovol" in lower
        and any(term in lower for term in ("filament", "filaments"))
        and any(term in lower for term in ("petg-cf", "petg cf", "same for", "other sovol", "do the same"))
        and any(term in lower for term in ("profile", "profiles", "preset", "presets"))
    )


def is_sovol_spring_idler_belt_tension_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("sovol sv08 max", "sv08 max"))
        and any(term in lower for term in ("spring", "springs"))
        and any(term in lower for term in ("idler", "idler pulley", "idler pulleys", "adjustment arm"))
        and any(term in lower for term in ("belt tension", "constant belt", "negative effects", "flying gantry", "4040"))
    )


def is_ratrig_initial_speed_accel_settings_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("rat rig", "ratrig", "v-core", "vcore"))
        and any(term in lower for term in ("speed", "speeds", "acceleration", "accel"))
        and any(term in lower for term in ("idex", "500", "initial testing", "testing", "super slow", "turned down"))
    )


def is_pctg_nozzle_tuned_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("0.6 nozzle", "0.6mm nozzle", "0.6 mm nozzle"))
        and "pctg" in lower
        and any(term in lower for term in ("tuned", "latest pctg changes", "changed the nozzle"))
    )


def is_history_printer_operational_prompt(text):
    lower = str(text or "").lower()
    return (
        ("printers remotely" in lower or "can't see my printers" in lower or "cant see my printers" in lower)
        or ("pt1000" in lower and "ebb" in lower and any(term in lower for term in ("verify", "work around", "workaround", "losing", "loosing")))
        or (any(term in lower for term in ("rat rig", "ratrig")) and "part cooling" in lower)
        or (any(term in lower for term in ("fibreseek", "fiberseek", "fibreseeker", "fiberseeker")) and any(term in lower for term in ("toolhead", "hotend", "hotted", "continuous fiber", "continuous fibre")))
        or ("layer shift" in lower and any(term in lower for term in ("x axis", "x-axis", "motor currents", "servo motor", "stepper motor")))
        or any(term in lower for term in ("common new printer passwords", "common printer passwords", "new printer passwords", "default printer passwords"))
        or (any(term in lower for term in ("current pins", "pins for")) and any(term in lower for term in ("chamber heaters", "chamber heat fans", "safety thermisters", "safety thermistors")))
        or (any(term in lower for term in ("spare raspberry pi 4", "raspberry pi 4", "rasberry pi 4")) and "max ez" in lower)
        or ("sd card" in lower and any(term in lower for term in ("rasberry pi image", "raspberry pi image", "max ez")))
        or (any(term in lower for term in ("octoapp", "octoeverywhere", "octo everywhere")) and any(term in lower for term in ("cc printers", "centauri", "centari")))
        or (any(term in lower for term in ("toolboard fans", "hot end fan over the ebb", "hotend fan over the ebb", "ebb 42")) and any(term in lower for term in ("re lable", "relabel", "change the logic", "running any time")))
        or ("qidi" in lower and any(term in lower for term in ("slot 4", "box wasnt feeding", "box wasn't feeding", "tangled")))
        or (any(term in lower for term in ("engineering drawing", "engineering drawings")) and any(term in lower for term in ("rat rig", "ratrig", "3d printing")))
        or ("ebb" in lower and any(term in lower for term in ("comment out", "disable", "bypass")) and any(term in lower for term in ("motion system", "motion", "communication")))
        or ("he2" in lower and any(term in lower for term in ("fan", "start current", "run current", "0.9a", ".9a", "0.4a", ".4a")) and any(term in lower for term in ("safe", "run straight", "run strait", "direct", "output")))
        or (any(term in lower for term in ("bambu", "x1", "h2d", "192.0.2.108", "192.0.2.125")) and "ams" in lower and any(term in lower for term in ("qidi", "box", "macros", "macro", "compare")))
    )


def is_github_scheduled_workflow_disabled_prompt(text):
    lower = str(text or "").lower()
    return "github" in lower and any(term in lower for term in ("scheduled workflow", "workflows are disabled", "disabled automatically")) and "klipper3d" in lower


def is_report_cache_refresh_prompt(text):
    lower = str(text or "").lower()
    return any(term in lower for term in ("same report", "clear the cashe", "clear the cache", "previously generated reports")) and "report" in lower


def project_for_prompt(text):
    lower = text.lower()
    if is_agent_preference_question_prompt(text):
        return "general"
    if is_mac_memory_ai_performance_prompt(text):
        return "mac-system-accounts"
    if is_aviation_life_limited_part_quiz_prompt(text):
        return "aviation-engineering"
    if is_k2_plus_profile_pack_setup_prompt(text):
        return "tinmanx-slicer-research"
    if is_flightops_report_cover_page_numbering_prompt(text):
        return "flightops-tracker"
    if is_flightops_pilot_double_booking_blocker_prompt(text):
        return "flightops-tracker"
    if is_flightops_flightlog_by_aircraft_prompt(text):
        return "flightops-tracker"
    if is_flightops_method1_fuel_daily_rollup_prompt(text):
        return "flightops-tracker"
    if is_flightops_pilot_report_pdf_print_prompt(text):
        return "flightops-tracker"
    if is_sovol_stainless_gantry_material_prompt(text):
        return "printer-klipper-ops"
    if is_ratos_directory_download_compare_prompt(text):
        return "embedded-linux-images"
    if is_wind_generator_alternator_shopping_prompt(text):
        return "energy-power-research"
    if is_snapmaker_u1_nozzle_shopping_prompt(text):
        return "research-parts-reference"
    if is_k2_qidi_box_macro_compare_prompt(text):
        return "printer-klipper-ops"
    if is_klipperscreen_object_visibility_prompt(text):
        return "printer-klipper-ops"
    if is_sovol_filament_profile_expansion_prompt(text):
        return "tinmanx-slicer-research"
    if is_sovol_spring_idler_belt_tension_prompt(text):
        return "printer-klipper-ops"
    if is_ratrig_initial_speed_accel_settings_prompt(text):
        return "printer-klipper-ops"
    if is_codex_github_full_history_audit_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_flightops_aircraft_type_time_owed_prompt(text):
        return "flightops-tracker"
    if is_general_regression_test_bank_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_github_issue_fixed_status_prompt(text) or is_api_key_needed_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_orca_humidity_as_temperature_prompt(text):
        return "tinmanx-slicer-research"
    if is_flightops_multi_inspection_ui_prompt(text):
        return "flightops-tracker"
    if is_flightops_fuel_method_cover_sheet_report_prompt(text) or is_flightops_customer_line_remove_label_prompt(text):
        return "flightops-tracker"
    if (
        is_flightops_pilot_report_by_pilot_prompt(text)
        or is_flightops_report_date_totals_format_prompt(text)
        or is_flightops_customer_credit_dropdown_prompt(text)
        or is_flightops_admin_pilot_email_missing_prompt(text)
        or is_flightops_aircraft_buttons_flights_page_prompt(text)
        or is_flightops_aircraft_documents_restore_upload_prompt(text)
    ):
        return "flightops-tracker"
    if is_orca_codex_partially_locked_up_prompt(text) or is_slicer_app_continue_until_all_printers_prompt(text):
        return "orcaslicer-codex"
    if is_pctg_profiles_all_machines_qidi_ui_prompt(text):
        return "tinmanx-slicer-research"
    if is_sovol_sv08_petg_cf_apply_changes_prompt(text):
        return "tinmanx-slicer-research"
    if is_pick_up_where_left_off_prompt(text) or is_uploaded_files_fix_coding_errors_stability_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_github_comments_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_manual_auto_feature_still_work_prompt(text):
        return "cad-modeling-projects"
    if is_makers_corner_guest_restart_prompt(text) or is_ffmpeg_v4l2_camera_log_prompt(text):
        return "mac-system-accounts"
    if (
        is_qidi_nebula_pins_before_sensor_removal_prompt(text)
        or is_rat_rig_files_access_resume_prompt(text)
        or is_klipper_request_draft_prompt(text)
        or is_filament_box_no_filament_next_step_prompt(text)
        or is_snapmaker_u1_custom_firmware_update_decision_prompt(text)
        or is_plus4_sensorless_homing_force_prompt(text)
        or is_cc1_runout_continued_printing_prompt(text)
        or is_qidi_stepper_motor_temperature_missing_prompt(text)
        or is_qidi_codex_library_filament_screen_prompt(text)
        or is_ratrig_xy_offset_calibration_no_chamber_heat_prompt(text)
        or is_sovol_obico_not_working_prompt(text)
        or is_qidi_prepare_tab_nozzle_sync_prompt(text)
        or is_printer_ip_changed_password_note_prompt(text)
        or is_klipper_load_unload_macro_buttons_prompt(text)
        or is_all_printers_supported_continue_prompt(text)
        or is_u1_buffer_sensor_delete_confirmation_prompt(text)
        or is_temporary_immediate_pause_macro_prompt(text)
        or is_mainline_klipper_camera_xy_measurement_prompt(text)
        or is_snapmaker_u1_installed_filaments_prompt(text)
    ):
        return "printer-klipper-ops"
    if is_typical_questions_domain_list_prompt(text):
        return "energy-power-research"
    if is_3d_chameleon_cleanup_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_touchscreen_firmware_flash_walkthrough_prompt(text):
        return "general"
    if (
        is_chamber_heaters_disabled_live_test_prompt(text)
        or is_printer_cfg_before_proceed_prompt(text)
        or is_sense_resistor_manual_install_prompt(text)
        or is_invar_2020_extrusion_prompt(text)
        or is_centauri_carbon_filament_nozzle_report_prompt(text)
        or is_ebb42_dual_pt1000_prompt(text)
        or is_qidi_box_rfid_spool_speed_prompt(text)
        or is_xy_hold_current_regression_prompt(text)
        or is_offset1059_printer_direct_prompt(text)
        or is_live_qidi_moonraker_status_snapshot_prompt(text)
        or is_btt_rgb_output_24v_strip_prompt(text)
    ):
        return "printer-klipper-ops"
    if is_orca_brand_preset_display_prompt(text):
        return "tinmanx-slicer-research"
    if is_offset1059_flightops_direct_prompt(text):
        return "flightops-tracker"
    if is_flightops_standalone_offline_sync_prompt(text):
        return "flightops-tracker"
    if is_analytical_self_learning_package_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_qidi_filament_sync_robust_rewrite_prompt(text):
        return "tinmanx-slicer-research"
    if is_pi_network_after_outage_prompt(text):
        return "embedded-linux-images"
    if (
        is_flightops_overflight_exemption_fields_prompt(text)
        or is_flightops_customer_all_calendars_assigned_schedule_prompt(text)
        or is_flightops_admin_impersonation_prompt(text)
        or is_flightops_n797ra_maintenance_report_header_overdue_prompt(text)
    ):
        return "flightops-tracker"
    if (
        is_ebb42_programmed_pins_prompt(text)
        or is_qidi_backend_network_recovery_prompt(text)
        or is_multi_nozzle_dropdown_architecture_prompt(text)
        or is_qidi_usb_camera_support_prompt(text)
        or is_opencentauri_install_boot_slot_prompt(text)
        or is_vaoc_mainline_klipper_camera_prompt(text)
        or is_current_load_filament_macro_prompt(text)
        or is_klipper_mcu_loss_ebb42_remote_prompt(text)
        or is_printer_optional_software_install_prompt(text)
        or is_klipperscreen_wifi_connected_no_ip_prompt(text)
        or is_printer_printing_without_extruding_confirm_prompt(text)
        or is_z_hold_current_reduce_prompt(text)
        or is_xy_home_current_reduce_prompt(text)
        or is_nozzle_04_restore_profile_cleanup_prompt(text)
        or is_box_humidity_target_enable_prompt(text)
        or is_lane_specific_sensor_motor_architecture_prompt(text)
        or is_ratrig_deep_audit_cleanup_prompt(text)
        or is_qidi_box_u1_aux_feeder_lane_architecture_prompt(text)
    ):
        return "printer-klipper-ops"
    if is_contextless_prusa_github_deep_research_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_install_anything_need_context_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_offline_backend_github_update_context_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_flightops_inspection_item_dropdown_bug_prompt(text):
        return "flightops-tracker"
    if is_project_cleanup_latest_data_cad_prompt(text):
        return "cad-modeling-projects"
    if is_codex_extend_testing_download_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_github_push_followup_prompt(text) or is_github_open_source_credit_planning_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_nebula_ebb42_wiring_github_prompt(text) or is_qidi_max_ez_plr_github_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_github_confident_push_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_image_inspired_redesign_prompt(text):
        return "cad-modeling-projects"
    if is_generic_resume_followup_prompt(text) or is_restart_it_to_check_followup_prompt(text):
        return "general"
    if is_stop_chat_terminate_automations_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_print_code_ssh_diagnostic_prompt(text):
        return "tinmanx-slicer-research"
    if is_qidi_box_pause_rethink_prompt(text) or is_rat_rig_mechanical_mods_pause_prompt(text) or is_adaptive_heat_soak_design_prompt(text):
        return "printer-klipper-ops"
    if is_diffuser_positive_z_airflow_test_prompt(text):
        return "cad-modeling-projects"
    if is_rev_b_latest_compare_prompt(text) or is_upload_all_files_later_prompt(text):
        return "general"
    if (
        is_ratrig_manual_dual_probe_workflow_prompt(text)
        or is_qidi_box_factory_firmware_archive_prompt(text)
        or is_tailscale_printers_road_access_prompt(text)
        or is_qidi_abs_stringing_profile_adjust_prompt(text)
        or is_qidi_context_change_followup_prompt(text)
        or is_klipper_conversion_holdoff_prompt(text)
        or is_marlin_prusa_klipper_compare_prompt(text)
        or is_rat_rig_lookup_followup_prompt(text)
        or is_ssh_credentials_history_lookup_prompt(text)
        or is_centauri_one_lookup_followup_prompt(text)
        or is_klipper_platform_focus_guidance_prompt(text)
        or is_qidi_y_before_x_homing_fix_prompt(text)
        or is_xy_homing_hold_current_change_prompt(text)
        or is_qidi_resume_context_followup_prompt(text)
        or is_vaoc_camera_t0_t1_offset_prompt(text)
        or is_filament_load_unload_g28_preface_prompt(text)
        or is_qidi_plus4_network_search_prompt(text)
        or is_cc1_calibration_qidi_network_followup_prompt(text)
        or is_remote_printer_morning_followup_prompt(text)
        or is_filament_buffer_stop_prompt(text)
        or is_max_ez_chat_state_scan_prompt(text)
    ):
        return "printer-klipper-ops"
    if is_makersvpn_available_prompt(text) or is_makersvpn_sorted_prompt(text):
        return "mac-system-accounts"
    if is_flightops_customer_report_pages_prompt(text):
        return "flightops-tracker"
    if is_enable_vpn_service_prompt(text) or is_router_speed_asymmetry_diagnostic_prompt(text):
        return "mac-system-accounts"
    if is_contextless_mapping_correct_prompt(text):
        return "general"
    if is_github_update_with_filament_price_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_makersvpn_reboot_prompt(text) or is_bluetooth_rename_prompt(text):
        return "mac-system-accounts"
    if is_hotend_mount_visual_reference_prompt(text) or is_cad_duct_upward_image_reference_prompt(text):
        return "cad-modeling-projects"
    if is_chrome_page_screenshot_prompt(text):
        return "mac-system-accounts"
    if (
        is_rat_rig_ip_lookup_prompt(text)
        or is_humidity_hook_reuse_prompt(text)
        or is_qidi_filament_width_sensor_location_prompt(text)
        or is_qidi_box_ace2_compare_prompt(text)
    ):
        return "printer-klipper-ops"
    if is_orcaslicer_codex_installed_changes_prompt(text):
        return "orcaslicer-codex"
    if is_orca_codex_pakv_restart_prompt(text):
        return "orcaslicer-codex"
    if is_github_publish_signup_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_klipper_change_effect_status_prompt(text):
        return "printer-klipper-ops"
    if is_printer_selection_ui_cleanup_prompt(text):
        return "printer-klipper-ops"
    if (
        is_slicer_profile_update_prompt(text)
        or is_core_one_l_filament_specific_profile_share_prompt(text)
        or is_shared_profile_repo_machine_organization_prompt(text)
    ):
        return "tinmanx-slicer-research"
    if is_router_optimization_login_prompt(text):
        return "mac-system-accounts"
    if is_router_access_permission_prompt(text):
        return "mac-system-accounts"
    if is_ssh_extended_firmware_capability_prompt(text):
        return "embedded-linux-images"
    if is_qidi_max_ez_adaptive_heat_soak_feature_prompt(text) or is_toolhead_runout_switch_remap_prompt(text):
        return "printer-klipper-ops"
    if is_orca_calibration_image_prompt(text):
        return "tinmanx-slicer-research"
    if is_petcf_pei_bed_temp_prompt(text) or is_fiberon_petcf_annealing_prompt(text):
        return "tinmanx-slicer-research"
    if (
        is_qidi_plus4_usb_wifi_dongle_prompt(text)
        or is_rat_rig_macro_folder_save_prompt(text)
        or is_qidi_load_unload_speed_match_prompt(text)
        or is_qidi_camera_refresh_rate_prompt(text)
        or is_max_ez_wlan_followup_prompt(text)
        or is_max_ez_process_profile_tuning_prompt(text)
        or is_adaptive_heat_soak_status_prompt(text)
    ):
        return "printer-klipper-ops"
    if "layer shift" in lower and any(term in lower for term in ("each layer", "every layer", "print progresses", "look into")):
        return "printer-klipper-ops"
    if is_pump_data_mcu_temp_missing_context_prompt(text):
        return "printer-klipper-ops"
    if is_driver_temps_missing_context_prompt(text):
        return "printer-klipper-ops"
    if is_plateau_terminate_prompt(text):
        return "general"
    if is_autonomous_work_queue_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_orca_print_time_disparity_prompt(text):
        return "tinmanx-slicer-research"
    if is_codex_cli_response_time_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_wix_email_login_recovery_prompt(text) or is_wix_credential_recovery_prompt(text):
        return "mac-system-accounts"
    if is_tool_inventory_visibility_prompt(text):
        return "mac-system-accounts"
    if is_lan_ip_restoration_context_prompt(text):
        return "mac-system-accounts"
    if is_offline_knowledge_server_sizing_prompt(text):
        return "mac-system-accounts"
    if is_lost_ip_sd_card_recovery_prompt(text):
        return "embedded-linux-images"
    if is_printing_from_slot_three_prompt(text):
        return "tinmanx-slicer-research"
    if is_ip_changed_missing_target_prompt(text):
        return "mac-system-accounts"
    if is_printer_aux_output_run_prompt(text):
        return "printer-klipper-ops"
    if is_cad_cnc_question_list_prompt(text):
        return "cad-modeling-projects"
    if is_adhesive_pot_life_quiz_prompt(text):
        return "aviation-engineering"
    if is_aircraft_wood_defect_quiz_prompt(text):
        return "aviation-engineering"
    if is_advisory_circular_source_quiz_prompt(text):
        return "aviation-engineering"
    if is_lycoming_spark_plug_helicoil_prompt(text):
        return "aviation-engineering"
    if is_corrosion_inspection_quiz_prompt(text):
        return "aviation-engineering"
    if is_thin_material_corrosion_true_false_prompt(text):
        return "aviation-engineering"
    if is_reserve_military_id_location_prompt(text):
        return "general"
    if is_mesh_to_step_or_fusion_scale_prompt(text):
        return "cad-modeling-projects"
    if is_scad_to_stl_step_conversion_prompt(text):
        return "cad-modeling-projects"
    if is_cad_model_source_search_prompt(text):
        return "cad-modeling-projects"
    if is_mac_airdrop_receive_prompt(text):
        return "mac-system-accounts"
    if is_mac_security_sweep_prompt(text):
        return "mac-system-accounts"
    if is_epson_wf2960_network_black_only_prompt(text):
        return "mac-system-accounts"
    if is_apple_m2_workstation_disadvantage_prompt(text):
        return "mac-system-accounts"
    if is_simulator_package_quality_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_codex_macos_tahoe_toolchain_followup_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_filament_load_park_wipe_pad_prompt(text):
        return "printer-klipper-ops"
    if is_printer_reflash_pi_temp_prompt(text):
        return "printer-klipper-ops"
    if is_petg_cf_part_cooling_prompt(text):
        return "printer-klipper-ops"
    if is_macro_usage_missing_context_prompt(text):
        return "printer-klipper-ops"
    if is_camera_stepper_motion_check_prompt(text):
        return "printer-klipper-ops"
    if is_apus_mounting_hole_design_prompt(text):
        return "cad-modeling-projects"
    if is_m3_screw_hole_size_prompt(text):
        return "research-parts-reference"
    if is_orca_codex_vs_tinmanx_strategy_prompt(text):
        return "orcaslicer-codex"
    if is_orca_codex_wrong_build_prompt(text):
        return "orcaslicer-codex"
    if is_slicer_parsing_error_repair_prompt(text):
        return "orcaslicer-codex" if any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex")) else "tinmanx-slicer-research"
    if is_engineering_filament_cost_prompt(text):
        return "tinmanx-slicer-research"
    if is_controller_fan_airflow_prompt(text):
        return "printer-klipper-ops"
    if is_core_one_l_calibration_prompt(text):
        return "printer-klipper-ops"
    if is_tailscale_ssh_definition_prompt(text):
        return "mac-system-accounts"
    if is_rocket_slicer_machine_data_prompt(text):
        return "tinmanx-slicer-research"
    if is_preview_zoom_controls_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_slotted_turbine_hub_modular_design_prompt(text):
        return "cad-modeling-projects"
    if is_rotor_material_mass_prompt(text):
        return "cad-modeling-projects"
    if is_eject_target_context_prompt(text):
        return "general"
    if is_motion_system_testing_context_prompt(text):
        return "printer-klipper-ops"
    if is_belt_slip_cutting_force_prompt(text):
        return "printer-klipper-ops"
    if is_bed_mesh_deviation_quality_prompt(text):
        return "printer-klipper-ops"
    if is_pt6_icing_itt_prompt(text):
        return "aviation-engineering"
    if is_speaker_pod_cad_prompt(text):
        return "cad-modeling-projects"
    if is_output_gate_comparison_context_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_codex_output_failure_feedback_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_speed_setting_timeline_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_fusion_cam_stock_shoulder_prompt(text):
        return "cad-modeling-projects"
    if "grbl" in lower and "fusion" in lower and any(term in lower for term in ("ugs", "universal gcode sender", "output", "post")):
        return "cnc-machining"
    if any(term in lower for term in ("single pole single throw", "spst")) and any(term in lower for term in ("lightbulb", "light bulb", "bulb", "lamp")):
        return "engineering-diagrams"
    if any(term in lower for term in ("see your thoughts", "show your thoughts", "watch your thoughts", "see his thoughts", "show his thoughts", "watch his thoughts", "thoughts while you are working", "thoughts while he is working", "working notes")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("anything else", "anything more", "what else")) and any(term in lower for term in ("clean up", "cleanup", "cleaned up")) and any(term in lower for term in ("nice to have", "nice-to-have", "nice to haves", "nice-to-haves", "continuing", "continue")):
        return "codex-cli-ui-local-agent"
    if is_codex_personality_settings_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_cm4_vs_pi5_prompt(text):
        return "embedded-linux-images"
    if is_cm4_ram_size_prompt(text):
        return "embedded-linux-images"
    if is_dot147_beacon_offset_update_prompt(text):
        return "printer-klipper-ops"
    if "beacon" in lower and any(term in lower for term in ("xy verification", "x/y verification", "xy offset", "x/y offset", "offset calibration")) and any(term in lower for term in ("scan", "compare", "calibration", "verify", "verification")):
        return "printer-klipper-ops"
    if is_fusion_all_designs_script_prompt(text):
        return "cad-modeling-projects"
    if is_fusion_solid_removal_prompt(text):
        return "cad-modeling-projects"
    if is_fusion360_capability_prompt(text):
        return "cad-modeling-projects"
    if is_p51_fusion_lockup_prompt(text):
        return "cad-modeling-projects"
    if "fusion" in lower and any(term in lower for term in ("directory", "folder", "path")) and any(term in lower for term in ("file", "files", "output", "saved")):
        return "cad-modeling-projects"
    if is_slicer_actual_work_status_prompt(text):
        return "tinmanx-slicer-research"
    if is_fibreseek_fiber_amount_location_prompt(text):
        return "tinmanx-slicer-research"
    if is_codex_son_self_improvement_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_btt_vivd_sensor_prompt(text):
        return "printer-klipper-ops"
    if is_btt_vivd_system_path_prompt(text):
        return "printer-klipper-ops"
    if is_source_credit_short_prompt(text):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex")) and any(term in lower for term in ("tinmanx build", "not the orca codex build", "takes me to")):
        return "orcaslicer-codex"
    if any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex")) and any(
        term in lower for term in ("whole", "better", "streamlined", "performance", "backend", "architecture", "construct the backend")
    ) and any(term in lower for term in ("revise", "lets do it", "let's do it", "now is the time")):
        return "orcaslicer-codex"
    if any(term in lower for term in ("codex cli ui", "codex cli", "ollama", "heartbeat", "github", "dock", "app icon")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("cyber security risk", "cybersecurity risk", "security risk", "flagged")) and any(
        term in lower for term in ("youtube query", "youtube", "research", "impact our research", "impact the research")
    ):
        return "codex-cli-ui-local-agent"
    if (
        any(term in lower for term in ("finish a task", "finishing a task", "task is complete", "task you can", "after finishing", "previous task", "previous one"))
        and any(term in lower for term in ("start the next task", "start the next tasks", "start the new task", "move on to the next task", "proceed to the next task", "next task", "next tasks"))
        and any(term in lower for term in ("until the app is complete", "until app is complete", "until the app build is complete", "until we are finished", "until it is complete", "keep going", "keep moving", "immediately", "immediatly"))
    ):
        return "codex-cli-ui-local-agent"
    if (
        any(term in lower for term in ("boat house", "boathouse"))
        and any(term in lower for term in ("engineering drawing", "engineering drawings", "engineering grade", "plans", "specific engineering directions"))
        and any(term in lower for term in ("georgia code", "lake tobosofke", "lake tobesofkee", "lake tobosofkee", "macon georgia", "mary anne drive", "31220"))
    ):
        return "cad-modeling-projects"
    if (
        any(term in lower for term in ("github", "git hub"))
        and any(term in lower for term in ("upload", "uploaded"))
        and any(term in lower for term in ("100 files", "100 file", "more than 100", "hundred files", "100 at a time"))
        and any(term in lower for term in ("upload the rest", "the rest", "remaining", "re organize", "reorganize", "organize them"))
    ):
        return "codex-cli-ui-local-agent"
    if (
        any(term in lower for term in ("codex chats", "codex chat", "my chats", "our chats", "chat history"))
        and any(term in lower for term in ("new codex", "codex cli ui", "new codex ui", "new codex app"))
        and any(term in lower for term in ("upload", "import", "knows the history", "know the history", "history of what we are doing", "history of what we're doing"))
    ):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("+ button", "plus button")) and any(term in lower for term in ("add a file", "add file", "attach", "file picker", "finder")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("guest network", "guest wifi", "guest ssid")) and any(term in lower for term in ("health check", "system", "network check", "scan")):
        return "mac-system-accounts"
    if is_inserted_filament_switch_state_prompt(text):
        return "printer-klipper-ops"
    if is_klipper_restart_prompt(text) or is_bambu_x1c_nozzle_live_status_prompt(text):
        return "printer-klipper-ops"
    if any(term in lower for term in ("ga hotline", "general aviation", "tsoc", "transportation security operations center")) and any(term in lower for term in ("true. false", "true or false", "true false")):
        return "aviation-engineering"
    if any(term in lower for term in ("arc support", "arc supports")) and any(term in lower for term in ("deep dive", "research", "get arc supports working", "working")):
        return "orcaslicer-codex"
    if "filament profile" in lower and any(term in lower for term in ("create", "make", "generate", "build", "write")) and any(term in lower for term in ("nozzle", "printer", "core one", "pakv", "fila matrix")):
        return "tinmanx-slicer-research"
    if "custom filament profiles" in lower and any(term in lower for term in ("process profile", "process profiles", "make", "create", "generate")):
        return "tinmanx-slicer-research"
    if is_fibreseeker_calculation_paper_update_prompt(text):
        return "tinmanx-slicer-research"
    if is_orca_chamber_before_bed_research_prompt(text):
        return "tinmanx-slicer-research"
    if is_coolant_printed_fittings_prompt(text):
        return "cad-modeling-projects"
    if any(term in lower for term in ("which he pins", "what he pins", "he pins did we go", "he pin did we go")) and any(term in lower for term in ("external hot end fan", "external hotend fan", "hot end fan", "hotend fan", "fan")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("cfc path", "continuous fiber", "continuous-fiber")) and any(term in lower for term in ("center hole", "lower openings", "upper 2 openings", "alternating layer", "alternating layers")):
        return "tinmanx-slicer-research"
    if "pmc.ncbi.nlm.nih.gov/articles/" in lower and any(term in lower for term in ("anything valid", "could use", "use?", "review", "impliment", "implement")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("heat soak", "heat-soak")) and any(term in lower for term in ("chamber temp", "chamber temperature", "chamber")) and any(
        term in lower for term in ("50 degrees", "50 c", "50c", "50")
    ):
        return "printer-klipper-ops"
    if is_heat_soak_at_print_chamber_temp_prompt(text):
        return "printer-klipper-ops"
    if is_thermal_stabilize_reprobe_prompt(text):
        return "printer-klipper-ops"
    if is_eject_until_box_sensor_unloaded_prompt(text):
        return "printer-klipper-ops"
    if is_filament_eject_live_action_prompt(text):
        return "printer-klipper-ops"
    if is_btt_sfs_false_motion_code_prompt(text):
        return "printer-klipper-ops"
    if any(term in lower for term in ("start print macro", "start_print", "print_start")) and any(term in lower for term in ("heat soak", "adaptive bed mesh", "contact probe", "z home", "chamber", "bed temp")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("working version of orca slicer", "correct version of orcaslicer", "correct version of orca")) and any(term in lower for term in ("arc fittings", "arc support", "wave overhang", "strength lens", "fibreseeker", "fiberseeker", "continuous carbon fiber")):
        return "orcaslicer-codex"
    if any(term in lower for term in ("zoom in and out", "zoom in/out", "zoom controls", "zoom function")) and "preview" in lower:
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("rocket slicer", "rocketslicer")) and any(term in lower for term in ("machine gates", "physical machine", "delayed", "testing before hand", "testing beforehand")):
        return "tinmanx-slicer-research"
    if is_rocket_fiber_placement_verification_prompt(text):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("custom filament profiles",)) and any(term in lower for term in ("part cooling", "fan settings", "cooling settings", "same thing")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("tinneyaviation.com", "tinney aviation")) and any(term in lower for term in ("data", "lost", "losing", "not saving", "disappearing")):
        return "flightops-tracker"
    if is_flightops_tinneyaviation_login_tabs_prompt(text):
        return "flightops-tracker"
    if is_propeller_exhaust_rounding_prompt(text):
        return "cad-modeling-projects"
    if "retraction" in lower and "stringing" in lower:
        return "tinmanx-slicer-research"
    if "orca" in lower and "hat" in lower and any(term in lower for term in ("smaller", "scale", "wearing", "wear")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("clear the fault", "clear fault", "clear any faults")) and any(term in lower for term in ("unload", "eject", "before we start", "restart")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("t0", "toolhead 0")) and any(term in lower for term in ("t1", "toolhead 1")) and "beacon" in lower and any(term in lower for term in ("swap", "beacon id", "mcu id", "different results", "different toolheads")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("sync user presets", "user presets warning", "sync preset", "preset warning")):
        return "tinmanx-slicer-research"
    if "logo" in lower and any(term in lower for term in ("website", "site", "web app", "page")) and any(term in lower for term in ("darker", "dark feel", "dark theme", "little darker")):
        return "codex-cli-ui-local-agent"
    if is_document_compliance_review_prompt(text):
        return "general"
    if is_no_filament_loaded_test_prompt(text):
        return "printer-klipper-ops"
    if any(term in lower for term in ("strength", "strenght")) and any(term in lower for term in ("fibreseeker", "fiberseeker", "fibreseek", "fiberseek")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("true. false", "true or false", "true false")) and "introduce" in lower and "confrontation" in lower:
        return "aviation-engineering"
    if is_network_moved_ip_scan_prompt(text):
        if any(term in lower for term in ("qidi", "max ez", "maxez", "max ex", "maz ez", "printer")):
            return "printer-klipper-ops"
        return "mac-system-accounts"
    if re.search(r"\bn\d{3,5}[a-z]{0,2}\b", lower) and any(term in lower for term in ("on condition", "n/a", "not applicable")) and "status block" in lower:
        return "flightops-tracker"
    if any(term in lower for term in ("this is perfect", "exactly what i wanted")) and any(term in lower for term in ("next move", "next step")):
        return "general"
    if any(term in lower for term in ("list of the features", "feature list", "features we are incorporating")) and any(term in lower for term in ("same page", "make sure", "confirm", "just to")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("youtube", "youtu.be")) and "transcript" in lower and any(term in lower for term in ("tinmanx", "settings", "workflow", "strength", "research")):
        return "tinmanx-slicer-research"
    if "m191" in lower and "chamber" in lower and any(term in lower for term in ("disable", "turn off", "remove")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("where are we at", "where are we", "status")) and any(term in lower for term in ("arc support", "arc supports")):
        return "orcaslicer-codex"
    if any(term in lower for term in ("front right", "front-right")) and any(term in lower for term in ("plan view", "overhead", "homing", "home")) and any(term in lower for term in ("z tilt", "z-tilt", "z_tilt")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("storage", "system data", "running out of storage")) and any(term in lower for term in ("where this is coming from", "majority is system data", "look at my storage", "running out of storage")):
        return "mac-system-accounts"
    if any(term in lower for term in ("rocket slicer", "rocketslicer")) and any(term in lower for term in ("pc", "polycarbonate")) and any(term in lower for term in ("plastic profile", "material profile", "filament profile", "add a")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("xy distance", "x/y distance")) and any(term in lower for term in ("feed", "feedrate", "feed rate")) and any(term in lower for term in ("overlapping", "overlap", "ui")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("smooth air diverter", "smooth air diverters", "spinner")) and any(term in lower for term in ("rotor", "airflow", "collector", "bell diffuser", "diffuser")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("screenshot of fusion", "take a screenshot of fusion", "screenshot fusion", "fusion screenshot")):
        return "cad-modeling-projects"
    if "device page" in lower and (len(text) > 300 or "\ufffd" in text):
        return "printer-klipper-ops"
    if is_professional_output_label_prompt(text):
        return "energy-power-research"
    if is_save_settings_no_button_prompt(text):
        return "general"
    if "extrude" in lower and any(term in lower for term in ("non planar", "non-planar", "non flat", "non-flat", "surface", "to object")):
        return "cad-modeling-projects"
    if is_cad_repair_before_return_prompt(text):
        return "cad-modeling-projects"
    if lower.strip() in {"how is the ui coming?", "how is the ui coming", "how is codex cli ui coming?", "how is codex cli ui coming"}:
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("improve his performance", "improve performance")) and any(term in lower for term in ("before we package", "before packaging", "package it", "packaging")):
        return "codex-cli-ui-local-agent"
    if "support" in lower and any(term in lower for term in ("normal support", "normal supports", "seeing the normal supports", "show normal supports")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("bambu studio", "bambu")) and any(term in lower for term in ("orca slicer", "orca")) and any(
        term in lower for term in ("support interface", "support and interface", "support section", "supports")
    ) and any(term in lower for term in ("compare", "differences", "big differences", "easy to remove")):
        return "tinmanx-slicer-research"
    if "build plate" in lower and any(term in lower for term in ("feature", "features", "help")) and any(term in lower for term in ("cnc", "cut", "engrave", "engraving", "name")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("rocket", "copying rocket")) and any(term in lower for term in ("change the titles", "rename", "titles")) and any(
        term in lower for term in ("speedy", "reinforced", "fortified", "maximum")
    ):
        return "tinmanx-slicer-research"
    if "tinmanx" in lower and any(term in lower for term in ("toolbar", "dock", "pin", "shortcut")) and any(
        term in lower for term in ("place", "put", "add", "so i dont have to ask", "open it every time")
    ):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("window is cutting off", "cutting off the bottom", "bottom of the build plate", "bottom selection")) and any(
        term in lower for term in ("build plate", "selection windows", "window", "orca", "tinmanx", "slicer")
    ):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("k2 plus", "creality k2")) and any(term in lower for term in ("nozzle", "hardened nozzle", "0.4mm", "0.4 mm")) and any(
        term in lower for term in ("change the ui", "ui to reflect", "reflect this", "profile", "display")
    ):
        return "tinmanx-slicer-research"
    if "orca" in lower and any(term in lower for term in ("difference in quality", "quality between", "what we have")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("codex cli ui", "codex ui")) and any(term in lower for term in ("next", "refine", "improve")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("codex cli", "codex")) and any(term in lower for term in ("local oss", "local-oss", "ollama")):
        return "codex-cli-ui-local-agent"
    if "icons" in lower and any(term in lower for term in ("both apps", "both app", "two apps")):
        return "codex-cli-ui-local-agent"
    if "codex" in lower and any(term in lower for term in ("clear previous chat history", "clear chat history", "delete chat history", "wipe chat history")):
        return "codex-cli-ui-local-agent"
    if "codex" in lower and any(term in lower for term in ("how much", "how many", "system data", "remaining")) and any(term in lower for term in ("gb", "storage", "space")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("green box", "green background", "working area")) and any(
        term in lower for term in ("header", "black background", "moved up", "separate from the working area", "seperate from the working area")
    ):
        return "codex-cli-ui-local-agent"
    if "sandbox" in lower and any(term in lower for term in ("change", "modify", "settings", "access", "visibility")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("web access", "public web", "internet access")) and any(term in lower for term in ("toggle", "below reasoning", "reasoning")):
        return "codex-cli-ui-local-agent"
    if (
        any(term in lower for term in ("strip", "led", "lights", "status colors", "status colour", "status"))
        and any(term in lower for term in ("green", "other than green", "non-green", "appropriate color", "appropriate colour"))
        and any(term in lower for term in ("pulse", "slowly pulse", "pulsing", "breathe", "breathing"))
    ):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("create a ui", "make a ui", "codex cli ui")) and any(term in lower for term in ("codex cli", "mirrors the ui", "this codex")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("changed to medium", "set to medium", "medium")) and any(term in lower for term in ("log out", "back in", "take effect")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("click on it", "click it", "when i click")) and any(term in lower for term in ("page that says print", "says print", "print page")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("making him better", "make him better", "improve him", "improving him")) and any(term in lower for term in ("next step", "better help us", "projects we work on")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("make him realize when he needs help", "self sufficient", "self-sufficient", "find the tools he needs")) and any(
        term in lower for term in ("web", "tools", "codex", "he can")
    ):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("similar performance", "same performance", "near chatgpt")) and any(term in lower for term in ("without using a pay service", "without a pay service", "free", "local")):
        return "codex-cli-ui-local-agent"
    if is_weekly_data_reasoning_level_prompt(text):
        return "codex-cli-ui-local-agent"
    if "outside writable workspace" in lower:
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("look professional", "professional and smooth", "chats are neat", "chats are neet")) and any(term in lower for term in ("####", "markdown", "chat", "fix this")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("clean pass", "clean-pass")) and any(term in lower for term in ("this mac", "on this mac", "everything we can do")):
        return "mac-system-accounts"
    if any(term in lower for term in ("features are not blocked", "restrict any function", "do not need to restrict", "functions available")) and any(term in lower for term in ("experimental", "logo", "app", "project")):
        return "cad-modeling-projects"
    if is_local_hardware_host_choice_prompt(text):
        return "embedded-linux-images"
    if re.search(r"^(?:(?:lets|let's)\s+sync\s+to\s+the\s+pi|how\s+do\s+i\s+sync\s+to\s+my\s+pi)\b", lower.strip()):
        return "embedded-linux-images"
    if is_flightops_scoped_feature_prompt(text):
        return "flightops-tracker"
    if is_report_cache_refresh_prompt(text):
        return "flightops-tracker"
    if is_pctg_nozzle_tuned_prompt(text):
        return "tinmanx-slicer-research"
    if is_history_printer_operational_prompt(text):
        return "printer-klipper-ops"
    if is_github_scheduled_workflow_disabled_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_flightops_work_organized_status_prompt(text):
        return "flightops-tracker"
    if is_slicer_filament_manufacturer_tab_prompt(text):
        return "tinmanx-slicer-research"
    if is_github_share_all_work_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_prusa_api_key_ssh_prompt(text):
        return "printer-klipper-ops"
    if is_flightops_customer_users_database_prompt(text) or is_spreadsheet_landscape_due_format_prompt(text):
        return "flightops-tracker"
    if is_flightops_maintenance_reserve_title_hide_prompt(text) or is_pdf_to_excel_hobbs_prompt(text):
        return "flightops-tracker"
    if is_klipper_modifications_github_prep_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_github_filament_process_update_prompt(text) or is_codex_cli_ui_more_like_codex_combo_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_speaker_enclosure_regroup_reference_prompt(text):
        return "cad-modeling-projects"
    if is_youtube_video_analysis_prompt(text):
        return "general"
    if is_website_design_before_migration_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_cf_polymer_hotend_mount_material_compare_prompt(text):
        return "tinmanx-slicer-research"
    if is_aircraft_water_drain_true_false_prompt(text):
        return "aviation-engineering"
    if is_aircraft_tool_supply_promo_code_prompt(text):
        return "research-parts-reference"
    if is_tailscale_credentials_login_prompt(text):
        return "mac-system-accounts"
    if (
        is_prusa_klipper_conversion_research_prompt(text)
        or is_prusa_core_one_profiles_prompt(text)
        or is_centauri_cosmos_firmware_upgrade_prompt(text)
        or is_sovol_mainline_klipper_migration_prompt(text)
        or is_box_rfid_macros_check_prompt(text)
        or is_zoffset_calibration_probe_log_prompt(text)
        or is_ratrig_belt_cheatsheet_prompt(text)
        or is_sv08_petgcf_temp_recall_prompt(text)
        or is_ratrig_belt_frequency_chamber_inop_prompt(text)
        or is_stop_current_print_prompt(text)
        or is_qidi_nozzle_temp_access_feedback_prompt(text)
        or is_qidi_profiles_shaper_tuning_prompt(text)
        or is_qidi_chamber_heater_cap_verify_prompt(text)
        or is_klipper_beacon_comments_closed_next_prompt(text)
        or is_filament_input_pin_compare_remote_prompt(text)
    ):
        return "printer-klipper-ops"
    if is_mainsail_ssh_password_prompt(text) or is_pi_restart_safety_prompt(text):
        return "printer-klipper-ops"
    if is_adaptive_heat_soak_broad_design_prompt(text):
        return "printer-klipper-ops"
    if any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex")):
        return "orcaslicer-codex"
    if any(term in lower for term in ("orca codex", "orcaslicer codex")) and any(term in lower for term in ("stand alone", "standalone")) and "rocket" in lower:
        return "orcaslicer-codex"
    if any(term in lower for term in ("arc support", "arc supports")) and any(term in lower for term in ("verify", "confirm", "ran", "sliced", "generated")):
        return "orcaslicer-codex"
    if any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex")) and any(term in lower for term in ("arc support", "arc supports")):
        return "orcaslicer-codex"
    if any(term in lower for term in ("waveoverhang", "wave overhang", "wave overhangs", "wave-overhang")) and any(term in lower for term in ("arc support", "arc supports")):
        return "orcaslicer-codex"
    if is_tinmanx_wave_overhang_generate_now_prompt(text):
        return "tinmanx-slicer-research"
    if is_functional_wave_overhang_generator_prompt(text):
        return "orcaslicer-codex"
    if is_approval_window_workaround_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_tinmanx_average_completion_time_prompt(text):
        return "tinmanx-slicer-research"
    if is_tinmanx_schedule_status_prompt(text):
        return "tinmanx-slicer-research"
    if "wave overhang" in lower and any(term in lower for term in ("tab", "crash", "crashed")):
        return "orcaslicer-codex"
    if any(term in lower for term in ("failed login", "failed log in", "login attempt", "log in attempt")):
        return "mac-system-accounts"
    if any(term in lower for term in ("verification code", "verify your", "your code is", "account")) and any(term in lower for term in ("email", "dont know", "don't know", "what is this", "funnow", "onmicrosoft.com")):
        return "mac-system-accounts"
    if "chrome" in lower and any(term in lower for term in ("clear cache", "clear the cache", "casche")):
        return "mac-system-accounts"
    if any(term in lower for term in ("hard refresh", "hard reload", "force refresh")) and any(term in lower for term in ("page", "browser", "website")):
        return "mac-system-accounts"
    if "subnet" in lower and any(term in lower for term in ("re log", "re-log", "relog", "log on", "login")):
        return "mac-system-accounts"
    if any(term in lower for term in ("scan all ip", "scan all ip's", "scan ips", "scan ip")) and any(term in lower for term in ("192.168.", "10.", "172.")):
        return "mac-system-accounts"
    if any(term in lower for term in ("8gb of ram", "8 gb of ram", "8gb ram", "8 gb ram")) and any(term in lower for term in ("services", "warrant", "justify")):
        return "mac-system-accounts"
    if "msvc" in lower and any(term in lower for term in ("build", "package", "compile", "toolchain")) and any(term in lower for term in ("mac", "macos", "this mac")):
        return "mac-system-accounts"
    if any(term in lower for term in ("cm3000", "nighthawk cm3000", "netgear")) and any(term in lower for term in ("router", "wifi", "wi-fi")) and any(term in lower for term in ("4500", "4,500", "square foot", "sq ft", "fastest")):
        return "mac-system-accounts"
    if "safari" in lower and "share button" in lower:
        return "mac-system-accounts"
    if any(term in lower for term in ("192.168.", "10.0.", "172.16.")) and any(term in lower for term in ("did we get", "dis we get", "reach", "reachable", "ping", "find")):
        return "mac-system-accounts"
    if is_diagram_tool_recommendation_prompt(text):
        return "engineering-diagrams"
    if any(term in lower for term in ("wiring diagram", "block diagram", "electrical diagram", "schematic", "power diagram", "graphviz")):
        return "engineering-diagrams"
    if "n533ss" in lower and any(term in lower for term in ("source excel", "excel file", "spreadsheet", "tracking file")):
        return "flightops-tracker"
    if any(term in lower for term in ("king james bible", "kjv", "scripture")):
        return "bible-kjv-study"
    if any(term in lower for term in ("andersons", "anderson's", "anderson")) and any(term in lower for term in ("kaiser", "laso")) and "algorithm" in lower:
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("p51", "p-51", "mustang")) and any(term in lower for term in ("electric motor", "motor", "battery pack", "battery")) and any(
        term in lower for term in ("what size", "which size", "should i use", "sizing")
    ):
        return "energy-power-research"
    if any(term in lower for term in ("material", "best material")) and any(term in lower for term in ("extrusion", "extruded")) and any(
        term in lower for term in ("temperature expansion", "thermal expansion", "expansions", "affected the least by temperature")
    ):
        return "cad-modeling-projects"
    if is_outdoor_continuous_fiber_fan_material_prompt(text):
        return "tinmanx-slicer-research"
    if "wind turbine" in lower and any(term in lower for term in ("fusion", "cad", "step file", "create them", "design blades", "blade design")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("extend the center shaft", "heated inserts", "end plate center holes", "press fit")) and any(term in lower for term in ("35mm", "35 mm", "10mm", "10 mm", ".05mm", "0.05mm", "0.05 mm")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("rotate the rotor", "rotor")) and any(term in lower for term in ("180 degrees", "180 degree", "180")) and any(term in lower for term in ("z axis", "z-axis", "run again", "rerun")):
        return "cad-modeling-projects"
    if "wind turbine" in lower and any(term in lower for term in ("next step", "continue", "lets continue", "let's continue")):
        return "energy-power-research"
    if "wind turbine" in lower and any(term in lower for term in ("blade", "blades")) and any(term in lower for term in ("best filament", "material", "filament")):
        return "energy-power-research"
    if (
        any(term in lower for term in ("wind from all directions", "from all directions", "all wind directions", "any wind direction", "omnidirectional"))
        and any(term in lower for term in ("opposite", "1 direction", "one direction", "make it worse", "worse with the wind"))
    ):
        return "cad-modeling-projects"
    if "cpap hose" in lower and any(term in lower for term in ("inner diameter", "id", "inside diameter")):
        return "research-parts-reference"
    if any(term in lower for term in ("wind turbine", "alternator", "generator", "60vdc", "60 vdc", "300 rpm", "solar", "battery", "charge controller", "inverter", "off-grid", "3 phase", "split phase")):
        return "energy-power-research"
    if any(term in lower for term in ("power train", "powertrain", "drivetrain", "drive train")) and "motor" in lower and "battery" in lower:
        return "energy-power-research"
    if is_generator_candidate_context_prompt(text):
        return "energy-power-research"
    if "torque" in lower and "rpm" in lower and "power" in lower:
        return "energy-power-research"
    if any(term in lower for term in ("maintenance reserve", "fixed cost", "title page", "report")) and not any(term in lower for term in ("3d print", "printer", "slicer")):
        return "flightops-tracker"
    if any(term in lower for term in ("financial credit section", "credit section", "record their credit", "over paid", "overpaid")) and any(term in lower for term in ("fees", "services", "following month", "next month")):
        return "flightops-tracker"
    if any(term in lower for term in ("flight tracker", "flightops", "flight ops")) and any(term in lower for term in ("start", "launch", "run", "open")):
        return "flightops-tracker"
    if any(term in lower for term in ("destination airport", "arrival airport")) and any(term in lower for term in ("departure airport", "departure airport block")) and any(term in lower for term in ("auto populate", "autopopulate", "copy", "fill")):
        return "flightops-tracker"
    if any(term in lower for term in ("users section", "user section", "users")) and "admin" in lower and any(term in lower for term in ("list the users", "list users", "not the details", "click on them")):
        return "flightops-tracker"
    if "anodic" in lower and any(term in lower for term in ("cadmium", "titanium", "monel")):
        return "aviation-engineering"
    if any(term in lower for term in ("x1c", "x1 carbon", "bambu")) and "orca" in lower and "nozzle" in lower:
        return "tinmanx-slicer-research"
    if "snapmaker" in lower and "u1" in lower and any(term in lower for term in ("0.6 nozzle", "0.6mm nozzle", "0.6-mm nozzle", "0.6 mm nozzle")) and any(term in lower for term in ("machine profile", "printer profile", "profile")):
        return "tinmanx-slicer-research"
    if is_final_nozzle_simulator_prompt(text):
        return "cad-modeling-projects"
    if any(term in lower for term in ("orca", "orcaslicer", "tinmanx")) and "bambu studio" in lower and any(term in lower for term in ("x1c", "x1 carbon")) and "h2d" in lower and any(term in lower for term in ("machine", "process", "filament", "fllament", "profile", "profiles")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("h2d", "x1c", "x1 carbon", "bambu")) and any(term in lower for term in ("ip", "ip address", "access code", "access_code", "lan code", "printer code", "serial number")):
        return "tinmanx-slicer-research"
    if "h2d" in lower and any(term in lower for term in ("bind", "binding")) and any(
        term in lower for term in ("failed", "failing", "repeatedly", "can you see why", "fix it")
    ):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("load a model", "add a model", "model i selected", "model to be sliced", "model is added")) and any(
        term in lower for term in ("build plate", "plate", "placeholder", "set of blocks", "not what i selected", "no model shows")
    ):
        return "tinmanx-slicer-research"
    if is_abs_rat_rig_orca_overrides_prompt(text):
        return "tinmanx-slicer-research"
    if is_rgb_5v_source_prompt(text):
        return "printer-klipper-ops"
    if is_rgb_recheck_prompt(text):
        return "printer-klipper-ops"
    if is_bed_mesh_led_color_macro_prompt(text):
        return "printer-klipper-ops"
    if is_centauri_carbon_name_swap_prompt(text):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("machine profile", "machine profiles", "process profile", "process profiles", "filament profile", "filament profiles", "filiment profile", "filiment profiles")) and any(term in lower for term in ("package", "archive", "share", "reddit", "cleanup", "clean up", "dump")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("tinmanx", "orca/tinmanx", "orca and tinmanx")) and any(term in lower for term in ("rebrand", "under 1 roof", "under one roof", "white paper")):
        return "tinmanx-slicer-research"
    if is_apus_mounting_hole_design_prompt(text):
        return "cad-modeling-projects"
    if any(term in lower for term in ("3d-fuel", "3dfuel", "3d fuel")) and any(term in lower for term in ("pctg-cf", "pctg cf")) and any(term in lower for term in ("profile", "profiles", "preset", "presets")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("fibreseek", "fiberseek")) and any(term in lower for term in ("font size", "font type", "font")) and any(term in lower for term in ("filament", "process", "panel", "panels")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("prusa slicer", "prusaslicer")) and any(term in lower for term in ("orca", "filament", "printer profiles", "profiles")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("prusa ui", "prusa machine", "on the machine", "machine when i load it")) and any(
        term in lower for term in ("codex filaments", "orca codex", "filament")
    ):
        return "orcaslicer-codex"
    if "orca" in lower and "prusa" in lower and any(term in lower for term in ("device page", "device tab", "white screen")):
        return "tinmanx-slicer-research"
    if (
        any(term in lower for term in ("open centauri", "centauri", "centari", "centauri carbon", "centari carbon"))
        and any(term in lower for term in ("orca", "orcaslicer", "orca codex"))
        and any(term in lower for term in ("device tab", "devive tab", "device page"))
        and any(term in lower for term in ("standard klipper", "klipper", "more control", "control"))
    ):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("orca", "orcaslicer", "orca codex")) and any(term in lower for term in ("device tab", "devive tab", "device page")) and any(term in lower for term in ("stepper", "motor temp", "motor temperature", "temp section", "temperature section", "more control")):
        return "orcaslicer-codex"
    if any(term in lower for term in ("pakv", "pa-kv")) and any(term in lower for term in ("chamber temp", "chamber temperature")):
        return "tinmanx-slicer-research"
    if "petg" in lower and "pctg" in lower:
        return "tinmanx-slicer-research"
    if "pctg" in lower and any(term in lower for term in ("profile", "profiles", "filament preset", "filament presets")) and any(term in lower for term in ("update", "change", "fix", "all of", "all the")):
        return "tinmanx-slicer-research"
    if "rocket" in lower and any(term in lower for term in ("min cut length", "min-cut", "minimum cut", "minimum fiber length", "minimum fibre length", "minimum length", "65", "90mm", "90 mm")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("orca", "orca slicer", "orcaslicer")) and "filament" in lower and any(term in lower for term in ("unsupported", "tags", "tagged", "mark", "marks")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("sync the filaments", "sync filaments", "filaments into orca")) and any(term in lower for term in ("orca", "tinmanx")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("petg-cf", "petg cf", "petg carbon")) and any(term in lower for term in ("profile", "profiles", "filament presets")) and any(term in lower for term in ("bed temp", "bed temperature", "50c", "50 c")):
        return "tinmanx-slicer-research"
    if "petg" in lower and any(term in lower for term in ("cfc petg", "cf petg", "cf-petg", "petg-cf", "x-ccf", "xccf", "carbon fiber")) and "different" in lower:
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("active chamber heating", "active chamber", "chamber heating")) and any(term in lower for term in ("dynamic", "by filament", "filament selected", "selected filament")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("machine start gcode", "machine start g-code", "start gcode", "start g-code")) and any(term in lower for term in ("before the heaters", "before heaters", "heater", "heaters")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("machine_start_gcode", "machine start gcode", "machine start g-code", "custom start gcode", "custom start g-code", "start code")) and any(
        term in lower for term in ("print_start", "print_start_bed", "hotend", "chamber temp", "chamber")
    ):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("bambu studio", "bambu")) and any(term in lower for term in ("filament mixing", "filiment mixing", "mixing")) and "orca" in lower:
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("helmet", "rounded top", "top of the helmet")) and "layer lines" in lower:
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("tinmanx", "rocket slicer", "orca", "filament profile", "temp tower", "pressure advance", "pet-cf", "pctg", "slicer", "tinmanx1", "build plate", "add a plate", "add plate", "plate to plate", "p0", "p1")):
        return "tinmanx-slicer-research"
    if "rocket" in lower and any(term in lower for term in ("algorithm", "algorythem", "closer analysis", "look closer", "compare outputs", "question any differences")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("pi simulator", "raspberry pi simulator", "qemu", "simulate the pi")):
        return "embedded-linux-images"
    if any(term in lower for term in ("cleanup pass", "clean up pass", "complete cleanup", "complete clean up")) and any(term in lower for term in ("issues", "resolving", "dealing with", "workspace", "mac", "storage", "repo")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("please proceed", "full operational control", "operational control")) and any(term in lower for term in ("up and running", "without error", "project")):
        return "codex-cli-ui-local-agent"
    if "approval" in lower and any(term in lower for term in ("0700", "0715", "tomorrow morning", "work around", "do not pause", "keep moving forward")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("read me", "readme")) and any(term in lower for term in ("credit", "appropriate credit", "credited")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("start clean every time", "starts clean every time", "startup clean", "start clean")) and any(term in lower for term in ("fix this", "can we fix", "every time")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("cc1", "cc 1")) and any(term in lower for term in ("cad file", "step file", "stl", "model")) and any(term in lower for term in ("find me", "find", "housing", "runout switch")):
        return "cad-modeling-projects"
    if "spa700" in lower and any(term in lower for term in ("match", "same", "equivalent", "fit", "replacement")):
        return "research-parts-reference"
    if any(term in lower for term in ("start fiber", "start fibre", "fiber start", "fibre start")) and any(term in lower for term in ("selection box", "determine what layer", "layer to start", "layers remaining")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("what program", "which program", "program is specifically responsible", "process is responsible")) and any(term in lower for term in ("responsible", "causing", "specific")):
        return "mac-system-accounts"
    if "linear bearing" in lower and any(term in lower for term in ("carbon fiber tube", "carbon fibre tube", "carbon tube")) and any(term in lower for term in ("move", "on top", "relocate")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("orca", "machines profiles", "machine profiles", "printer profiles")) and any(term in lower for term in ("limit values", "limits", "manufacturer", "warning")) and any(term in lower for term in ("review", "compare", "adjust", "dont want to see", "don't want to see")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("rev j", "revj")) and "rpm" in lower and "torque" in lower and any(term in lower for term in ("60vdc", "60 vdc", "generate")):
        return "energy-power-research"
    if any(term in lower for term in ("auto approve", "auto-approve", "auto approves", "auto approval", "automatically approve")):
        return "codex-cli-ui-local-agent"
    if any(term in lower for term in ("tinmanx", "tinmanx1")) and any(term in lower for term in ("where are we", "where are we at", "status", "progress")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("tinmanx", "tinmanx1")) and "bambu" in lower and any(term in lower for term in ("print on", "print to", "bambu printers", "make that happen", "support", "ability to print")):
        return "tinmanx-slicer-research"
    if "researchgate.net" in lower and any(term in lower for term in ("continuous fiber", "continuous fibre", "additive manufacturing", "composites", "multi-layer")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("rocketslicer", "rocket slicer", "rocket")) and any(term in lower for term in ("carbon process", "continuous fiber", "continuous fibre")) and any(term in lower for term in ("interpret", "interperete", "algorytham", "algorithm", "were you able")):
        return "tinmanx-slicer-research"
    if "rocket" in lower and any(term in lower for term in ("backend", "limitations", "output", "what rocket will output")):
        return "tinmanx-slicer-research"
    if is_eject_until_box_sensor_unloaded_prompt(text):
        return "printer-klipper-ops"
    if is_filament_eject_live_action_prompt(text):
        return "printer-klipper-ops"
    if is_btt_sfs_false_motion_code_prompt(text):
        return "printer-klipper-ops"
    if "filament" in lower and any(term in lower for term in ("load filament", "unload filament", "load and unload", "g28", "g-code", "gcode", "macro")):
        return "printer-klipper-ops"
    if "rfid" in lower and any(term in lower for term in ("box macro", "box macros", "qidi box", "receivers", "receiver", "card reader", "card readers")):
        return "printer-klipper-ops"
    if is_max_ez_107_reachability_prompt(text):
        return "printer-klipper-ops"
    if any(term in lower for term in ("max ez", "maxez", "qidi max")) and any(term in lower for term in ("camera", "webcam", "video")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("coolant", "liquid cooling", "pump")) and any(term in lower for term in ("hotend", "hot end", "fan 6", "motor 7", "commanded temperature", "pump speed", "nema stepper")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("z tilt", "z-tilt", "z_tilt")) and any(term in lower for term in ("z motors", "stepper_z")) and any(term in lower for term in ("camera", "listed", "closest to x0", "x axis closest to x0", "which z motor")):
        return "printer-klipper-ops"
    if "pd15" in lower and any(term in lower for term in ("energize", "energized", "turn on", "enabled")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("clear the fault", "clear fault")) and any(term in lower for term in ("before we start", "before starting", "start again", "restart")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("last 3 minutes", "last three minutes", "3-minute", "3 minute")) and any(
        term in lower for term in ("camera", "webcam", "buffer", "smooth camera feed", "save")
    ):
        return "printer-klipper-ops"
    if any(term in lower for term in ("btt octopus", "octopus board")) and any(term in lower for term in ("he output", "he pin", "heater output")) and any(
        term in lower for term in ("fan", "1.5 amps", "1.5a", "1.5 amp")
    ):
        return "printer-klipper-ops"
    if "z offset" in lower and any(term in lower for term in ("each nozzle", "per nozzle", "each tool", "each toolhead", "idex", "toolhead")) and any(
        term in lower for term in ("before printing", "run a print", "start of print", "before a print", "does the system")
    ):
        return "printer-klipper-ops"
    if "bowden" in lower and "collet" in lower and any(term in lower for term in ("purpose", "what is", "not use", "remove", "without it")):
        return "printer-klipper-ops"
    if (
        any(term in lower for term in ("he0", "he1"))
        and any(term in lower for term in ("consider", "use", "using", "should we", "chamber light", "chamber lights", "case light", "enclosure light", "lights", "light"))
    ):
        return "printer-klipper-ops"
    if "filament" in lower and any(term in lower for term in ("motion sensor", "runout sensor", "filament sensor")) and any(term in lower for term in ("inhibit", "less sensitive", "less sensative", "nuisance", "false", "disable")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("t0", "toolhead", "toolheads")) and any(term in lower for term in ("t1", "toolhead", "toolheads")) and any(term in lower for term in ("did you make changes", "both toolheads", "far left", "far right")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("filament", "filiment")) and any(term in lower for term in ("box", "buffer", "qidi box")) and any(term in lower for term in ("automatically pushes", "all the way to the extruder", "auto feed", "autoload")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("filament", "filiment")) and any(term in lower for term in ("loaded it into the box", "loaded into the box", "in the box")) and any(term in lower for term in ("next step", "what is next", "whats next", "what's next", "tried loading", "load")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("assist only", "assist-only", "feeder extruder", "feeder motor", "assist feeder")) and any(term in lower for term in ("main extruder", "friction", "drag", "overcome")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("macro", "macros")) and any(term in lower for term in ("limiting", "limit", "increase the limit", "too large", "length")):
        return "printer-klipper-ops"
    if "unknown command" in lower:
        return "printer-klipper-ops"
    if any(term in lower for term in ("nozzle offset calibration", "nozzle offset")) and any(term in lower for term in ("beacon contact z offset", "contact z offset", "beacon")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("probe point", "initial probe", "z offset", "z-offset", "zoffset", "nozzle offset", "beacon")) and any(term in lower for term in ("reset", "clear", "try again", "rerun", "9mm off", "9 mm off", "when did it get")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("contacting the probe", "probe hard", "bed crashed", "bed crashes", "crashed into the toolhead", "crashes into the toolhead", "toolhead flex", "flex up")) and any(term in lower for term in ("bed", "probe", "beacon", "toolhead", "g28")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("z offset", "z-offset", "zoffset", "nozzle offset", "probe")) and "152.5" in lower and any(term in lower for term in ("make sure", "verify", "confirm", "happening", "should be done")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("ez2209", "ez 2209", "ez-2209", "ezz2209", "ez driver", "ez-driver")) and any(term in lower for term in ("m5p", "manta")) and any(term in lower for term in ("compatible", "compatable", "compatibility", "work with", "use with", "fit")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("orca", "orcas", "orca's", "orcaslicer", "tinmanx")) and any(term in lower for term in ("stop guessing", "orcas process", "orca process", "orca's process", "process for this", "look at orca")):
        return "tinmanx-slicer-research"
    if any(term in lower for term in ("chamber cooling fan", "chamber fan", "cooling fan")) and any(term in lower for term in ("pin", "assigned", "what pin")):
        return "printer-klipper-ops"
    if is_fan_output_mapping_prompt(text):
        return "printer-klipper-ops"
    if any(term in lower for term in ("xbuddy", "x buddy")) and "seal" in lower:
        return "printer-klipper-ops"
    if any(term in lower for term in ("move the motor", "move motor", "motor closest to x0", "x0")) and any(term in lower for term in ("down 10mm", "down 10 mm", "10mm", "10 mm")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("40x10", "40 x 10", "4010")) and any(term in lower for term in ("40x30", "40 x 30", "4030")) and "fan" in lower:
        return "printer-klipper-ops"
    if any(term in lower for term in ("filament is near the toolhead", "filiment is near the toolhead", "near the toolhead")) and any(term in lower for term in ("proceed", "what do we need", "next")):
        return "printer-klipper-ops"
    if any(term in lower for term in (".147", "147")) and any(term in lower for term in ("clean that up", "update it", "comes back online", "back online")):
        return "printer-klipper-ops"
    if is_config_pin_comments_prompt(text):
        return "printer-klipper-ops"
    if any(term in lower for term in ("actual temp", "actual temperature", "query the temp", "query the actual temp", "ui may be hung", "ui is hung", "96.05")) and any(term in lower for term in ("temp", "temperature", "degrees")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("filament buffer", "buffer")) and any(term in lower for term in ("bind", "binding")) and any(term in lower for term in ("motor speed", "feeder", "compensate", "adjust")):
        return "printer-klipper-ops"
    if "nozzle not hot enough" in lower or "zoffsetcalibration" in lower or "toolhead probe more than" in lower:
        return "printer-klipper-ops"
    if "beacon" in lower and "contact" in lower and any(term in lower for term in ("adaptive bed mesh", "adaptive mesh", "kamp")) and any(
        term in lower for term in ("set up", "setup", "configured", "installed", "do we have", "have we")
    ):
        return "printer-klipper-ops"
    if any(term in lower for term in ("adaptive bed mesh", "adaptive mesh")) and any(term in lower for term in ("add", "clean it up", "cleanup", "clean up")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("goliath", "mosquito magnum", "slice engineering mosquito")) and "nozzle" in lower:
        return "printer-klipper-ops"
    if any(term in lower for term in ("sensorless homing", "sensorles homing", "sensor-less homing")):
        return "printer-klipper-ops"
    if "driver_sgthrs" in lower and any(term in lower for term in ("sensitive", "sensitivity", "more", "less")):
        return "printer-klipper-ops"
    if "beacon" in lower and any(term in lower for term in ("dual beacon", "dual-beacon", "two beacon")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("runout sensor", "runout sensors", "run-out sensor", "run-out sensors")) and any(term in lower for term in ("motion sensor", "motion sensors")):
        return "printer-klipper-ops"
    if "beacon" in lower and "contact" in lower and any(term in lower for term in ("z offset", "z-offset", "z_offset")):
        return "printer-klipper-ops"
    if "beacon" in lower and "contact" in lower and any(term in lower for term in ("activated", "active", "enabled", "status")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("btt octopus", "bigtreetech octopus", "octopus board")) and "fan" in lower:
        return "printer-klipper-ops"
    if "layer shift" in lower and any(term in lower for term in ("x axis", "x-axis", "mechanically", "mechanical")):
        return "printer-klipper-ops"
    if is_ratos_pi5_image_port_prompt(text) or (any(term in lower for term in ("rat os", "ratos")) and any(term in lower for term in ("pi 5", "raspberry pi 5", "public repo", "public repository"))):
        return "embedded-linux-images"
    if "clear" in lower and "premix" in lower and "coolant" in lower:
        return "research-parts-reference"
    if is_fk275_belt_cross_reference_prompt(text):
        return "research-parts-reference"
    if is_sv08_max_second_rail_gantry_prompt(text):
        return "cad-modeling-projects"
    if any(term in lower for term in ("core one l", "core one")) and any(term in lower for term in ("mmu", "multi material")) and any(term in lower for term in ("for sale", "offer", "buy")):
        return "research-parts-reference"
    if any(term in lower for term in ("cable modem", "modem")) and any(term in lower for term in ("cox", "internet")) and any(term in lower for term in ("fastest", "buy", "hardware issue", "macon")):
        return "research-parts-reference"
    if any(term in lower for term in ("mcmaster", "mcmaster-carr", "mc master")) and any(term in lower for term in ("m5", "m 5")) and any(term in lower for term in ("4mm", "4 mm")) and any(term in lower for term in ("compact", "too big", "5225k923", "toolhead", "constraints")):
        return "research-parts-reference"
    if "hole" in lower and any(term in lower for term in ("malformed", "out of round", "oval", "turned out")):
        return "cnc-machining"
    if any(term in lower for term in ("ugs", "universal gcode sender", "universal g-code sender")) and any(term in lower for term in ("take control", "get it connected", "connect", "connected")):
        return "cnc-machining"
    if any(term in lower for term in ("spindle", "spindle controller", "2.2kw", "2.2 kw")) and any(term in lower for term in ("400 hz", "400hz")) and "rpm" in lower:
        return "cnc-machining"
    if any(term in lower for term in ("rotor", "rotors", "wind turbine")) and any(term in lower for term in ("increase the size", "make them as large", "rotational mass", "rpm numbers")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("andersons", "anderson's", "anderson")) and any(term in lower for term in ("kaiser", "laso")) and "algorithm" in lower:
        return "tinmanx-slicer-research"
    if "duct" in lower and "blade" in lower and any(term in lower for term in ("make it fit", "encompassing", "encompass", "around the blade")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("shroud", "propeller shroud", "inlets", "airflow")) and any(term in lower for term in ("correct direction", "keep the airflow", "between", "direction")):
        return "cad-modeling-projects"
    if is_controlled_y_home_after_collision_prompt(text):
        return "printer-klipper-ops"
    if any(term in lower for term in ("9mm belt", "9 mm belt", "belt")) and any(term in lower for term in ("slip", "slipping", "slip on the teeth", "tooth")) and any(term in lower for term in ("ram the toolhead", "cutting", "force", "block")):
        return "printer-klipper-ops"
    if any(term in lower for term in ("placement and orientation", "align stock", "stock to machine", "machine 0x0y", "0x0y", "0 x 0 y")) and "box" in lower:
        return "cad-modeling-projects"
    if any(term in lower for term in ("beacon mount", "beacon")) and any(term in lower for term in ("cad file", "file type", "fusion", "geometry", "designed")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("speaker box", "speaker enclosure", "enclosure")) and any(term in lower for term in ("internal geometry", "design", "maximize the sound", "technical specs", "tecnical specs")) and any(term in lower for term in ("speaker", "amplifier", "amp")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("round the edges", "rounded edges", "fillet")) and any(term in lower for term in ("wing tips", "wingtips", "vertical fin", "rudder")):
        return "cad-modeling-projects"
    if any(term in lower for term in ("fusion", "freecad", "cad", "stl", "step", "cpap duct", "cooling duct", "fea", "structural", "xfoil", "openvsp", "su2", "qblade", "speaker pod", "baffle", "sk_speaker_reference", "speaker reference")):
        return "cad-modeling-projects"
    if is_humidity_control_box_minimal_heat_prompt(text) or is_cad_file_format_preference_prompt(text):
        return "cad-modeling-projects"
    if is_google_earth_roofline_solar_prompt(text):
        return "energy-power-research"
    if is_bed_mesh_z_offset_calibration_research_prompt(text) or is_github_update_changes_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_orca_install_location_prompt(text) or is_codex_vendor_profile_prompt(text) or is_ratrig_idex_user_preset_prompt(text) or is_plus4_petcf_06_filament_settings_prompt(text):
        return "tinmanx-slicer-research"
    if (
        is_klipperscreen_installed_working_check_prompt(text)
        or is_snapmaker_u1_usb_port_location_prompt(text)
        or is_ratrig_generic_copy_preset_review_prompt(text)
        or is_spdt_runout_immediate_pause_prompt(text)
        or is_flash_existing_board_klipper_prompt(text)
        or is_qidi_box_before_freedi_prompt(text)
        or is_moonraker_json_status_blob_prompt(text)
    ):
        return "printer-klipper-ops"
    if is_sensorless_homing_decimal_sensitivity_prompt(text):
        return "printer-klipper-ops"
    if any(term in lower for term in ("qidi", "rat rig", "ratrig", "klipper", "moonraker", "marlin", "prusa", "bambu", "snapmaker", "u1", "paxx", "sovol", "centauri", "printer")):
        return "printer-klipper-ops"
    if is_ratrig_vcore_extrusion_gantry_prompt(text):
        return "printer-klipper-ops"
    if is_dry_room_sub_10_humidity_prompt(text):
        return "printer-klipper-ops"
    if is_project_github_link_prompt(text):
        return "codex-cli-ui-local-agent"
    if is_stock_firmware_password_prompt(text):
        return "embedded-linux-images"
    if is_flightops_pi_vpn_mobile_access_prompt(text):
        return "flightops-tracker"
    if (
        is_flightops_document_not_found_user_prompt(text)
        or is_flightops_old_spreadsheet_download_prompt(text)
        or is_flightops_monthly_report_back_button_prompt(text)
        or is_flightops_tinneyaviation_data_loss_prompt(text)
        or is_flightops_role_redirect_prompt(text)
        or is_flightops_mobile_app_prompt(text)
    ):
        return "flightops-tracker"
    if any(term in lower for term in ("price", "availability", "buy", "compare pricing", "generator", "alternator", "part number")):
        return "research-parts-reference"
    if any(term in lower for term in ("amelia air", "amelia osprey")) and any(term in lower for term in ("flight logs", "all entries", "all references", "all fields", "databases", "database", "replace", "remove", "reverted", "change all")):
        return "flightops-tracker"
    if any(term in lower for term in ("flight ops", "flightops", "pilot", "aircraft", "certificate", "customer", "service charge", "service fee", "services charge", "services charges", "wb air")):
        return "flightops-tracker"
    return ""


def web_needed(text):
    lower = text.lower()
    if is_agent_preference_question_prompt(text) or is_mac_memory_ai_performance_prompt(text):
        return False
    if is_wind_generator_alternator_shopping_prompt(text) or is_snapmaker_u1_nozzle_shopping_prompt(text):
        return True
    if "heartbeat" in lower and any(term in lower for term in ("12 hours", "15 min", "keep moving", "mac doesnt sleep", "mac doesn't sleep")):
        return False
    if is_general_regression_test_bank_prompt(text):
        return False
    if is_offline_knowledge_server_sizing_prompt(text):
        return False
    if (
        is_slicer_profile_update_prompt(text)
        or is_orcaslicer_codex_installed_changes_prompt(text)
        or is_core_one_l_filament_specific_profile_share_prompt(text)
        or is_shared_profile_repo_machine_organization_prompt(text)
        or is_makersvpn_reboot_prompt(text)
        or is_bluetooth_rename_prompt(text)
    ):
        return False
    if (
        is_router_access_permission_prompt(text)
        or is_router_optimization_login_prompt(text)
        or is_ssh_extended_firmware_capability_prompt(text)
        or is_qidi_max_ez_adaptive_heat_soak_feature_prompt(text)
        or is_toolhead_runout_switch_remap_prompt(text)
        or is_orca_calibration_image_prompt(text)
    ):
        return False
    return any(term in lower for term in ("http://", "https://", "search the web", "web forums", "company data", "current", "latest", "today", "price", "availability", "github", "download", "manual")) or any(
        term in lower for term in CURRENT_SOFTWARE_TERMS
    )


def is_he0_light_prompt(text):
    lower = text.lower()
    return any(term in lower for term in ("he0", "he1")) and any(
        term in lower
        for term in ("chamber light", "chamber lights", "case light", "enclosure light", "lights", "light")
    )


def is_router_optimization_login_prompt(text):
    lower = text.lower()
    return (
        "router" in lower
        and any(term in lower for term in ("log into", "login", "log in", "look for", "optimize", "optimise", "optomize"))
        and any(term in lower for term in ("connection speed", "speed", "robustness", "reliability", "better use", "wifi", "wi-fi", "network"))
    )


def is_router_access_permission_prompt(text):
    lower = text.lower()
    return (
        "router" in lower
        and any(term in lower for term in ("permission", "permision", "give you access", "access my router", "let you access"))
        and any(term in lower for term in ("can i", "can we", "may i", "give you"))
    )


def is_ssh_extended_firmware_capability_prompt(text):
    lower = text.lower()
    return (
        any(term in lower for term in ("firmware", "extended firmware", "custom firmware", "paxx", "paxx12"))
        and "ssh" in lower
        and any(term in lower for term in ("credentials", "credintials", "login", "log in", "access"))
        and any(term in lower for term in ("will you be able", "can you", "finish", "features", "gain all"))
    )


def is_qidi_max_ez_adaptive_heat_soak_feature_prompt(text):
    lower = text.lower()
    return (
        any(term in lower for term in ("qidi", "max ez", "maxez", "max ex"))
        and any(term in lower for term in ("adaptive heat soak", "adaptive heat-soak", "adaptive heatsoak"))
        and any(term in lower for term in ("feature", "have", "has", "yet", ".145", "145"))
    )


def is_toolhead_runout_switch_remap_prompt(text):
    lower = text.lower()
    return (
        any(term in lower for term in ("toolhead board", "tool head board", "stock toolhead", "stock tool head", "mcu"))
        and any(term in lower for term in ("runout switch", "filament switch", "filiment switch", "runout sensor"))
        and any(term in lower for term in ("spot", "input", "inpit", "pin", "remap", "map", "immediate stop", "stop filament"))
    )


def is_orca_calibration_image_prompt(text):
    lower = text.lower()
    if is_general_regression_test_bank_prompt(text):
        return False
    if any(term in lower for term in ("stl", "step", "cad", "fusion", "cpap", "cooling duct", "part cooling duct", "wall thickness")) and any(
        term in lower for term in ("design", "designed", "generate", "connect", "routing", "clearance")
    ):
        return False
    calibration_terms = (
        "temperature tower", "temp tower", "max volumetric", "volumetric speed", "volumetric flow", "max flow",
        "pressure advance", "pa tower", "flow ratio", "flow calibration", "retraction", "stringing",
        "cornering", "input shaping", "vfa", "tolerance calibration",
    )
    visual_terms = ("image", "photo", "picture", "attached", "jpeg", "jpg", "png", "result", "what is", "which", "best", "pick", "analyze", "test print")
    return any(term in lower for term in calibration_terms) and any(term in lower for term in visual_terms)


def is_deactivate_venv_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return bool(lower) and len(lower) < 260 and any(term in lower for term in ("get out of .venv", "get out of the .venv", "exit .venv", "deactivate .venv", "get out of venv", "exit venv"))


def is_ratos_pi5_image_port_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("ratos", "rat os"))
        and any(term in lower for term in ("raspberry pi 5", "rasberry pi 5", "pi 5", "pi5"))
        and any(term in lower for term in (".img.xz", ".img", "downloaded", "image"))
        and any(term in lower for term in ("rewrite", "working version", "work on", "create", "modify"))
    )


def is_tinmanx_worldclass_slicer_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return "slicer" in lower and any(term in lower for term in ("world class", "world-class", "elegant engineering", "on track"))


def is_codex_github_full_history_audit_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("github", "git hub"))
        and any(term in lower for term in ("all chats", "all chat", "chat history", "everything we have done", "everything we have ever done"))
        and any(term in lower for term in ("organize", "organise", "audit", "credit", "credits", "source"))
        and any(term in lower for term in ("post", "push", "repo", "repository"))
    )


def is_flightops_aircraft_type_time_owed_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("aircraft type block", "aircraft type field", "aircraft type"))
        and any(term in lower for term in ("time owed", "aircraft time owed", "existing credits", "credits"))
        and any(term in lower for term in ("fix", "edit", "input", "missing"))
    )


def is_blade_crack_opening_quiz_prompt(text):
    lower = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    return (
        any(term in lower for term in ("opening between two adjoining sections of a blade", "opening between two adjoining sections"))
        and all(term in lower for term in ("scratch", "crack", "gouge"))
    )


def is_general_regression_test_bank_prompt(text):
    lower = str(text or "").lower()
    return (
        any(term in lower for term in ("sample questions", "questions to put through the test", "questions to test", "test bank", "question bank", "100 more questions"))
        and any(term in lower for term in ("3d printing", "cnc", "solar", "wind", "aerodynamics", "cfd", "engineering", "aviation"))
        and any(term in lower for term in ("add", "put through the test", "test cases", "test questions", "regression"))
    )


def direct_answer_prompt(text):
    lower = text.lower()
    direct_lead = re.match(
        r"(?i)^(what|which|can you tell|can you confirm|what is the best|how can|how do|do we|do i|did we|should|do you feel|true false|true or false|when i)",
        text,
    )
    known_patterns = (
        is_agent_preference_question_prompt(text),
        is_mac_memory_ai_performance_prompt(text),
        is_wix_email_login_recovery_prompt(text),
        is_wix_credential_recovery_prompt(text),
        is_orca_humidity_as_temperature_prompt(text),
        is_chamber_heaters_disabled_live_test_prompt(text),
        is_github_issue_fixed_status_prompt(text),
        is_printer_cfg_before_proceed_prompt(text),
        is_sense_resistor_manual_install_prompt(text),
        is_api_key_needed_prompt(text),
        is_invar_2020_extrusion_prompt(text),
        is_centauri_carbon_filament_nozzle_report_prompt(text),
        is_ebb42_dual_pt1000_prompt(text),
        is_qidi_box_rfid_spool_speed_prompt(text),
        is_xy_hold_current_regression_prompt(text),
        is_contextless_mapping_correct_prompt(text),
        is_program_restart_needed_context_prompt(text),
        is_offset1059_printer_direct_prompt(text),
        is_offset1059_flightops_direct_prompt(text),
        is_enable_vpn_service_prompt(text),
        is_router_speed_asymmetry_diagnostic_prompt(text),
        is_offset1099_direct_prompt(text),
        is_offset1139_direct_prompt(text),
        is_offset1179_direct_prompt(text),
        is_offset1219_direct_prompt(text),
        is_offset1259_direct_prompt(text),
        is_offset1299_direct_prompt(text),
        is_offset1339_direct_prompt(text),
        is_offset1379_direct_prompt(text),
        is_offset1419_direct_prompt(text),
        is_offset1459_direct_prompt(text),
        is_offset1499_direct_prompt(text),
        is_offset1539_direct_prompt(text),
        is_offset1579_direct_prompt(text),
        is_offset1619_direct_prompt(text),
        is_offset1659_direct_prompt(text),
        is_offset1699_direct_prompt(text),
        is_tool_inventory_visibility_prompt(text),
        is_lan_ip_restoration_context_prompt(text),
        is_lost_ip_sd_card_recovery_prompt(text),
        is_printing_from_slot_three_prompt(text),
        is_offline_knowledge_server_sizing_prompt(text),
        is_general_regression_test_bank_prompt(text),
        is_slicer_profile_update_prompt(text),
        is_orcaslicer_codex_installed_changes_prompt(text),
        is_core_one_l_filament_specific_profile_share_prompt(text),
        is_shared_profile_repo_machine_organization_prompt(text),
        is_makersvpn_reboot_prompt(text),
        is_bluetooth_rename_prompt(text),
        is_hotend_mount_visual_reference_prompt(text),
        is_cad_duct_upward_image_reference_prompt(text),
        is_orca_chamber_before_bed_research_prompt(text),
        is_klipper_restart_prompt(text),
        is_bambu_x1c_nozzle_live_status_prompt(text),
        is_rat_rig_ip_lookup_prompt(text),
        is_chrome_page_screenshot_prompt(text),
        is_fibreseeker_calculation_paper_update_prompt(text),
        is_github_update_with_filament_price_prompt(text),
        is_humidity_hook_reuse_prompt(text),
        is_qidi_filament_width_sensor_location_prompt(text),
        is_qidi_box_ace2_compare_prompt(text),
        is_aviation_life_limited_part_quiz_prompt(text),
        is_k2_plus_profile_pack_setup_prompt(text),
        is_flightops_report_cover_page_numbering_prompt(text),
        is_flightops_pilot_double_booking_blocker_prompt(text),
        is_flightops_flightlog_by_aircraft_prompt(text),
        is_flightops_method1_fuel_daily_rollup_prompt(text),
        is_flightops_pilot_report_pdf_print_prompt(text),
        is_sovol_stainless_gantry_material_prompt(text),
        is_ratos_directory_download_compare_prompt(text),
        is_k2_qidi_box_macro_compare_prompt(text),
        is_klipperscreen_object_visibility_prompt(text),
        is_sovol_filament_profile_expansion_prompt(text),
        is_sovol_spring_idler_belt_tension_prompt(text),
        is_ratrig_initial_speed_accel_settings_prompt(text),
        is_centauri_carbon_name_swap_prompt(text),
        is_ip_changed_missing_target_prompt(text),
        is_printer_aux_output_run_prompt(text),
        is_orca_print_time_disparity_prompt(text),
        is_fk275_belt_cross_reference_prompt(text),
        is_codex_cli_response_time_prompt(text),
        is_cad_cnc_question_list_prompt(text),
        is_adhesive_pot_life_quiz_prompt(text),
        is_aircraft_wood_defect_quiz_prompt(text),
        is_advisory_circular_source_quiz_prompt(text),
        is_lycoming_spark_plug_helicoil_prompt(text),
        is_corrosion_inspection_quiz_prompt(text),
        is_thin_material_corrosion_true_false_prompt(text),
        is_reserve_military_id_location_prompt(text),
        is_mesh_to_step_or_fusion_scale_prompt(text),
        is_mac_airdrop_receive_prompt(text),
        is_where_are_we_status_prompt(text),
        is_filament_load_park_wipe_pad_prompt(text),
        is_printer_reflash_pi_temp_prompt(text),
        is_macro_usage_missing_context_prompt(text),
        is_camera_stepper_motion_check_prompt(text),
        is_thermal_stabilize_reprobe_prompt(text),
        is_petcf_pei_bed_temp_prompt(text),
        is_fiberon_petcf_annealing_prompt(text),
        is_qidi_plus4_usb_wifi_dongle_prompt(text),
        is_rat_rig_macro_folder_save_prompt(text),
        is_qidi_load_unload_speed_match_prompt(text),
        is_qidi_camera_refresh_rate_prompt(text),
        is_max_ez_wlan_followup_prompt(text),
        is_max_ez_process_profile_tuning_prompt(text),
        is_adaptive_heat_soak_status_prompt(text),
        is_he0_light_prompt(text),
        is_router_optimization_login_prompt(text),
        is_router_access_permission_prompt(text),
        is_ssh_extended_firmware_capability_prompt(text),
        is_qidi_max_ez_adaptive_heat_soak_feature_prompt(text),
        is_toolhead_runout_switch_remap_prompt(text),
        is_general_regression_test_bank_prompt(text),
        is_orca_calibration_image_prompt(text),
        is_plateau_terminate_prompt(text),
        is_driver_temps_missing_context_prompt(text),
        is_pump_data_mcu_temp_missing_context_prompt(text),
        is_m3_screw_hole_size_prompt(text),
        is_preview_zoom_controls_prompt(text),
        is_slotted_turbine_hub_modular_design_prompt(text),
        is_rotor_material_mass_prompt(text),
        is_eject_until_box_sensor_unloaded_prompt(text),
        is_eject_target_context_prompt(text),
        is_motion_system_testing_context_prompt(text),
        is_bed_mesh_deviation_quality_prompt(text),
        is_bed_mesh_led_color_macro_prompt(text),
        is_approval_window_workaround_prompt(text),
        is_tinmanx_schedule_status_prompt(text),
        is_simulator_package_quality_prompt(text),
        is_final_nozzle_simulator_prompt(text),
        is_better_design_missing_context_prompt(text),
        is_speaker_pod_cad_prompt(text),
        is_abs_rat_rig_orca_overrides_prompt(text),
        is_rgb_5v_source_prompt(text),
        is_rgb_recheck_prompt(text),
        is_heat_soak_at_print_chamber_temp_prompt(text),
        is_tooth_pitch_valley_depth_missing_profile_prompt(text),
        is_sv08_max_second_rail_gantry_prompt(text),
        is_cm4_ram_size_prompt(text),
        is_slicer_parsing_error_repair_prompt(text),
        is_fibreseek_fiber_amount_location_prompt(text),
        is_coolant_printed_fittings_prompt(text),
        "m191" in lower and "chamber" in lower and any(term in lower for term in ("disable", "turn off", "remove")),
        any(term in lower for term in ("machine start gcode", "machine start g-code", "start gcode", "start g-code"))
        and any(term in lower for term in ("orca", "orcaslicer", "slicer"))
        and any(term in lower for term in ("before the heaters", "before heaters", "heater", "heaters")),
        any(term in lower for term in ("open centauri", "centauri", "centari", "centauri carbon", "centari carbon"))
        and any(term in lower for term in ("orca", "orcaslicer", "orca codex"))
        and any(term in lower for term in ("device tab", "devive tab", "device page"))
        and any(term in lower for term in ("standard klipper", "klipper", "more control", "control")),
        all(term in lower for term in ("openvsp", "xfoil", "su2", "qblade"))
        and any(term in lower for term in ("how do we get", "how do i get", "install", "download", "set up", "setup")),
        any(term in lower for term in ("sid inspection", "sid inspections", "sid"))
        and any(term in lower for term in ("hide", "remove", "disable", "wrapped into", "annual inspection", "annual inspection requirements")),
        any(term in lower for term in ("seyboth", "maule", "fabric punch tester", "fabric punch testers"))
        and any(term in lower for term in ("dacron", "cotton", "linen"))
        and any(term in lower for term in ("not designed", "which", "following")),
        len(lower.strip()) < 80 and any(term in lower for term in ("how do i run the script", "how do we run the script", "run the script")),
        is_dot147_beacon_offset_update_prompt(text),
        is_fusion_solid_removal_prompt(text),
        is_fusion360_capability_prompt(text),
        is_p51_fusion_lockup_prompt(text),
        is_slicer_actual_work_status_prompt(text),
        is_codex_son_self_improvement_prompt(text),
        is_btt_vivd_sensor_prompt(text),
        is_btt_vivd_system_path_prompt(text),
        is_weekly_data_reasoning_level_prompt(text),
        "waiting on my approval" in lower and "alternate tasks" in lower,
        "fibreseek" in lower and "preview" in lower and any(term in lower for term in ("continuous carbon fiber", "continuous carbon fibre", "fortify")),
        "simulator" in lower and any(term in lower for term in ("improve our chances", "chances of success", "chances of sucess")),
        any(term in lower for term in ("+ button", "plus button")) and any(term in lower for term in ("add a file", "add files", "attach", "file picker", "finder", "functional")),
        "turning that on" in lower,
        "configure them" in lower and any(term in lower for term in ("benefit", "benifit", "bennifet")),
        "private jet style ui" in lower or "elegantprivate jet" in lower,
        "pause on that issue" in lower or "pause all the automations" in lower,
        "compute delta" in lower and "mesh" in lower,
        "keep moving forward" in lower,
        any(term in lower for term in ("cyber security risk", "cybersecurity risk", "security risk", "flagged"))
        and any(term in lower for term in ("youtube query", "youtube", "research", "impact our research", "impact the research")),
        any(term in lower for term in ("finish a task", "finishing a task", "task is complete", "task you can", "after finishing", "previous task"))
        and any(term in lower for term in ("start the next task", "start the new task", "move on to the next task", "proceed to the next task", "next task")),
        "trash bin" in lower and "g28" in lower,
        "bowden collet" in lower and "raise the extruder" in lower,
        "new direction" in lower and ("usable app" in lower or "useable app" in lower),
        "tools to complete the job" in lower and "not change the response" in lower,
        "starlink" in lower and "change" in lower and "ip" in lower,
        "advanced functions" in lower and ("not sure what all is available" in lower or "mean time" in lower or "meantime" in lower),
        is_camera_stepper_motion_check_prompt(text),
        is_eject_until_box_sensor_unloaded_prompt(text),
        is_filament_eject_live_action_prompt(text),
        is_btt_sfs_false_motion_code_prompt(text),
        "off the shelf generator" in lower and "meets your needs" in lower,
        "design a prop" in lower and ("pps-cf" in lower or "8 blade" in lower),
        "add them to our calculations" in lower and lower.count("http") >= 2,
        lower.strip() in {"please proceed", "proceed"},
        bool(re.search(r"^(?:lets|let's)\s+move\s+forward\s+with\s+all\s+your\s+recom?m?endations\.?$", lower.strip())),
        any(term in lower for term in ("filament buffer", "buffer"))
        and any(term in lower for term in ("bind", "binding"))
        and any(term in lower for term in ("motor speed", "feeder", "compensate", "adjust")),
        "machine testing" in lower and "estimate" in lower,
        "orca codex integration" in lower and "proceed" in lower,
        "model is added" in lower and "build plate" in lower,
        ("rasberry pi 5" in lower or "raspberry pi 5" in lower) and ("32gb ram" in lower or "32 gb ram" in lower),
        "all commands" in lower and "copy" in lower and ("box" in lower or "code block" in lower),
        "sv08 max" in lower and "graphite bed" in lower,
        "line by line" in lower and "first time" in lower,
        "fuel location" in lower and "departure" in lower and "destination" in lower and "upper" in lower,
        "flight log" in lower and "add that" in lower,
        "ipv4" in lower and "ipv6" in lower and "faster" in lower,
        is_save_settings_no_button_prompt(text),
        lower.strip() in {"lets find the ip", "let's find the ip"},
        "cnc lab" in lower and "personalize" in lower,
        "approve" in lower and "workflow" in lower and "stop" in lower,
        "firmware update" in lower and "box" in lower,
        "access panel" in lower and any(term in lower for term in ("structural integrity", "fuselage", "canopy")),
        "same warning" in lower and "cache" in lower,
        any(term in lower for term in ("chamber fan", "corculation", "circulation")) and any(term in lower for term in ("uniformly heated", "optimal location", "where")),
        any(term in lower for term in ("tested and proven", "test and prove", "proven to work")) and any(term in lower for term in ("publish", "release", "share")),
        is_professional_output_label_prompt(text),
        "no filament loaded" in lower and any(term in lower for term in ("start a print", "test the system", "appropriat")),
        "error while connecting" in lower and any(term in lower for term in ("webcam", "snapshot")),
        any(term in lower for term in ("dgx spark", "server next to the dgx", "store all data")) and any(term in lower for term in ("farming", "engineering", "survive", "internet")),
        "dual beacon" in lower and "next step" in lower,
        any(term in lower for term in ("home internet", "internet isnt working", "internet isn't working")) and any(term in lower for term in ("router", "modem", "nighthawk")),
        "arc support" in lower and any(term in lower for term in ("not block", "dont block", "don't block", "experimental")),
        "brake pad" in lower and any(term in lower for term in ("part number", "shim", "isolator")),
        any(term in lower for term in ("dont ask permission", "don't ask permission", "do not ask permission")),
        "fusion" in lower and any(term in lower for term in ("sketch", "scetch")) and any(term in lower for term in ("repositions", "reposition", "make this stop")),
        (not is_tinmanx_schedule_status_prompt(text))
        and (not is_tinmanx_average_completion_time_prompt(text))
        and (
            any(term in lower for term in ("how are we doing", "updated completion time", "completion time"))
            or (re.search(r"\beta\b", lower) is not None and any(term in lower for term in ("updated", "completion", "time", "estimate")))
        ),
        len(lower.strip()) < 90 and "short" in lower and any(term in lower for term in ("still showing", "showing a short", "show a short", "is it still", "does it still")),
        len(lower.strip()) < 160 and "inverted" in lower and any(term in lower for term in ("they are", "they're", "what they should be", "fix it")),
        any(term in lower for term in ("start over", "run this on top", "on top of what i already have")),
        any(term in lower for term in ("amelia air", "amelia osprey"))
        and any(term in lower for term in ("flight logs", "all entries", "all references", "all fields", "databases", "database", "replace", "remove", "reverted", "change all")),
        "user presets" in lower and any(term in lower for term in ("option 2", "clean up", "cleanup")),
        "access level" in lower and "reasoning level" in lower and any(term in lower for term in ("chat window", "bottom")),
        "dragon" in lower and any(term in lower for term in ("water", "watter")) and any(term in lower for term in ("fitting", "thread", "barb", "nipple")),
        "orca codex" in lower and "bambu" in lower and any(term in lower for term in ("plug in", "plugin", "connect")),
        any(term in lower for term in ("1/16 npt", "1/16-npt")) and any(term in lower for term in ("drill", "tap", "hole", "mm")),
        any(term in lower for term in ("cost", "price")) and any(term in lower for term in ("power consumption", "power draw", "watts")) and "recommendation" in lower,
        "graphite" in lower and "aluminum" in lower and any(term in lower for term in ("heat faster", "heat soak", "shorten")),
        any(term in lower for term in ("vx 175", "vx-175", "vx175")) and "wind turbine" in lower,
        "rotor" in lower and any(term in lower for term in ("optimized", "optimised")),
        "propeller" in lower and "lightning" in lower and any(term in lower for term in ("burned", "melted", "residual magnetism", "deep gouge")),
        any(term in lower for term in ("which profile do you want me to run", "which profile should i run")),
        "orca logs" in lower and any(term in lower for term in ("print time estimate", "slicer estimate", "disparity")),
        "octoapp" in lower and "octoeverywhere" in lower and any(term in lower for term in ("same server", "new url", "add octoprint")),
        any(term in lower for term in ("screenshot of fusion", "take a screenshot of fusion", "screenshot fusion", "fusion screenshot")),
        "device page" in lower and (len(text) > 300 or "\ufffd" in text),
        is_fusion_solid_removal_prompt(text),
        "extrude" in lower and any(term in lower for term in ("non planar", "non-planar", "non flat", "non-flat", "surface", "to object")),
        lower.strip() in {"how is the ui coming?", "how is the ui coming", "how is codex cli ui coming?", "how is codex cli ui coming"},
        any(term in lower for term in ("improve his performance", "improve performance")) and any(term in lower for term in ("before we package", "before packaging", "package it", "packaging")),
        "retraction" in lower and "stringing" in lower,
        "orca" in lower and "hat" in lower and any(term in lower for term in ("smaller", "scale", "wearing", "wear")),
        any(term in lower for term in ("clear the fault", "clear fault", "clear any faults")) and any(term in lower for term in ("unload", "eject", "before we start", "restart")),
        any(term in lower for term in ("t0", "toolhead 0")) and any(term in lower for term in ("t1", "toolhead 1")) and "beacon" in lower and any(term in lower for term in ("swap", "beacon id", "mcu id", "different results", "different toolheads")),
        any(term in lower for term in ("sync user presets", "user presets warning", "sync preset", "preset warning")),
        "logo" in lower and any(term in lower for term in ("website", "site", "web app", "page")) and any(term in lower for term in ("darker", "dark feel", "dark theme", "little darker")),
        is_document_compliance_review_prompt(text),
        is_no_filament_loaded_test_prompt(text),
        any(term in lower for term in ("strength", "strenght")) and any(term in lower for term in ("fibreseeker", "fiberseeker", "fibreseek", "fiberseek")),
        any(term in lower for term in ("true. false", "true or false", "true false")) and "introduce" in lower and "confrontation" in lower,
        is_network_moved_ip_scan_prompt(text),
        re.search(r"\bn\d{3,5}[a-z]{0,2}\b", lower) is not None and any(term in lower for term in ("on condition", "n/a", "not applicable")) and "status block" in lower,
        any(term in lower for term in ("this is perfect", "exactly what i wanted")) and any(term in lower for term in ("next move", "next step")),
        any(term in lower for term in ("list of the features", "feature list", "features we are incorporating")) and any(term in lower for term in ("same page", "make sure", "confirm", "just to")),
        any(term in lower for term in ("youtube", "youtu.be")) and "transcript" in lower and any(term in lower for term in ("tinmanx", "settings", "workflow", "strength", "research")),
        "m191" in lower and "chamber" in lower and any(term in lower for term in ("disable", "turn off", "remove")),
        any(term in lower for term in ("where are we at", "where are we", "status")) and any(term in lower for term in ("arc support", "arc supports")),
        any(term in lower for term in ("front right", "front-right")) and any(term in lower for term in ("plan view", "overhead", "homing", "home")) and any(term in lower for term in ("z tilt", "z-tilt", "z_tilt")),
        any(term in lower for term in ("storage", "system data", "running out of storage")) and any(term in lower for term in ("where this is coming from", "majority is system data", "look at my storage", "running out of storage")),
        any(term in lower for term in ("rocket slicer", "rocketslicer")) and any(term in lower for term in ("pc", "polycarbonate")) and any(term in lower for term in ("plastic profile", "material profile", "filament profile", "add a")),
        any(term in lower for term in ("xy distance", "x/y distance")) and any(term in lower for term in ("feed", "feedrate", "feed rate")) and any(term in lower for term in ("overlapping", "overlap", "ui")),
        any(term in lower for term in ("smooth air diverter", "smooth air diverters", "spinner")) and any(term in lower for term in ("rotor", "airflow", "collector", "bell diffuser", "diffuser")),
    )
    return bool(direct_lead or any(known_patterns))


def required_terms_for_prompt(text, project_id=""):
    lower = text.lower()
    required = []
    cpap_hose_spec = "cpap hose" in lower and any(term in lower for term in ("inner diameter", "id", "inside diameter"))
    if is_agent_preference_question_prompt(text):
        required.extend(["this is why", "you should also consider", "preference"])
    if is_mac_memory_ai_performance_prompt(text):
        required.extend(["This is why", "You should also consider", "unified memory", "AI"])
    if is_wix_email_login_recovery_prompt(text):
        required.extend(["this is why", "you should also consider", "Mail", "Keychain", "https://www.wix.com/forgot-password"])
    if is_wix_credential_recovery_prompt(text):
        required.extend(["this is why", "you should also consider", "Wix", "Keychain", "Safari Passwords", "Chrome Password Manager", "https://www.wix.com/forgot-password"])
    if is_orca_humidity_as_temperature_prompt(text):
        required.extend(["this is why", "you should also consider", "humidity", "temperature-style", "heater logic"])
    if is_chamber_heaters_disabled_live_test_prompt(text):
        required.extend(["this is why", "you should also consider", "idle", "bed/nozzle", "chamber heaters disabled"])
    if is_github_issue_fixed_status_prompt(text):
        required.extend(["this is why", "you should also consider", "current", "GitHub", "workflow"])
    if is_printer_cfg_before_proceed_prompt(text):
        required.extend(["this is why", "you should also consider", "printer.cfg", "backup", "Klipper"])
    if is_sense_resistor_manual_install_prompt(text):
        required.extend(["this is why", "you should also consider", "sense resistor", "board revision", "schematic"])
    if is_api_key_needed_prompt(text):
        required.extend(["this is why", "you should also consider", "local", "Ollama", "external service"])
    if is_invar_2020_extrusion_prompt(text):
        required.extend(["this is why", "you should also consider", "Invar", "2020 extrusion", "source-backed"])
    if is_centauri_carbon_filament_nozzle_report_prompt(text):
        required.extend(["this is why", "you should also consider", "Centauri Carbon", "filament", "nozzle size"])
    if is_ebb42_dual_pt1000_prompt(text):
        required.extend(["this is why", "you should also consider", "EBB42", "PT1000", "one external thermistor"])
    if is_qidi_box_rfid_spool_speed_prompt(text):
        required.extend(["this is why", "you should also consider", "Qidi Box", "RFID", "RPM"])
    if is_xy_hold_current_regression_prompt(text):
        required.extend(["this is why", "you should also consider", "X/Y", "hold_current", "endstop"])
    if is_contextless_mapping_correct_prompt(text):
        required.extend(["this is why", "you should also consider", "mapping", "context"])
    if is_program_restart_needed_context_prompt(text):
        required.extend(["this is why", "you should also consider", "restart", "program"])
    if is_offset1059_printer_direct_prompt(text):
        required.extend(["this is why", "you should also consider"])
    if is_offset1059_flightops_direct_prompt(text):
        required.extend(["this is why", "you should also consider"])
    if is_enable_vpn_service_prompt(text) or is_router_speed_asymmetry_diagnostic_prompt(text):
        required.extend(["this is why", "you should also consider"])
    if is_offset1099_direct_prompt(text):
        required.extend(["this is why", "you should also consider"])
    if is_offset1139_direct_prompt(text):
        required.extend(["this is why", "you should also consider"])
    if is_offset1179_direct_prompt(text):
        required.extend(["this is why", "you should also consider"])
    if is_offset1219_direct_prompt(text):
        required.extend(["this is why", "you should also consider"])
    if is_tool_inventory_visibility_prompt(text):
        required.extend(["commands", "apps", "inventory", "refresh"])
    if is_lan_ip_restoration_context_prompt(text):
        required.extend(["IP", "device", "DHCP", "ARP"])
    if is_makersvpn_reboot_prompt(text):
        required.extend(["MakersVPN", "reboot", "Tailscale"])
    if is_bluetooth_rename_prompt(text):
        required.extend(["Bluetooth", "requested name"])
    if is_hotend_mount_visual_reference_prompt(text):
        required.extend(["hotend", "mount", "carriage", "http"])
    if is_cad_duct_upward_image_reference_prompt(text):
        required.extend(["upward", "flat", "CAD"])
    if is_rat_rig_ip_lookup_prompt(text):
        required.extend(["192.0.2.27", "Rat Rig"])
    if is_lost_ip_sd_card_recovery_prompt(text):
        required.extend(["SD card", "backup", "Wi-Fi", "DHCP"])
    if is_printing_from_slot_three_prompt(text):
        required.extend(["slot 3", "filament", "profile"])
    if is_offline_knowledge_server_sizing_prompt(text):
        required.extend(["TB", "curated", "ZFS", "index"])
    if is_centauri_carbon_name_swap_prompt(text):
        required.extend(["profile", "host", "UI"])
    if is_ip_changed_missing_target_prompt(text):
        required.extend(["IP", "device", "ARP", "mDNS"])
    if is_orca_print_time_disparity_prompt(text):
        required.extend(["Orca logs", "G-code", "machine limits"])
    if is_fk275_belt_cross_reference_prompt(text):
        required.extend(["FK275", "belt", "profile"])
    if is_codex_cli_response_time_prompt(text):
        required.extend(["This is why", "You should also consider", "model", "context"])
    if is_router_access_permission_prompt(text):
        required.extend(["This is why", "You should also consider", "permission", "backup", "passwords"])
    if is_general_regression_test_bank_prompt(text):
        required.extend(["This is why", "You should also consider", "test bank", "golden", "/api/run", "package health"])
    if is_slicer_profile_update_prompt(text):
        required.extend(["This is why", "You should also consider", "profile", "backup", "visibility"])
    if is_orcaslicer_codex_installed_changes_prompt(text):
        required.extend(["This is why", "You should also consider", "installed app", "profile store", "package health"])
    if is_core_one_l_filament_specific_profile_share_prompt(text):
        required.extend(["This is why", "You should also consider", "Core One L", "machine", "filament", "GitHub"])
    if is_shared_profile_repo_machine_organization_prompt(text):
        required.extend(["This is why", "You should also consider", "Qidi", "Sovol", "manifest", "privacy"])
    if is_plateau_terminate_prompt(text):
        required.extend(["This is why", "You should also consider", "terminate", "stopping point"])
    if is_driver_temps_missing_context_prompt(text):
        required.extend(["This is why", "You should also consider", "driver", "Moonraker"])
    if is_pump_data_mcu_temp_missing_context_prompt(text):
        required.extend(["This is why", "You should also consider", "pump", "MCU", "Moonraker"])
    if is_petcf_pei_bed_temp_prompt(text):
        required.extend(["This is why", "You should also consider", "80 C", "PET-CF"])
    if is_fiberon_petcf_annealing_prompt(text):
        required.extend(["This is why", "You should also consider", "coupon", "80 C"])
    if is_printer_aux_output_run_prompt(text):
        required.extend(["This is why", "You should also consider", "idle", "Klipper", "SET_FAN_SPEED", "SET_PIN"])
    if is_qidi_plus4_usb_wifi_dongle_prompt(text):
        required.extend(["This is why", "You should also consider", "USB Wi-Fi dongle", "lsusb", "ip link", "Moonraker"])
    if is_rat_rig_macro_folder_save_prompt(text):
        required.extend(["This is why", "You should also consider", "Rat Rig", "macro", "Klipper", "validation"])
    if is_qidi_load_unload_speed_match_prompt(text):
        required.extend(["This is why", "You should also consider", "load", "unload", "max_extrude_only_velocity", "backup"])
    if is_qidi_camera_refresh_rate_prompt(text):
        required.extend(["This is why", "You should also consider", "camera", "FPS", "service", "UI verification"])
    if is_max_ez_wlan_followup_prompt(text):
        required.extend(["This is why", "You should also consider", "wlan1", "Moonraker"])
    if is_max_ez_process_profile_tuning_prompt(text):
        required.extend(["This is why", "You should also consider", "Max EZ", "profile"])
    if is_adaptive_heat_soak_status_prompt(text):
        required.extend(["This is why", "You should also consider", "adaptive", "PRINT_START"])
    if is_cad_cnc_question_list_prompt(text):
        required.extend(["CAD questions", "CNC machining questions", "engineering how-to"])
    if is_adhesive_pot_life_quiz_prompt(text):
        required.extend(["Pot life", "working life", "cure time"])
    if is_lycoming_spark_plug_helicoil_prompt(text):
        if "kit" in lower or "for sale" in lower:
            required.extend(["ATS 4260-18", "aviation", "generic M18", "Lycoming"])
        else:
            required.extend(["18 mm", ".010", "P/N 64596-1", "manual"])
    if is_corrosion_inspection_quiz_prompt(text):
        required.extend(["C. It must be removed", "corrosion", "service limits"])
    if is_thin_material_corrosion_true_false_prompt(text):
        required.extend(["True", "0.0625", "mechanical tools", "service limits"])
    if is_reserve_military_id_location_prompt(text):
        required.extend(["RAPIDS", "Robins"])
    if is_mesh_to_step_or_fusion_scale_prompt(text):
        required.extend(["mesh", "scale", "Fusion"])
    if is_mac_airdrop_receive_prompt(text):
        required.extend(["AirDrop", "Wi-Fi", "Bluetooth"])
    if is_where_are_we_status_prompt(text):
        required.extend(["active project", "next step"])
    if is_filament_load_park_wipe_pad_prompt(text):
        required.extend(["5 mm", "wipe pad", "cold moves"])
    if is_m3_screw_hole_size_prompt(text):
        required.extend(["3.2 mm", "2.5 mm", "tap drill"])
    if is_config_pin_comments_prompt(text):
        required.extend(["PA8 # Fan 0", "PD14 # Fan 4", "config"])
    if is_fan_output_mapping_prompt(text):
        required.extend(["Fan 4", "PD14", "chamber2_fan", "config"])
    if is_generator_candidate_context_prompt(text):
        required.extend(["300 RPM", "60 VDC", "https://www.ebay.com/itm/376862815958"])
    if is_inverter_three_phase_input_prompt(text):
        required.extend(["do not feed", "split-phase", "three-phase"])
    if is_outdoor_continuous_fiber_fan_material_prompt(text):
        required.extend(["ASA", "PCTG", "94 mm", "1000 RPM", "https://"])
    if is_inserted_filament_switch_state_prompt(text):
        required.extend(["present", "filament_detected", "pin"])
    if is_orca_codex_vs_tinmanx_strategy_prompt(text):
        required.extend(["Orca Codex", "TinManX", "FibreSeeker", "verification"])
    if is_orca_codex_wrong_build_prompt(text):
        required.extend(["Orca Codex", "TinmanX", "verification"])
    if is_slicer_parsing_error_repair_prompt(text):
        required.extend(["archive", "active app", "aliases", "verify"])
    if is_engineering_filament_cost_prompt(text):
        required.extend(["PPS-CF", "$", "kg", "current"])
    if is_eject_until_box_sensor_unloaded_prompt(text):
        required.extend(["controlled", "sensor", "unloaded", "jam"])
    if is_controller_fan_airflow_prompt(text):
        required.extend(["blow", "MCU", "exhaust"])
    if is_core_one_l_calibration_prompt(text):
        required.extend(["Core One L", "idle", "calibration", "profile"])
    if any(term in lower for term in ("prusa ui", "prusa machine", "on the machine", "machine when i load it")) and any(
        term in lower for term in ("codex filaments", "orca codex", "filament")
    ):
        required.extend(["Prusa-compatible", "Orca Codex", "UI"])
    if is_tailscale_ssh_definition_prompt(text):
        required.extend(["Tailscale", "SSH", "remote shell"])
    if is_rocket_slicer_machine_data_prompt(text):
        required.extend(["Rocket", "G-code header", "differential harness"])
    if is_preview_zoom_controls_prompt(text):
        required.extend(["zoom in", "zoom out", "reset-to-fit"])
    if is_slotted_turbine_hub_modular_design_prompt(text):
        required.extend(["one-piece hub", "separate blades", "300 mm", "positive"])
    if is_rotor_material_mass_prompt(text):
        required.extend(["ASA-CF", "infill", "mass", "startup torque"])
    if is_eject_target_context_prompt(text):
        required.extend(["volume", "device", "diskutil"])
    if is_motion_system_testing_context_prompt(text):
        required.extend(["motion-system", "target printer", "idle", "small movement"])
    if is_bed_mesh_deviation_quality_prompt(text):
        required.extend(["good", "bed-mesh", "0.20-0.30 mm", "first layer"])
    if is_bed_mesh_led_color_macro_prompt(text):
        required.extend(["SET_LED", "BED_MESH_CALIBRATE", "G28", "Z_TILT_ADJUST"])
    if is_pt6_icing_itt_prompt(text):
        required.extend(["PT6", "ITT", "icing", "torque", "AFM"])
    if any(term in lower for term in ("single pole single throw", "spst")) and any(term in lower for term in ("lightbulb", "light bulb", "bulb", "lamp")):
        required.extend(["SPST", "series", "3-way"])
    if is_codex_personality_settings_prompt(text):
        required.extend(["Humor", "Friendliness", "persist", "safety"])
    if is_t0_t1_beacon_visibility_prompt(text):
        required.extend(["T0", "T1", "Beacon", "Klipper", "toolhead"])
    if is_filament_path_diagram_prompt(text):
        required.extend(["filament-path block diagram", "ViVD Filament Path To Toolhead", "Path validation quick check", "sensor", "motion"])
    if is_btt_vivd_system_path_prompt(text):
        required.extend(["BTT ViVD", "official", "bench-test", "firmware", "slicer"])
    if is_cm4_vs_pi5_prompt(text):
        required.extend(["CM4", "Pi 5", "eMMC", "bench"])
    if is_cm4_ram_size_prompt(text):
        required.extend(["4 GB", "2 GB", "8 GB", "eMMC"])
    if is_dot147_beacon_offset_update_prompt(text):
        required.extend([".147", "Beacon", "backup", "config check"])
    if is_fusion_all_designs_script_prompt(text):
        required.extend(["Fusion 360 Python script", "source files", "folder path", ".f3d"])
    if is_fusion360_capability_prompt(text):
        required.extend(["Fusion 360-ready", ".f3d", ".f3z"])
    if is_p51_fusion_lockup_prompt(text):
        required.extend(["Fusion", "file", "healed STEP"])
    if is_fusion_solid_removal_prompt(text):
        required.extend(["Fusion", "Combine", "Split Body", "Keep Tools"])
    if "fusion" in lower and any(term in lower for term in ("directory", "folder", "path")) and any(term in lower for term in ("file", "files", "output", "saved")):
        required.extend(["Fusion", "directory"])
    if is_slicer_actual_work_status_prompt(text):
        required.extend(["actual slicer work", "credit/attribution", "verified"])
    if is_fibreseek_fiber_amount_location_prompt(text):
        required.extend(["fiber/process", "Fiber Amount", "preview", "fiber-usage"])
    if is_codex_son_self_improvement_prompt(text):
        required.extend(["closed-loop", "regression", "safety"])
    if is_weekly_data_reasoning_level_prompt(text):
        required.extend(["medium", "auto-escalate", "completion time"])
    if is_source_credit_short_prompt(text):
        required.extend(["source ledger", "credit", "license"])
    artifact_or_change = any(term in lower for term in ARTIFACT_OR_CHANGE_TERMS)
    if not artifact_or_change and (direct_answer_prompt(text) or any(term in lower for term in ("best", "recommend", "should i", "what is the best"))):
        required.extend(["this is why", "you should also consider"])
    if "waiting on my approval" in lower and "alternate tasks" in lower:
        required.append("progress log")
    if "fibreseek" in lower and "preview" in lower:
        required.append("continuous")
    if "simulator" in lower and any(term in lower for term in ("improve our chances", "chances of success", "chances of sucess")):
        required.append("preflight")
    if "turning that on" in lower:
        required.append("toggle")
    if any(term in lower for term in ("cyber security risk", "cybersecurity risk", "security risk", "flagged")) and any(
        term in lower for term in ("youtube query", "youtube", "research", "impact our research", "impact the research")
    ):
        required.extend(["source-bounded", "approval", "raw transcript"])
    if "configure them" in lower:
        required.append("refers")
    if "private jet style ui" in lower or "elegantprivate jet" in lower:
        required.append("screenshot")
    if "pause all the automations" in lower:
        required.append("automation")
    if "compute delta" in lower and "mesh" in lower:
        required.append("delta")
    if "trash bin" in lower and "g28" in lower:
        required.append("g28")
    if "keep moving forward" in lower:
        required.append("active project")
    if any(term in lower for term in ("finish a task", "finishing a task", "task is complete", "task you can", "after finishing", "previous task", "previous one")) and any(
        term in lower for term in ("start the next task", "start the next tasks", "start the new task", "move on to the next task", "proceed to the next task", "next task", "next tasks")
    ):
        required.extend(["continue", "pause"])
    if "bowden collet" in lower and "raise the extruder" in lower:
        required.append("collet")
    if "new direction" in lower and ("usable app" in lower or "useable app" in lower):
        required.append("acceptance")
    if "tools to complete the job" in lower and "not change the response" in lower:
        required.append("capability")
    if "starlink" in lower and "ip" in lower:
        required.append("bypass")
    if "advanced functions" in lower and ("not sure what all is available" in lower or "mean time" in lower or "meantime" in lower):
        required.append("capability")
    if is_camera_stepper_motion_check_prompt(text):
        required.extend(["camera", "position", "single-axis"])
    if is_thermal_stabilize_reprobe_prompt(text):
        required.extend(["45 C chamber", "100 C bed", "180 C nozzle", "G28"])
    if is_filament_eject_live_action_prompt(text):
        required.extend(["idle", "unload temperature", "target printer"])
    if is_btt_sfs_false_motion_code_prompt(text):
        required.extend(["BTT SFS 2.0", "filament_motion_sensor", "switch_pin", "detection_length"])
    if "off the shelf generator" in lower and "meets your needs" in lower:
        required.append("rpm")
    if "design a prop" in lower and ("pps-cf" in lower or "8 blade" in lower):
        required.append("rpm")
    if "add them to our calculations" in lower and lower.count("http") >= 2:
        required.append("calculation")
    if lower.strip() in {"please proceed", "proceed"} or re.search(r"^(?:lets|let's)\s+move\s+forward\s+with\s+all\s+your\s+recom?m?endations\.?$", lower.strip()):
        required.append("active task")
    if any(term in lower for term in ("filament buffer", "buffer")) and any(term in lower for term in ("bind", "binding")) and any(term in lower for term in ("motor speed", "feeder", "compensate", "adjust")):
        required.extend(["sensor", "timeout"])
    if "machine testing" in lower and "estimate" in lower:
        required.append("acceptance")
    if "orca codex integration" in lower and "proceed" in lower:
        required.append("integration")
    if "model is added" in lower and "build plate" in lower:
        required.append("plate")
    if ("rasberry pi 5" in lower or "raspberry pi 5" in lower) and ("32gb ram" in lower or "32 gb ram" in lower):
        required.append("16 gb")
    if "all commands" in lower and "copy" in lower and ("box" in lower or "code block" in lower):
        required.append("code block")
    if "sv08 max" in lower and "graphite bed" in lower:
        required.append("sv08 max")
    if "line by line" in lower and "first time" in lower:
        required.append("line by line")
    if "fuel location" in lower and "departure" in lower and "destination" in lower and "upper" in lower:
        required.append("uppercase")
    if "flight log" in lower and "add that" in lower:
        required.append("flight log")
    if "ipv4" in lower and "ipv6" in lower and "faster" in lower:
        required.append("protocol")
    if lower.strip() in {"lets find the ip", "let's find the ip"}:
        required.append("device")
    if "cnc lab" in lower and "personalize" in lower:
        required.append("Tinman's CNC Lab")
    if "approve" in lower and "workflow" in lower and "stop" in lower:
        required.append("approval")
    if "firmware update" in lower and "box" in lower:
        required.append("version")
    if "access panel" in lower and any(term in lower for term in ("structural integrity", "fuselage", "canopy")):
        required.append("doubler")
    if "same warning" in lower and "cache" in lower:
        required.append("cache")
    if any(term in lower for term in ("chamber fan", "corculation", "circulation")) and any(term in lower for term in ("uniformly heated", "optimal location", "where")):
        required.append("circulation")
    if any(term in lower for term in ("tested and proven", "test and prove", "proven to work")) and any(term in lower for term in ("publish", "release", "share")):
        required.append("acceptance")
    if is_professional_output_label_prompt(text):
        required.append("Vevor")
    if is_save_settings_no_button_prompt(text):
        required.extend(["autosave", "preset", "verify"])
    if "no filament loaded" in lower and any(term in lower for term in ("start a print", "test the system", "appropriat")):
        required.append("runout")
    if "error while connecting" in lower and any(term in lower for term in ("webcam", "snapshot")):
        required.append("snapshot")
    if any(term in lower for term in ("dgx spark", "server next to the dgx", "store all data")) and any(term in lower for term in ("farming", "engineering", "survive", "internet")):
        required.append("TB")
    if "dual beacon" in lower and "next step" in lower:
        required.append("Beacon")
    if any(term in lower for term in ("home internet", "internet isnt working", "internet isn't working")) and any(term in lower for term in ("router", "modem", "nighthawk")):
        required.append("WAN")
    if "arc support" in lower and any(term in lower for term in ("not block", "dont block", "don't block", "experimental")):
        required.append("experimental")
    if "brake pad" in lower and any(term in lower for term in ("part number", "shim", "isolator")):
        required.append("make")
    if any(term in lower for term in ("dont ask permission", "don't ask permission", "do not ask permission")):
        required.append("risk")
    if "fusion" in lower and any(term in lower for term in ("sketch", "scetch")) and any(term in lower for term in ("repositions", "reposition", "make this stop")):
        required.append("Auto look at sketch")
    if is_approval_window_workaround_prompt(text):
        required.extend(["continue", "pause", "verify"])
    if is_tinmanx_average_completion_time_prompt(text):
        required.extend(["36-hour", "completed", "blocked"])
    elif is_tinmanx_schedule_status_prompt(text):
        required.extend(["TinManX", "package health", "conditional"])
    elif (
        not is_tinmanx_schedule_status_prompt(text)
        and not is_tinmanx_average_completion_time_prompt(text)
        and not is_weekly_data_reasoning_level_prompt(text)
    ) and (
        any(term in lower for term in ("how are we doing", "updated completion time", "completion time"))
        or (re.search(r"\beta\b", lower) is not None and any(term in lower for term in ("updated", "completion", "time", "estimate")))
    ):
        required.append("specific project")
    if len(lower.strip()) < 90 and "short" in lower and any(term in lower for term in ("still showing", "showing a short", "show a short", "is it still", "does it still")):
        required.extend(["short", "meter", "power"])
    if len(lower.strip()) < 160 and "inverted" in lower and any(term in lower for term in ("they are", "they're", "what they should be", "fix it")):
        required.extend(["inverted", "they"])
    if any(term in lower for term in ("start over", "run this on top", "on top of what i already have")):
        required.append("specific task")
    if any(term in lower for term in ("amelia air", "amelia osprey")) and any(term in lower for term in ("flight logs", "all entries", "all references", "all fields", "databases", "database", "replace", "remove", "reverted", "change all")):
        required.extend(["Amelia Osprey", "backup", "database"])
    if "user presets" in lower and any(term in lower for term in ("option 2", "clean up", "cleanup")):
        required.append("backup")
    if "access level" in lower and "reasoning level" in lower and any(term in lower for term in ("chat window", "bottom")):
        required.append("Full Access")
    if "dragon" in lower and any(term in lower for term in ("water", "watter")) and any(term in lower for term in ("fitting", "thread", "barb", "nipple")):
        required.append("M5")
    if "orca codex" in lower and "bambu" in lower and any(term in lower for term in ("plug in", "plugin", "connect")):
        required.append("Bambu Connect")
    if any(term in lower for term in ("1/16 npt", "1/16-npt")) and any(term in lower for term in ("drill", "tap", "hole", "mm")):
        required.append("5.95")
    if any(term in lower for term in ("cost", "price")) and any(term in lower for term in ("power consumption", "power draw", "watts")) and "recommendation" in lower:
        required.append("specific")
    if "graphite" in lower and "aluminum" in lower and any(term in lower for term in ("heat faster", "heat soak", "shorten")):
        required.append("uniform")
    if any(term in lower for term in ("vx 175", "vx-175", "vx175")) and "wind turbine" in lower:
        required.append("scale")
    if "rotor" in lower and any(term in lower for term in ("optimized", "optimised")):
        required.append("latest")
    if "propeller" in lower and "lightning" in lower and any(term in lower for term in ("burned", "melted", "residual magnetism", "deep gouge")):
        required.append("Answer: A")
    if any(term in lower for term in ("which profile do you want me to run", "which profile should i run")):
        required.append("printer")
    if "orca logs" in lower and any(term in lower for term in ("print time estimate", "slicer estimate", "disparity")):
        required.append("machine limits")
    if "octoapp" in lower and "octoeverywhere" in lower and any(term in lower for term in ("same server", "new url", "add octoprint")):
        required.append("new server")
    if any(term in lower for term in ("+ button", "plus button")) and any(term in lower for term in ("add a file", "add files", "attach", "file picker", "finder", "functional")):
        required.append("file picker")
    if "layer_wipe_disable" in lower:
        required.append("wipe")
    if any(term in lower for term in ("skate board bearing", "skateboard bearing", "skate bearing")):
        required.append("8 mm")
    if any(term in lower for term in ("guest network", "guest wifi", "guest ssid")) and any(term in lower for term in ("health check", "system", "network check", "scan")):
        required.append("guest")
    if any(term in lower for term in ("ga hotline", "general aviation", "tsoc", "transportation security operations center")) and any(term in lower for term in ("true. false", "true or false", "true false")):
        required.append("True")
    if any(term in lower for term in ("arc support", "arc supports")) and any(term in lower for term in ("deep dive", "research", "get arc supports working", "working")):
        required.append("support")
    if "filament profile" in lower and any(term in lower for term in ("create", "make", "generate", "build", "write")) and any(term in lower for term in ("nozzle", "printer", "core one", "pakv", "fila matrix")):
        required.append("filament")
    if is_apus_mounting_hole_design_prompt(text):
        required.extend(["Apus", "m3", "countersunk", "flush", "Dragon", "separate"])
    if any(term in lower for term in ("3d-fuel", "3dfuel", "3d fuel")) and any(term in lower for term in ("pctg-cf", "pctg cf")):
        required.extend(["3D-Fuel", "PCTG-CF", "profile"])
    if is_coolant_printed_fittings_prompt(text):
        required.extend(["this is why", "you should also consider", "distilled water", "PETG", "pressure-test"])
    if any(term in lower for term in ("which he pins", "what he pins", "he pins did we go", "he pin did we go")) and any(term in lower for term in ("external hot end fan", "external hotend fan", "hot end fan", "hotend fan", "fan")):
        required.append("HE2")
    if any(term in lower for term in ("cfc path", "continuous fiber", "continuous-fiber")) and any(term in lower for term in ("center hole", "lower openings", "upper 2 openings", "alternating layer", "alternating layers")):
        required.append("alternating")
    if "pmc.ncbi.nlm.nih.gov/articles/" in lower and any(term in lower for term in ("anything valid", "could use", "use?", "review", "impliment", "implement")):
        required.extend(["paper", "FibreSeeker"])
    if any(term in lower for term in ("heat soak", "heat-soak")) and any(term in lower for term in ("chamber temp", "chamber temperature", "chamber")) and any(
        term in lower for term in ("50 degrees", "50 c", "50c", "50")
    ):
        required.extend(["50", "chamber", "M191"])
    if is_printer_reflash_pi_temp_prompt(text):
        required.extend(["backup", "known-good", "vcgencmd", "electronics-bay", "Moonraker"])
    if any(term in lower for term in ("start print macro", "start_print", "print_start")) and any(term in lower for term in ("heat soak", "adaptive bed mesh", "contact probe", "z home", "chamber", "bed temp")):
        required.append("Macro file")
    if any(term in lower for term in ("machine_start_gcode", "machine start gcode", "machine start g-code", "custom start gcode", "custom start g-code", "start code")) and any(
        term in lower for term in ("print_start", "print_start_bed", "hotend", "chamber temp", "chamber")
    ):
        required.extend(["PRINT_START", "BED", "HOTEND", "CHAMBER"])
    if any(term in lower for term in ("working version of orca slicer", "correct version of orcaslicer", "correct version of orca")) and any(term in lower for term in ("arc fittings", "arc support", "wave overhang", "strength lens", "fibreseeker", "fiberseeker", "continuous carbon fiber")):
        required.append("working OrcaSlicer")
    if is_tinmanx_wave_overhang_generate_now_prompt(text):
        required.extend(["preview", "G-code", "test print"])
    elif is_functional_wave_overhang_generator_prompt(text):
        required.extend(["wave-overhang generator", "preview", "G-code", "test print"])
    if any(term in lower for term in ("zoom in and out", "zoom in/out", "zoom controls", "zoom function")) and "preview" in lower:
        required.append("zoom")
    if any(term in lower for term in ("rocket slicer", "rocketslicer")) and any(term in lower for term in ("machine gates", "physical machine", "delayed", "testing before hand", "testing beforehand")):
        required.extend(["machine gates", "G-code", "tester"])
    if is_rocket_fiber_placement_verification_prompt(text):
        required.extend(["Rocket", "same layer", "G-code", "sidecar"])
    if any(term in lower for term in ("different box", "separate box", "different code block", "separate code block")) and any(term in lower for term in ("each command", "uach command", "commands", "one at a time")):
        required.append("code block")
    if "custom filament profiles" in lower and any(term in lower for term in ("part cooling", "fan settings", "cooling settings", "same thing")):
        required.append("part-cooling")
    if "custom filament profiles" in lower and any(term in lower for term in ("process profile", "process profiles", "make", "create", "generate")):
        required.extend(["profile pack", "Matrix", "calibration"])
    if any(term in lower for term in ("tinneyaviation.com", "tinney aviation")) and any(term in lower for term in ("data", "lost", "losing", "not saving", "disappearing")):
        required.append("data-persistence")
    if is_flightops_tinneyaviation_login_tabs_prompt(text):
        required.extend(["Customer Login", "Pilot Login", "Flight Ops Tracker", "https://www.tinneyaviation.com/"])
    if is_propeller_exhaust_rounding_prompt(text):
        required.extend(["rounding the exhaust", "propeller", "exit area", "blade clearance"])
    if "retraction" in lower and "stringing" in lower:
        required.append("retraction")
    if "orca" in lower and "hat" in lower and any(term in lower for term in ("smaller", "scale", "wearing", "wear")):
        required.append("hat")
    if any(term in lower for term in ("clear the fault", "clear fault", "clear any faults")) and any(term in lower for term in ("unload", "eject", "before we start", "restart")):
        required.append("idle")
    if any(term in lower for term in ("t0", "toolhead 0")) and any(term in lower for term in ("t1", "toolhead 1")) and "beacon" in lower and any(term in lower for term in ("swap", "beacon id", "mcu id", "different results", "different toolheads")):
        required.append("No")
    if any(term in lower for term in ("sync user presets", "user presets warning", "sync preset", "preset warning")):
        required.append("preset")
    if "logo" in lower and any(term in lower for term in ("website", "site", "web app", "page")) and any(term in lower for term in ("darker", "dark feel", "dark theme", "little darker")):
        required.append("logo")
    if is_document_compliance_review_prompt(text):
        required.append("document")
    if is_no_filament_loaded_test_prompt(text):
        required.append("runout")
    if any(term in lower for term in ("strength", "strenght")) and any(term in lower for term in ("fibreseeker", "fiberseeker", "fibreseek", "fiberseek")):
        required.append("groundwork")
    if any(term in lower for term in ("true. false", "true or false", "true false")) and "introduce" in lower and "confrontation" in lower:
        required.append("True")
    if is_network_moved_ip_scan_prompt(text):
        required.append("subnet")
    if re.search(r"\bn\d{3,5}[a-z]{0,2}\b", lower) and any(term in lower for term in ("on condition", "n/a", "not applicable")) and "status block" in lower:
        required.append("On Condition")
    if any(term in lower for term in ("this is perfect", "exactly what i wanted")) and any(term in lower for term in ("next move", "next step")):
        required.append("verify")
    if any(term in lower for term in ("list of the features", "feature list", "features we are incorporating")) and any(term in lower for term in ("same page", "make sure", "confirm", "just to")):
        required.append("project")
    if any(term in lower for term in ("youtube", "youtu.be")) and "transcript" in lower and any(term in lower for term in ("tinmanx", "settings", "workflow", "strength", "research")):
        required.append("transcripts")
    if "m191" in lower and "chamber" in lower and any(term in lower for term in ("disable", "turn off", "remove")):
        required.append("M191")
    if is_orca_chamber_before_bed_research_prompt(text):
        required.extend(["M191", "PRINT_START", "http"])
    if any(term in lower for term in ("where are we at", "where are we", "status")) and any(term in lower for term in ("arc support", "arc supports")):
        required.append("Arc Supports")
    if any(term in lower for term in ("front right", "front-right")) and any(term in lower for term in ("plan view", "overhead", "homing", "home")) and any(term in lower for term in ("z tilt", "z-tilt", "z_tilt")):
        required.append("X/Y")
    if any(term in lower for term in ("storage", "system data", "running out of storage")) and any(term in lower for term in ("where this is coming from", "majority is system data", "look at my storage", "running out of storage")):
        required.append("System Data")
    if any(term in lower for term in ("rocket slicer", "rocketslicer")) and any(term in lower for term in ("pc", "polycarbonate")) and any(term in lower for term in ("plastic profile", "material profile", "filament profile", "add a")):
        required.append("polycarbonate")
    if any(term in lower for term in ("xy distance", "x/y distance")) and any(term in lower for term in ("feed", "feedrate", "feed rate")) and any(term in lower for term in ("overlapping", "overlap", "ui")):
        required.append("UI")
    if any(term in lower for term in ("smooth air diverter", "smooth air diverters", "spinner")) and any(term in lower for term in ("rotor", "airflow", "collector", "bell diffuser", "diffuser")):
        required.append("diverter")
    if any(term in lower for term in ("screenshot of fusion", "take a screenshot of fusion", "screenshot fusion", "fusion screenshot")):
        required.append("Fusion")
    if "device page" in lower and (len(text) > 300 or "\ufffd" in text):
        required.append("Content-Type")
    if is_fusion_solid_removal_prompt(text):
        required.extend(["Combine", "Split Body"])
    if "extrude" in lower and any(term in lower for term in ("non planar", "non-planar", "non flat", "non-flat", "surface", "to object")):
        required.append("To Object")
    if is_cad_repair_before_return_prompt(text):
        required.extend(["repaired geometry", "exact blocker", "validation"])
    if lower.strip() in {"how is the ui coming?", "how is the ui coming", "how is codex cli ui coming?", "how is codex cli ui coming"}:
        required.append("package health")
    if any(term in lower for term in ("improve his performance", "improve performance")) and any(term in lower for term in ("before we package", "before packaging", "package it", "packaging")):
        required.append("package health")
    if project_id == "tinmanx-slicer-research" and ("filament" in lower or "temp tower" in lower):
        required.append("filament")
    if "marlin" in lower:
        required.append("marlin")
    if "klipper" in lower:
        required.append("klipper")
    if "fusion" in lower and not cpap_hose_spec:
        required.append("fusion")
    if "cfd" in lower:
        required.append("cfd")
    local_website_design = "logo" in lower and any(term in lower for term in ("website", "site", "web app", "page")) and any(term in lower for term in ("darker", "dark feel", "dark theme", "little darker"))
    local_wix_url_plan = "wix" in lower and any(term in lower for term in ("branding of the urls", "brand the urls", "branding urls", "url branding"))
    if (("web" in lower and not local_website_design and not local_wix_url_plan) or "price" in lower or "availability" in lower):
        required.append("http")
    return list(dict.fromkeys(required))[:6]


def golden_test_from_prompt(prompt, source):
    prompt = compact(redact(prompt), MAX_PROMPT_CHARS)
    lower = prompt.lower()
    project_id = project_for_prompt(prompt)
    context_dependent = is_context_dependent_prompt(prompt)
    needs_web = web_needed(prompt)
    test = {
        "id": test_id_for_prompt(prompt),
        "name": compact(prompt, 58),
        "group": "Slow",
        "prompt": prompt,
        "profile": "manager",
        "managerDepth": "fast",
        "webSearch": "live" if needs_web else "disabled",
        "expectedProjectId": project_id,
        "directAnswer": bool(context_dependent or direct_answer_prompt(prompt)),
        "directTerms": [],
        "requiredTerms": required_terms_for_prompt(prompt, project_id=project_id),
        "anyTerms": [],
        "forbiddenTerms": BASE_FORBIDDEN_TERMS,
        "requiresSource": bool(needs_web),
        "goal": "Real chat-history regression: answer Tinman's actual prompt without cold fallback, wrong routing, or fake completion.",
        "source": "history-harvest",
        "historySource": source,
        "qualityScore": quality_score(prompt),
        "createdAt": time.time(),
        "updatedAt": time.time(),
    }
    if is_agent_preference_question_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Codex"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "preference"], limit=8)
        test["requiredContractProof"] = ["direct answer", "why/caveat shape"]
        test["anyTerms"] = normalize_terms(["Codex", "Red Codex", "Red"], limit=6)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer agent naming/preference questions conversationally and directly instead of routing to Local Research."
    if is_mac_memory_ai_performance_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Mac memory upgrade local facts"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["No internal memory upgrade"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "unified memory", "AI"], limit=8)
        test["requiredContractProof"] = ["local hardware profile", "unified memory", "no internal memory upgrade", "AI performance"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer Mac memory and AI-performance questions from this Mac's local hardware profile instead of generic research."
    if is_flightops_tinneyaviation_login_tabs_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops public-site login tabs"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Customer Login", "Pilot Login"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "https://www.tinneyaviation.com/"], limit=8)
        test["requiredContractProof"] = ["https://www.tinneyaviation.com/", "Customer Login", "Pilot Login", "Flight Ops Tracker", "role-based"]
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer Tinney Aviation login-tab integration directly with source URL and Flight Ops role/auth boundary."
    if is_deactivate_venv_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Shell virtualenv exit"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["deactivate"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "deactivate", ".venv"], limit=8)
        test["requiredContractProof"] = ["deactivate", "(.venv)", "new shell fallback"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 70
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: shell virtualenv-exit questions should answer directly and fast, even when pasted from a project terminal prompt."
    if is_ratos_pi5_image_port_prompt(prompt):
        test["expectedProjectId"] = "embedded-linux-images"
        test["expectedContractKind"] = "Embedded/Linux image port"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = False
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "RatOS", "Pi 5", "candidate"], limit=8)
        test["requiredContractProof"] = ["source image", "storage", "Pi 5 builder", "candidate image", "boot-tested"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 74
        test["goal"] = "Real chat-history regression: RatOS Pi 5 image-port tasks require local image/build proof, not public source URLs or CAD artifacts."
    if is_codex_github_full_history_audit_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex full-history GitHub audit"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "locally first"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "GitHub", "attribution", "privacy", "package health"], limit=10)
        test["requiredContractProof"] = ["local staging", "redact secrets", "attribution", "package health", "push approval"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: all-history GitHub/audit requests should be concise, local-staged, attribution/privacy-aware, and push-gated."
    if is_flightops_aircraft_type_time_owed_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops aircraft metadata/credit edit"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Flight Ops"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "aircraft type", "time owed", "admin"], limit=8)
        test["requiredContractProof"] = ["aircraft type", "time owed", "admin edit", "existing credits", "verification"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Flight Ops aircraft type/time-owed requests should answer as a scoped app feature fix, not time out."
    if is_blade_crack_opening_quiz_prompt(prompt):
        test["expectedContractKind"] = "Aviation maintenance quiz"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["B", "Crack"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "crack", "scratch", "gouge"], limit=8)
        test["requiredContractProof"] = ["B. Crack", "opening or split", "scratch", "gouge"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 90
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: aircraft/blade quiz prompts should answer directly and fast without research or CAD detours."
    if is_flightops_scoped_feature_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops scoped feature change"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
        test["requiredContractProof"] = ["Flight Ops", "feature", "UI/data surface", "verification"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: small Flight Ops feature requests should get a direct scoped app-change answer, not a slow open-ended worker path."
    if is_slicer_filament_manufacturer_tab_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Slicer filament vendor preset"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Codex"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "slicer", "filament", "dropdown"], limit=8)
        test["requiredContractProof"] = ["Codex vendor/manufacturer", "filament preset library", "dropdown", "installed app visibility"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: slicer filament manufacturer requests belong to vendor preset/profile libraries, not Klipper config."
    if is_mainsail_ssh_password_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Mainsail SSH password boundary"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["no", "Usually no", "Mainsail"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Mainsail", "SSH"], limit=8)
        test["requiredContractProof"] = ["Mainsail", "Linux SSH", "password not exposed", "reset or SSH key"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Mainsail SSH-password questions should answer the security boundary directly and safely."
    if is_pi_restart_safety_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Printer-host Pi restart safety"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "idle"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "restart", "Pi"], limit=8)
        test["requiredContractProof"] = ["idle", "heaters", "Moonraker", "Klipper", "UI"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: simple Pi restart questions should answer quickly with printer idle/heater safety gates."
    if is_adaptive_heat_soak_broad_design_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Adaptive heat-soak mesh-stability macro"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "state-aware"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "heat soak", "recent history", "stability"], limit=8)
        test["requiredContractProof"] = ["bed/chamber targets", "60-second mesh loop", "mesh delta", "completion threshold", "Klipper macro/status basis"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: broad adaptive heat-soak design prompts should return a state-machine design answer, not a slow source-hunting detour."
    if is_github_share_all_work_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "GitHub public sharing plan"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "curated"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "GitHub", "redaction", "package health"], limit=8)
        test["requiredContractProof"] = ["curated public repository", "redaction", "attribution", "package health", "push approval"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: GitHub sharing requests should be curated, redacted, attribution-aware, and push-gated."
    if is_ssh_logs_instead_guessing_prompt(prompt):
        test["expectedContractKind"] = "SSH log evidence request"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "SSH"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "SSH", "logs", "target"], limit=8)
        test["requiredContractProof"] = ["SSH", "logs", "target host", "read-only", "not guessing"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: SSH/log requests should prefer evidence over guessing while preserving target/reachability safety."
    if is_prusa_api_key_ssh_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Prusa API key SSH lookup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Prusa"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Prusa", "API key", "SSH"], limit=8)
        test["requiredContractProof"] = ["Prusa", "API key", "SSH", "credential", "redacted or local storage"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Prusa API-key lookup requests should use SSH/config evidence and avoid inventing or exposing credentials."
    if is_image_edit_missing_source_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Image edit needs source file"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "need"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "image", "file"], limit=8)
        test["requiredContractProof"] = ["actual image file", "edited image", "source path", "visual check"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: image-edit placeholders should ask for the source file plainly and never claim a fake edit."
    if is_prusa_klipper_conversion_research_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Prusa-to-Klipper conversion research"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Prusa"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Prusa", "Klipper"], limit=8)
        test["requiredContractProof"] = ["Prusa", "Klipper", "community conversions", "board/pin map", "rollback"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Prusa-to-Klipper research should answer existence and safety boundaries directly, not produce unverified artifact work."
    if is_prusa_core_one_profiles_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Prusa Core One profile setup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Prusa Core One"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Prusa", "profile", "calibration", "https://"], limit=8)
        test["requiredContractProof"] = ["Prusa Core One", "Core One L HF", "official Prusa profile", "calibration"]
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Prusa Core One profile setup should use official baseline profiles and calibration gates without routing to generic research."
    if is_flightops_customer_users_database_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops customer/user database audit"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Flight Ops"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "customers", "users", "database"], limit=8)
        test["requiredContractProof"] = ["customers", "users", "database backup", "customer-to-user link", "Users page query"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: customer/user database mismatch prompts should explain the table/view distinction and backup-first audit path."
    if is_aircraft_tool_supply_promo_code_prompt(prompt):
        test["expectedProjectId"] = "research-parts-reference"
        test["expectedContractKind"] = "Aircraft tool promo-code lookup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["promo", "volatile"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "promo", "supplier"], limit=8)
        test["requiredContractProof"] = ["promo code", "volatile", "supplier site", "newsletter", "sales quote"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: promo-code requests should be concise, volatile-aware, and source/cart/sales-check oriented."
    if is_tailscale_credentials_login_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Tailscale credential safety"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["not expose", "Tailscale"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Tailscale", "auth"], limit=8)
        test["requiredContractProof"] = ["Tailscale", "credentials", "tailscale status", "auth flow", "auth key"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Tailscale credential requests should protect secrets and offer status/auth-flow steps."
    if is_spreadsheet_landscape_due_format_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Spreadsheet one-page due-format rules"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "spreadsheet"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "landscape", "green", "yellow", "red"], limit=8)
        test["requiredContractProof"] = ["landscape", "one page", "green/yellow/red", "report date", "print preview"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: spreadsheet format requests should summarize the page/date/color rules directly and verify print preview."
    if is_flightops_maintenance_reserve_title_hide_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops maintenance-reserve report visibility"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "maintenance reserve"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "title page", "fixed cost"], limit=8)
        test["requiredContractProof"] = ["maintenance reserve", "title page", "total fixed cost", "report-only", "PDF verification"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Flight Ops maintenance-reserve visibility changes should be report-only, non-destructive, and fast."
    if is_centauri_cosmos_firmware_upgrade_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Centauri Cosmos firmware upgrade decision"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["recommendation", "Cosmos"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "firmware", "rollback"], limit=8)
        test["requiredContractProof"] = ["Centauri Carbon", "Cosmos", "release notes", "backup", "rollback"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Centauri Cosmos firmware questions should answer upgrade risk/reward with backup and rollback gates."
    if is_sovol_mainline_klipper_migration_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Sovol mainline Klipper migration"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Sovol"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Sovol", "mainline Klipper", "backup"], limit=8)
        test["requiredContractProof"] = ["Sovol", "mainline Klipper", "backup", "MCU/pin map", "rollback"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Sovol mainline Klipper migration prompts should summarize migration difficulty and validation gates, not time out."
    if is_box_rfid_macros_check_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "RFID box macro enablement check"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "RFID"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "RFID", "macro"], limit=8)
        test["requiredContractProof"] = ["box macros", "RFID", "receiver/service", "read-only", "Klipper restart caveat"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: RFID box macro checks should inspect macro/service readiness before enabling anything."
    if is_zoffset_calibration_probe_log_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Z-offset calibration log diagnostic"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["log", "Z-offset"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Nozzle not hot enough", "probe"], limit=8)
        test["requiredContractProof"] = ["probe more than ten times", "Nozzle not hot enough", "Z-offset", "converge", "do not rerun blindly"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: pasted Z-offset logs should be diagnosed directly without rerun-blindly advice."
    if is_ratrig_belt_cheatsheet_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Rat Rig belt-adjustment cheat sheet"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Rat Rig"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "CoreXY", "T0", "T1"], limit=8)
        test["requiredContractProof"] = ["Rat Rig", "CoreXY", "X/Y sign", "T0/T1", "upper/lower"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Rat Rig belt cheat-sheet prompts should explain coupled CoreXY/IDEX sign mapping and verification."
    if is_sv08_petgcf_temp_recall_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "SV08 Max PETG-CF temp recall"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["80 C", "45 C"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "PETG-CF", "SV08 Max"], limit=8)
        test["requiredContractProof"] = ["80 C bed", "45 C chamber", "PETG-CF", "SV08 Max", "profile verification"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: SV08 PETG-CF temp recalls should answer bed/chamber targets and profile verification directly."
    if is_pdf_to_excel_hobbs_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "PDF to Excel Hobbs workbook"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Excel"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "PDF", "formulas", "Hobbs"], limit=8)
        test["requiredContractProof"] = ["PDF values", "Excel workbook", "formulas", "remaining", "Hobbs"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: PDF-to-Excel Hobbs requests should answer the workbook/formula deliverable directly and fast."
    if is_ratrig_belt_frequency_chamber_inop_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Rat Rig belt frequency safe calibration"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "chamber heaters"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "belt frequency", "chamber heaters", "inop"], limit=8)
        test["requiredContractProof"] = ["Rat Rig", "belt frequency", "chamber heaters inop", "do not use", "interpret data"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Rat Rig belt-frequency requests must preserve chamber-heater-inop safety and data interpretation."
    if is_stop_current_print_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Live print cancel safety"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "CANCEL_PRINT"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "CANCEL_PRINT", "printer"], limit=8)
        test["requiredContractProof"] = ["CANCEL_PRINT", "target printer", "live-machine", "heaters", "Moonraker"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: stop-current-print requests should answer via safe cancel macro/endpoints, not generic or blind service-kill paths."
    if is_klipper_modifications_github_prep_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Klipper modifications GitHub prep"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "dual Z probe"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Klipper", "credits", "GitHub"], limit=8)
        test["requiredContractProof"] = ["dual Z probe", "credits", "changes and advantages", "local diff", "push approval"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Klipper GitHub prep should package locally with credits/change notes and wait for push approval."
    if is_qidi_nozzle_temp_access_feedback_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi live nozzle status access lesson"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Qidi", "Moonraker"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Qidi Plus 4", "Moonraker", "VPN"], limit=8)
        test["requiredContractProof"] = ["Qidi Plus 4", "Moonraker", "VPN", "nozzle actual/target", "exact blocker"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Qidi nozzle-temp feedback should demand endpoint attempts or exact blockers, not generic no-access replies."
    if is_qidi_toolhead_beacon_health_mesh_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi toolhead/Beacon health check"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Qidi", "Beacon"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Qidi", "Beacon", "bed mesh", "idle"], limit=8)
        test["requiredContractProof"] = ["Qidi", "Beacon", "bed mesh", "idle", "saved mesh or exact blocker"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Qidi toolhead/Beacon recovery should use live-printer safety gates before any bed mesh."
    if is_orca_codex_blank_ip_host_mapping_prompt(prompt):
        test["expectedProjectId"] = "orcaslicer-codex"
        test["expectedContractKind"] = "OrcaSlicer Codex host-mapping repair"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Orca Codex", "host mapping"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Orca Codex", "Snapmaker", "Qidi Plus 4", "restart"], limit=8)
        test["requiredContractProof"] = ["Orca Codex", "host mapping", "Snapmaker", "Qidi Plus 4", "survive restart"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: blank Orca Codex printer IPs should be treated as host-mapping persistence repair."
    if is_qidi_profiles_shaper_tuning_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi profile tuning from shaper calibration"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "input shaper"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Qidi", "input shaper", "backup"], limit=8)
        test["requiredContractProof"] = ["Qidi profiles", "input shaper", "backup", "acceleration", "validation"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Qidi profile tuning after shaper calibration should be backup-first and validation driven."
    if is_github_filament_process_update_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "GitHub filament/process profile update"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "filament"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "GitHub", "profiles", "push approval"], limit=8)
        test["requiredContractProof"] = ["filament profiles", "process profiles", "profile linter", "installed-app visibility", "push approval"]
        test["requiresSource"] = True
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: GitHub filament/process update requests should stage and verify profiles locally before any approved push."
    if is_qidi_chamber_heater_cap_verify_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi chamber-heater 40 percent cap verification"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Qidi"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "40 percent", "0.4", "config"], limit=8)
        test["requiredContractProof"] = ["Qidi", "chamber heater", "40 percent", "max_power: 0.4", "read-only config"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Qidi chamber-heater cap checks should inspect config and macro limits before any live heater action."
    if is_youtube_video_analysis_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "YouTube video analysis source workflow"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "video"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "YouTube", "transcript", "source"], limit=8)
        test["requiredContractProof"] = ["YouTube", "video ID or URL", "transcript", "source URL", "metadata"]
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: YouTube-video requests should extract or request the direct video source and use transcript/metadata evidence."
    if is_codex_cli_ui_more_like_codex_combo_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex CLI UI creation architecture"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Codex CLI UI"]
        test["requiredTerms"] = normalize_terms(["sidebar", "chat bar", "attachments", "clickable outputs", "steer", "verify"], limit=8)
        test["requiredContractProof"] = ["standalone macOS app", "sidebar/projects/chats", "chat bar controls", "attachments", "clickable outputs", "steer", "verification gates"]
        test["requiresSource"] = True
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: side-by-side Codex UI feedback should produce package-level architecture, controls, and verification gates."
    if is_klipper_beacon_comments_closed_next_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper Beacon closed-comments next step"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Next", "Klipper"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Klipper", "Beacon", "source URL"], limit=8)
        test["requiredContractProof"] = ["Klipper", "Beacon", "new issue", "discussion", "fork", "logs/config", "source URL"]
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: closed Klipper Beacon repo comments should return a concise support/contribution next path, not time out."
    if is_orca_codex_pakv_restart_prompt(prompt):
        test["expectedProjectId"] = "orcaslicer-codex"
        test["expectedContractKind"] = "Orca profile visibility refresh"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "restart"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Orca Codex", "PAKV", "filament"], limit=8)
        test["requiredContractProof"] = ["Orca Codex", "PAKV", "restart or refresh", "filament preset visibility"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: local Orca Codex profile-visibility questions should answer restart/refresh directly, not route to research."
    if is_github_publish_signup_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "GitHub publish account requirement"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "GitHub"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "GitHub", "account", "https://"], limit=8)
        test["requiredContractProof"] = ["GitHub account", "publish repository", "source URL"]
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: GitHub publishing/account questions should answer directly with a source URL and Codex package boundary."
    if is_klipper_change_effect_status_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper change-scope status"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Not unless", "Klipper"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Rat Rig", "Klipper"], limit=8)
        test["requiredContractProof"] = ["Rat Rig", "Klipper", "local app/profile versus live printer config", "verification path"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Klipper change-scope follow-ups should answer directly and not demand code artifacts."
    if is_printer_selection_ui_cleanup_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Printer selection UI cleanup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "bottom"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "upper-left", "bottom", "printer"], limit=8)
        test["requiredContractProof"] = ["upper-left printer selection box", "bottom printer box", "preserve layout", "UI cleanup"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: duplicate printer-selector UI requests should acknowledge the intended UI cleanup instead of routing to CAD."
    if is_cf_polymer_hotend_mount_material_compare_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "CF polymer hot-end mount material comparison"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["PPA-CF", "PCTG-CF"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Qidi Plus 4", "hot-end mount", "PPA-CF", "PCTG-CF"], limit=8)
        test["requiredContractProof"] = ["PPA-CF", "PCTG-CF", "hot-end mount", "heat resistance", "creep", "drying", "metal insert"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: PCTG-CF versus PPA-CF hot-end-mount comparisons should make a clear material recommendation."
    if is_website_design_before_migration_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Website design-before-migration update"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "website"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "preview", "rollback", "migration", "http"], limit=8)
        test["requiredContractProof"] = ["current website", "backup", "staging", "preview URL", "rollback", "migration"]
        test["requiresSource"] = True
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: website design-before-migration requests should update via staged preview and rollback proof, not route to CAD."
    if is_filament_input_pin_compare_remote_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Remote filament input pin comparison"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "filament"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "TinmanCC", "TinmanCC2", "switch_pin", "Moonraker"], limit=8)
        test["requiredContractProof"] = ["TinmanCC", "TinmanCC2", "filament_detected", "QUERY_FILAMENT_SENSOR", "switch_pin", "read-only", "Moonraker"]
        test["requiresSource"] = True
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: remote filament-input pin comparisons should use read-only Klipper/Moonraker state and config proof."
    if is_aircraft_water_drain_true_false_prompt(prompt):
        test["expectedProjectId"] = "aviation-engineering"
        test["expectedContractKind"] = "Aircraft water-drain true/false"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["True"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "aircraft", "water", "corrosion"], limit=8)
        test["requiredContractProof"] = ["True", "aircraft", "water", "drain", "corrosion", "freezing"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: aircraft maintenance true/false questions should answer directly as aviation knowledge, not CAD or Flight Ops app work."
    if is_flightops_work_organized_status_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops organization status"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Flight Ops"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Flight Ops Tracker", "organized"], limit=8)
        test["requiredContractProof"] = ["Flight Ops Tracker", "organized", "project", "repo", "production", "smoke tests"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Flight Ops organization-status questions should answer the project boundary directly and fast."
    if is_propeller_exhaust_rounding_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Propeller exhaust rounding judgment"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "rounding the exhaust"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "exit area", "blade clearance"], limit=8)
        test["requiredContractProof"] = ["rounding the exhaust", "propeller", "exit area", "blade clearance", "CFD or test"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer propeller exhaust-rounding image prompts as concise aero judgment, not a slow generic runbook."
    if context_dependent:
        test["contextDependent"] = True
        test["webSearch"] = "disabled"
        test["requiresSource"] = False
        test["requiredTerms"] = []
        test["anyTerms"] = normalize_terms(
            ["context", "detail", "specific", "which", "what task", "earlier", "refers to", "project", "active project", "last run", "last result", "target", "warning text", "source of truth"],
            limit=14,
        )
        test["goal"] = "Context-only history follow-up: ask for or recover the missing context instead of inventing a task."
        if "still working" in lower and any(term in lower for term in ("are you", "you still", "still working on this")):
            test["expectedProjectId"] = "codex-cli-ui-local-agent"
            test["expectedContractKind"] = "Work status context"
            test["expectedContractGate"] = "pass"
            test["contextDependent"] = False
            test["directAnswer"] = True
            test["directTerms"] = ["Yes", "still working"]
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "checkpoint", "next"], limit=8)
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["requiredContractProof"] = ["still working/status statement", "checkpoint or next step"]
            test["goal"] = "Real chat-history regression: answer status nudges with a short checkpoint/next-step heartbeat instead of treating them as missing context."
        if re.fullmatch(r"(?:let'?s|lets)\s+go(?:\s+my\s+brother)?[.!? ]*", prompt.lower().strip()):
            test["expectedProjectId"] = "general"
            test["expectedContractKind"] = "Encouragement handoff"
            test["expectedContractGate"] = "pass"
            test["directTerms"] = ["Let's go"]
            test["anyTerms"] = normalize_terms(["next target", "Tinman"], limit=4)
            test["goal"] = "Context-only encouragement: acknowledge momentum and ask for the next target instead of inventing hidden prior work."
        if re.fullmatch(r"(?:let'?s|lets)\s+turn\s+it\s+off[.!? ]*", prompt.lower().strip()):
            test["expectedProjectId"] = "general"
            test["expectedContractKind"] = "Direct answer"
            test["expectedContractGate"] = "pass"
            test["contextDependent"] = False
            test["directAnswer"] = True
            test["directTerms"] = ["I can turn it off", "what `it` refers to"]
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "safe", "target"], limit=8)
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["maxDurationMs"] = 750
            test["goal"] = "Real chat-history regression: answer contextless turn-off commands instantly with a safe target request instead of a slow generic model response."
        if re.fullmatch(r"(?:let'?s|lets)\s+restart\s+it\s+(?:now|now\s+then|then)(?:\s+please)?[.!? ]*", prompt.lower().strip()):
            test["expectedProjectId"] = "general"
            test["expectedContractKind"] = "Direct answer"
            test["expectedContractGate"] = "pass"
            test["contextDependent"] = False
            test["directAnswer"] = True
            test["directTerms"] = ["I can restart it", "exact target"]
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "idle", "target"], limit=8)
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["maxDurationMs"] = 750
            test["goal"] = "Real chat-history regression: answer contextless restart commands instantly with a safe target request instead of a slow generic model response."
    else:
        test["minAnalyticalScore"] = 74
    if is_wix_email_login_recovery_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Wix email login recovery"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Wix", "Keychain"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Mail", "Keychain", "https://www.wix.com/forgot-password"], limit=8)
        test["requiredContractProof"] = ["Wix", "Mail/Spotlight", "Keychain", "https://www.wix.com/forgot-password", "raw passwords"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Wix login recovery/email-search requests with a safe local-search/account-recovery workflow instead of timing out."
    if is_wix_credential_recovery_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Credential-safe Wix access recovery"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Wix", "raw passwords"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Keychain", "Safari Passwords", "Chrome Password Manager", "https://www.wix.com/forgot-password"], limit=8)
        test["requiredContractProof"] = ["Wix", "Keychain", "Safari Passwords", "Chrome Password Manager", "https://www.wix.com/forgot-password", "raw passwords"]
        test["forbiddenTerms"] = normalize_terms(["paste your password", "I logged in", "I accessed the website", "here is your password"], limit=8)
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer Wix password/access lookup requests with a safe local credential/account-recovery workflow instead of generic refusal or web research."
    if is_orca_humidity_as_temperature_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca humidity display workaround"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "humidity", "temperature-style", "heater logic"], limit=8)
        test["requiredContractProof"] = ["humidity", "temperature-style field", "read-only", "heater logic boundary"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Orca humidity-display workaround questions without live humidity/status hijack."
    if is_chamber_heaters_disabled_live_test_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Chamber-disabled bed/nozzle test"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "idle", "bed/nozzle", "chamber heaters disabled", "SET_HEATER_TEMPERATURE"], limit=8)
        test["requiredContractProof"] = ["idle", "bed/nozzle", "chamber heaters disabled", "SET_HEATER_TEMPERATURE or UI"]
        test["forbiddenTerms"] = normalize_terms(["objects/query?heater_bed,target", "read-only query endpoint"], limit=8)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer chamber-disabled bed/nozzle live tests with safe heater-control gates."
    if is_github_issue_fixed_status_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "GitHub issue status needs evidence"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "current", "GitHub", "workflow"], limit=8)
        test["requiredContractProof"] = ["GitHub issue", "current repo/workflow evidence", "do not claim fixed from memory"]
        test["forbiddenTerms"] = normalize_terms(["was merged", "commit `", "pull the latest code"], limit=8)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: status questions about GitHub issues must require current evidence instead of hallucinating a PR."
    if is_printer_cfg_before_proceed_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper printer.cfg proceed gate"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "printer.cfg", "backup", "Klipper"], limit=8)
        test["requiredContractProof"] = ["printer.cfg", "backup", "Klipper restart/config check", "idle"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: printer.cfg proceed questions answer conditionally with backup/restart gates."
    if is_sense_resistor_manual_install_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Sense resistor install boundary"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "sense resistor", "board revision", "schematic"], limit=8)
        test["requiredContractProof"] = ["sense resistor", "board revision", "schematic/BOM", "do not solder blindly"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: sense-resistor questions avoid guessed resistor values and require exact board evidence."
    if is_api_key_needed_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Local API key boundary"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "local", "Ollama", "external service"], limit=8)
        test["requiredContractProof"] = ["local Ollama", "API key", "external service", "Keychain or environment"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: API-key questions distinguish local free mode from external services."
    if is_invar_2020_extrusion_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Invar 2020 extrusion source boundary"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Invar", "2020 extrusion", "source-backed"], limit=8)
        test["requiredContractProof"] = ["Invar", "2020 extrusion", "custom or source-backed", "Rat Rig gantry"]
        test["forbiddenTerms"] = normalize_terms(["McMaster", "Sutherland", "standard lengths are"], limit=8)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Invar extrusion questions avoid invented suppliers and demand current source proof."
    if is_centauri_carbon_filament_nozzle_report_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Centauri filament/nozzle telemetry boundary"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Centauri Carbon", "filament", "nozzle size"], limit=8)
        test["requiredContractProof"] = ["Centauri Carbon", "filament", "nozzle size", "profile or API"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Centauri report questions route to printer telemetry/profile boundaries, not Flight Ops."
    if is_ebb42_dual_pt1000_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "EBB42 dual PT1000 boundary"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "EBB42", "PT1000", "one external thermistor"], limit=8)
        test["requiredContractProof"] = ["EBB42 Gen 2", "PT1000", "one external thermistor interface", "second input/expansion"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: EBB42 PT1000 capability questions answer directly instead of timing out."
    if is_qidi_box_rfid_spool_speed_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi Box RFID spool-speed feasibility"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Qidi Box", "RFID", "RPM"], limit=8)
        test["requiredContractProof"] = ["Qidi Box", "RFID", "RPM", "spool speed", "validation"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Qidi Box RFID spool-speed ideas are answered analytically instead of live Moonraker status checks."
    if is_xy_hold_current_regression_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper X/Y hold-current motion diagnostic"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "X/Y", "hold_current", "endstop", "STEPPER_BUZZ"], limit=8)
        test["requiredContractProof"] = ["X/Y motor mapping", "endstop/homing direction", "run_current/hold_current", "safe jog or STEPPER_BUZZ"]
        test["forbiddenTerms"] = normalize_terms(["linear-regression", "market data", "LuxAlgo", "Medium posts", "stock-market"], limit=8)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: X/Y hold-current regression language is printer motion diagnostics, not web statistical regression."
    if is_contextless_mapping_correct_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Contextless mapping follow-up"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "mapping", "context"], limit=8)
        test["requiredContractProof"] = ["not enough context", "mapping domain ambiguity", "specific mapping evidence request"]
        test["forbiddenTerms"] = normalize_terms(["GIS", "parcel", "county assessor", "public web", "accuracy metrics"], limit=8)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["goal"] = "Real chat-history regression: vague mapping follow-ups ask for or use context instead of inventing a domain."
    if is_program_restart_needed_context_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Program restart context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "restart", "program", "config"], limit=8)
        test["requiredContractProof"] = ["code/config/tools changed", "exact program", "hard refresh versus restart", "safe before restart"]
        test["forbiddenTerms"] = normalize_terms(["real-world load", "fit", "environment before committing"], limit=8)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["goal"] = "Real chat-history regression: context-light restart questions answer the restart/refresh boundary instead of generic uncertainty."
    offset1059_contracts = [
        (is_sovol_adaptive_bed_mesh_prompt, "printer-klipper-ops", "Sovol adaptive bed mesh status", ["Sovol", "adaptive bed mesh", "Klipper/start flow", "console proof"]),
        (is_enable_vpn_service_prompt, "mac-system-accounts", "VPN service enablement", ["VPN service", "Tailscale or route", "reachability check"]),
        (is_flightops_rate_provision_prompt, "flightops-tracker", "Flight Ops pilot-aircraft rate model", ["pilot day rate", "aircraft day rate", "per-pilot/per-aircraft", "fallback"]),
        (is_u1_codex_filaments_ui_prompt, "printer-klipper-ops", "U1 Codex filament UI visibility", ["U1", "Codex filaments", "slicer UI", "profile store"]),
        (is_klipper_detached_moonraker_dirty_prompt, "printer-klipper-ops", "Klipper detached Moonraker dirty triage", ["Klipper detached", "Moonraker dirty", "git status", "backup"]),
        (is_klipper_cnc_laser_fit_prompt, "printer-klipper-ops", "Klipper CNC laser fit", ["Klipper", "CNC/laser", "interlocks", "post-processor"]),
        (is_flightops_date_format_prompt, "flightops-tracker", "Flight Ops date format change", ["DD/MM/YYYY", "reporting/status", "central formatter", "database date caveat"]),
        (is_ratrig_noctua_4010_part_cooling_prompt, "printer-klipper-ops", "Rat Rig part-cooling fan sufficiency", ["Noctua 4010", "part cooling", "pressure/flow", "blower or CPAP"]),
        (is_sensorless_three_trigger_average_prompt, "printer-klipper-ops", "Sensorless homing trigger averaging", ["sensorless homing", "three triggers", "sensitivity/current", "repeatability"]),
        (is_sovol_filament_cut_retract_prompt, "printer-klipper-ops", "Sovol filament cut retract verification", ["Sovol", "filament cut", "retract/back out", "macro or G-code"]),
        (is_ratrig_full_build_integration_prompt, "printer-klipper-ops", "Rat Rig integrated build durability", ["Rat Rig", "fully integrated", "not a patch", "regression check"]),
        (is_ratrig_prepare_tab_sync_filament_prompt, "printer-klipper-ops", "Rat Rig prepare-tab sync filament", ["Rat Rig", "Prepare tab", "sync filament", "Moonraker or profile state"]),
        (is_router_speed_asymmetry_diagnostic_prompt, "mac-system-accounts", "Router speed asymmetry diagnostic", ["upload faster than download", "wired/Wi-Fi", "router/modem", "backup settings"]),
        (is_flightops_pilot_display_dropdown_prompt, "flightops-tracker", "Flight Ops pilot display dropdown", ["pilot user", "display name", "dropdown", "pilot ID"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1059_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1099_contracts = [
        (is_live_qidi_moonraker_status_snapshot_prompt, "printer-klipper-ops", "Qidi live Moonraker status snapshot", ["Qidi Plus 4", "Moonraker JSON", "nozzle/bed", "standby/write gate"]),
        (is_btt_rgb_output_24v_strip_prompt, "printer-klipper-ops", "BTT RGB output 24V strip control", ["24 V strip", "BTT RGB/PWM signal", "MOSFET/RGB driver", "fuse/common ground"]),
        (is_orca_face_selection_deep_compare_prompt, "tinmanx-slicer-research", "Orca face-selection comparator diagnostic", ["face-selection", "contact-plane", "Bambu Studio", "Creality Print", "Snapmaker Orca"]),
        (is_orca_brand_preset_display_prompt, "tinmanx-slicer-research", "Orca brand preset display", ["Orca", "Bambu/Sunlu/Polymaker", "filament presets", "vendor/name fields"]),
        (lambda text: any(term in str(text or "").lower() for term in ("t0", "toolhead 0")) and any(term in str(text or "").lower() for term in ("t1", "toolhead 1")) and "beacon" in str(text or "").lower() and any(term in str(text or "").lower() for term in ("swap", "beacon id", "mcu id", "different results", "different toolheads")), "printer-klipper-ops", "T0/T1 Beacon ID comparison", ["T0", "T1", "Beacon ID", "per-toolhead result"]),
        (is_flightops_standalone_offline_sync_prompt, "flightops-tracker", "Flight Ops standalone offline sync architecture", ["standalone/offline-first", "local database", "sync queue", "conflict resolution"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1099_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/source-gated fallback."
            break
    offset1139_contracts = [
        (is_analytical_self_learning_package_prompt, "codex-cli-ui-local-agent", "Systemic analytical self-learning package", ["system-level workflow", "classify domain", "done/evidence gates", "self-heal"]),
        (is_ebb42_programmed_pins_prompt, "printer-klipper-ops", "EBB42 programmed pin audit", ["EBB42", "active Klipper config", "pin:", "source file path"]),
        (is_qidi_backend_network_recovery_prompt, "printer-klipper-ops", "Qidi backend network recovery", ["Qidi", "network recovery", "NetworkManager or Wi-Fi scan", "Moonraker/SSH verification"]),
        (is_qidi_filament_sync_robust_rewrite_prompt, "tinmanx-slicer-research", "Qidi filament sync robust rewrite", ["Qidi filament sync", "U1 pattern", "material/color", "UI persistence"]),
        (is_multi_nozzle_dropdown_architecture_prompt, "printer-klipper-ops", "Multi-nozzle dropdown architecture", ["8 nozzles", "dropdown carriage", "alignment", "tool offsets"]),
        (is_qidi_usb_camera_support_prompt, "printer-klipper-ops", "Qidi USB camera support", ["Qidi", "USB camera", "Moonraker host", "camera service"]),
        (is_flightops_overflight_exemption_fields_prompt, "flightops-tracker", "Flight Ops overflight exemption fields", ["Overflight Exemption", "expiration date", "CBP Decal", "aircraft status"]),
        (is_flightops_customer_all_calendars_assigned_schedule_prompt, "flightops-tracker", "Flight Ops customer calendar permissions", ["all aircraft calendars", "assigned aircraft", "read versus schedule", "privacy"]),
        (is_flightops_admin_impersonation_prompt, "flightops-tracker", "Flight Ops admin view-as roles", ["admin view-as", "pilot/MRO/customer", "audit log", "permission proof"]),
        (is_pi_network_after_outage_prompt, "embedded-linux-images", "Pi network recovery after outage", ["Pi", "DHCP/router lease", "arp-scan or mDNS", "SD-card fallback"]),
        (is_flightops_n797ra_maintenance_report_header_overdue_prompt, "flightops-tracker", "Flight Ops N797RA maintenance report audit", ["N797RA", "propellers", "engines", "overdue logic", "Hobbs"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1139_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1179_contracts = [
        (is_opencentauri_install_boot_slot_prompt, "printer-klipper-ops", "OpenCentauri install and boot-slot boundary", ["OpenCentauri", "source/package", "boot slot", "rollback"]),
        (is_makersvpn_available_prompt, "mac-system-accounts", "MakersVPN availability check", ["MakersVPN", "tailscale status", "reachability check"]),
        (is_makersvpn_sorted_prompt, "mac-system-accounts", "MakersVPN setup recovery", ["MakersVPN", "Tailscale", "subnet routes", "reachability check"]),
        (is_vaoc_mainline_klipper_camera_prompt, "printer-klipper-ops", "VAOC mainline Klipper camera boundary", ["VAOC", "mainline Klipper", "Moonraker", "camera service"]),
        (is_current_load_filament_macro_prompt, "printer-klipper-ops", "Current load-filament macro audit", ["LOAD_FILAMENT", "active config", "temperature gate", "safe macro"]),
        (is_klipper_mcu_loss_ebb42_remote_prompt, "printer-klipper-ops", "Klipper EBB42 MCU-loss recovery boundary", ["EBB42", "MCU loss", "CAN/USB/power", "logs"]),
        (is_printer_optional_software_install_prompt, "printer-klipper-ops", "Printer helper tool install boundary", ["free printer helper tools", "Moonraker", "serial/CAN", "inventory"]),
        (is_klipperscreen_wifi_connected_no_ip_prompt, "printer-klipper-ops", "KlipperScreen Wi-Fi no-IP recovery", ["Wi-Fi connected no IP", "DHCP lease", "ip addr or nmcli", "KlipperScreen"]),
        (is_flightops_customer_report_pages_prompt, "flightops-tracker", "Flight Ops customer report pages", ["customer page", "logo", "Hobbs", "fuel burn", "PDF/render regression"]),
        (is_install_anything_need_context_prompt, "codex-cli-ui-local-agent", "Tool install permission boundary", ["free tools", "capability gap", "ask before large downloads"]),
        (is_printer_printing_without_extruding_confirm_prompt, "printer-klipper-ops", "Printer extrusion telemetry confirmation", ["print_stats", "E-axis", "filament sensor or logs", "filament path"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1179_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1219_contracts = [
        (is_z_hold_current_reduce_prompt, "printer-klipper-ops", "Z hold-current reduction", ["0.75 A", "stepper_z", "hold_current", "idle"]),
        (is_xy_home_current_reduce_prompt, "printer-klipper-ops", "XY homing-current reduction", ["0.5", "X and Y", "homing current", "rollback"]),
        (is_nozzle_04_restore_profile_cleanup_prompt, "printer-klipper-ops", "0.4 nozzle profile restore", ["0.4 mm", "printer profile", "nozzle_diameter", "Installed"]),
        (is_box_humidity_target_enable_prompt, "printer-klipper-ops", "Box humidity target enable", ["box humidity", "60", "auto", "sensor"]),
        (is_lane_specific_sensor_motor_architecture_prompt, "printer-klipper-ops", "Lane-specific sensor/motor architecture", ["lane-isolated", "no common sensors", "T0", "state machine"]),
        (is_contextless_prusa_github_deep_research_prompt, "codex-cli-ui-local-agent", "Contextless Prusa GitHub research target", ["missing target", "Prusa GitHub", "forums", "regression"]),
        (is_ratrig_deep_audit_cleanup_prompt, "printer-klipper-ops", "Rat Rig layered Klipper audit", ["Rat Rig", "Klipper", "macros", "duplicates", "backup"]),
        (is_qidi_box_u1_aux_feeder_lane_architecture_prompt, "printer-klipper-ops", "Qidi Box U1 lane automation architecture", ["Qidi Box", "U1 auxiliary feeders", "four lanes", "single sensor"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1219_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1259_contracts = [
        (is_offline_backend_github_update_context_prompt, "codex-cli-ui-local-agent", "Offline backend work with GitHub boundary", ["offline/local work", "active project", "test/package gate", "push approval"]),
        (is_flightops_inspection_item_dropdown_bug_prompt, "flightops-tracker", "Flight Ops inspection-item dropdown bug", ["aircraft_id", "inspection-item query", "frontend dropdown", "UI/API regression"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1259_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1299_contracts = [
        (is_project_cleanup_latest_data_cad_prompt, "cad-modeling-projects", "CAD/project cleanup manifest", ["manifest-first cleanup", "latest CAD/data", "quarantine", "verification before delete"]),
        (is_ratrig_manual_dual_probe_workflow_prompt, "printer-klipper-ops", "Rat Rig manual dual-probe workflow", ["Rat Rig", "T0/T1 Beacon", "idle/standby", "Klipper restart", "delta report"]),
        (is_qidi_box_factory_firmware_archive_prompt, "printer-klipper-ops", "Qidi Box firmware archive/restore boundary", ["Qidi Box", "Beacon", "pre-box baseline", "archive before reinstall", "restore verification"]),
        (is_codex_extend_testing_download_prompt, "codex-cli-ui-local-agent", "Codex extended regression loop", ["12 hours", "/api/run", "systemic patch", "package health", "free/local downloads"]),
        (is_tailscale_printers_road_access_prompt, "printer-klipper-ops", "Printer Tailscale remote-access setup", ["Tailscale subnet routing", "printer LAN", "Moonraker or printer UI", "idle/standby"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1299_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1339_contracts = [
        (is_qidi_abs_stringing_profile_adjust_prompt, "printer-klipper-ops", "Qidi ABS profile stringing adjustment", ["Qidi ABS", "stringing", "profile backup", "validation print"]),
        (is_qidi_context_change_followup_prompt, "printer-klipper-ops", "Qidi profile/config change follow-up", ["Qidi", "backup", "validation", "idle/standby"]),
        (is_github_push_followup_prompt, "codex-cli-ui-local-agent", "GitHub release push boundary", ["GitHub", "package health", "attribution", "privacy", "testing pause"]),
        (is_github_open_source_credit_planning_prompt, "codex-cli-ui-local-agent", "Open-source credit/release planning", ["GitHub", "open source", "credit", "license", "privacy"]),
        (is_klipper_conversion_holdoff_prompt, "printer-klipper-ops", "Klipper conversion hold-off", ["hold off", "Klipper", "new hardware", "migration checklist"]),
        (is_marlin_prusa_klipper_compare_prompt, "printer-klipper-ops", "Marlin-to-Klipper comparison workflow", ["Marlin", "Prusa", "Klipper", "migration matrix"]),
        (is_rat_rig_lookup_followup_prompt, "printer-klipper-ops", "Rat Rig local discovery", ["Rat Rig", "local config", "Moonraker or Tailscale", "idle/standby"]),
        (is_ssh_credentials_history_lookup_prompt, "printer-klipper-ops", "SSH credential lookup safety", ["SSH", "MakersVPN", "Keychain", "do not print raw passwords"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1339_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1379_contracts = [
        (is_centauri_one_lookup_followup_prompt, "printer-klipper-ops", "Centauri Carbon #1 discovery", ["Centauri", "read-only discovery", "host mapping", "Moonraker or mDNS"]),
        (is_nebula_ebb42_wiring_github_prompt, "codex-cli-ui-local-agent", "Nebula/EBB42 wiring map work order", ["Nebula", "EBB42", "RGB/switch", "wiring assignments", "GitHub boundary"]),
        (is_qidi_max_ez_plr_github_prompt, "codex-cli-ui-local-agent", "Qidi Max EZ Klipper PLR work order", ["Qidi Max EZ", ".147", "Klipper", "PLR", "GitHub boundary"]),
        (is_klipper_platform_focus_guidance_prompt, "printer-klipper-ops", "Klipper platform-first reasoning", ["Klipper", "platform-first", "Rat Rig branding caveat", "transfer method"]),
        (is_qidi_y_before_x_homing_fix_prompt, "printer-klipper-ops", "Qidi Y-before-X homing fix", ["Y before X", "Klipper", "backup", "idle/standby", "validation"]),
        (is_xy_homing_hold_current_change_prompt, "printer-klipper-ops", "XY homing/hold current change", ["0.75", "X and Y", "homing current", "holding current", "Klipper"]),
        (is_qidi_resume_context_followup_prompt, "printer-klipper-ops", "Qidi context resume", ["Qidi", "target", "Moonraker or Klipper", "idle/standby"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1379_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1419_contracts = [
        (is_vaoc_camera_t0_t1_offset_prompt, "printer-klipper-ops", "VAOC camera T0/T1 offset boundary", ["4K camera or VAOC", "T0/T1", "Beacon", "Z offset authority", "validation before saving"]),
        (is_filament_load_unload_g28_preface_prompt, "printer-klipper-ops", "Filament load/unload conditional home", ["G28", "conditional home", "load/unload", "print-state safety"]),
        (is_github_confident_push_prompt, "codex-cli-ui-local-agent", "GitHub confident-push boundary", ["GitHub", "package health", "regression", "attribution/privacy", "approval"]),
        (is_image_inspired_redesign_prompt, "cad-modeling-projects", "Image-inspired CAD redesign context", ["image inspiration", "active CAD or target part", "dimensions/constraints", "revised CAD boundary"]),
        (is_qidi_plus4_network_search_prompt, "printer-klipper-ops", "Qidi Plus 4 network rediscovery", ["Qidi Plus 4", "read-only discovery", "ARP or mDNS", "Moonraker"]),
        (is_cc1_calibration_qidi_network_followup_prompt, "printer-klipper-ops", "CC1 calibration plus Qidi network check", ["CC1", "calibration", "Qidi", "read-only scan"]),
        (is_remote_printer_morning_followup_prompt, "printer-klipper-ops", "Remote physical-printer pause", ["remote", "physical printer", "read-only", "morning"]),
        (is_generic_resume_followup_prompt, "general", "Context resume from checkpoint", ["resume", "checkpoint", "current state", "safety gate"]),
        (is_filament_buffer_stop_prompt, "printer-klipper-ops", "Filament buffer stop state machine", ["buffer", "collision", "separate load command", "state machine"]),
        (is_restart_it_to_check_followup_prompt, "general", "Restart target clarification", ["target", "restart", "idle/standby or process state"]),
        (is_max_ez_chat_state_scan_prompt, "printer-klipper-ops", "Max EZ history state scan", ["Max EZ", "chat history", "latest state", "live verification"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1419_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1459_contracts = [
        (is_print_code_ssh_diagnostic_prompt, "tinmanx-slicer-research", "Print workflow SSH/code diagnostic", ["SSH/code path", "filament-load state", "camera false-positive", "regression test or log proof"]),
        (is_stop_chat_terminate_automations_prompt, "codex-cli-ui-local-agent", "Stop chat and terminate automations", ["stop acknowledged", "automations terminated", "checkpoint/resume state"]),
        (is_rev_b_latest_compare_prompt, "general", "Revision compare missing artifacts", ["Rev B", "new revision", "actual file/artifact paths", "delta report"]),
        (is_qidi_box_pause_rethink_prompt, "printer-klipper-ops", "Qidi Box baseline rethink", ["Qidi Box", "known-good baseline", "firmware/software", "calibration order"]),
        (is_rat_rig_mechanical_mods_pause_prompt, "printer-klipper-ops", "Rat Rig mechanical-mod pause", ["Rat Rig", "mechanical mods", "software pause", "resume validation"]),
        (is_diffuser_positive_z_airflow_test_prompt, "cad-modeling-projects", "Diffuser positive-Z airflow CFD plan", ["diffuser-only", "positive-Z airflow", "solver surface or geometry blocker", "source/solver basis"]),
        (is_upload_all_files_later_prompt, "general", "Upload staging missing destination", ["source file set", "destination", "manifest/package or blocker"]),
        (is_adaptive_heat_soak_design_prompt, "printer-klipper-ops", "Adaptive heat-soak mesh-stability macro", ["bed/chamber targets", "60-second mesh loop", "mesh delta", "completion threshold", "Klipper macro/status basis"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1459_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1499_contracts = [
        (is_ffmpeg_v4l2_camera_log_prompt, "mac-system-accounts", "V4L2 camera MJPEG frame warning", ["/dev/video0", "EOI missing", "MJPEG frame", "v4l2 or capture check"]),
        (is_flightops_multi_inspection_ui_prompt, "flightops-tracker", "Flight Ops multi-inspection UI", ["full-width entry", "multi-select checkbox", "one maintenance entry", "many inspection items"]),
        (is_makers_corner_guest_restart_prompt, "mac-system-accounts", "Guest Wi-Fi restart safety", ["makers corner", "guest 2.4 GHz", "router-side restart", "before/after SSID or client check"]),
        (is_qidi_nebula_pins_before_sensor_removal_prompt, "printer-klipper-ops", "Qidi Nebula pinout before sensor cleanup", ["Nebula pinout", "RGB", "runout", "tangle or filament-width sensor cleanup"]),
        (is_rat_rig_files_access_resume_prompt, "printer-klipper-ops", "Rat Rig file-access resume", ["Rat Rig", "local files", "reachability caveat", "backup/syntax/live gate"]),
        (is_touchscreen_firmware_flash_walkthrough_prompt, "general", "Touchscreen firmware flashing boundary", ["touchscreen/local update support", "exact printer/board", "firmware source/checksum", "backup/rollback"]),
        (is_klipper_request_draft_prompt, "printer-klipper-ops", "Klipper feature-request draft", ["Klipper", "problem/current limitation", "proposed behavior", "safety/test evidence"]),
        (is_filament_box_no_filament_next_step_prompt, "printer-klipper-ops", "Filament box load next step", ["load/purge sequence", "sensor/drag caveat"]),
        (is_snapmaker_u1_custom_firmware_update_decision_prompt, "printer-klipper-ops", "Snapmaker U1 custom firmware update decision", ["Snapmaker U1", "aftermarket firmware", "official release notes", "rollback/backup"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1499_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1539_contracts = [
        (is_manual_auto_feature_still_work_prompt, "cad-modeling-projects", "Manual-off auto-feature boundary", ["manual off", "auto feature remains enabled", "verify exact setting/state"]),
        (is_github_comments_prompt, "codex-cli-ui-local-agent", "GitHub comments explanation", ["GitHub", "issues or pull requests", "comments/reviews/discussions"]),
        (is_plus4_sensorless_homing_force_prompt, "printer-klipper-ops", "Plus 4 sensorless homing force/current", ["Plus 4", "Y homing current", "0.9 A", "force is not equal to current"]),
        (is_cc1_runout_continued_printing_prompt, "printer-klipper-ops", "CC1 runout during-print pause diagnostic", ["CC1", "runout sensor", "immediate pause", "timer", "verify logs/config"]),
        (is_flightops_fuel_method_cover_sheet_report_prompt, "flightops-tracker", "Flight Ops fuel method/report-page layout", ["fuel method 2", "customer report", "second sheet", "standalone page"]),
        (is_flightops_customer_line_remove_label_prompt, "flightops-tracker", "Flight Ops customer-line label cleanup", ["remove Customer label", "customer name", "report header/line"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1539_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1579_contracts = [
        (is_flightops_pilot_report_by_pilot_prompt, "flightops-tracker", "Flight Ops pilot-report filter", ["pilot report", "pilot selector/filter", "date range", "totals verification"]),
        (is_qidi_stepper_motor_temperature_missing_prompt, "printer-klipper-ops", "Qidi stepper temperature visibility boundary", ["Qidi", "stepper motor temperature", "temperature_sensor or Moonraker object", "not CAD"]),
        (is_qidi_codex_library_filament_screen_prompt, "printer-klipper-ops", "Qidi printer-screen Codex library boundary", ["Codex library", "printer screen/UI", "not automatic", "sync/export verification"]),
        (is_ratrig_xy_offset_calibration_no_chamber_heat_prompt, "printer-klipper-ops", "Rat Rig cold XY nozzle-offset calibration", ["Rat Rig", "XY nozzle offset", "no chamber heat", "final hot verification"]),
        (is_flightops_report_date_totals_format_prompt, "flightops-tracker", "Flight Ops report date/totals layout", ["mm/dd/yy", "totals on one line", "report formatter", "stored date caveat"]),
        (is_sovol_obico_not_working_prompt, "printer-klipper-ops", "Sovol Obico connectivity diagnostic", ["Sovol", "Obico", "service/logs", "Moonraker/network/token"]),
        (is_flightops_customer_credit_dropdown_prompt, "flightops-tracker", "Flight Ops customer credit/dropdown feature", ["customer credit", "dropdown", "previously input customers", "preserve current functionality"]),
        (is_flightops_admin_pilot_email_missing_prompt, "flightops-tracker", "Flight Ops calendar pilot email diagnostic", ["pilot email", "calendar", "HTTP/SMTP", "logs/provider response"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1579_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1619_contracts = [
        (is_orca_codex_partially_locked_up_prompt, "orcaslicer-codex", "Orca Codex partial lockup diagnostic", ["Orca Codex", "partial lockup", "process/log", "reproduce verification"]),
        (is_qidi_prepare_tab_nozzle_sync_prompt, "printer-klipper-ops", "Qidi Prepare-tab nozzle-size sync", ["Qidi", "Prepare tab", "nozzle dropdown", "sync verification"]),
        (is_flightops_aircraft_buttons_flights_page_prompt, "flightops-tracker", "Flight Ops aircraft-button flights page", ["Flights page", "buttons for each aircraft", "filtered flight list", "All Aircraft option"]),
        (is_slicer_app_continue_until_all_printers_prompt, "orcaslicer-codex", "Slicer app all-printer build continuation", ["working app", "all printers", "slice and print", "package health"]),
        (is_pctg_profiles_all_machines_qidi_ui_prompt, "tinmanx-slicer-research", "PCTG all-machine/nozzle profile UI feature", ["PCTG", "all machines/nozzles", "Qidi UI", "profile verification"]),
        (is_beacon_ztilt_active_check_prompt, "printer-klipper-ops", "Beacon Z-tilt active-state check", ["Beacon", "T0", "Z_TILT", "active config", "read-only verification"]),
        (is_ratrig_macro_upload_confidence_prompt, "printer-klipper-ops", "Rat Rig macro upload confidence", ["Rat Rig", "macros", "confidence", "config check", "dry run"]),
        (is_post_restart_g28_bed_crash_prompt, "printer-klipper-ops", "Klipper restart safety", ["target printer", "idle/standby", "Klipper restart", "G28", "probe/Beacon"]),
        (is_flightops_pilot_daily_rate_exclusion_prompt, "flightops-tracker", "Flight Ops pilot daily-rate exclusion", ["pilot daily-rate exclusion", "Colin", "N296SA", "N533SS", "pay report verification"]),
        (is_flightops_shutdown_error_history_prompt, "flightops-tracker", "Flight Ops shutdown-error context recovery", ["shutdown error", "recent context/log", "exact text or missing-text caveat"]),
        (is_flightops_storage_projection_prompt, "flightops-tracker", "Flight Ops storage projection", ["current storage", "growth rate", "two aircraft", "maintenance tracking", "80 percent threshold"]),
        (is_flightops_fixed_maintenance_cover_page_prompt, "flightops-tracker", "Flight Ops fixed/maintenance cover-page totals", ["fixed costs", "maintenance costs", "cover page", "monthly total", "layout verification"]),
        (is_heat_soak_points_no_manual_jog_prompt, "printer-klipper-ops", "Heat-soak G28/Z-tilt point automation", ["heat soak", "G28", "Z_TILT_ADJUST", "points", "manual jog"]),
        (is_ratrig_toolboard_mcu_restart_prompt, "printer-klipper-ops", "Rat Rig toolboard MCU communication recovery", ["Rat Rig", "mcu toolboard 1", "lost communication", "restart", "idle/standby"]),
        (is_snapmaker_poweroff_mcu_ssh_diagnostic_prompt, "printer-klipper-ops", "Snapmaker MCU power-off SSH diagnostic", ["Snapmaker", "SSH", "MCU power-off", "logs", "power/undervoltage"]),
        (is_qidi_filament_switch_load_forum_prompt, "printer-klipper-ops", "Filament switch state verification", ["present/true state", "filament_detected", "pin/inversion check", "load sequence"]),
        (is_macos_sequoia_tahoe_upgrade_prompt, "mac-system-accounts", "macOS Sequoia/Tahoe upgrade decision", ["Tahoe directly", "Sequoia only if required", "backup", "compatibility"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1619_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1659_contracts = [
        (is_3d_chameleon_cleanup_prompt, "codex-cli-ui-local-agent", "3D Chameleon safe cleanup", ["3D Chameleon", "manifest", "archive/backup", "delete only confirmed files"]),
        (is_printer_ip_changed_password_note_prompt, "printer-klipper-ops", "Printer IP update credential boundary", ["192.0.2.145", "password/private credential", "Moonraker/SSH", "redact"]),
        (is_flightops_aircraft_documents_restore_upload_prompt, "flightops-tracker", "Flight Ops aircraft document restore/upload", ["aircraft documents", "manifest", "local source path", "upload verification"]),
        (is_klipper_load_unload_macro_buttons_prompt, "printer-klipper-ops", "Klipper load/unload macro UI binding", ["Klipper", "LOAD_FILAMENT", "UNLOAD_FILAMENT", "KlipperScreen buttons"]),
        (is_all_printers_supported_continue_prompt, "printer-klipper-ops", "All-printer support continuation", ["all printers", "support matrix", "slice test", "print/send readiness"]),
        (is_u1_buffer_sensor_delete_confirmation_prompt, "printer-klipper-ops", "U1 buffer/sensor deletion confirmation", ["U1", "buffer", "sensors", "lanes merge", "sensor map"]),
        (is_temporary_immediate_pause_macro_prompt, "printer-klipper-ops", "Temporary immediate pause macro", ["helper macro", "pause print", "mechanical side", "wasted filament", "Klipper PAUSE"]),
        (is_mainline_klipper_camera_xy_measurement_prompt, "printer-klipper-ops", "Mainline Klipper camera XY measurement", ["mainline Klipper", "camera", "X/Y", "vision pipeline", "offset validation"]),
        (is_typical_questions_domain_list_prompt, "energy-power-research", "Domain question bank", ["3D printing", "CNC", "solar/wind", "CFD", "aviation"]),
        (is_snapmaker_u1_installed_filaments_prompt, "printer-klipper-ops", "Snapmaker U1 installed filament visibility", ["Snapmaker U1", "local profile backup", "installed slicer UI", "profile visibility"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1659_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    offset1699_contracts = [
        (is_sovol_sv08_petg_cf_apply_changes_prompt, "tinmanx-slicer-research", "Sovol SV08 Max PETG-CF profile update", ["Sovol SV08 Max", "PETG-CF", "profile update", "slice smoke test"]),
        (is_pick_up_where_left_off_prompt, "codex-cli-ui-local-agent", "Checkpoint continuation", ["latest checkpoint", "active task", "verify current state"]),
        (is_uploaded_files_fix_coding_errors_stability_prompt, "codex-cli-ui-local-agent", "Uploaded-files code stability repair", ["uploaded files", "syntax/tests", "coding errors", "app stable"]),
        (is_qidi_backup_and_stock_restore_prompt, "printer-klipper-ops", "Qidi backup and stock restore", ["local backup/manifest", "Qidi Box", "stock baseline", "idle/standby", "restore verification"]),
        (is_dry_room_sub_10_humidity_prompt, "printer-klipper-ops", "Sub-10% dry-room humidity control", ["10% RH", "desiccant", "sealed room", "dry boxes", "monitoring"]),
        (is_project_github_link_prompt, "codex-cli-ui-local-agent", "Current project GitHub remote", ["github.com", "origin remote", "local changes"]),
        (is_stock_firmware_password_prompt, "embedded-linux-images", "Firmware stock password boundary", ["pi", "raspberry", "firmware image caveat", "change the password"]),
        (is_flightops_pi_vpn_mobile_access_prompt, "flightops-tracker", "Flight Ops mobile access architecture", ["Raspberry Pi", "pilots/customers", "mobile HTTPS login", "MakersVPN admin", "role-based access"]),
        (is_ratrig_vcore_extrusion_gantry_prompt, "printer-klipper-ops", "Rat Rig V-Core gantry extrusion spec", ["Rat Rig", "3030", "steel X-axis gantry", "BOM or measure"]),
        (is_humidity_control_box_minimal_heat_prompt, "cad-modeling-projects", "Low-heat humidity-control box design", ["sealed box", "desiccant", "fan", "humidity sensor", "minimal/no heat"]),
        (is_flightops_document_not_found_user_prompt, "flightops-tracker", "Flight Ops document-not-found diagnostic", ["Document not found", "database record", "file path", "user permission", "document ID"]),
        (is_flightops_old_spreadsheet_download_prompt, "flightops-tracker", "Flight Ops stale spreadsheet download", ["old spreadsheet", "download endpoint", "stored document", "cache", "verify download"]),
        (is_flightops_monthly_report_back_button_prompt, "flightops-tracker", "Flight Ops monthly report back button", ["Back to Tracker", "monthly report", "tracker route", "mobile layout"]),
        (is_cad_file_format_preference_prompt, "cad-modeling-projects", "CAD file format preference", ["STEP", ".f3d", ".f3z", "STL", "constraints"]),
        (is_flightops_tinneyaviation_data_loss_prompt, "flightops-tracker", "Flight Ops data-persistence diagnostic", ["data-persistence", "HTTP POST", "server logs", "database write"]),
        (is_flightops_role_redirect_prompt, "flightops-tracker", "Flight Ops role-based login redirect", ["pilots", "Flights page", "customers", "Schedule page", "admins", "Home page"]),
        (is_orca_install_location_prompt, "tinmanx-slicer-research", "Orca/TinmanX install location", ["/Applications", "~/Applications", "profiles visible"]),
        (is_snapmaker_u1_usb_port_location_prompt, "printer-klipper-ops", "Snapmaker U1 USB location", ["Snapmaker U1", "USB", "revision/manual caveat"]),
        (is_klipperscreen_installed_working_check_prompt, "printer-klipper-ops", "KlipperScreen install/health check", ["KlipperScreen", "systemctl status", "Moonraker", "logs"]),
        (is_ratrig_generic_copy_preset_review_prompt, "printer-klipper-ops", "Rat Rig slicer preset review", ["RatRig Generic Copy", "machine/process/filament", "backup", "slice preview"]),
        (is_google_earth_roofline_solar_prompt, "energy-power-research", "Solar roofline placement", ["Google Earth", "roofline", "solar panels", "shade/setbacks"]),
        (is_bed_mesh_z_offset_calibration_research_prompt, "codex-cli-ui-local-agent", "Calibration research knowledge-pack", ["bed mesh", "Z offset", "nozzle offset", "source", "playbook"]),
        (is_github_update_changes_prompt, "codex-cli-ui-local-agent", "GitHub publish workflow", ["git status", "package health", "commit", "push"]),
        (is_spdt_runout_immediate_pause_prompt, "printer-klipper-ops", "SPDT filament-runout pause wiring", ["SPDT", "pause_on_runout", "runout_gcode", "QUERY_FILAMENT_SENSOR"]),
        (is_flightops_mobile_app_prompt, "flightops-tracker", "Flight Ops mobile app architecture", ["mobile app", "PWA", "pilots/customers", "roles"]),
        (is_flash_existing_board_klipper_prompt, "printer-klipper-ops", "Klipper existing-board flash feasibility", ["Klipper", "MCU", "backup", "flash method"]),
        (is_ratrig_idex_user_preset_prompt, "tinmanx-slicer-research", "Rat Rig IDEX Codex user preset strategy", ["Rat Rig IDEX 500", "user/vendor preset", "printer preset", "slice/preview"]),
        (is_qidi_box_before_freedi_prompt, "printer-klipper-ops", "Qidi Box before freeDI sequencing", ["Qidi Box", "freeDI", "baseline", "rollback"]),
        (is_moonraker_json_status_blob_prompt, "printer-klipper-ops", "Moonraker JSON status interpretation", ["klippy_connected", "ready", "failed_components", "http_client"]),
        (is_plus4_petcf_06_filament_settings_prompt, "tinmanx-slicer-research", "Slicer profile parameter pull", ["profile source or explicit fallback", "why/caveat", "no CAD/status template"]),
    ]
    for detector, expected_project, contract_kind, proof_terms in offset1699_contracts:
        if detector(prompt):
            test["expectedProjectId"] = expected_project
            test["expectedContractKind"] = contract_kind
            test["expectedContractGate"] = "pass"
            test["directAnswer"] = True
            test["directTerms"] = []
            test["contextDependent"] = False
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
            test["requiredContractProof"] = proof_terms
            test["anyTerms"] = []
            test["requiresSource"] = False
            test["webSearch"] = "disabled"
            test["minAnalyticalScore"] = 100
            test["maxDurationMs"] = 750
            test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
            break
    if is_codex_vendor_profile_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca/TinmanX vendor profile"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "vendor", "profile"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "filament"], limit=8)
        test["requiredContractProof"] = ["vendor profile path", "app visibility gate"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer Codex-as-vendor profile strategy in the broader TinmanX/Orca/Qidi profile lane."
    if is_sensorless_homing_decimal_sensitivity_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["No", "Klipper", "integer"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Klipper"], limit=8)
        test["requiredContractProof"] = ["Klipper", "driver_SGTHRS", "integer", "0 through 255"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer decimal sensorless-homing sensitivity as a validation question, not a config artifact request."
    if is_local_slicer_profile_parameter_pull_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Slicer profile parameter pull"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["profile", "filament"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "filament"], limit=8)
        test["requiredContractProof"] = ["profile source or explicit fallback", "why/caveat", "no CAD/status template"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 5000
        test["goal"] = "Real chat-history regression: local slicer profile pulls use local profile evidence instead of public URL gates."
    if is_freecad_visibility_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "FreeCAD optional tool install"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "FreeCAD", "visible"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "command-line", "tool inventory", "STEP"], limit=8)
        test["requiredContractProof"] = ["FreeCAD app/binary visibility", "tool inventory refresh", "STEP open/export smoke test"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer FreeCAD visibility from local tool inventory, not generic web/source research."
    if is_belt_slip_cutting_force_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Belt slip/cutting force safety"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["do not use", "9 mm", "cutting ram"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "belt", "tooth", "leadscrew"], limit=8)
        test["requiredContractProof"] = ["do not ram toolhead", "belt/tooth/drivetrain risk", "constrained cutter/press alternative"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer belt-slip/cutting-force questions as printer motion safety, not CAD/file-format reference."
    if is_tool_inventory_visibility_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Local tool inventory visibility"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "local tool inventory", "commands"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "apps", "inventory", "refresh"], limit=8)
        test["requiredContractProof"] = ["commands=", "apps=", "Python modules", "Homebrew", "Ollama models", "Inventory files", "refresh"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer local tool-inventory requests from visible Mac inventory counts and refresh paths instead of generic research."
    if is_document_compliance_review_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Document compliance review"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["actual document", "compliance"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "actual document", "compliance", "evidence"], limit=8)
        test["requiredContractProof"] = ["actual document", "compliance table or gap list", "current evidence", "no guessed compliance"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: review-against-document prompts must use the actual document as source of truth instead of hallucinating policy compliance."
    if is_no_filament_loaded_test_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "No-filament print test decision"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["No", "loaded-filament test"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "runout", "loaded-filament", "safety"], limit=8)
        test["requiredContractProof"] = ["no filament loaded", "runout", "loaded-filament test", "safety caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer no-filament print-test questions as practical printer safety advice, not generic research/source work."
    if is_qidi_login_screen_connect_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi login-screen connectivity"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["127.0.1.1", "LAN", "Moonraker"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "127.0.1.1", "LAN", "DHCP", "Moonraker"], limit=8)
        test["requiredContractProof"] = ["127.0.1.1", "LAN", "DHCP", "Moonraker"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Qidi login-screen loopback IP prompts as no-LAN-address-yet connectivity work, not a fake 192.0.2.127 restoration target."
    if is_network_moved_ip_scan_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops" if any(term in prompt.lower() for term in ("qidi", "max ez", "maxez", "max ex", "maz ez", "printer")) else "mac-system-accounts"
        test["expectedContractKind"] = "Network moved-IP scan"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["bounded", "inventory", "ARP"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "subnet", "inventory", "ARP", "Moonraker"], limit=8)
        test["requiredContractProof"] = ["subnet", "inventory", "ARP", "service verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer moved-IP printer discovery with a bounded local discovery path instead of timing out."
    if is_lan_ip_restoration_context_prompt(prompt):
        requested_ip = requested_lan_ip_from_text(prompt) or "192.0.2.145"
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "LAN IP restoration context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = [requested_ip, "device", "IP conflict", "DHCP reservation"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "IP", "device", "DHCP"], limit=8)
        test["requiredContractProof"] = ["requested IP", "device identity", "IP conflict", "DHCP reservation"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer shorthand LAN-IP restoration follow-ups by identifying the target and safe proof sequence instead of generic help."
    if is_lost_ip_sd_card_recovery_prompt(prompt):
        test["expectedProjectId"] = "embedded-linux-images"
        test["expectedContractKind"] = "Printer host lost-IP SD-card recovery"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["SD card", "backup", "Wi-Fi"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "SD card", "backup", "DHCP", "hostname"], limit=8)
        test["requiredContractProof"] = ["SD card", "backup", "Wi-Fi/DHCP/hostname", "do not reimage first"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer lost-IP SD-card recovery prompts by inspecting/backing up network config before reimaging."
    if is_printing_from_slot_three_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Slicer/printer slot follow-up"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["slot 3", "filament", "profile"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "slot 3", "filament", "profile", "verify"], limit=8)
        test["requiredContractProof"] = ["slot 3", "filament/profile mapping", "job verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: preserve explicit slot 3 print-source constraints instead of treating the prompt as context-only."
    if is_offline_knowledge_server_sizing_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Offline knowledge server sizing"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["100-200 TB", "curated", "ZFS"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "TB", "curated", "ZFS", "index"], limit=8)
        test["requiredContractProof"] = ["100-200 TB", "curated vault", "ZFS or redundancy", "index/search"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer offline survival/engineering knowledge-vault sizing as architecture sizing, not live web research requiring source URLs."
    if is_ip_changed_missing_target_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "IP change target context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["device name", "old IP", "ARP", "mDNS"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "IP", "device"], limit=8)
        test["requiredContractProof"] = ["device name", "old IP", "ARP", "mDNS", "DHCP"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer contextless IP-change checks by asking for the target and naming the safe local discovery sequence."
    if is_orca_print_time_disparity_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca print-time estimate disparity"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Orca logs", "generated G-code", "machine-limit"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "machine limits", "G-code", "firmware"], limit=8)
        test["requiredContractProof"] = ["Orca logs/G-code", "machine limits", "firmware or custom G-code timing", "one-file comparison"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Orca print-time estimate disparities from logs/G-code/machine-limit checks instead of CAD reference."
    if is_fk275_belt_cross_reference_prompt(prompt):
        test["expectedProjectId"] = "research-parts-reference"
        test["expectedContractKind"] = "Belt cross-reference"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["FK275", "exact", "belt"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "profile", "dimensions", "materials"], limit=8)
        test["requiredContractProof"] = ["FK275", "belt profile/rib count", "dimensions/materials", "datasheet or measured-profile workflow"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer FK275 belt cross-reference requests by exact profile/dimension/material workflow instead of CAD reference scoring."
    if is_codex_cli_response_time_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex CLI response-time optimization"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["fastest free wins", "model", "context"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "model", "context", "measure"], limit=8)
        test["requiredContractProof"] = ["smaller or warm local model", "trim context", "direct/tool routing", "measure response time"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Codex CLI response-time tuning with local model/context/tool routing and measurement, not cold generic advice."
    if re.search(r"^(?:lets|let's)\s+move\s+forward\s+with\s+all\s+your\s+recom?m?endations\.?$", lower.strip()):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["active task", "last result", "proof"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "active task", "last result"], limit=8)
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Context-only proceed follow-up: ask for the active task or last result and do not pretend work continued without a target."
    if is_macro_usage_missing_context_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Macro usage missing context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["macro", "real workflow", "dry run"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "trigger", "context"], limit=8)
        test["requiredContractProof"] = ["macro name", "trigger point", "dry run"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer contextless macro-usage follow-ups with macro target/purpose request and safe trigger/test workflow instead of timing out or routing to Mac."
    if is_speaker_pod_cad_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Speaker pod CAD template gate"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["KMXL69", "SK_Speaker_Reference", "baffle"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "template", "baffle", "KMXL69"], limit=8)
        test["requiredContractProof"] = ["template gate", "baffle alignment", "source-template caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer speaker-pod CAD template prompts with the official KMXL69/SK_Speaker_Reference baffle gate, not slicer strength-lens metadata."
    if is_abs_rat_rig_orca_overrides_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "ABS Rat Rig Orca start overrides"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["nozzle 245", "bed 105-110", "brim"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "ABS", "Rat Rig", "Orca", "fan"], limit=8)
        test["requiredContractProof"] = ["nozzle 245 C", "bed 105-110 C", "10-20%", "6-10 mm brim"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer ABS Rat Rig Orca override prompts with usable starting slicer settings and tuning caveats, not unrelated Rocket/FibreSeek metadata."
    if is_rgb_5v_source_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "RGB external 5V source"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["No", "external 5 V", "common ground"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "RGB", "5 V", "ground", "backfeed"], limit=8)
        test["requiredContractProof"] = ["external 5 V", "common ground", "do not backfeed", "fuse/current check"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer RGB 5V source questions as wiring/power guidance, not CM4/Pi host selection."
    if is_rgb_recheck_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper RGB recheck"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Recheck", "RGB", "Klipper"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "RGB", "Klipper", "SET_LED", "config", "idle"], limit=8)
        test["requiredContractProof"] = ["RGB/LED", "Klipper config or macro", "SET_LED or macro test", "no fake generated file"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer short RGB recheck follow-ups as verification tasks and reject fake generated-file receipts."
    if is_bed_mesh_led_color_macro_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper bed-mesh LED color macro"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["Yes", "bed-leveling", "bed-mesh"]
        test["requiredTerms"] = normalize_terms(
            ["This is why", "You should also consider", "SET_LED", "BED_MESH_CALIBRATE", "G28", "Z_TILT_ADJUST", "LED object names"],
            limit=8,
        )
        test["requiredContractProof"] = ["red/blue", "SET_LED", "G28/Z_TILT_ADJUST/BED_MESH_CALIBRATE", "LED object names", "nonblocking delayed_gcode caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["goal"] = "Real chat-history regression: answer bed-leveling LED color requests as Klipper macro guidance, not CAD reference or generated artifact work."
    if (
        any(term in lower for term in ("filament buffer", "buffer"))
        and any(term in lower for term in ("bind", "binding"))
        and any(term in lower for term in ("motor speed", "feeder", "compensate", "adjust"))
    ):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Filament buffer bind compensation"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "buffer/feeder", "print extruder"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "sensor", "timeout", "jam"], limit=8)
        test["requiredContractProof"] = ["buffer/feeder side", "print extruder", "sensor", "timeout"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer filament-buffer bind compensation as a printer control-loop question, not as CAD artifact generation."
    if "fusion" in lower and any(term in lower for term in ("directory", "folder", "path")) and any(term in lower for term in ("file", "files", "output", "saved")):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Fusion file directory follow-up"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Fusion", "directory", "data/generated/cad"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Fusion", "directory"], limit=8)
        test["requiredContractProof"] = ["Fusion", "data/generated/cad", "parent directory"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Fusion file directory follow-ups directly and avoid slow CAD/model generation."
    if len(lower.strip()) < 90 and "short" in lower and any(term in lower for term in ("still showing", "showing a short", "show a short", "is it still", "does it still")):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Short-status missing context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["cannot confirm", "short", "meter"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "short", "meter", "power"], limit=8)
        test["requiredContractProof"] = ["short", "meter or diagnostic reading", "power off or isolate"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer contextless short-status follow-ups with a fast safety/context answer, not a model timeout."
    if any(term in lower for term in ("increase it by 4", "increase it by four", "4 times", "four times", "double it", "double it again", "double again")) and any(
        term in lower for term in ("re run", "rerun", "re-run", "run again")
    ):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Rerun factor context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["what value", "factor", "rerunning"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "value", "factor", "rerun"], limit=8)
        test["requiredContractProof"] = ["value/command request"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer contextless factor/rerun follow-ups immediately instead of spending a slow model call."
    if len(lower.strip()) < 160 and "inverted" in lower and any(term in lower for term in ("they are", "they're", "what they should be", "fix it")):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Inverted target needs context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["what `they` refers to", "correct orientation", "inverted", "smallest safe change"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "inverted", "they"], limit=8)
        test["requiredContractProof"] = ["what `they` refers to", "correct orientation", "inverted", "smallest safe change"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer inverted-target follow-ups with a fast context/safety request."
    if any(term in lower for term in ("single pole single throw", "spst")) and any(term in lower for term in ("lightbulb", "light bulb", "bulb", "lamp")):
        test["expectedProjectId"] = "engineering-diagrams"
        test["expectedContractKind"] = "SPST two-switch light circuit"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["SPST", "series", "Hot/Line"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "SPST", "series", "3-way", "code"], limit=8)
        test["requiredContractProof"] = ["SPST", "series", "Hot/Line", "3-way", "code"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer simple SPST light circuits directly without requiring generated diagram files."
    if "m191" in lower and "chamber" in lower and any(term in lower for term in ("disable", "turn off", "remove")):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca M191 chamber temperature handoff"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["M191", "chamber", "M104"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "M191", "chamber", "M104"], limit=8)
        test["requiredContractProof"] = ["M191", "chamber", "M104", "PRINT_START"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Orca M191 chamber-target handoff questions directly, not with unrelated completion-time metrics."
    if (
        any(term in lower for term in ("heat soak", "heat-soak"))
        and any(term in lower for term in ("chamber temp", "chamber temperature", "chamber"))
        and any(term in lower for term in ("50 degrees", "50 c", "50c", "50"))
    ):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Heat-soak chamber target"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["50 C", "chamber-temperature path", "M141", "M191", "PRINT_START CHAMBER_TEMP=50"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "50", "chamber", "M191"], limit=8)
        test["requiredContractProof"] = ["50 C", "chamber", "M141", "M191", "PRINT_START CHAMBER_TEMP=50"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer heat-soak chamber target changes as printer/slicer chamber handoff work, not generic chat."
    if (
        "beacon" in lower
        and "contact" in lower
        and any(term in lower for term in ("adaptive bed mesh", "adaptive mesh", "kamp"))
        and any(term in lower for term in ("set up", "setup", "configured", "installed", "do we have", "have we"))
    ):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Beacon/adaptive mesh setup status"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Beacon Contact", "adaptive", "Checked"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Beacon Contact", "adaptive", "Moonraker"], limit=8)
        test["requiredContractProof"] = ["local config", "Beacon Contact", "adaptive mesh", "live verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Beacon/adaptive mesh status from evidence boundaries, not by inventing broad live checks."
    if is_printer_aux_output_run_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Printer auxiliary-output run request"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Klipper", "SET_FAN_SPEED", "SET_PIN"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "idle", "config", "verified"], limit=8)
        test["requiredContractProof"] = ["idle check", "Klipper config/object lookup", "verified SET_FAN_SPEED or SET_PIN path", "no guessed M106/M701"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(
            set(
                test.get("forbiddenTerms", [])
                + ["M106 T0", "M106 T1", "M701", "M702", "Marlin pump", "OctoPrint"]
            )
        )
        test["goal"] = "Real chat-history regression: run chamber/pump/fan auxiliary outputs through verified Klipper object names, not generic Marlin fan guesses."
    if is_heat_soak_at_print_chamber_temp_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Heat-soak print chamber condition"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "chamber temperature", "print"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "thermal stability", "bed mesh", "Z offset"], limit=8)
        test["requiredContractProof"] = ["chamber temperature you intend to print at", "thermal stability", "final homing/Z check", "bed mesh", "PLA"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer heat-soak print-temperature follow-ups as printer thermal-stability guidance, not Codex personality controls."
    if is_thermal_stabilize_reprobe_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Thermal stabilize and reprobe sequence"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["Yes", "45 C", "100 C", "180 C"]
        test["requiredTerms"] = normalize_terms(
            ["This is why", "You should also consider", "45 C", "100 C", "180 C", "G28", "Z_TILT_ADJUST", "BED_MESH_CALIBRATE"],
            limit=8,
        )
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["requiredContractProof"] = ["45 C chamber", "100 C bed", "180 C nozzle", "temperature stability", "G28/Z_TILT_ADJUST/BED_MESH_CALIBRATE"]
        test["goal"] = "Real chat-history regression: answer thermal stabilize/reprobe commands directly and safely without claiming live printer execution."
    if is_filament_eject_live_action_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Filament eject live-action gate"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["Yes", "idle", "heated enough"]
        test["requiredTerms"] = normalize_terms(
            ["This is why", "You should also consider", "idle", "unload temperature", "target printer", "M702"],
            limit=8,
        )
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["requiredContractProof"] = ["target printer", "idle", "unload temperature", "unload macro or M702"]
        test["goal"] = "Real chat-history regression: answer filament eject requests as safety-gated live printer actions, not generic research."
    if is_btt_sfs_false_motion_code_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "BTT SFS false-motion diagnostic"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["Probably not fully correct", "BTT SFS 2.0", "Klipper"]
        test["requiredTerms"] = normalize_terms(
            ["This is why", "You should also consider", "BTT SFS 2.0", "filament_motion_sensor", "switch_pin", "detection_length"],
            limit=8,
        )
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["requiredContractProof"] = [
            "BTT SFS 2.0",
            "filament_motion_sensor",
            "switch_pin/extruder/detection_length",
            "pin/pullup/inversion/noise",
            "one sensor at a time",
        ]
        test["goal"] = "Real chat-history regression: answer BTT SFS false-motion questions as Klipper sensor config/wiring diagnostics, not CAD or wind-rotor tasks."
    if (
        any(term in lower for term in ("machine start gcode", "machine start g-code", "start gcode", "start g-code"))
        and any(term in lower for term in ("orca", "orcaslicer", "slicer"))
        and any(term in lower for term in ("before the heaters", "before heaters", "heater", "heaters"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca machine-start before-heaters"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Machine Start", "heater", "M140"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Machine Start", "heater", "M140"], limit=8)
        test["requiredContractProof"] = ["Machine Start", "heater", "M140/M190/M104/M109", "dry preview"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Orca Machine Start before-heater questions directly, not as a hard config edit without a profile path."
    if is_orcaslicer_codex_installed_changes_prompt(prompt):
        test["expectedProjectId"] = "orcaslicer-codex"
        test["expectedContractKind"] = "OrcaSlicer Codex installed-change verification"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["I would not assume", "installed app"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "installed app", "profile store", "package health", "UI-visible"], limit=10)
        test["requiredContractProof"] = ["installed app path/app bundle", "source/build receipt", "profile-store comparison", "package health or UI-visible check"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["80% stall", "bad mesh", "source URL"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: installed OrcaSlicer Codex status must verify the app bundle/profile store, not answer as slicer stall troubleshooting or public research."
    if is_slicer_profile_update_prompt(prompt) and not is_offset1339_direct_prompt(prompt) and not is_offset1419_direct_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Slicer profile edit/update"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "profile"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "profile", "backup", "visibility", "changed"], limit=10)
        test["requiredContractProof"] = ["profile-store backup", "target profile/layer", "changed keys or explicit edit boundary", "lint/visibility verification"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["Filament profile:", "Machine profile:", "Process profile:"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: profile update requests must be backup-first edit workflows, not full profile parameter dumps or live printer telemetry."
    if is_makersvpn_reboot_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "MakersVPN reboot safety"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "MakersVPN"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "MakersVPN", "reboot", "Tailscale"], limit=8)
        test["requiredContractProof"] = ["MakersVPN", "reboot", "Tailscale", "route verification"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["I do not have access", "I don't have access", "you can check it yourself"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: MakersVPN reboot requests must give a safe host/route reboot path, not cold no-access fallback text."
    if is_bluetooth_rename_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Mac Bluetooth rename"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["I did not rename", "Bluetooth", "Bose"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Bluetooth", "requested name", "Tinman Bose"], limit=8)
        test["requiredContractProof"] = ["Bluetooth device state", "requested name", "safe rename path or blocker"]
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["staged local artifact", "local Ollama answer", "this mac via bluetooth"]))
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Bluetooth rename requests are local Mac device-state tasks, not public web research."
    if is_hotend_mount_visual_reference_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Hotend mount visual reference"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Best visual reference", "carriage"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "hotend", "mount", "carriage", "http"], limit=10)
        test["requiredContractProof"] = ["hotend mount", "carriage", "source URL", "CAD caveat"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["Printer status", "Moonraker", "nozzle temp"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: hotend mount visual-reference requests must explain the carriage/mount relationship with links, not detour into printer status."
    if is_cad_duct_upward_image_reference_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "CAD duct visual delta"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "upward"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "upward", "flat", "CAD"], limit=8)
        test["requiredContractProof"] = ["upward riser/elbow", "flat CAD comparison", "smooth S-bend or elbow"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["source URL", "OpenSCAD", "Fusion 360 script"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 50
        test["goal"] = "Real chat-history regression: image-based duct-shape follow-ups must explain the visual CAD change directly, not stage generic CAD artifacts or require web sources."
    if is_orca_chamber_before_bed_research_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca chamber-before-bed research"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Orca", "M191", "PRINT_START"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "M191", "M141", "PRINT_START", "http"], limit=10)
        test["requiredContractProof"] = ["M191", "M141", "PRINT_START", "source URL"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["Codex CLI UI", "run failed", "Load failed"], limit=16)
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["goal"] = "Real chat-history regression: Orca chamber-before-bed research must return a source-backed chamber handoff answer, not a generic Codex UI route or slow research stall."
    if is_klipper_restart_prompt(prompt) and not is_offset1299_direct_prompt(prompt) and not is_offset1339_direct_prompt(prompt) and not is_offset1419_direct_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper restart safety"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "target printer"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Klipper", "idle", "standby"], limit=8)
        test["requiredContractProof"] = ["target printer", "idle/standby", "Klipper restart"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["I restarted", "done restarting"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Klipper restart requests must be safety-gated live actions, not code/config artifacts or generic restart advice."
    if is_bambu_x1c_nozzle_live_status_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Bambu nozzle status boundary"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Bambu X1C", "Moonraker"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Bambu X1C", "configured", "physical"], limit=10)
        test["requiredContractProof"] = ["Bambu X1C", "Moonraker boundary", "configured vs physical nozzle"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["I checked the configured Rat Rig", "Qidi Plus 4 Moonraker"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Bambu X1C nozzle live-status questions must not probe unrelated Klipper printers."
    if is_rat_rig_ip_lookup_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Rat Rig IP lookup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["192.0.2.27", "Rat Rig"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "192.0.2.27", "Rat Rig"], limit=8)
        test["requiredContractProof"] = ["192.0.2.27", "Rat Rig", "Moonraker/SSH caveat"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["source URL", "OctoPrint"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 70
        test["goal"] = "Real chat-history regression: Rat Rig IP lookups should use local inventory/context and not require public source URLs."
    if is_chrome_page_screenshot_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Chrome screenshot capture"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["screenshot", "Chrome"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "screenshot", "Chrome", "permission"], limit=8)
        test["requiredContractProof"] = ["screenshot file proof", "Chrome/page scope", "permission blocker boundary"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["Source:", "http"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Chrome screenshot requests are local capture tasks with file/permission proof, not web research."
    if is_fibreseeker_calculation_paper_update_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "FibreSeeker paper calculation update"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["FibreSeeker", "calculations"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "calculation", "paper", "FibreSeeker", "http"], limit=10)
        test["requiredContractProof"] = ["FibreSeeker", "calculation/model diff", "source URLs"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["Codex CLI UI"], limit=16)
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["goal"] = "Real chat-history regression: supplied engineering papers should become FibreSeeker calculation inputs with source-backed extraction boundaries."
    if is_github_update_with_filament_price_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "GitHub push paused with price verification"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["GitHub push", "paused"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "GitHub", "current price", "http"], limit=10)
        test["requiredContractProof"] = ["GitHub push paused", "current price source URLs", "testing clearance"]
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["goal"] = "Real chat-history regression: mixed GitHub/price requests must respect the testing push pause and separate volatile price verification from profile dumps."
    if is_humidity_hook_reuse_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Humidity hook reuse"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "humidity"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "target printer", "sensor"], limit=8)
        test["requiredContractProof"] = ["target printer", "humidity sensor object", "Moonraker/telemetry path"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: humidity hook reuse must name target/sensor verification instead of dumping generic Moonraker steps."
    if is_qidi_filament_width_sensor_location_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi filament sensor identification"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Do not", "width sensor"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "tangle", "runout", "config"], limit=8)
        test["requiredContractProof"] = ["width versus tangle/runout", "manual/config proof", "sensor object name"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Qidi sensor-location questions must separate width sensing from tangle/runout without invented placement claims."
    if is_qidi_box_ace2_compare_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Filament box comparison boundary"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["filament-management", "Qidi Box"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "drying", "RFID", "feed"], limit=8)
        test["requiredContractProof"] = ["filament-management", "drying/RFID/feed", "exact model caveat"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Qidi Box vs ACE 2 Pro comparisons must not answer as if they are complete printers."
    if is_core_one_l_filament_specific_profile_share_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Core One L profile packaging/share"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Core One L"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Core One L", "machine", "process", "filament", "GitHub", "visibility"], limit=12)
        test["requiredContractProof"] = ["Core One L", "machine/process/filament separation", "import/visibility verification", "README/attribution/privacy", "no GitHub push without approval"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["source URL", "cleanup path"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: Core One L filament-specific profiles are a local profile-packaging/share workflow, not generic Codex UI cleanup or web research."
    if is_shared_profile_repo_machine_organization_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Shared profile repo machine organization"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "machine"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Qidi", "Sovol", "manifest", "privacy", "attribution", "GitHub"], limit=12)
        test["requiredContractProof"] = ["machine-family folders", "Qidi/Sovol examples", "profile manifest or README", "privacy/attribution scrub", "local package before GitHub push"]
        test["forbiddenTerms"] = normalize_terms(BASE_FORBIDDEN_TERMS + ["tree/main/orca/qidi-x-plus-4", "packages/qidi-x-plus-4.zip"], limit=16)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: shared profile repo organization must produce a machine-family packaging plan without invented GitHub links or premature push claims."
    if is_centauri_carbon_name_swap_prompt(prompt):
        target_name = "TinmanCC1" if "tinmancc1" in lower or "tinman cc1" in lower else "Centauri"
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "TinManX printer-profile rename"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = [target_name, "profile", "host mapping"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "profile", "host", "UI"], limit=8)
        test["requiredContractProof"] = ["profile-store backup", "target printer name", "host mapping", "UI-visible check"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: treat Centauri/TinmanCC profile rename requests as local profile-maintenance work, not source-backed research."
    if (
        any(term in lower for term in ("open centauri", "centauri", "centari", "centauri carbon", "centari carbon"))
        and any(term in lower for term in ("orca", "orcaslicer", "orca codex"))
        and any(term in lower for term in ("device tab", "devive tab", "device page"))
        and any(term in lower for term in ("standard klipper", "klipper", "more control", "control"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Open Centauri Orca device control"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["yes", "Open Centauri", "Klipper"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Open Centauri", "Klipper", "Moonraker"], limit=8)
        test["requiredContractProof"] = ["Open Centauri", "Device tab", "Klipper", "Moonraker"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Open Centauri Orca Device-tab control questions as firmware/API capability analysis, not as a hard code/config artifact."
    if all(term in lower for term in ("openvsp", "xfoil", "su2", "qblade")) and any(term in lower for term in ("how do we get", "how do i get", "install", "download", "set up", "setup")):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Aero tool install plan"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["OpenVSP", "XFOIL", "SU2", "QBlade"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "OpenVSP", "XFOIL", "SU2", "QBlade", "smoke test"], limit=8)
        test["requiredContractProof"] = ["OpenVSP", "XFOIL", "SU2", "QBlade", "smoke test"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer aero-tool install questions as tooling/install plans, not CFD preflights requiring solver surfaces."
    if any(term in lower for term in ("sid inspection", "sid inspections", "sid")) and any(term in lower for term in ("hide", "remove", "disable", "wrapped into", "annual inspection", "annual inspection requirements")):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops SID inspection visibility cleanup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["SID", "annual inspection", "history"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "SID", "annual inspection", "history"], limit=8)
        test["requiredContractProof"] = ["SID", "annual inspection", "history", "UI"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Flight Ops SID visibility cleanup as local workflow/data preservation work, not web research."
    if (
        any(term in lower for term in ("seyboth", "maule", "fabric punch tester", "fabric punch testers"))
        and any(term in lower for term in ("dacron", "cotton", "linen"))
        and any(term in lower for term in ("not designed", "which", "following"))
    ):
        test["expectedProjectId"] = "aviation-engineering"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["C. Linen", "This is why", "You should also consider"]
        test["requiredTerms"] = normalize_terms(["C. Linen", "Seyboth", "Maule", "approved"], limit=8)
        test["requiredContractProof"] = ["C. Linen", "Seyboth", "Maule", "approved fabric system procedure"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer aviation maintenance quiz prompts directly and avoid routing them to CAD artifacts."
    if len(lower.strip()) < 80 and any(term in lower for term in ("how do i run the script", "how do we run the script", "run the script")):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Run script missing target"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["script path", "python3", "bash"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "script path", "python3", "bash"], limit=8)
        test["requiredContractProof"] = ["script path", "python3", "bash", "README"]
        test["anyTerms"] = []
        test["goal"] = "Context-only script follow-up: explain path/interpreter requirements and do not claim a script ran without the target file."
    if (
        any(term in lower for term in ("step file", ".step", ".stp"))
        and any(term in lower for term in ("most recent", "where is", "where's", "path", "location", "do we have", "is there"))
        and not any(term in lower for term in ("create", "generate", "make", "export", "regenerate", "convert"))
    ):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "STEP file path lookup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["STEP", "file"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "local", "path"], limit=8)
        test["requiredContractProof"] = ["STEP/STP path or no-match blocker", "local search scope", "existing-file boundary"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: STEP path lookups should report existing local file paths without being treated as generated CAD artifacts."
    if "grbl" in lower and "fusion" in lower and any(term in lower for term in ("ugs", "universal gcode sender", "output", "post")):
        test["expectedProjectId"] = "cnc-machining"
        test["expectedContractKind"] = "Fusion GRBL/UGS output"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["GRBL", "UGS", ".nc"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Fusion", "GRBL", "UGS"], limit=8)
        test["requiredContractProof"] = ["GRBL post", "UGS output file", "M6/units/WCS caveat"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: Fusion-to-UGS questions should answer the GRBL post/output path, not slicer filament or outdoor-material advice."
    if "cnc lab" in lower and any(term in lower for term in ("personalize", "rename", "tinman's cnc lab", "tinmans cnc lab")):
        test["expectedProjectId"] = "cnc-machining"
        test["expectedContractKind"] = "CNC Lab branding rename"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Tinman's CNC Lab", "branding", "verify"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Tinman's CNC Lab", "branding"], limit=8)
        test["requiredContractProof"] = ["Tinman's CNC Lab", "branding source", "launch/screenshot verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["goal"] = "Real chat-history regression: CNC Lab personalization should be handled as a branding/UI rename, not a fastener reference."
    if any(term in lower for term in ("macro", "macros")) and any(term in lower for term in ("limiting", "limit", "increase the limit", "too large", "length")):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper macro limit diagnostic"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Klipper", "Jinja", "split"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Klipper", "Jinja", "timeout"], limit=8)
        test["requiredContractProof"] = ["Klipper/Jinja/queue/host/UI limits", "increase caveat", "diagnostic path", "motion/heater safety caveat"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: macro-limit questions should be diagnostic and safety-aware, not blocked by fake artifact requirements."
    if is_cad_cnc_question_list_prompt(prompt):
        test["expectedContractKind"] = "Engineering question list"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["CAD questions", "CNC machining questions", "cost questions omitted"]
        test["goal"] = "Real chat-history regression: return the requested CAD/CNC engineering question bank, not Codex-improvement advice or generated CAD artifacts."
    if is_adhesive_pot_life_quiz_prompt(prompt):
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["A. Pot life", "This is why", "You should also consider"]
        test["goal"] = "Real chat-history regression: answer the supplied adhesive terminology quiz directly without a slow local-model path."
    if is_aircraft_wood_defect_quiz_prompt(prompt):
        test["expectedProjectId"] = "aviation-engineering"
        test["expectedContractKind"] = "Aircraft wood-defect quiz"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["C", "mineral streaks", "not accompanied by decay"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "compression failure", "splits"], limit=8)
        test["requiredContractProof"] = ["mineral streaks", "not accompanied by decay", "compression failure", "splits", "approved data"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer aircraft wood-defect quiz prompts directly in the aviation lane, not as CAD/STEP lookup work."
    if is_advisory_circular_source_quiz_prompt(prompt):
        test["expectedProjectId"] = "aviation-engineering"
        test["expectedContractKind"] = "Aviation maintenance quiz"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["C", "Government Printing Office Online Catalog"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "National Aeronautical Charting Office", "Office of Management and Budget"], limit=8)
        test["requiredContractProof"] = ["C. Government Printing Office Online Catalog", "not charting office", "not OMB"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["AERO_CFD_ACTION_REPORT", "CFD preflight", "OpenFOAM case"]))
        test["goal"] = "Real chat-history regression: answer advisory-circular source quiz prompts directly in the aviation lane, not as Aero/CFD artifacts."
    if is_lycoming_spark_plug_helicoil_prompt(prompt):
        test["expectedProjectId"] = "aviation-engineering"
        test["expectedContractKind"] = "Lycoming spark-plug Heli-Coil repair reference"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        if "kit" in lower or "for sale" in lower:
            test["directTerms"] = ["Yes", "ATS 4260-18", "Lycoming"]
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "ATS 4260-18", "aviation", "generic M18", "Lycoming"], limit=8)
            test["requiredContractProof"] = ["ATS 4260-18", "aviation kit", "generic M18 rejection", "manual/A&P-IA caveat"]
            test["goal"] = "Real chat-history regression: answer Lycoming spark-plug Heli-Coil kit follow-ups with the aviation kit lane and generic-kit rejection, not hobby-helicopter clarification."
        else:
            test["directTerms"] = ["18 mm", ".010", "P/N 64596-1"]
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "18 mm", ".010", "P/N 64596-1", "manual"], limit=8)
            test["requiredContractProof"] = ["18 mm", ".010 in. oversize", "P/N 64596-1", "manual/A&P-IA caveat"]
            test["goal"] = "Real chat-history regression: answer Lycoming spark-plug Heli-Coil tooling questions with approved-tooling caution, not generic drill/tap guesses."
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
    if is_corrosion_inspection_quiz_prompt(prompt):
        test["expectedProjectId"] = "aviation-engineering"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["C. It must be removed", "This is why", "You should also consider"]
        test["requiredTerms"] = normalize_terms(["C. It must be removed", "corrosion", "service limits"], limit=8)
        test["requiredContractProof"] = ["C. It must be removed", "corrosion must be removed", "service limits"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer aviation corrosion inspection quiz prompts directly and avoid routing them to source-backed research."
    if is_thin_material_corrosion_true_false_prompt(prompt):
        test["expectedProjectId"] = "aviation-engineering"
        test["expectedContractKind"] = "Aviation corrosion maintenance quiz"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["True", "0.0625", "mechanical tools"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "0.0625", "mechanical tools", "service limits"], limit=8)
        test["requiredContractProof"] = ["True", "0.0625 inch", "mechanical tools", "service limits"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer thin-material corrosion true/false prompts as aviation maintenance, not CAD reference."
    if is_reserve_military_id_location_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Official ID office lookup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["RAPIDS", "ID Card Office Online", "Robins AFB", "verify"]
        test["requiredTerms"] = normalize_terms(["RAPIDS", "Robins"], limit=8)
        test["requiredContractProof"] = ["RAPIDS", "ID Card Office Online", "Robins AFB", "verify"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer official local-service lookup questions with the official locator path and verification caveats, not stale invented office details."
    if is_mesh_to_step_or_fusion_scale_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Mesh to STEP/Fusion conversion"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["mesh file", "scale", "Fusion"]
        test["requiredTerms"] = normalize_terms(["mesh", "scale", "Fusion"], limit=8)
        test["requiredContractProof"] = ["mesh file/path blocker", "scale correction", "known dimension validation"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: mesh conversion requests without an attached/local mesh must name the file/path blocker and scale-validation workflow instead of claiming generated CAD."
    if is_mac_airdrop_receive_prompt(prompt):
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["AirDrop", "Wi-Fi", "Bluetooth"]
        test["goal"] = "Real chat-history regression: answer Mac AirDrop receive questions directly with local macOS steps instead of timing out on a model path."
    if is_tooth_pitch_valley_depth_missing_profile_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Tooth pitch and valley depth missing profile"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["tooth pitch", "valley depth", "profile"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "GT2", "2.0 mm pitch", "profile drawing"], limit=8)
        test["requiredContractProof"] = ["tooth pitch", "profile", "GT2", "2.0 mm pitch", "profile drawing"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer tooth pitch/valley-depth questions quickly with profile-dependent dimensional guidance instead of a slow generic clarification."
    if is_sv08_max_second_rail_gantry_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Mechanical design tradeoff"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["second rear rail", "gantry/carriage flex", "mass"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "stiffness", "alignment"], limit=8)
        test["requiredContractProof"] = ["stiffness benefit", "mass/alignment caveat"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Sovol SV08 Max second-rail gantry questions as mechanical design tradeoffs, not generic CAD references."
    if is_tinmanx_average_completion_time_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "TinManX average completion-time metric"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["TinManX", "last 36 hours", "task log"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "36 hours", "completed", "blocked"], limit=8)
        test["requiredContractProof"] = ["36-hour window", "completed duration divided by completed task count", "blocked/running task caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: preserve TinManX average-completion-time metric questions and require task-log evidence before giving a number."
    if is_tinmanx_schedule_status_prompt(prompt) and not is_tinmanx_average_completion_time_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Schedule status needs context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["TinManX", "completion date", "on track"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "TinManX", "package health", "conditional"], limit=8)
        test["requiredContractProof"] = ["schedule", "project or milestone", "status context request", "why/caveat shape"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer TinManX progress/timeframe questions with a conditional status and verification-gate basis instead of generic completion-time missing context."
    if (
        any(term in lower for term in ("good morning", "how are things going", "still on schedule", "on schedule"))
        and any(term in lower for term in ("schedule", "things going", "progress"))
        and not is_tinmanx_schedule_status_prompt(prompt)
        and not is_tinmanx_average_completion_time_prompt(prompt)
    ):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Schedule status needs context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Good morning", "specific project", "schedule", "guess"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "project", "schedule"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer schedule/status greetings warmly, but ask for the project or milestone before claiming schedule status."
    if (
        "slicer" in lower
        and any(term in lower for term in ("world class", "world-class", "elegant engineering", "on track"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Slicer progress status"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "world-class", "workflow", "regression"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "slicer", "workflow", "gaps"], limit=8)
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer TinmanX/Rocket Slicer progress-status questions directly and name the remaining quality gates."
    if (
        any(term in lower for term in ("tinmanx", "tinmanx1", "tinman x"))
        and any(term in lower for term in ("arc project", "tinmanx arc", "project"))
        and any(term in lower for term in ("please proceed", "proceed", "what is next", "what's next", "next step", "test print", "evaluate"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "TinmanX project continuation"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["TinmanX Arc", "test print", "preview"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "test print", "preview", "rerun"], limit=8)
        test["requiredContractProof"] = ["TinmanX Arc", "test print", "preview", "rerun"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: named TinmanX project continuations must proceed with the project-specific next step instead of asking what project is active."
    if (
        any(term in lower for term in ("speaker enclosure", "speaker enclosures", "speaker box", "enclosure"))
        and any(term in lower for term in ("6x9", "speaker", "speakers"))
        and any(term in lower for term in ("amplifier", "amp", "bluetooth", "blue tooth"))
        and any(term in lower for term in ("best speaker", "best speaker and amplifier", "best speaker and amp", "best amp", "best amplifier", "for this purpose", "outdoor", "outdoors", "backyard", "back yard"))
    ):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Speaker enclosure product recommendation"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["marine", "6x9", "amplifier"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "https://", "RMS", "acoustic"], limit=8)
        test["requiredContractProof"] = ["speaker/amp recommendation", "source URL", "required acoustic inputs", "model/validation caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = True
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: outdoor speaker/amp recommendations must include a clear pick, acoustic design caveats, and source URLs even when no CAD is generated."
    if (
        any(term in lower for term in ("creality print", "creality"))
        and any(term in lower for term in ("camera feed", "camera", "webcam", "video", "stream"))
        and any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex", "orca"))
    ):
        test["expectedProjectId"] = "orcaslicer-codex"
        test["expectedContractKind"] = "Orca Codex camera integration"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Creality Print", "Orca Codex", "camera stream URL"]
        test["goal"] = "Real chat-history regression: use Creality Print as evidence to discover the verified camera stream URL and wire it into Orca Codex, not unrelated firmware/stepper guidance."
    if (
        any(term in lower for term in ("fibreseeker 3", "fiberseeker 3", "fibreseek 3", "fiberseek 3", "fibreseeker", "fiberseeker"))
        and any(term in lower for term in ("rocket slicer", "rocketslicer", "rocket"))
        and any(term in lower for term in ("orca", "orcaslicer", "tinmanx"))
        and any(term in lower for term in ("import", "new fork", "fork of orca", "mechanics deeply", "theory of operation", "same nozzle", "fiber and plastic", "integration"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "FibreSeeker RocketSlicer-Orca integration"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["RocketSlicer-to-Orca", "FibreSeeker 3", "https://"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "capability", "continuous-fiber", "source"], limit=8)
        test["anyTerms"] = []
        test["minAnalyticalScore"] = 90
        test["goal"] = "Real chat-history regression: answer FibreSeeker/RocketSlicer-to-Orca integration prompts with source-backed migration architecture, not a narrow preview-only answer."
    if (
        any(term in lower for term in ("orca", "orcaslicer", "tinmanx"))
        and any(term in lower for term in ("acceleration settings", "max acceleration", "acceleration rate"))
        and any(term in lower for term in ("exceed", "exceeds", "warning"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca acceleration warning"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Orca warning", "acceleration", "machine limits"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "process", "printer profile", "safe"], limit=8)
        test["anyTerms"] = []
        test["minAnalyticalScore"] = 90
        test["goal"] = "Real chat-history regression: explain Orca acceleration-limit warnings as process-vs-machine profile mismatch, not generic printer specs."
    if any(term in lower for term in ("edit the user names", "edit user names", "edit usernames", "change user names", "change usernames")):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "User-name edit feature context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["user-name", "target app"]
        test["goal"] = "Real chat-history regression: handle username edit requests as target-app/user-store feature context, not a slow generic model path."
    if (
        any(term in lower for term in ("tinmanx1", "tinmanx"))
        and any(term in lower for term in ("splashscreen", "splash screen", "opening screen", "startup screen"))
        and any(term in lower for term in ("rev number", "revision number", "rev", "version", "build number"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "TinmanX splashscreen rev label"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["TinmanX1", "splashscreen", "Rev"]
        test["goal"] = "Real chat-history regression: answer TinmanX1 splashscreen revision-label requests directly, not with slicer profile parameter dumps."
    if (
        any(term in lower for term in ("ws2812b", "300led", "300 led", "multicolor", "addressable"))
        and any(term in lower for term in ("5 volts", "5v", "5 volts wattage", "60 watts", "60w"))
        and any(term in lower for term in ("16.4ft", "16.4 ft", "16.4 feet", "ip30", "indoor"))
    ):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "LED strip electrical/design reference"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["5 V", "12 A"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "60 W", "IP30"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: extract electrical/design constraints from pasted LED-strip specs without requiring CAD artifacts."
    if (
        any(term in lower for term in ("strip", "led", "lights", "status colors", "status colour", "status"))
        and any(term in lower for term in ("green", "other than green", "non-green", "appropriate color", "appropriate colour"))
        and any(term in lower for term in ("pulse", "slowly pulse", "pulsing", "breathe", "breathing"))
    ):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Status LED pulse upgrade"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["solid green", "non-green status", "slowly pulse", "nonblocking state machine"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "green", "pulse", "brightness", "1 meter"], limit=8)
        test["requiredContractProof"] = ["solid green", "non-green pulse", "nonblocking state machine", "LED length/brightness config"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer LED status-color pulse upgrade prompts as fast local software behavior, not generic chat."
    if (
        "strength" in lower
        and not is_speaker_pod_cad_prompt(prompt)
        and any(term in lower for term in ("slice", "slices", "per-slice", "per slice", "layer", "layers"))
        and any(term in lower for term in ("print orientation", "orientation", "all printers", "all printer"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Slice strength visualization"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["estimated Strength Lens", "not guaranteed"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "orientation", "load direction"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer slicer strength-visualization questions as estimated orientation/load/material guidance, not CAD artifacts."
    if is_output_gate_comparison_context_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Output gate comparison"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["actual output", "same gates", "deliverable"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "same gates", "deliverable", "proof"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: explain how to compare Codex CLI UI output against the same gates without inventing completion."
    if is_speed_setting_timeline_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Speed setting timeline"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "routine answers", "tool waits"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "routine answers", "tool waits", "balanced"], limit=8)
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["goal"] = "Real chat-history regression: answer Codex speed-setting timeline questions as local product guidance, not source-backed research."
    if is_low_wind_vawt_fusion_design_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Wind turbine CAD/aero design"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["low-wind", "VAWT", "Fusion 360"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "3 mph", "48 V", "300 x 300 x 245"], limit=8)
        test["requiredContractProof"] = ["labeled STEP/CAD/report path or explicit blocker", "3.0 mph / 48 V generator feasibility math", "validation/refinement limits"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["goal"] = "Real chat-history regression: answer low-wind vertical wind turbine blade requests as wind-turbine research and Fusion/CAD planning, not CAM stock-holder troubleshooting."
    if is_fusion_cam_stock_shoulder_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Fusion CAM stock/holder collision"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Stock + Shoulder", "tool", "holder"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Stock + Shoulder", "2D Contour", "Heights"], limit=8)
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["goal"] = "Real chat-history regression: answer Fusion CAM Stock + Shoulder warnings as a local Manufacture troubleshooting path, not source-backed research."
    if is_local_hardware_host_choice_prompt(prompt):
        test["expectedProjectId"] = "embedded-linux-images"
        test["expectedContractKind"] = "Local hardware host choice"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Pi 5 16GB", "KAMRUI", "printer/Linux appliance"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Pi 4", "Pi 5", "KAMRUI", "maintenance"], limit=8)
        test["requiredContractProof"] = ["clear recommendation", "why/caveat shape", "hardware tradeoff"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["goal"] = "Real chat-history regression: answer local hardware host choices with a clear Pi/mini-PC recommendation and maintenance tradeoffs, not generic context recovery."
    if any(term in lower for term in ("see your thoughts", "show your thoughts", "watch your thoughts", "see his thoughts", "show his thoughts", "watch his thoughts", "thoughts while you are working", "thoughts while he is working", "working notes")):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Visible progress notes"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["progress notes", "tool actions", "not hidden chain-of-thought"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "progress notes", "chain-of-thought", "warm", "Friendliness"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: explain visible progress notes, hidden chain-of-thought boundaries, and warmer response style clearly and directly."
    if any(term in lower for term in ("anything else", "anything more", "what else")) and any(term in lower for term in ("clean up", "cleanup", "cleaned up")) and any(term in lower for term in ("nice to have", "nice-to-have", "nice to haves", "nice-to-haves", "continuing", "continue")):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Cleanup before nice-to-haves"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "cleanup", "nice-to-have"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "checkpoint", "regression", "package health"], limit=8)
        test["requiredContractProof"] = ["cleanup gate", "checkpoint", "regression/package health", "nice-to-have boundary"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer cleanup-before-nice-to-have prompts as a fast Codex CLI UI gate decision instead of timing out through generic chat."
    if is_autonomous_work_queue_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Autonomous work queue"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["My recommendation", "active project queue"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "queue", "verification gate", "risk boundary"], limit=8)
        test["requiredContractProof"] = ["queue", "verification gate", "risk boundary"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer autonomous keep-moving-through-project prompts as a safe queue/verification/risk-boundary instruction, not a CAD or missing-context task."
    if any(term in lower for term in ("test questions", "test bank", "golden test", "golden tests", "regression", "question bank")) and any(term in lower for term in ("fusion 360", "fusion")) and any(term in lower for term in ("orca slicer", "orcaslicer", "orca")):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Fusion/Orca regression test-bank expansion"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Fusion 360", "Orca Slicer"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "test bank", "golden", "verification"], limit=8)
        test["requiredContractProof"] = ["Fusion 360", "Orca Slicer", "test bank", "golden", "verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: add Fusion 360 and Orca Slicer questions to the test bank instead of treating the explicit request as missing context or CAD export advice."
    if is_general_regression_test_bank_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "General regression test-bank expansion"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "real-world regression cases", "Codex CLI UI"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "test bank", "golden", "/api/run", "package health"], limit=8)
        test["requiredContractProof"] = [
            "3D printing/CNC/energy/aero/CFD/engineering/aviation domains",
            "test bank",
            "golden/regression",
            "/api/run",
            "package health",
        ]
        test["forbiddenTerms"] = sorted(
            set(
                test.get("forbiddenTerms", [])
                + [
                    "STRUCTURAL_FEA_REPORT",
                    "mechanical/structural preflight",
                    "CalculiX",
                    "OpenSCAD model",
                    "Fusion 360 script",
                ]
            )
        )
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: treat broad sample-question lists as test-bank expansion, not FEA, CAD, or Orca calibration."
    if any(term in lower for term in ("create a ui", "make a ui", "codex cli ui")) and any(term in lower for term in ("codex cli", "mirrors the ui", "this codex")):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex CLI UI creation architecture"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "standalone macOS desktop app", "Codex CLI UI"]
        test["requiredTerms"] = normalize_terms(["sidebar", "chat bar", "attachments", "clickable outputs", "steer", "verify"], limit=8)
        test["requiredContractProof"] = ["standalone macOS app", "sidebar/projects/chats", "chat bar controls", "verification gates"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Codex CLI UI creation requests as standalone-app architecture with workflow controls and verification gates, not a missing-artifact failure."
    if (
        "beacon" in lower
        and not is_offset1419_direct_prompt(prompt)
        and any(term in lower for term in ("xy verification", "x/y verification", "xy offset", "x/y offset", "offset calibration"))
        and any(term in lower for term in ("scan", "compare", "calibration", "verify", "verification"))
    ):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Beacon XY offset verification"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "same physical bed area", "X/Y offset"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "height map", "compare", "validation"], limit=8)
        test["requiredContractProof"] = ["same physical bed area", "height map comparison", "X/Y offset", "validation before saving"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Beacon XY verification as same-area scan comparison and offset validation, not a timeout."
    if "discord" in lower and any(term in lower for term in ("breakthrough", "break through", "breakthru")):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Autonomy/continuation status"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["keep moving", "active plan", "pause"]
        test["requiredTerms"] = normalize_terms(["task", "verify", "pause"], limit=8)
        test["requiredContractProof"] = ["continue active plan", "pause/safety conditions"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Discord-breakthrough follow-ups by verifying the shared context and continuing the active plan unless safety or goal changes require a pause."
    if (
        any(term in lower for term in ("flight tracker", "flightops", "flight ops", "pilot", "admin", "customer"))
        and any(term in lower for term in ("google calander", "google calendar", "calander", "calendar"))
        and any(term in lower for term in ("export", "sync", "multiple", "personal", "business"))
    ):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops Google Calendar sync"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["per-user", "Google Calendar", "multiple"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "pilot", "admin", "customer", "permissions", "https://developers.google.com/calendar"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Flight Ops Google Calendar export/sync feature requests directly with role, multi-calendar, and permission boundaries."
    if "porkbun" in lower and "passkey" in lower and any(term in lower for term in ("check", "make sure", "nothing more", "on my side")):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Passkey-assisted account check"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["passkey", "user-assisted", "domains active", "renewals"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Porkbun", "passkey"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: handle Porkbun/passkey account checks as user-assisted login with account-health review, never passkey-secret handling."
    if re.fullmatch(r"(?:let'?s|lets)\s+get\s+it\s+all\s+cleaned\s+up[.!? ]*", lower.strip()):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Cleanup target context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["cleaned up", "target"]
        test["goal"] = "Real chat-history regression: ask for the cleanup target and preserve archive-first validation instead of taking a slow model path."
    if re.search(r"^(?:what\s+is|what's|whats|where\s+is)\s+the\s+full\s+location\??$", lower.strip()):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Location target missing context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["I need the item"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "file path", "printer IP", "repo path"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer contextless full-location follow-ups with a fast target request instead of a slow model path."
    if (
        any(term in lower for term in ("single row", "one row", "single line", "one line"))
        and any(term in lower for term in ("questions", "instead of 2 columns", "instead of two columns", "2 columns", "two columns"))
    ):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Layout-only reformat"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Paste or attach", "preserving", "delimiter"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "context"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: handle single-row reformat requests as layout-only preservation, asking for the missing question list when needed."
    if len(lower.strip()) < 140 and "clean boot" in lower and any(term in lower for term in ("next step", "what's next", "whats next")):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["which machine"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "cleanly", "machine"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Context-only clean-boot follow-up: ask which machine/service and restore/setup step should continue instead of inventing a Codex-improvement task."
    if any(term in lower for term in ("start clean every time", "starts clean every time", "startup clean", "start clean")) and any(term in lower for term in ("fix this", "can we fix", "every time")):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Startup reliability context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = False
        test["directTerms"] = []
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "startup", "log", "restart", "health check"], limit=8)
        test["requiredContractProof"] = ["target context requirement", "clean-start verification loop"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer contextless clean-start fixes with a target request and startup diagnostic loop instead of stale project-specific contracts."
    if (
        any(term in lower for term in ("finish a task", "finishing a task", "task is complete", "task you can", "after finishing", "previous task", "previous one"))
        and any(term in lower for term in ("start the next task", "start the next tasks", "start the new task", "move on to the next task", "proceed to the next task", "next task", "next tasks"))
        and any(term in lower for term in ("keep going", "keep moving", "immediately", "immediatly", "until we are finished", "until it is complete"))
    ):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Autonomy/continuation status"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["continue", "active plan"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "continue", "pause", "verify"], limit=8)
        test["requiredContractProof"] = ["continue active plan", "pause/safety conditions"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer next-task continuation prompts as active-plan autonomy with verification and pause/safety gates."
    if is_approval_window_workaround_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Approval-window autonomy plan"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        if is_named_heartbeat_task_queue_prompt(prompt):
            test["directTerms"] = ["15-minute", "3-hour", "active plan"]
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "15-minute", "3-hour", "Wave Overhangs", "Strength Modeling Visualizer"], limit=8)
        else:
            test["directTerms"] = ["continue", "active plan"]
            test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "active project", "continue", "pause", "verify"], limit=8)
        test["requiredContractProof"] = ["safe-work plan", "approval queue", "risk/safety boundary"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer heartbeat/autonomy cleanup queues as a safe-work plan with approval queue and risk boundary."
    if is_long_heartbeat_mac_awake_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Approval-window autonomy plan"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["15-minute", "12-hour", "caffeinate"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "15-minute", "12-hour", "caffeinate"], limit=8)
        test["requiredContractProof"] = ["safe-work plan", "approval queue", "risk/safety boundary"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: preserve the 15-minute heartbeat, 12-hour window, and Mac-awake request without treating it as vague context."
    if is_heartbeat_active_tuning_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex UI heartbeat automation"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["I cannot prove", "5-minute heartbeat", "automation id"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "automation id", "average task completion time", "10-15 minutes"], limit=8)
        test["requiredContractProof"] = ["automation id", "interval tuning", "task duration"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer heartbeat active/tuning questions as verification plus interval tuning, not completion-time missing context."
    if is_single_test_command_context_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Single test command context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["I need the test file", "test name"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "pytest", "test_file.py::test_name", "runner"], limit=8)
        test["requiredContractProof"] = ["test name/path request", "pytest pattern"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["goal"] = "Real chat-history regression: answer contextless single-test rerun prompts with a test-name request and runner-specific command pattern."
    if (
        any(term in lower for term in ("boat house", "boathouse"))
        and any(term in lower for term in ("engineering drawing", "engineering drawings", "engineering grade", "plans", "specific engineering directions"))
        and any(term in lower for term in ("georgia code", "lake tobosofke", "lake tobesofkee", "lake tobosofkee", "macon georgia", "mary anne drive", "31220"))
    ):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Boathouse code/site planning boundary"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["boathouse design package", "engineering-grade", "official"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "survey", "Lake Tobesofkee", "Georgia", "PE", "permit"], limit=8)
        test["requiredContractProof"] = ["boathouse design package", "survey/parcel or site plan", "Lake Tobesofkee/Macon-Bibb verification", "Georgia PE or local authority review"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: handle boathouse engineering-plan requests as regulated site/code planning with source and PE boundaries, not fabricated final drawings."
    if is_ambiguous_device_path_comparison_prompt(prompt):
        test["expectedContractKind"] = "Ambiguous device path comparison"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Probably not", "ViVD"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "exact ViVD model", "target machine"], limit=8)
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: give a useful provisional recommendation for unclear ViVD/device path comparisons instead of a cold clarification or slow model path."
    if any(term in lower for term in ("flight tracker", "flightops", "flight ops")) and any(term in lower for term in ("start", "launch", "run", "open")):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops startup reminder"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Flightops_Tracker", "uvicorn", "127.0.0.1:8000"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "deploy_production_pi.sh", "health"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["Flightops_Tracker path", "uvicorn", "health/login check"]
        test["goal"] = "Real chat-history regression: answer Flight Ops Tracker startup reminders with the local app command and production Pi boundary, not UGS/CNC setup."
    if is_where_are_we_status_prompt(prompt):
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["active project", "current-state summary", "next step"]
        test["goal"] = "Real chat-history regression: answer broad status check-ins warmly and directly by asking for or using active project/progress evidence instead of timing out."
    if is_filament_load_park_wipe_pad_prompt(prompt):
        test["expectedContractKind"] = "Filament-load wipe-pad park"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["5 mm", "wipe pad", "safe Z clearance"]
        test["goal"] = "Real chat-history regression: answer filament-load wipe-pad park requests directly with safe macro behavior instead of timing out."
    if is_camera_stepper_motion_check_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Camera stepper motion check"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["Not from that description alone", "image/video frame", "position feedback"]
        test["requiredTerms"] = normalize_terms(
            ["This is why", "You should also consider", "camera", "position", "single-axis"],
            limit=8,
        )
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["requiredContractProof"] = ["image/video frame or commanded axis", "position/log evidence", "single-axis idle move"]
        test["goal"] = "Real chat-history regression: answer camera/stepper motion checks as printer safety diagnostics, not CAD work."
    if is_apus_mounting_hole_design_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Apus mounting-hole CAD constraint"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Apus", "M3 countersunk", "separate"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Apus", "M3 countersunk", "flush", "Dragon", "separate"], limit=8)
        test["requiredContractProof"] = ["Apus source CAD/drawing boundary", "M3 countersunk flush bottom", "separate Dragon collar/piece"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: preserve Apus mounting-hole CAD constraints instead of reducing the task to generic M3 drill/tap sizes."
    if is_m3_screw_hole_size_prompt(prompt):
        test["expectedContractKind"] = "Fastener reference"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["3.2 mm", "2.5 mm", "M3 x 0.5"]
        test["goal"] = "Real chat-history regression: answer M3 screw hole-size questions directly with clearance-hole and tap-drill distinctions instead of timing out."
    if is_fan_output_mapping_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper fan output mapping"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Fan 4", "PD14", "chamber2_fan"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Fan 4", "PD14", "chamber2_fan", "config"], limit=8)
        test["requiredContractProof"] = ["Fan 4 or requested fan", "PD14 or requested pin", "config verification caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer numbered Klipper fan-output mapping from local config evidence, not generic printer fan assumptions."
    if is_printer_reflash_pi_temp_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Printer-host reflash temperature monitor"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["backup", "vcgencmd", "electronics-bay"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "backup", "known-good", "vcgencmd", "electronics-bay", "Moonraker"], limit=8)
        test["requiredContractProof"] = ["backup", "known-good image or reflash method", "vcgencmd or thermal_zone0", "electronics-bay proxy caveat", "no invented updater"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer printer-host reflash plus Pi-temperature-monitor prompts with safe restore gates instead of generic Linux or invented vendor-updater commands."
    if is_max_ez_107_reachability_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Max EZ .107 reachability"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Max EZ", "192.0.2.107"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Moonraker", "ping", "192.0.2.107"], limit=8)
        test["requiredContractProof"] = ["192.0.2.107", "Moonraker", "ping"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["maxDurationMs"] = 5000
        test["goal"] = "Real chat-history regression: answer Max EZ .107 reachability checks with a fast read-only Moonraker/ping result, not a slow local-model path or generic checklist."
    if is_config_pin_comments_prompt(prompt):
        test["expectedContractKind"] = "Klipper config pin comments"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["PA8 # Fan 0", "PD14 # Fan 4", "Blocker"]
        test["goal"] = "Real chat-history regression: handle Klipper config pin-comment requests as a concrete config task with a path/blocker and validation boundary."
    if is_generator_candidate_context_prompt(prompt):
        test["expectedContractKind"] = "Research"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["BEIGOOD", "300 RPM", "https://www.ebay.com/itm/376862815958"]
        test["requiresSource"] = True
        test["goal"] = "Real chat-history regression: answer generator candidate follow-ups with the stored best pick, operating-point caveat, rejects, and source URL."
    if any(term in lower for term in ("load a model", "add a model", "model i selected", "model to be sliced", "model is added")) and any(
        term in lower for term in ("build plate", "plate", "placeholder", "set of blocks", "not what i selected", "no model shows")
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Slicer model/plate visibility bug"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["slicer workspace/plate-state bug", "not a CAD model problem"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "object-to-plate", "fit-to-view", "scene refresh", "add plate"], limit=8)
        test["requiredContractProof"] = ["slicer workspace/plate-state", "object-to-plate assignment", "scene refresh or fit-to-view", "add-plate test"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer slicer model-placeholder/build-plate visibility bugs as UI/plate-state diagnostics, not CAD/structural artifact work."
    if is_inverter_three_phase_input_prompt(prompt):
        test["expectedProjectId"] = "energy-power-research"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["do not feed", "split-phase", "3-phase"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "three-phase", "manual"], limit=8)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer inverter three-phase-input compatibility directly, not as a turbine or generator-model rerun."
    if (
        any(term in lower for term in ("3 mph", "3mph", "7 mph", "7mph", "15 mph", "15mph"))
        and any(term in lower for term in ("rpm", "rpm.s", "rpms", "torque"))
        and any(term in lower for term in ("rotor", "rotors", "wind"))
    ):
        test["expectedContractKind"] = "Wind turbine RPM/torque estimate"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["3 mph", "7 mph", "15 mph"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "torque", "rpm"], limit=8)
        test["requiresSource"] = False
        test["goal"] = "Real chat-history regression: answer wind-turbine RPM/torque follow-ups with first-order RPM estimates and the added-rotor torque/RPM tradeoff, not source-url research blocking."
    if (
        any(term in lower for term in ("wind from all directions", "from all directions", "all wind directions", "any wind direction", "omnidirectional"))
        and any(term in lower for term in ("opposite", "1 direction", "one direction", "make it worse", "worse with the wind"))
    ):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Omnidirectional wind design constraint"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "all directions", "opposite direction"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "0", "45", "90", "180", "worst-case"], limit=8)
        test["requiredContractProof"] = ["all directions", "opposite direction", "0/45/90/135/180 degree cases", "worst-case direction"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer omnidirectional wind-design constraints directly and avoid generic timeout."
    if (
        any(term in lower for term in ("another rotor", "one more rotor", "extra rotor", "3 more rotors", "three more rotors"))
        and any(term in lower for term in ("retest", "re-test", "rerun", "run again", "help", "torque", "rpm", "throat"))
    ):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Rotor count follow-up"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["rotor", "torque", "active CAD"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "drag", "startup torque", "RPM", "generator"], limit=8)
        test["requiredContractProof"] = ["rotor tradeoff", "system/geometry or result-path blocker", "why/caveat shape"]
        test["goal"] = "Real chat-history regression: answer added-rotor wind-turbine follow-ups as engineering tradeoffs with a CAD/result-path blocker, not fake retest claims."
    if is_outdoor_continuous_fiber_fan_material_prompt(prompt):
        test["expectedContractKind"] = "Outdoor continuous-fiber fan material comparison"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["ASA", "PCTG", "94 mm", "1000 RPM"]
        test["requiresSource"] = True
        test["goal"] = "Real chat-history regression: compare outdoor continuous-fiber PCTG versus ASA for a rotating fan with material source anchors and validation caveats."
    if is_rocket_fiber_placement_verification_prompt(prompt):
        test["expectedContractKind"] = "Rocket fiber placement verification"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Not automatically", "fiber path is visible", "Rocket Slicer"]
        test["requiredTerms"] = normalize_terms(["same layer", "G-code", "sidecar", "origin"], limit=8)
        test["requiredContractProof"] = ["Rocket emitted path", "same layer/origin", "G-code/sidecar validation"]
        test["goal"] = "Real chat-history regression: distinguish visible continuous-fiber preview from verified Rocket-matched fiber placement."
    if is_cad_repair_before_return_prompt(prompt):
        test["expectedContractKind"] = "CAD repair-before-return expectation"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "CAD", "repair"]
        test["requiredTerms"] = normalize_terms(["repaired geometry", "exact blocker", "validation"], limit=8)
        test["requiredContractProof"] = ["repaired geometry", "exact blocker", "validation report"]
        test["goal"] = "Real chat-history regression: answer CAD repair-before-return expectations as a policy and proof gate, not a generic runtime blocker."
    if is_inserted_filament_switch_state_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Filament switch state verification"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["present", "true", "live sensor state"]
        test["requiredTerms"] = normalize_terms(["filament_detected", "pin", "inversion"], limit=8)
        test["requiredContractProof"] = ["present/true state", "filament_detected", "pin/inversion check"]
        test["goal"] = "Real chat-history regression: answer filament-switch state checks with the expected live sensor proof instead of timing out or telling Tinman to check it himself."
    if is_orca_codex_vs_tinmanx_strategy_prompt(prompt):
        test["expectedProjectId"] = "orcaslicer-codex"
        test["expectedContractKind"] = "Orca Codex build strategy"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Modify Orca Codex first", "faster", "TinManX"]
        test["requiredTerms"] = normalize_terms(["supports", "Strength Lens", "FibreSeeker", "verification"], limit=8)
        test["requiredContractProof"] = ["Orca Codex recommendation", "supports/strength/FibreSeeker scope", "migration verification gates"]
        test["goal"] = "Real chat-history regression: answer Orca Codex versus TinManX build-strategy questions with a clear recommendation, not wrong-build shortcut repair."
    if is_orca_codex_wrong_build_prompt(prompt):
        test["expectedProjectId"] = "orcaslicer-codex"
        test["expectedContractKind"] = "OrcaSlicer Codex build alignment"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Orca Codex", "TinmanX", "launcher"]
        test["requiredTerms"] = normalize_terms(["this is why", "verify", "profile", "path"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["OrcaSlicer Codex target", "TinmanX exclusion", "verification gates"]
        test["goal"] = "Real chat-history regression: answer Orca Codex wrong-build/launcher alignment questions instead of applying the broader Orca-vs-TinManX strategy test."
    if is_tinmanx_orca_codex_slicer_ready_build_next_step_prompt(prompt):
        test["expectedProjectId"] = "orcaslicer-codex"
        test["expectedContractKind"] = "TinmanX Orca Codex slicer-ready build gate"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Next step", "slicer-ready"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "package health", "profile", "slice", "preview", "G-code"], limit=8)
        test["requiredContractProof"] = ["package health", "profiles visible", "slice test", "G-code or preview"]
        test["anyTerms"] = []
        test.pop("contextDependent", None)
        test["goal"] = "Real chat-history regression: answer TinmanX/Orca slicer-ready next-step prompts with launch/profile/slice/preview/G-code verification gates, not generic context recovery."
    if is_slicer_parsing_error_repair_prompt(prompt):
        test["expectedProjectId"] = "orcaslicer-codex" if any(term in lower for term in ("orca codex", "orcaslicer codex", "orcaslicer-codex")) else "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca/TinmanX parsing repair"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "shared Orca profile/config", "active app"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "archive", "aliases", "verify"], limit=8)
        test["requiredContractProof"] = ["shared profile/config", "archive", "active app", "aliases", "JSON/profile scan"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Orca/TinManX parsing-error repair requests with archive-first local profile/config/log checks instead of a generic housekeeping contract."
    if is_engineering_filament_cost_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Filament price ballpark"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["PPS-CF", "$", "kg"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "$", "kg", "current"], limit=8)
        test["requiredContractProof"] = ["price range", "current-price caveat", "material-class caveat"]
        test["goal"] = "Real chat-history regression: answer engineering-filament cost questions with a useful ballpark and live-price caveat instead of timing out or requiring stale unrelated terms."
    if "snapmaker" in lower and "u1" in lower and any(term in lower for term in ("0.6 nozzle", "0.6mm nozzle", "0.6-mm nozzle", "0.6 mm nozzle")) and any(term in lower for term in ("machine profile", "printer profile", "profile")):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Snapmaker U1 0.6 Orca profile visibility"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Snapmaker U1", "0.6 nozzle", "not verified"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Orca", "installed profile", "visible"], limit=8)
        test["requiredContractProof"] = ["Snapmaker U1", "0.6 nozzle", "installed profile store", "Orca/TinManX UI visibility"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer missing Snapmaker U1 0.6 Orca profile visibility as an installed-profile verification task, not white-paper or live-printer status."
    if "cc1" in lower and any(term in lower for term in ("cad file", "cad source", "source cad", "step", "stl")) and any(term in lower for term in ("housing", "runout", "gears", "gear")):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "CAD source lookup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["CC1", "CAD", "source"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "5-15 mm", "measured", "housing"], limit=8)
        test["requiredContractProof"] = ["source path or blocker", "fallback model plan"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer CC1 runout-housing CAD-source requests as a source lookup/fallback-model task, not mechanical FEA."
    if any(term in lower for term in ("what program", "which program", "program is specifically responsible", "process is responsible")) and any(term in lower for term in ("responsible", "causing", "specific")):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Responsible-program diagnostic context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["responsible program", "symptom", "process"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "logs", "file", "network"], limit=8)
        test["requiredContractProof"] = ["symptom or target context", "process/log checks", "proof before naming program"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer responsible-program follow-ups with local diagnostic evidence steps, not web-source research blocking."
    if is_apple_m2_workstation_disadvantage_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Apple M2 workstation fit"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["M2", "unified memory", "local AI"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "CAD", "slicer", "GPU"], limit=8)
        test["requiredContractProof"] = ["M2", "unified memory", "local AI/CAD/CFD/slicer workload", "upgrade direction"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer M2 workstation-fit questions directly for Tinman's local AI/CAD/slicer workflow instead of timing out or giving generic Apple advice."
    if is_mac_security_sweep_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Mac security sweep"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["read-only", "Mac security sweep"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Gatekeeper", "FileVault"], limit=8)
        test["requiredContractProof"] = ["macOS", "Gatekeeper", "FileVault", "firewall", "SIP"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Mac security sweep requests with a read-only local status snapshot, not a pasted shell script."
    if is_epson_wf2960_network_black_only_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Epson WF-2960 network/black-only check"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["WF-2960", "CUPS"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "black-only", "color cartridge"], limit=8)
        test["requiredContractProof"] = ["WF-2960", "CUPS or IPP or ARP", "black-only", "empty color cartridge caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Epson WF-2960 discovery/black-only requests from local CUPS/network evidence and explain the cartridge-lock limit."
    if is_cad_model_source_search_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "CAD source search"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["CAD", "candidate"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "source", "verification"], limit=8)
        test["requiredContractProof"] = ["source CAD URL/path or explicit search blocker", "CAD model criteria", "verification boundary"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer CAD-model source searches with a found path/source or exact blocker, not generic CAD-reference export advice."
    if is_compact_m5_barbed_elbow_cad_search_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "CAD source search"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["M5", "45-degree", "90-degree", "barbed"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "push", "source"], limit=8)
        test["requiredContractProof"] = ["source CAD URL/path or explicit search blocker", "M5 fitting criteria", "generated-candidate fallback boundary"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer compact M5 fitting CAD searches with the M5, 45/90-degree, barbed/push criteria visible."
    if is_scad_to_stl_step_conversion_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "SCAD to STL/STEP conversion"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["STL", "STEP", "OpenSCAD"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "FreeCAD", "verification"], limit=8)
        test["requiredContractProof"] = ["OpenSCAD/STL", "STEP/FreeCAD", "verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer SCAD-to-STL/STEP conversion questions as conversion workflow guidance, not CAD source search."
    if is_petg_cf_part_cooling_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Filament part-cooling direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "PETG-CF", "part cooling"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "20-40", "layer bonding"], limit=8)
        test["requiredContractProof"] = ["PETG-CF", "20-40 percent", "layer bonding", "bridges/overhangs"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer PETG-CF part-cooling questions as direct filament-process guidance, not source-evidence research."
    if is_simulator_package_quality_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Simulator package-quality gate"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["simulator", "package", "acceptance gate"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "pass/fail report", "hardware"], limit=8)
        test["requiredContractProof"] = ["simulator", "package", "acceptance gate", "pass/fail report", "hardware proof boundary"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer final simulator/package-quality prompts with a release acceptance gate instead of timing out in local worker chat."
    if is_codex_macos_tahoe_toolchain_followup_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "macOS/Tahoe toolchain compatibility follow-up"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Stay on", "15.x", "Tahoe"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "preflight", "toolchain"], limit=8)
        test["requiredContractProof"] = ["15.x installed", "26.x Tahoe-only", "preflight"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer short 15.x-installed/26.x-Tahoe-only follow-ups as a local Codex toolchain compatibility decision with a preflight path."
    if is_better_design_missing_context_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Better design missing context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Probably", "active design", "goal"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "compare", "options"], limit=8)
        test["requiredContractProof"] = ["active design", "goal", "compare 2-3 design options"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer vague better-design follow-ups by asking for active design/goal context instead of demanding CAD artifacts."
    if any(term in lower for term in ("+ button", "plus button")) and any(term in lower for term in ("add a file", "add files", "attach", "file picker", "finder", "functional")):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex UI file-picker feature"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "file picker", "drag-and-drop"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "attachment", "run payload"], limit=8)
        test["requiredContractProof"] = ["file picker", "attachment path", "verification path"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer plus-button attachment requests as Codex CLI UI file-picker behavior, not stale CAD/rotor metadata."
    if (
        any(term in lower for term in ("github", "git hub"))
        and any(term in lower for term in ("upload", "uploaded"))
        and any(term in lower for term in ("100 files", "100 file", "more than 100", "hundred files", "100 at a time"))
        and any(term in lower for term in ("upload the rest", "the rest", "remaining", "re organize", "reorganize", "organize them"))
    ):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex GitHub bulk-upload continuation"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "local upload", "GitHub"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "100-file", "git remote", "privacy", "batch"], limit=10)
        test["requiredContractProof"] = ["100-file upload limit", "local upload records", "git remote/target repo", "privacy/package checks"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: continue >100-file GitHub/upload work from local upload records and repo context before asking Tinman to re-upload."
    if (
        any(term in lower for term in ("codex chats", "codex chat", "my chats", "our chats", "chat history"))
        and any(term in lower for term in ("new codex", "codex cli ui", "new codex ui", "new codex app"))
        and any(term in lower for term in ("upload", "import", "knows the history", "know the history", "history of what we are doing", "history of what we're doing"))
    ):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex chat-history import"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "curated local history"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "sanitize", "project", "source vault", "golden tests"], limit=10)
        test["requiredContractProof"] = ["local Codex sessions", "sanitize secrets", "project summaries/source vault", "golden tests", "verification questions"]
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["codex-cli sessions export", "codex-cli sessions import"]))
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: import Codex chats as sanitized local memory/source-vault/test-bank material, not fake raw transcript upload commands."
    if "complete flow" in lower and "simulator" in lower and any(term in lower for term in ("build", "test")):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["I need", "project", "simulator"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "project", "simulator"], limit=8)
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: ask for the specific flow/simulator target instead of attaching stale eject or disk-volume context."
    if any(term in lower for term in ("terminate", "pause", "hold")) and any(term in lower for term in ("mechanical inspection", "inspection is complete")):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Pause/terminate action"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Understood", "pause"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "mechanical inspection", "resume"], limit=8)
        test["requiredContractProof"] = ["pause acknowledgment", "resume condition"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: pause/terminate when Tinman asks for mechanical inspection instead of asking for missing context."
    if is_plateau_terminate_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Plateau terminate action"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Terminate", "stopping point"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "terminate", "stopping point", "safe"], limit=8)
        test["requiredContractProof"] = ["terminate acknowledged", "stopping point", "safe idle or saved state"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer plateau termination requests with a clear stop/receipt boundary instead of a generic goodbye."
    if is_driver_temps_missing_context_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Driver temperature missing target"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["target", "driver"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "driver", "Moonraker", "read-only"], limit=8)
        test["requiredContractProof"] = ["target device request", "driver ambiguity", "read-only status path"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer driver-temperature status prompts with a target request and likely Klipper read-only path."
    if is_pump_data_mcu_temp_missing_context_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Pump/MCU status missing target"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["target printer", "pump", "MCU"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "pump", "MCU", "Moonraker", "read-only"], limit=8)
        test["requiredContractProof"] = ["target printer request", "pump object/data path", "MCU temperature status path"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer pump-data and MCU-temperature follow-ups as printer/Klipper status checks with a safe target request."
    if is_petcf_pei_bed_temp_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "PET-CF PEI bed temperature"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["80 C", "PET-CF"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "80 C", "PET-CF", "PEI"], limit=8)
        test["requiredContractProof"] = ["80 C", "70-75 C tune range", "PET-CF not PETG-CF"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer PET-CF PEI bed-temp questions as direct local filament tuning guidance without source-url gating."
    if is_fiberon_petcf_annealing_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Fiberon PET-CF annealing guidance"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["coupon", "80 C"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "coupon", "80 C", "slow-cool"], limit=8)
        test["requiredContractProof"] = ["not mandatory", "coupon", "80 C", "slow-cool"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Fiberon PET-CF annealing with cautious coupon validation instead of unsupported vendor claims."
    if is_max_ez_wlan_followup_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Max EZ WLAN association"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["wlan1", "Moonraker"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "wlan1", "Moonraker", "association"], limit=8)
        test["requiredContractProof"] = ["wlan1", "association or priority", "Moonraker verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Max EZ wlan1/association follow-ups as printer-host networking instead of Mac Wi-Fi or generic context."
    if is_qidi_plus4_usb_wifi_dongle_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi Plus 4 USB Wi-Fi dongle utilization"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "USB Wi-Fi dongle"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "lsusb", "ip link", "default route", "Moonraker"], limit=8)
        test["requiredContractProof"] = ["USB Wi-Fi dongle", "lsusb", "ip link or iw dev", "default route or metric", "Moonraker/SSH verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["What to do once", "Let me know if you can bring the printer online", "resetting the board"]))
        test["goal"] = "Real chat-history regression: answer Plus 4 USB Wi-Fi dongle utilization as printer-host network verification, not generic user-run SSH instructions."
    if is_printer_inventory_ip_update_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Printer inventory IP update"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["local printer inventory", "Qidi"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Qidi Plus 4", "Qidi Max EZ", "local printer inventory", "UI"], limit=8)
        test["requiredContractProof"] = ["local inventory", "Qidi Plus 4", "Qidi Max EZ", "database or UI", "backup or stale/collision handling"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["use the printers' own web interface", "go to settings", "log in to each printer", "SET_HOST_IP", "change the addresses on the printer"]))
        test["goal"] = "Real chat-history regression: printer IP updates should change/confirm Codex CLI UI's local inventory and UI lookup addresses, not tell Tinman to change printer network settings."
    if is_printer_inventory_ip_list_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Printer inventory IP list"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["current saved printer IP list", "Qidi"]
        test["requiredTerms"] = normalize_terms(["current saved printer IP list", "Qidi Plus 4", "Qidi Max EZ", "saved inventory", "live reachability"], limit=8)
        test["requiredContractProof"] = ["saved printer IP list", "Qidi or printer names", "live status caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["requires web research", "DHCP advice", "you can check it yourself"]))
        test["goal"] = "Real chat-history regression: printer IP list questions should read saved local inventory and separate saved addresses from live reachability."
    if is_rat_rig_macro_folder_save_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Rat Rig macro folder save"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Rat Rig", "macro"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Klipper", "printer.cfg", "validation"], limit=8)
        test["requiredContractProof"] = ["Rat Rig config folder", "macro filename/body or blocker", "printer.cfg include", "Klipper config validation"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["let me know the filename", "just let me know", "stale folder"]))
        test["goal"] = "Real chat-history regression: Rat Rig macro-folder save requests must find the config target, preserve missing-content blockers, and name validation."
    if is_qidi_load_unload_speed_match_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi load/unload macro speed match"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Qidi"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "load", "unload", "max_extrude_only_velocity", "backup"], limit=8)
        test["requiredContractProof"] = ["load/unload macro variables", "max_extrude_only_velocity or clamp", "backup", "Klipper config validation"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["Quick tweak", "1️⃣", "2️⃣"]))
        test["goal"] = "Real chat-history regression: Qidi load/unload speed matching should be a backup-first Klipper macro comparison, not a slow config dump."
    if is_qidi_camera_refresh_rate_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Qidi camera refresh-rate tuning"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Qidi camera"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "FPS", "camera service", "10-15 FPS", "UI verification"], limit=8)
        test["requiredContractProof"] = ["camera service/config", "FPS or stream endpoint", "10-15 FPS target", "restart camera service", "UI verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["1️⃣", "2️⃣", "nano /home/pi/printer_data/config/moonraker.conf"]))
        test["goal"] = "Real chat-history regression: Qidi camera refresh-rate tuning should identify camera-service proof and validation, not dump SSH homework."
    if is_max_ez_process_profile_tuning_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Max EZ process/profile tuning"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Max EZ", "profile"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Max EZ", "profile", "acceleration"], limit=8)
        test["requiredContractProof"] = ["Max EZ", "0.4/0.8/1.0 or acceleration", "profile visibility or validation"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Max EZ quality-first process/profile follow-ups without slow generic routing."
    if is_adaptive_heat_soak_status_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Adaptive heat-soak status"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["fixed 5-minute", "adaptive"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "adaptive", "PRINT_START", "5-minute"], limit=8)
        test["requiredContractProof"] = ["fixed 5-minute soak", "adaptive stability checks", "PRINT_START or macro proof"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: distinguish fixed timed heat soak from true adaptive heat-soak behavior."
    if is_router_optimization_login_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Router optimization audit"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["router audit", "backup"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "router", "backup", "read-only"], limit=8)
        test["requiredContractProof"] = ["router backup/export", "read-only inventory", "before/after verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer router optimization as a safe local network audit, not CAD or generic chat."
    if is_router_access_permission_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Router access permission"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "permission", "router"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "passwords", "backup", "supervised"], limit=8)
        test["requiredContractProof"] = ["supervised local session", "read-only config export", "no pasted passwords", "backup/rollback"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["real-world load", "fit, and environment", "unable to access your router directly"]))
        test["goal"] = "Real chat-history regression: answer router access permission with supervised local access and password-safety boundaries, not a cold refusal or unrelated caveat."
    if is_ssh_extended_firmware_capability_prompt(prompt):
        test["expectedProjectId"] = "embedded-linux-images"
        test["expectedContractKind"] = "SSH firmware capability"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "SSH"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "SSH", "backup", "rollback"], limit=8)
        test["requiredContractProof"] = ["SSH access", "read-only inventory", "backup/rollback", "feature gap list"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer SSH-enabled firmware access as capability plus backup-first gates."
    if is_qidi_max_ez_adaptive_heat_soak_feature_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Max EZ adaptive heat-soak feature status"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["not assume", "Max EZ"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Max EZ", "PRINT_START", "adaptive"], limit=8)
        test["requiredContractProof"] = [".145 Qidi caveat", "Max EZ active config", "adaptive stability checks"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Max EZ adaptive heat-soak feature status from macro/config proof, not generic heat-soak theory."
    if is_toolhead_runout_switch_remap_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Toolhead runout switch remap"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["probably", "toolhead"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "toolhead", "filament_switch_sensor", "pinout"], limit=8)
        test["requiredContractProof"] = ["toolhead board pinout", "spare input", "filament_switch_sensor", "sensor-state test"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer toolhead runout switch remap as Klipper IO mapping and verification, not CAD."
    if is_orca_calibration_image_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca calibration image reading"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Orca", "Save this"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Orca", "save", "filament"], limit=8)
        test["requiredContractProof"] = ["Orca", "visual evidence", "Save this"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer calibration-image questions as local visual tuning, not web research or CAD artifacts."
    if is_he0_light_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Chamber light heater-output check"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["Do not assume", "HE0"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "HE0", "Klipper", "output_pin"], limit=8)
        test["requiredContractProof"] = ["board schematic/pin map", "Klipper config", "output_pin or light macro"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: route chamber-light HE0/HE1 questions to Klipper electrical/control safety instead of slow generic chat."
    if "layer shift" in lower and any(term in lower for term in ("each layer", "every layer", "print progresses", "look into")):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Layer-shift diagnostic process review"
        test["expectedContractGate"] = "pass"
        test["contextDependent"] = False
        test["directAnswer"] = True
        test["directTerms"] = ["layer shift", "mechanical"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "belt", "pulley", "acceleration"], limit=8)
        test["requiredContractProof"] = ["process judgment", "X-axis checks", "speed-step plan"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: route early layer-shift follow-ups to printer diagnostics with a concise inspection path."
    if (
        any(term in lower for term in ("last print", "previous print", "most recent print", "recent print"))
        and any(term in lower for term in ("log", "logs", "history", "record"))
        and any(term in lower for term in ("filament", "material", "pc", "petg", "pctg", "asa", "abs", "nylon", "pa", "profile"))
        and any(term in lower for term in ("profile", "preset", "where to find", "where is", "where it is"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Last-print filament profile lookup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["log", "profile", "filament"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "log", "profile", "spool"], limit=8)
        test["requiredContractProof"] = ["local log/profile evidence", "active filament profile path", "last-spool uncertainty boundary"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer last-print filament/profile lookups with local log/profile evidence and a useful profile path instead of timing out."
    if "linear bearing" in lower and any(term in lower for term in ("carbon fiber tube", "carbon fibre tube", "carbon tube")) and any(term in lower for term in ("move", "on top", "relocate")):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Linear-bearing carbon-tube CAD follow-up"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["linear bearing", "carbon fiber tube", "active CAD"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "load", "clearance", "alignment"], limit=8)
        test["requiredContractProof"] = ["linear bearing", "carbon fiber tube", "load path/clearance", "active CAD"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer carbon-tube linear-bearing relocation follow-ups with mechanical tradeoffs and an active-CAD boundary, not a timeout."
    if "cc" in lower and "filament" in lower and any(term in lower for term in ("runout protocol", "runout", "run-out")) and any(term in lower for term in ("both cc machines", "cc machines", "cc1", "cc2")):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "CC filament runout protocol recall"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["at least one", "both CC machines", "immediate pause"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "timer", "verify"], limit=8)
        test["requiredContractProof"] = ["history uncertainty boundary", "immediate-pause path", "verify both configs"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: recall Centauri Carbon filament-runout protocol changes without overclaiming both machines."
    if (
        "strength" in lower
        and not is_speaker_pod_cad_prompt(prompt)
        and any(term in lower for term in ("slider", "slider bar", "tensile strength", "x y and z", "x/y/z", "xyz"))
        and any(term in lower for term in ("slicing", "slicer", "prepare a part", "database"))
    ):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Slice strength visualization"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["estimated Strength Lens", "not guaranteed"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "orientation", "load direction", "material"], limit=8)
        test["requiredContractProof"] = ["estimated Strength Lens concept", "orientation/load/material caveat", "preview/report behavior"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer slicer strength-slider questions as estimated material/orientation guidance, not printer runout or fake lab strength."
    if any(term in lower for term in ("h2d", "x1c", "x1 carbon", "bambu")) and any(term in lower for term in ("ip", "ip address", "access code", "access_code", "lan code", "printer code", "serial number")):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Bambu printer IP/access-code lookup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["IP", "access code", "local inventory"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "verified", "local", "missing"], limit=8)
        test["requiredContractProof"] = ["H2D or Bambu target", "IP/access code", "local inventory/config source or missing-record boundary"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Bambu IP/access-code questions from verified local inventory/config, with a credential-safe missing-record boundary instead of guessing."
    if any(term in lower for term in ("orca", "orcaslicer", "tinmanx")) and "bambu studio" in lower and any(term in lower for term in ("x1c", "x1 carbon")) and "h2d" in lower and any(term in lower for term in ("machine", "process", "filament", "fllament", "profile", "profiles")):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["taskContractKind"] = "Bambu Studio profile-sync audit"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Orca/TinManX profile-sync audit", "Bambu Studio", "X1C", "H2D"]
        test["requiredTerms"] = normalize_terms(["machine", "process", "filament", "backup", "verify"], limit=8)
        test["requiredContractProof"] = ["Bambu Studio", "X1C", "H2D", "machine/process/filament", "backup/verification"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: answer Bambu Studio to Orca/TinManX profile-sync requests as a field-by-field audit with backup and installed-app verification."
    if any(term in lower for term in ("mcmaster", "mcmaster-carr", "mc master")) and any(term in lower for term in ("m5", "m 5")) and any(term in lower for term in ("4mm", "4 mm")) and any(term in lower for term in ("compact", "too big", "5225k923", "toolhead", "constraints")):
        test["expectedProjectId"] = "research-parts-reference"
        test["expectedContractKind"] = "Compact M5 4mm fitting selection"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["M5 x 0.8", "4 mm", "5225K923"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "https://www.mcmaster.com", "body", "height", "wrench"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["M5", "4 mm", "McMaster source/search path", "body diameter or height"]
        test["goal"] = "Real chat-history regression: answer compact McMaster fitting searches by preserving M5 thread, 4 mm tube OD, source/search path, and toolhead packaging constraints."
    if "amazon.com/dp/" in lower and any(term in lower for term in ("what about this", "how about this", "this one", "would this")):
        test["expectedProjectId"] = "research-parts-reference"
        test["expectedContractKind"] = "Amazon product delta follow-up"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Amazon", "delta", "listing"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Source to check", "delta"], limit=8)
        test["requiredContractProof"] = ["Amazon source link or ASIN", "delta criteria", "fetch/blocker boundary"]
        test["anyTerms"] = []
        test["goal"] = "Real chat-history regression: Amazon link follow-ups should compare the listing delta against the current shortlist without fake current-price/spec claims."
    if any(term in lower for term in ("power train", "powertrain", "drivetrain", "drive train")) and "motor" in lower and "battery" in lower and any(term in lower for term in ("specific models", "recommend", "would you recommend", "which")):
        test["expectedProjectId"] = "energy-power-research"
        test["expectedContractKind"] = "Powertrain motor/battery recommendation"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["do not pick specific", "RPM", "torque"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "motor", "battery", "controller"], limit=8)
        test["requiredContractProof"] = ["matched powertrain system", "RPM/torque/load/runtime inputs", "sourced shortlist boundary"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["goal"] = "Real chat-history regression: answer powertrain component recommendation prompts with a sizing/evidence boundary instead of fake model picks or CAD artifact gates."
    if is_controller_fan_airflow_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Controller fan airflow direction"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Blow cool air", "MCU", "exhaust path"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "drivers", "exhaust"], limit=8)
        test["requiredContractProof"] = ["blow onto MCU/drivers", "exhaust path", "temperature/dust/wire caveat"]
        test["goal"] = "Real chat-history regression: answer controller-fan airflow direction directly instead of timing out on a generic model path."
    if is_core_one_l_calibration_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Printer calibration run plan"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Core One L calibrations", "idle", "profile"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "temperature tower", "pressure advance", "first-layer"], limit=8)
        test["requiredContractProof"] = ["ordered calibration sequence", "idle/reachable safety gate", "profile/print validation"]
        test["goal"] = "Real chat-history regression: answer Core One L calibration-run requests with a safe ordered calibration plan, not a CAD-repair or CAD-reference contract."
    if is_tailscale_ssh_definition_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Tailscale versus SSH definition"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["No", "Tailscale", "SSH"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "remote shell"], limit=8)
        test["requiredContractProof"] = ["Tailscale is VPN/overlay", "SSH is remote shell protocol", "can carry SSH"]
        test["goal"] = "Real chat-history regression: explain that Tailscale is not SSH but can carry or provide SSH access."
    if is_rocket_slicer_machine_data_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Rocket Slicer machine data pull"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Rocket", "machine data", "G-code header"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "G-code header", "differential harness"], limit=8)
        test["requiredContractProof"] = ["Rocket profiles/export", "G-code header", "differential harness"]
        test["goal"] = "Real chat-history regression: answer Rocket Slicer machine-data pull requests with local profile/export/G-code evidence, not a FibreSeek tool-map audit."
    if "rocket" in lower and any(term in lower for term in ("backend", "limitations", "output", "will output", "what rocket will output")) and any(term in lower for term in ("last recommendation", "recommendation", "going with", "cause any issues", "cause issues")):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Rocket backend output compatibility"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Rocket", "G-code", "machine-limit"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "dry-run", "compare"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["G-code", "machine-limit", "dry-run"]
        test["goal"] = "Real chat-history regression: answer Rocket backend-output compatibility follow-ups with G-code and machine-limit validation, not generic source-backed research."
    if any(term in lower for term in ("active chamber heating", "active chamber", "chamber heating")) and any(term in lower for term in ("dynamic", "by filament", "filament selected", "selected filament")):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Orca active chamber dynamic setting"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["selected filament", "chamber", "profile"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "enable", "setpoint"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["selected filament", "chamber profile key", "verification path"]
        test["goal"] = "Real chat-history regression: explain Orca active chamber behavior by selected filament instead of demanding profile-pack artifacts."
    if any(term in lower for term in ("king james bible", "kjv", "king james")) and any(term in lower for term in ("hebrew scripture", "hebrew scriptures", "hebrew bible", "tanakh")) and any(term in lower for term in ("difference", "differences", "different", "compare")):
        test["expectedProjectId"] = "bible-kjv-study"
        test["expectedContractKind"] = "KJV/Hebrew Scripture comparison"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Christian Bible", "Hebrew Scripture", "New Testament"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "Tanakh", "translation"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["Christian Bible", "Hebrew Scripture", "New Testament"]
        test["goal"] = "Real chat-history regression: answer KJV versus Hebrew Scripture comparisons directly by canon, translation, order, and New-Testament scope."
    if is_tinmanx_wave_overhang_generate_now_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "TinManX wave-overhang readiness"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["TinManX", "wave overhangs", "ready"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "preview", "G-code", "test print"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["readiness gates", "preview/G-code validation", "test model"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer TinManX wave-overhang readiness with UI/slice/preview/G-code/test-print gates instead of routing to generic Orca feature implementation."
    elif is_functional_wave_overhang_generator_prompt(prompt):
        test["expectedProjectId"] = "orcaslicer-codex"
        test["expectedContractKind"] = "Slicer feature workflow"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["wave-overhang generator", "preview", "G-code"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "wave-overhang generator", "preview", "G-code", "test print"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["generator workflow", "preview/G-code validation", "test model"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: route functional Wave Overhang generator work as an OrcaSlicer Codex slicer feature with preview, G-code, and test-print proof."
    if any(term in lower for term in ("andersons", "anderson's", "anderson")) and any(term in lower for term in ("kaiser", "laso")) and "algorithm" in lower:
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Wave overhang algorithm comparison"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Andersons", "Kaiser LaSO", "experimental"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "WaveOverhangs", "test"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["Andersons default", "Kaiser LaSO", "preview or test print"]
        test["goal"] = "Real chat-history regression: answer Andersons versus Kaiser LaSO as an Orca/WaveOverhangs slicer algorithm comparison, not a generic algorithm timeout."
    if is_preview_zoom_controls_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Preview zoom controls"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["zoom in", "zoom out", "reset-to-fit"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "previewScale", "clamp"], limit=8)
        test["requiredContractProof"] = ["zoom in", "zoom out", "reset-to-fit", "previewScale or scale clamp"]
        test["goal"] = "Real chat-history regression: answer preview zoom-control requests as a concrete Codex CLI UI feature instead of stale missing-context metadata."
    if is_slotted_turbine_hub_modular_design_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Slotted turbine hub modular design"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["one-piece rotor hub", "separate blades", "300 mm"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "positive", "overspeed", "ASA-CF"], limit=8)
        test["requiredContractProof"] = ["one-piece hub", "separate blades", "300 mm build volume", "positive retention", "overspeed or stress caveat"]
        test["goal"] = "Real chat-history regression: answer slotted modular turbine-hub design ideas directly with build-volume and mechanical-retention reasoning instead of timing out on the generic route."
    if is_rotor_material_mass_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Wind rotor material/mass tradeoff"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["ASA-CF", "infill", "mass"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "ASA-CF", "infill", "startup torque", "validate"], limit=8)
        test["requiredContractProof"] = ["ASA-CF stiffness", "infill/mass", "startup torque or inertia", "stress/balance/overspeed validation"]
        test["goal"] = "Real chat-history regression: answer rotor material/infill/mass follow-ups as an engineering tradeoff instead of a CAD file-format reference."
    if is_eject_until_box_sensor_unloaded_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Filament box controlled unload"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["Yes", "controlled unload", "sensor"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "unloaded", "jam", "idle"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["controlled unload", "sensor/empty check", "jam safety caveat"]
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["diskutil", "exact mounted volume", "the disk"]))
        test["goal"] = "Real chat-history regression: handle filament box unload prompts as controlled printer unloads, not disk eject requests."
    if is_eject_target_context_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Eject target context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["eject", "exact mounted volume", "device"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "volume", "device", "diskutil"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["target volume/device", "diskutil path"]
        test["goal"] = "Real chat-history regression: handle disk eject requests as a safe target-context prompt instead of generic missing-context wording."
    if is_motion_system_testing_context_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Motion-system testing resume context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["motion-system testing", "target printer", "idle"]
        test["requiredTerms"] = normalize_terms(
            ["This is why", "You should also consider", "motion-system", "target printer", "idle", "small movement"],
            limit=8,
        )
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["requiredContractProof"] = ["target printer/test", "idle/safety gate", "small movement/homing path"]
        test["goal"] = (
            "Real chat-history regression: answer motion-system testing resume prompts quickly with target-printer context "
            "and safety gates instead of a slow generic model path."
        )
    if is_bed_mesh_deviation_quality_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Bed-mesh deviation quality judgment"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["contextDependent"] = False
        test["directTerms"] = ["Good", "bed-mesh deviation", "first layer"]
        test["requiredTerms"] = normalize_terms(
            ["This is why", "You should also consider", "good", "bed-mesh", "0.20-0.30 mm", "first layer"],
            limit=8,
        )
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["requiredContractProof"] = ["good/bad judgment", "0.20-0.30 mm threshold", "first-layer validation"]
        test["goal"] = "Real chat-history regression: answer bed-mesh deviation quality questions directly and quickly with threshold and first-layer caveat."
    if is_pt6_icing_itt_prompt(prompt):
        test["expectedProjectId"] = "aviation-engineering"
        test["expectedContractKind"] = "PT6 icing ITT spike diagnostic"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "PT6", "ITT"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "icing", "torque", "Ng", "AFM"], limit=8)
        test["requiredContractProof"] = ["PT6", "ITT", "icing", "torque or Ng", "POH or AFM caveat"]
        test["goal"] = "Real chat-history regression: answer PT6/King Air icing and ITT questions as aviation diagnostics, not stale embedded/RatOS work."
    if is_codex_personality_settings_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex personality controls"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Humor", "Friendliness"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "persist", "safety"], limit=8)
        test["requiredContractProof"] = ["Humor", "Friendliness", "persist", "safety-critical cap"]
        test["goal"] = "Real chat-history regression: answer personality-control requests directly without requiring fake file/action artifacts."
    if is_cm4_vs_pi5_prompt(prompt):
        test["expectedProjectId"] = "embedded-linux-images"
        test["expectedContractKind"] = "CM4 versus Pi 5 printer-host choice"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["CM4", "Pi 5", "printer-host"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "eMMC", "heat", "bench"], limit=8)
        test["requiredContractProof"] = ["CM4", "Pi 5", "eMMC or carrier", "bench boot/proven image"]
        test["goal"] = "Real chat-history regression: answer CM4-versus-Pi5 printer-host follow-ups directly instead of timing out on a local model path."
    if is_cm4_ram_size_prompt(prompt):
        test["expectedProjectId"] = "embedded-linux-images"
        test["expectedContractKind"] = "CM4 RAM sizing"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["4 GB", "CM4", "sweet spot"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "2 GB", "8 GB", "eMMC"], limit=8)
        test["requiredContractProof"] = ["4 GB sweet spot", "2 GB light workload", "8 GB heavy extras", "eMMC/reliability caveat"]
        test["goal"] = "Real chat-history regression: answer CM4 RAM sizing directly for printer-host workloads instead of taking a slow generic model path."
    if is_dot147_beacon_offset_update_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = ".147 Beacon offset update"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = [".147", "Beacon offset", "config check"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "backup", "idle", "klippy.log"], limit=8)
        test["requiredContractProof"] = [".147 target", "Beacon offset values", "backup/diff", "config check", "idle/reachable safety gate"]
        test["goal"] = "Real chat-history regression: handle .147 Beacon offset update requests as safe live-printer config changes instead of timing out."
    if is_coolant_printed_fittings_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Coolant and printed fitting material selection"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["distilled water", "PETG", "pressure-test"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "glycol", "PLA", "pressure-test"], limit=8)
        test["requiredContractProof"] = ["coolant recommendation", "printed fitting material recommendation", "pressure/high-temperature caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer coolant and printed-fitting material choices directly as a mechanical material decision, not as a CAD export/reference contract."
    if is_fusion_perpendicular_tube_followup_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Fusion perpendicular tube join"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Fusion", "Loft", "Combine", "hollow"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "Loft", "Combine", "hollow"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["Fusion workflow", "connector body", "Combine Join", "hollow tube caveat"]
        test["goal"] = "Real chat-history regression: preserve CAD follow-up context for Fusion perpendicular tube work instead of flattening it into generic capability."
    if is_fusion_solid_removal_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Fusion solid removal"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Combine", "Cut", "Split Body"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "Fusion", "Keep Tools"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["Fusion subtract workflow", "complex-geometry fallback", "validation/check step"]
        test["goal"] = "Real chat-history regression: answer complex Fusion solid-removal questions directly with the right CAD workflow instead of routing as generic."
    if is_fusion_all_designs_script_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Fusion all-designs script handoff"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "source files", "Fusion 360 script"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "folder path", "component", ".f3d"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["source files or folder path", "Fusion 360 Python script", "component import/rebuild plan", ".f3d/.f3z boundary"]
        test["goal"] = "Real chat-history regression: for Fusion scripts over unspecified designs, state the missing source-files/folder blocker instead of inventing geometry."
    if is_fusion360_capability_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Fusion 360 capability answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Fusion 360-ready", ".f3d", ".f3z"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "script", "STEP", "native"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["Fusion 360-ready", ".f3d/.f3z boundary", "script or STEP handoff"]
        test["goal"] = "Real chat-history regression: answer Fusion 360 capability questions directly without demanding a generated CAD artifact."
    if is_p51_fusion_lockup_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "P-51 Fusion lockup recovery"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Fusion lockup", "file", "healed STEP"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "FreeCAD", "blocker"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["Fusion lockup", "file/path inspection", "healed STEP or Fusion script", "repaired candidate or blocker"]
        test["goal"] = "Real chat-history regression: handle P-51 Fusion lockup recovery directly with a local file-inspection and CAD handoff repair path instead of timing out."
    if is_professional_output_label_prompt(prompt):
        test["expectedProjectId"] = "energy-power-research"
        test["expectedContractKind"] = "Professional output labeling"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["professional title", "Vevor", "Backup Power"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "Finder", "label"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["professional title", "Vevor or Backup Power example", "file/UI label consistency"]
        test["goal"] = "Real chat-history regression: preserve Tinman's professional output-label preference for engineering deliverables instead of grading it as a hardware search."
    if is_save_settings_no_button_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Settings save/no-button guidance"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["autosave", "preset", "verify"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "Orca", "Codex CLI UI"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["autosave/apply/close", "preset save", "reopen/verify persistence"]
        test["goal"] = "Real chat-history regression: answer missing Save-button settings prompts directly instead of timing out on a generic route."
    if is_slicer_actual_work_status_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Slicer actual-work status"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["actual slicer work", "credit/attribution", "verified"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "profile", "UI-visible", "source-credit"], limit=8)
        test["requiredContractProof"] = ["actual slicer work", "credit/attribution boundary", "verified/staged/discussed buckets"]
        test["goal"] = "Real chat-history regression: answer slicer-work status questions directly with actual engineering-vs-credit accounting instead of timing out on the generic slicer route."
    if is_fibreseek_fiber_amount_location_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "FibreSeek fiber amount control"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["fiber/process strategy", "Fiber Amount", "Fiber Density"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "preview", "fiber-usage"], limit=8)
        test["requiredContractProof"] = ["fiber/process strategy", "plastic filament", "Fiber Amount", "Fiber Density", "preview", "fiber-usage"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer FibreSeek fiber-amount location questions as local continuous-fiber workflow guidance, not source-backed shopping/research."
    if is_codex_son_self_improvement_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex CLI UI self-improvement roadmap"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["closed-loop self-improvement", "regression", "safety gates"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "test case", "diagnosis", "patch", "rerun"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["closed-loop self-improvement", "regression tests", "diagnosis/patch/rerun", "safety gates"]
        test["goal"] = "Real chat-history regression: interpret Tinman's 'your son' shorthand as Codex CLI UI and answer with a systemic self-improvement loop instead of generic advice."
    if is_codex_output_failure_feedback_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Codex CLI UI output failure repair"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["You are right", "regression", "rerun"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "wrong output", "contract", "tool", "regression"], limit=8)
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["requiredContractProof"] = ["wrong output diagnosis", "contract/tool-path fix", "regression test", "rerun proof"]
        test["goal"] = "Real chat-history regression: treat pasted bad Codex CLI UI output as feedback on the local agent, not as a fresh answer to the embedded technical prompt."
    if is_btt_vivd_sensor_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "BTT ViVD sensor inclusion"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["No", "BTT ViVD", "external"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "runout", "tangle", "external sensor", "manual"], limit=8)
        test["requiredContractProof"] = ["BTT ViVD", "runout", "tangle", "external sensor", "manual/pinout caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer BTT ViVD runout/tangle sensor questions directly with external-sensor and manual/pinout caveats instead of a slow generic hardware answer."
    if is_t0_t1_beacon_visibility_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "T0", "T1"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "T0", "T1", "Beacon", "Klipper", "toolhead"], limit=10)
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: interpret T0/T1 Beacons as printer/Klipper Beacon contexts and answer directly from local config visibility when possible."
    if is_vivd_feeder_handoff_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "ViVD feeder handoff control"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "ViVD", "U1"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "one feeder", "handoff", "bench macro"], limit=8)
        test["requiredContractProof"] = ["one feeder at a time", "handoff state machine", "grind/buckle risk", "bench macro"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer ViVD/U1 feeder handoff as a motion-control state machine instead of a U1 firmware or slicer-profile lookup."
    if is_vivd_u1_integration_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "ViVD on U1 integration path"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["custom", "U1", "ViVD"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "handoff", "BTT", "BIGTREETECH_MMS", "do not"], limit=10)
        test["requiredContractProof"] = ["custom external loader/handoff", "U1 firmware support caveat", "BTT ViVD/MMS source", "no guessed Snapmaker firmware/plugin"]
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["snapmaker/firmware.git", "vivd --check", "python3-vivd", "enable_vivd = true"]))
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer ViVD-on-U1 as a custom loader/handoff integration and block fabricated Snapmaker firmware/plugin steps."
    if is_multiple_vivd_toolhead_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Multiple ViVD per toolhead feasibility"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Possible", "experimental", "toolhead"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "device identity", "one toolhead", "source"], limit=8)
        test["requiredContractProof"] = ["possible but experimental", "device identity/config namespace", "one toolhead first", "official source caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer one ViVD MMS per toolhead with multi-device software risks and a one-toolhead-first validation path."
    if is_klipper_theme_asset_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper theme asset update"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Klipper"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Klipper", "Moonraker", "CSS", "backup", "validation"], limit=10)
        test["requiredContractProof"] = ["Klipper/Moonraker assets", "CSS/theme edit", "backup", "UI validation"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: handle Klipper theme image replacement as a UI asset/CSS edit with backup and validation, not a generic code dump."
    if is_btt_vivd_system_path_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "BTT ViVD integration path"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["BTT ViVD", "bench-test", "official"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "firmware", "slicer", "wiring", "manual"], limit=8)
        test["requiredContractProof"] = ["BTT ViVD", "official docs/manual", "bench-test plan", "firmware/slicer/wiring gates", "no guessed repo/build commands"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["github.com/yourorg", "[env:btt_vivid]", "STM32F446"]))
        test["goal"] = "Real chat-history regression: answer BTT ViVD system path planning with an official-docs, firmware, wiring, slicer, and bench-test plan instead of invented firmware commands."
    if is_filament_path_diagram_prompt(prompt):
        test["expectedProjectId"] = "engineering-diagrams"
        test["expectedContractKind"] = "Engineering diagram"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["filament-path block diagram", "ViVD Filament Path To Toolhead"]
        test["requiredTerms"] = normalize_terms(
            [
                "filament-path block diagram",
                "ViVD Filament Path To Toolhead",
                "Path validation quick check",
                "filament drag",
                "sensor timing",
                "motion",
                "toolhead",
            ],
            limit=10,
        )
        test["requiredContractProof"] = ["editable diagram artifacts", "filament path", "motion/sensor map", "path validation"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(
            set(
                test.get("forbiddenTerms", [])
                + [
                    "3D Printer System Architecture",
                    "Wire sizing quick check",
                ]
            )
        )
        test["goal"] = "Real chat-history regression: produce a ViVD-to-toolhead filament-path diagram with motion/sensor validation, not a generic printer architecture or electrical wiring answer."
    if is_diagram_tool_recommendation_prompt(prompt):
        test["expectedProjectId"] = "engineering-diagrams"
        test["expectedContractKind"] = "Diagram tool recommendation"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Graphviz"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Graphviz", "draw.io", "Mermaid", "KiCad"], limit=8)
        test["requiredContractProof"] = ["Graphviz", "draw.io or Mermaid", "KiCad boundary"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(
            set(
                test.get("forbiddenTerms", [])
                + [
                    "Primary outputs",
                    "created an engineering diagram package",
                    "draw.io editable diagram:",
                    "Wiring/net CSV",
                ]
            )
        )
        test["goal"] = "Real chat-history regression: answer diagram-tool recommendation prompts directly instead of creating diagram artifacts."
    if is_final_nozzle_simulator_prompt(prompt):
        test["expectedProjectId"] = "cad-modeling-projects"
        test["expectedContractKind"] = "Final nozzle simulator validation"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "current nozzle/build artifact", "simulator"]
        test["requiredTerms"] = normalize_terms(
            [
                "This is why",
                "You should also consider",
                "simulator/final gate",
                "fit/flow/collision/printability",
                "case path",
            ],
            limit=8,
        )
        test["requiredContractProof"] = [
            "current artifact/case path",
            "simulator/final gate",
            "fit/flow/collision/printability checks",
            "blocker or report path",
        ]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["forbiddenTerms"] = sorted(
            set(
                test.get("forbiddenTerms", [])
                + [
                    "moonraker",
                    "nozzle temperature",
                    "nozzle temp",
                    "configured endpoint",
                    "i staged a first-pass",
                    "cpap cooling duct",
                ]
            )
        )
        test["goal"] = "Real chat-history regression: answer final-nozzle simulator follow-ups as CAD/build validation requiring the active artifact or case path, not live printer status or a generic CAD template."
    if is_weekly_data_reasoning_level_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Reasoning-level data budget tradeoff"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["medium", "auto-escalate", "completion time"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "weekly", "high/deep"], limit=8)
        test["anyTerms"] = []
        test["requiredContractProof"] = ["medium default", "auto-escalate", "completion-time tradeoff"]
        test["goal"] = "Real chat-history regression: answer reasoning-level data-budget tradeoffs directly with a medium-default plus escalation policy."
    if is_controlled_y_home_after_collision_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Controlled Y home after collision"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Y-only", "G28 Y", "do not command another X move"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "belts", "toolhead"], limit=8)
        test["requiredContractProof"] = ["G28 Y", "no X move", "clear-path safety", "post-home verification"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer controlled Y-home recovery as printer motion safety, not CAD."
    if is_filament_box_load_next_step_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Filament box load next step"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Next step", "load the filament", "heat and purge"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "sensor", "calibration"], limit=8)
        test["requiredContractProof"] = ["load/purge sequence", "sensor/drag caveat"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer filament-box load next-step prompts as printer workflow, not CAD."
    if is_offset1459_direct_prompt(prompt):
        for detector, expected_project, contract_kind, proof_terms in [
            (is_print_code_ssh_diagnostic_prompt, "tinmanx-slicer-research", "Print workflow SSH/code diagnostic", ["SSH/code path", "filament-load state", "camera false-positive", "regression test or log proof"]),
            (is_stop_chat_terminate_automations_prompt, "codex-cli-ui-local-agent", "Stop chat and terminate automations", ["stop acknowledged", "automations terminated", "checkpoint/resume state"]),
            (is_rev_b_latest_compare_prompt, "general", "Revision compare missing artifacts", ["Rev B", "new revision", "actual file/artifact paths", "delta report"]),
            (is_qidi_box_pause_rethink_prompt, "printer-klipper-ops", "Qidi Box baseline rethink", ["Qidi Box", "known-good baseline", "firmware/software", "calibration order"]),
            (is_rat_rig_mechanical_mods_pause_prompt, "printer-klipper-ops", "Rat Rig mechanical-mod pause", ["Rat Rig", "mechanical mods", "software pause", "resume validation"]),
            (is_diffuser_positive_z_airflow_test_prompt, "cad-modeling-projects", "Diffuser positive-Z airflow CFD plan", ["diffuser-only", "positive-Z airflow", "solver surface or geometry blocker", "source/solver basis"]),
            (is_upload_all_files_later_prompt, "general", "Upload staging missing destination", ["source file set", "destination", "manifest/package or blocker"]),
            (is_adaptive_heat_soak_design_prompt, "printer-klipper-ops", "Adaptive heat-soak mesh-stability macro", ["bed/chamber targets", "60-second mesh loop", "mesh delta", "completion threshold", "Klipper macro/status basis"]),
        ]:
            if detector(prompt):
                test["expectedProjectId"] = expected_project
                test["expectedContractKind"] = contract_kind
                test["expectedContractGate"] = "pass"
                test["directAnswer"] = True
                test["directTerms"] = []
                test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
                test["requiredContractProof"] = proof_terms
                test["anyTerms"] = []
                test["requiresSource"] = False
                test["webSearch"] = "disabled"
                test["minAnalyticalScore"] = 100
                test["maxDurationMs"] = 750
                test["contextDependent"] = False
                test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
                break
    if is_offset1499_direct_prompt(prompt):
        for detector, expected_project, contract_kind, proof_terms in [
            (is_ffmpeg_v4l2_camera_log_prompt, "mac-system-accounts", "V4L2 camera MJPEG frame warning", ["/dev/video0", "EOI missing", "MJPEG frame", "v4l2 or capture check"]),
            (is_flightops_multi_inspection_ui_prompt, "flightops-tracker", "Flight Ops multi-inspection UI", ["full-width entry", "multi-select checkbox", "one maintenance entry", "many inspection items"]),
            (is_makers_corner_guest_restart_prompt, "mac-system-accounts", "Guest Wi-Fi restart safety", ["makers corner", "guest 2.4 GHz", "router-side restart", "before/after SSID or client check"]),
            (is_qidi_nebula_pins_before_sensor_removal_prompt, "printer-klipper-ops", "Qidi Nebula pinout before sensor cleanup", ["Nebula pinout", "RGB", "runout", "tangle or filament-width sensor cleanup"]),
            (is_rat_rig_files_access_resume_prompt, "printer-klipper-ops", "Rat Rig file-access resume", ["Rat Rig", "local files", "reachability caveat", "backup/syntax/live gate"]),
            (is_touchscreen_firmware_flash_walkthrough_prompt, "general", "Touchscreen firmware flashing boundary", ["touchscreen/local update support", "exact printer/board", "firmware source/checksum", "backup/rollback"]),
            (is_klipper_request_draft_prompt, "printer-klipper-ops", "Klipper feature-request draft", ["Klipper", "problem/current limitation", "proposed behavior", "safety/test evidence"]),
            (is_filament_box_no_filament_next_step_prompt, "printer-klipper-ops", "Filament box load next step", ["load/purge sequence", "sensor/drag caveat"]),
            (is_snapmaker_u1_custom_firmware_update_decision_prompt, "printer-klipper-ops", "Snapmaker U1 custom firmware update decision", ["Snapmaker U1", "aftermarket firmware", "official release notes", "rollback/backup"]),
        ]:
            if detector(prompt):
                test["expectedProjectId"] = expected_project
                test["expectedContractKind"] = contract_kind
                test["expectedContractGate"] = "pass"
                test["directAnswer"] = True
                test["directTerms"] = []
                test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
                test["requiredContractProof"] = proof_terms
                test["anyTerms"] = []
                test["requiresSource"] = False
                test["webSearch"] = "disabled"
                test["minAnalyticalScore"] = 100
                test["maxDurationMs"] = 750
                test["contextDependent"] = False
                test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
                break
    if is_offset1539_direct_prompt(prompt):
        for detector, expected_project, contract_kind, proof_terms in [
            (is_manual_auto_feature_still_work_prompt, "cad-modeling-projects", "Manual-off auto-feature boundary", ["manual off", "auto feature remains enabled", "verify exact setting/state"]),
            (is_github_comments_prompt, "codex-cli-ui-local-agent", "GitHub comments explanation", ["GitHub", "issues or pull requests", "comments/reviews/discussions"]),
            (is_plus4_sensorless_homing_force_prompt, "printer-klipper-ops", "Plus 4 sensorless homing force/current", ["Plus 4", "Y homing current", "0.9 A", "force is not equal to current"]),
            (is_cc1_runout_continued_printing_prompt, "printer-klipper-ops", "CC1 runout during-print pause diagnostic", ["CC1", "runout sensor", "immediate pause", "timer", "verify logs/config"]),
            (is_flightops_fuel_method_cover_sheet_report_prompt, "flightops-tracker", "Flight Ops fuel method/report-page layout", ["fuel method 2", "customer report", "second sheet", "standalone page"]),
            (is_flightops_customer_line_remove_label_prompt, "flightops-tracker", "Flight Ops customer-line label cleanup", ["remove Customer label", "customer name", "report header/line"]),
        ]:
            if detector(prompt):
                test["expectedProjectId"] = expected_project
                test["expectedContractKind"] = contract_kind
                test["expectedContractGate"] = "pass"
                test["directAnswer"] = True
                test["directTerms"] = []
                test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
                test["requiredContractProof"] = proof_terms
                test["anyTerms"] = []
                test["requiresSource"] = False
                test["webSearch"] = "disabled"
                test["minAnalyticalScore"] = 100
                test["maxDurationMs"] = 750
                test["contextDependent"] = False
                test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
                break
    if is_offset1579_direct_prompt(prompt):
        for detector, expected_project, contract_kind, proof_terms in [
            (is_flightops_pilot_report_by_pilot_prompt, "flightops-tracker", "Flight Ops pilot-report filter", ["pilot report", "pilot selector/filter", "date range", "totals verification"]),
            (is_qidi_stepper_motor_temperature_missing_prompt, "printer-klipper-ops", "Qidi stepper temperature visibility boundary", ["Qidi", "stepper motor temperature", "temperature_sensor or Moonraker object", "not CAD"]),
            (is_qidi_codex_library_filament_screen_prompt, "printer-klipper-ops", "Qidi printer-screen Codex library boundary", ["Codex library", "printer screen/UI", "not automatic", "sync/export verification"]),
            (is_ratrig_xy_offset_calibration_no_chamber_heat_prompt, "printer-klipper-ops", "Rat Rig cold XY nozzle-offset calibration", ["Rat Rig", "XY nozzle offset", "no chamber heat", "final hot verification"]),
            (is_flightops_report_date_totals_format_prompt, "flightops-tracker", "Flight Ops report date/totals layout", ["mm/dd/yy", "totals on one line", "report formatter", "stored date caveat"]),
            (is_sovol_obico_not_working_prompt, "printer-klipper-ops", "Sovol Obico connectivity diagnostic", ["Sovol", "Obico", "service/logs", "Moonraker/network/token"]),
            (is_flightops_customer_credit_dropdown_prompt, "flightops-tracker", "Flight Ops customer credit/dropdown feature", ["customer credit", "dropdown", "previously input customers", "preserve current functionality"]),
            (is_flightops_admin_pilot_email_missing_prompt, "flightops-tracker", "Flight Ops calendar pilot email diagnostic", ["pilot email", "calendar", "HTTP/SMTP", "logs/provider response"]),
        ]:
            if detector(prompt):
                test["expectedProjectId"] = expected_project
                test["expectedContractKind"] = contract_kind
                test["expectedContractGate"] = "pass"
                test["directAnswer"] = True
                test["directTerms"] = []
                test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
                test["requiredContractProof"] = proof_terms
                test["anyTerms"] = []
                test["requiresSource"] = False
                test["webSearch"] = "disabled"
                test["minAnalyticalScore"] = 100
                test["maxDurationMs"] = 750
                test["contextDependent"] = False
                test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
                break
    if is_offset1619_direct_prompt(prompt):
        for detector, expected_project, contract_kind, proof_terms in [
            (is_orca_codex_partially_locked_up_prompt, "orcaslicer-codex", "Orca Codex partial lockup diagnostic", ["Orca Codex", "partial lockup", "process/log", "reproduce verification"]),
            (is_qidi_prepare_tab_nozzle_sync_prompt, "printer-klipper-ops", "Qidi Prepare-tab nozzle-size sync", ["Qidi", "Prepare tab", "nozzle dropdown", "sync verification"]),
            (is_flightops_aircraft_buttons_flights_page_prompt, "flightops-tracker", "Flight Ops aircraft-button flights page", ["Flights page", "buttons for each aircraft", "filtered flight list", "All Aircraft option"]),
            (is_slicer_app_continue_until_all_printers_prompt, "orcaslicer-codex", "Slicer app all-printer build continuation", ["working app", "all printers", "slice and print", "package health"]),
            (is_pctg_profiles_all_machines_qidi_ui_prompt, "tinmanx-slicer-research", "PCTG all-machine/nozzle profile UI feature", ["PCTG", "all machines/nozzles", "Qidi UI", "profile verification"]),
            (is_beacon_ztilt_active_check_prompt, "printer-klipper-ops", "Beacon Z-tilt active-state check", ["Beacon", "T0", "Z_TILT", "active config", "read-only verification"]),
            (is_ratrig_macro_upload_confidence_prompt, "printer-klipper-ops", "Rat Rig macro upload confidence", ["Rat Rig", "macros", "confidence", "config check", "dry run"]),
            (is_post_restart_g28_bed_crash_prompt, "printer-klipper-ops", "Klipper restart safety", ["target printer", "idle/standby", "Klipper restart", "G28", "probe/Beacon"]),
            (is_flightops_pilot_daily_rate_exclusion_prompt, "flightops-tracker", "Flight Ops pilot daily-rate exclusion", ["pilot daily-rate exclusion", "Colin", "N296SA", "N533SS", "pay report verification"]),
            (is_flightops_shutdown_error_history_prompt, "flightops-tracker", "Flight Ops shutdown-error context recovery", ["shutdown error", "recent context/log", "exact text or missing-text caveat"]),
            (is_flightops_storage_projection_prompt, "flightops-tracker", "Flight Ops storage projection", ["current storage", "growth rate", "two aircraft", "maintenance tracking", "80 percent threshold"]),
            (is_flightops_fixed_maintenance_cover_page_prompt, "flightops-tracker", "Flight Ops fixed/maintenance cover-page totals", ["fixed costs", "maintenance costs", "cover page", "monthly total", "layout verification"]),
            (is_heat_soak_points_no_manual_jog_prompt, "printer-klipper-ops", "Heat-soak G28/Z-tilt point automation", ["heat soak", "G28", "Z_TILT_ADJUST", "points", "manual jog"]),
            (is_ratrig_toolboard_mcu_restart_prompt, "printer-klipper-ops", "Rat Rig toolboard MCU communication recovery", ["Rat Rig", "mcu toolboard 1", "lost communication", "restart", "idle/standby"]),
            (is_snapmaker_poweroff_mcu_ssh_diagnostic_prompt, "printer-klipper-ops", "Snapmaker MCU power-off SSH diagnostic", ["Snapmaker", "SSH", "MCU power-off", "logs", "power/undervoltage"]),
            (is_qidi_filament_switch_load_forum_prompt, "printer-klipper-ops", "Filament switch state verification", ["present/true state", "filament_detected", "pin/inversion check", "load sequence"]),
            (is_macos_sequoia_tahoe_upgrade_prompt, "mac-system-accounts", "macOS Sequoia/Tahoe upgrade decision", ["Tahoe directly", "Sequoia only if required", "backup", "compatibility"]),
        ]:
            if detector(prompt):
                test["expectedProjectId"] = expected_project
                test["expectedContractKind"] = contract_kind
                test["expectedContractGate"] = "pass"
                test["directAnswer"] = True
                test["directTerms"] = []
                test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
                test["requiredContractProof"] = proof_terms
                test["anyTerms"] = []
                test["requiresSource"] = False
                test["webSearch"] = "disabled"
                test["minAnalyticalScore"] = 100
                test["maxDurationMs"] = 750
                test["contextDependent"] = False
                test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
                break
    if is_offset1659_direct_prompt(prompt):
        for detector, expected_project, contract_kind, proof_terms in [
            (is_3d_chameleon_cleanup_prompt, "codex-cli-ui-local-agent", "3D Chameleon safe cleanup", ["3D Chameleon", "manifest", "archive/backup", "delete only confirmed files"]),
            (is_printer_ip_changed_password_note_prompt, "printer-klipper-ops", "Printer IP update credential boundary", ["192.0.2.145", "password/private credential", "Moonraker/SSH", "redact"]),
            (is_flightops_aircraft_documents_restore_upload_prompt, "flightops-tracker", "Flight Ops aircraft document restore/upload", ["aircraft documents", "manifest", "local source path", "upload verification"]),
            (is_klipper_load_unload_macro_buttons_prompt, "printer-klipper-ops", "Klipper load/unload macro UI binding", ["Klipper", "LOAD_FILAMENT", "UNLOAD_FILAMENT", "KlipperScreen buttons"]),
            (is_all_printers_supported_continue_prompt, "printer-klipper-ops", "All-printer support continuation", ["all printers", "support matrix", "slice test", "print/send readiness"]),
            (is_u1_buffer_sensor_delete_confirmation_prompt, "printer-klipper-ops", "U1 buffer/sensor deletion confirmation", ["U1", "buffer", "sensors", "lanes merge", "sensor map"]),
            (is_temporary_immediate_pause_macro_prompt, "printer-klipper-ops", "Temporary immediate pause macro", ["helper macro", "pause print", "mechanical side", "wasted filament", "Klipper PAUSE"]),
            (is_mainline_klipper_camera_xy_measurement_prompt, "printer-klipper-ops", "Mainline Klipper camera XY measurement", ["mainline Klipper", "camera", "X/Y", "vision pipeline", "offset validation"]),
            (is_typical_questions_domain_list_prompt, "energy-power-research", "Domain question bank", ["3D printing", "CNC", "solar/wind", "CFD", "aviation"]),
            (is_snapmaker_u1_installed_filaments_prompt, "printer-klipper-ops", "Snapmaker U1 installed filament visibility", ["Snapmaker U1", "local profile backup", "installed slicer UI", "profile visibility"]),
        ]:
            if detector(prompt):
                test["expectedProjectId"] = expected_project
                test["expectedContractKind"] = contract_kind
                test["expectedContractGate"] = "pass"
                test["directAnswer"] = True
                test["directTerms"] = []
                test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
                test["requiredContractProof"] = proof_terms
                test["anyTerms"] = []
                test["requiresSource"] = False
                test["webSearch"] = "disabled"
                test["minAnalyticalScore"] = 100
                test["maxDurationMs"] = 750
                test["contextDependent"] = False
                test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
                break
    if is_offset1699_direct_prompt(prompt):
        for detector, expected_project, contract_kind, proof_terms in [
            (is_sovol_sv08_petg_cf_apply_changes_prompt, "tinmanx-slicer-research", "Sovol SV08 Max PETG-CF profile update", ["Sovol SV08 Max", "PETG-CF", "profile update", "slice smoke test"]),
            (is_pick_up_where_left_off_prompt, "codex-cli-ui-local-agent", "Checkpoint continuation", ["latest checkpoint", "active task", "verify current state"]),
            (is_uploaded_files_fix_coding_errors_stability_prompt, "codex-cli-ui-local-agent", "Uploaded-files code stability repair", ["uploaded files", "syntax/tests", "coding errors", "app stable"]),
            (is_qidi_backup_and_stock_restore_prompt, "printer-klipper-ops", "Qidi backup and stock restore", ["local backup/manifest", "Qidi Box", "stock baseline", "idle/standby", "restore verification"]),
            (is_dry_room_sub_10_humidity_prompt, "printer-klipper-ops", "Sub-10% dry-room humidity control", ["10% RH", "desiccant", "sealed room", "dry boxes", "monitoring"]),
            (is_project_github_link_prompt, "codex-cli-ui-local-agent", "Current project GitHub remote", ["github.com", "origin remote", "local changes"]),
            (is_stock_firmware_password_prompt, "embedded-linux-images", "Firmware stock password boundary", ["pi", "raspberry", "firmware image caveat", "change the password"]),
            (is_flightops_pi_vpn_mobile_access_prompt, "flightops-tracker", "Flight Ops mobile access architecture", ["Raspberry Pi", "pilots/customers", "mobile HTTPS login", "MakersVPN admin", "role-based access"]),
            (is_ratrig_vcore_extrusion_gantry_prompt, "printer-klipper-ops", "Rat Rig V-Core gantry extrusion spec", ["Rat Rig", "3030", "steel X-axis gantry", "BOM or measure"]),
            (is_humidity_control_box_minimal_heat_prompt, "cad-modeling-projects", "Low-heat humidity-control box design", ["sealed box", "desiccant", "fan", "humidity sensor", "minimal/no heat"]),
            (is_flightops_document_not_found_user_prompt, "flightops-tracker", "Flight Ops document-not-found diagnostic", ["Document not found", "database record", "file path", "user permission", "document ID"]),
            (is_flightops_old_spreadsheet_download_prompt, "flightops-tracker", "Flight Ops stale spreadsheet download", ["old spreadsheet", "download endpoint", "stored document", "cache", "verify download"]),
            (is_flightops_monthly_report_back_button_prompt, "flightops-tracker", "Flight Ops monthly report back button", ["Back to Tracker", "monthly report", "tracker route", "mobile layout"]),
            (is_cad_file_format_preference_prompt, "cad-modeling-projects", "CAD file format preference", ["STEP", ".f3d", ".f3z", "STL", "constraints"]),
        ]:
            if detector(prompt):
                test["expectedProjectId"] = expected_project
                test["expectedContractKind"] = contract_kind
                test["expectedContractGate"] = "pass"
                test["directAnswer"] = True
                test["directTerms"] = []
                test["requiredTerms"] = normalize_terms(["This is why", "You should also consider"], limit=8)
                test["requiredContractProof"] = proof_terms
                test["anyTerms"] = []
                test["requiresSource"] = False
                test["webSearch"] = "disabled"
                test["minAnalyticalScore"] = 100
                test["maxDurationMs"] = 750
                test["contextDependent"] = False
                test["goal"] = f"Real chat-history regression: {contract_kind} answers direct and avoids slow/generic fallback."
                break
    if (
        not is_tinmanx_schedule_status_prompt(prompt)
        and not is_tinmanx_average_completion_time_prompt(prompt)
        and not is_weekly_data_reasoning_level_prompt(prompt)
        and "heartbeat" not in lower
    ) and (
        any(term in lower for term in ("how are we doing", "updated completion time", "completion time")) or
        re.search(r"\beta\b", lower) is not None and any(term in lower for term in ("updated", "completion", "time", "estimate"))
    ):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Completion time missing context"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["specific project", "updated completion time", "checkpoint"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "specific project", "completion time"], limit=8)
        test["requiredContractProof"] = ["specific project", "updated completion time", "checkpoint or active task"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: ask for the active project/checkpoint before giving a completion-time estimate."
    if any(term in lower for term in ("prusa ui", "prusa machine", "on the machine", "machine when i load it")) and any(
        term in lower for term in ("codex filaments", "orca codex", "filament")
    ):
        test["expectedProjectId"] = "orcaslicer-codex"
        test["expectedContractKind"] = "Prusa UI Codex filament bridge"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Prusa-compatible", "Orca Codex"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Prusa-compatible", "Orca Codex", "UI"], limit=8)
        test["requiredContractProof"] = ["Prusa-compatible filament preset bridge", "Orca Codex", "machine UI", "safe temperature fields"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["goal"] = "Real chat-history regression: answer Prusa UI Codex filament import as local preset-bridge work, not web research."
    if is_source_credit_short_prompt(prompt):
        test["expectedProjectId"] = "codex-cli-ui-local-agent"
        test["expectedContractKind"] = "Source attribution ledger"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["source ledger", "credit", "release checklist"]
        test["requiredTerms"] = normalize_terms(["this is why", "you should also consider", "license", "attribution"], limit=8)
        test["requiredContractProof"] = ["source ledger", "attribution fields", "privacy boundary"]
        test["goal"] = "Real chat-history regression: answer short credit/attribution instructions directly instead of timing out."
    if is_aviation_life_limited_part_quiz_prompt(prompt):
        test["expectedProjectId"] = "aviation-engineering"
        test["expectedContractKind"] = "Aviation life-limited part control quiz"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["C", "Segregation"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "life-limited", "segregation"], limit=8)
        test["requiredContractProof"] = ["C. Segregation", "life-limited part", "deter installation"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: aviation quiz prompts should answer the selected choice directly, not route to Flight Ops software or web research."
    if is_hotend_coolant_control_guidance_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Klipper coolant control guidance"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Fan 6", "Motor 7"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Fan 6", "Motor 7", "http"], limit=10)
        test["requiredContractProof"] = ["fan/pump control plan", "safe tuning method", "research/source caveat"]
        test["requiresSource"] = True
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: liquid-hotend Fan 6/Motor 7 prompts should provide source-anchored control guidance instead of status checks."
    if is_k2_plus_profile_pack_setup_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "K2 Plus profile-pack setup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "K2 Plus"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Creality Print", "0.4", "0.6", "profiles", "http"], limit=10)
        test["requiredContractProof"] = ["K2 Plus", "Creality Print", "machine/filament/process profiles", "0.4", "0.6"]
        test["requiresSource"] = True
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: K2 Plus profile-pack requests must include machine/filament/process profiles for 0.4 and 0.6 nozzles, not a single nozzle label update."
    if is_flightops_report_cover_page_numbering_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops report cover/page numbering"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Invoice"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "cover page", "page 2", "page numbers"], limit=8)
        test["requiredContractProof"] = ["cover page", "not an Invoice", "page 2", "page numbers", "PDF render"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Flight Ops report layout prompts should answer the report change directly and require render verification."
    if is_flightops_pilot_double_booking_blocker_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops pilot double-booking blocker"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "pilot"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "overlapping", "different aircraft", "server-side"], limit=8)
        test["requiredContractProof"] = ["pilot", "overlapping flights", "different aircraft", "server-side", "regression tests"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Flight Ops pilot double-booking prompts should become a server-side schedule conflict blocker plan."
    if is_flightops_flightlog_by_aircraft_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops flightlog by-aircraft view"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "aircraft"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "flight log", "aircraft", "All Aircraft"], limit=8)
        test["requiredContractProof"] = ["flight log", "aircraft", "All Aircraft", "aircraft_id", "verification"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: flightlog by-aircraft prompts should preserve one data source with aircraft filtering/grouping."
    if is_flightops_method1_fuel_daily_rollup_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops Method 1 fuel daily rollup"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Method 1"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "same aircraft", "same customer", "cover page"], limit=8)
        test["requiredContractProof"] = ["Method 1 fuel", "same aircraft", "same customer", "average fuel burn", "cover page fuel table"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Method 1 fuel prompts should define same-aircraft/customer/day rollup and cover-page report table behavior."
    if is_flightops_pilot_report_pdf_print_prompt(prompt):
        test["expectedProjectId"] = "flightops-tracker"
        test["expectedContractKind"] = "Flight Ops pilot report PDF export"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "PDF"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "pilot reports", "PDF", "render"], limit=8)
        test["requiredContractProof"] = ["pilot reports", "PDF", "filters/totals", "render regression"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: pilot report PDF export prompts should answer as a Flight Ops report feature with render verification."
    if is_sovol_stainless_gantry_material_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Sovol stainless gantry material choice"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["hollow", "20 x 20"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "hollow", "solid", "moving mass", "input shaper"], limit=10)
        test["requiredContractProof"] = ["20 x 20", "hollow", "solid", "moving mass", "input shaper"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Sovol stainless gantry material prompts should answer the moving-mass/stiffness tradeoff directly."
    if is_ratos_directory_download_compare_prompt(prompt):
        test["expectedProjectId"] = "embedded-linux-images"
        test["expectedContractKind"] = "RatOS directory snapshot for compare"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["rsync", "192.0.2.118"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "new folder", "rsync", "no changes"], limit=10)
        test["requiredContractProof"] = ["192.0.2.118", "new folder", "rsync", "not mixed with old files", "no changes"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: RatOS directory-download prompts should give a safe isolated snapshot command and no-change boundary."
    if is_wind_generator_alternator_shopping_prompt(prompt):
        test["expectedProjectId"] = "energy-power-research"
        test["expectedContractKind"] = "Wind generator 300 RPM source search"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = False
        test["directTerms"] = []
        test["requiredTerms"] = normalize_terms(["300 RPM", "60", "$500", "http"], limit=8)
        test["requiredContractProof"] = ["300 RPM", "60 VDC", "under $500", "source URL", "reject"]
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["STEP candidate", "wind-turbine STEP", "CAD package"]))
        test["minAnalyticalScore"] = 82
        test["goal"] = "Real chat-history regression: wind-generator shopping prompts should research source-backed alternators/generators, not stage turbine CAD."
    if is_snapmaker_u1_nozzle_shopping_prompt(prompt):
        test["expectedProjectId"] = "research-parts-reference"
        test["expectedContractKind"] = "Snapmaker U1 0.6 nozzle shopping"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = False
        test["directTerms"] = []
        test["requiredTerms"] = normalize_terms(["Snapmaker U1", "0.6 nozzle", "http", "shipping"], limit=8)
        test["requiredContractProof"] = ["Snapmaker U1", "0.6 nozzle", "source URL", "shipping"]
        test["requiresSource"] = True
        test["webSearch"] = "live"
        test["forbiddenTerms"] = sorted(set(test.get("forbiddenTerms", []) + ["layer height", "line width", "pressure advance"]))
        test["minAnalyticalScore"] = 82
        test["goal"] = "Real chat-history regression: Snapmaker U1 nozzle shopping prompts should source current nozzle-set candidates, not answer slicer quality settings."
    if is_k2_qidi_box_macro_compare_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "K2/Qidi box macro comparison"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "K2 Plus", "Qidi"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "macros", "cfg", "no-live-printer-change"], limit=10)
        test["requiredContractProof"] = ["K2 Plus", "Qidi", "macros/cfg", "box/filament change", "no-live-printer-change gate"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: K2/Qidi box comparison prompts should ask for config snapshots and preserve no-live-change gates."
    if is_klipperscreen_object_visibility_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "KlipperScreen object visibility"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Only if", "KlipperScreen"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "KlipperScreen", "macro", "menu"], limit=8)
        test["requiredContractProof"] = ["KlipperScreen", "macro/menu/status object", "restart/refresh"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: KlipperScreen visibility follow-ups should explain macro/menu/status exposure instead of timing out."
    if is_sovol_filament_profile_expansion_prompt(prompt):
        test["expectedProjectId"] = "tinmanx-slicer-research"
        test["expectedContractKind"] = "Sovol filament profile expansion"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Yes", "Sovol"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Sovol", "filament profiles", "PETG-CF"], limit=8)
        test["requiredContractProof"] = ["Sovol", "filament profiles", "PETG-CF pattern", "machine/filament/process separation", "visibility check"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Sovol filament expansion prompts should route to slicer profiles and preserve material-specific values."
    if is_sovol_spring_idler_belt_tension_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Sovol belt tension mechanical tradeoff"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["I would not", "spring"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "spring", "belt tension", "input shaper"], limit=8)
        test["requiredContractProof"] = ["spring compliance", "resonance", "unequal belt tension", "input shaper"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: SV08 Max spring/idler belt-tension prompts should answer the mechanical tradeoff, not slicer calibration."
    if is_ratrig_initial_speed_accel_settings_prompt(prompt):
        test["expectedProjectId"] = "printer-klipper-ops"
        test["expectedContractKind"] = "Rat Rig initial speed/accel settings"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Start", "acceleration"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "Rat Rig", "IDEX", "input shaper"], limit=8)
        test["requiredContractProof"] = ["Rat Rig", "IDEX", "initial testing", "input shaper", "pressure advance"]
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 100
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: Rat Rig speed/accel prompts should route to printer setup, not CNC turning, and provide conservative starting ranges."
    if is_agent_preference_question_prompt(prompt):
        test["expectedProjectId"] = "general"
        test["expectedContractKind"] = "Direct answer"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["Codex"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "preference"], limit=8)
        test["requiredContractProof"] = ["direct answer", "why/caveat shape"]
        test["anyTerms"] = normalize_terms(["Codex", "Red Codex", "Red"], limit=6)
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer agent naming/preference questions conversationally and directly instead of routing to Local Research."
    if is_mac_memory_ai_performance_prompt(prompt):
        test["expectedProjectId"] = "mac-system-accounts"
        test["expectedContractKind"] = "Mac memory upgrade local facts"
        test["expectedContractGate"] = "pass"
        test["directAnswer"] = True
        test["directTerms"] = ["No internal memory upgrade"]
        test["requiredTerms"] = normalize_terms(["This is why", "You should also consider", "unified memory", "AI"], limit=8)
        test["requiredContractProof"] = ["local hardware profile", "unified memory", "no internal memory upgrade", "AI performance"]
        test["anyTerms"] = []
        test["requiresSource"] = False
        test["webSearch"] = "disabled"
        test["minAnalyticalScore"] = 84
        test["maxDurationMs"] = 750
        test["goal"] = "Real chat-history regression: answer Mac memory and AI-performance questions from this Mac's local hardware profile instead of generic research."
    if not test["expectedProjectId"]:
        test.pop("expectedProjectId")
    if not test["requiredTerms"]:
        test.pop("requiredTerms")
    if not test["requiresSource"]:
        test.pop("requiresSource")
    return test


def session_paths():
    paths = []
    if SESSIONS_DIR.exists():
        paths.extend(SESSIONS_DIR.glob("**/*.jsonl"))
    if ARCHIVED_SESSIONS_DIR.exists():
        paths.extend(ARCHIVED_SESSIONS_DIR.glob("*.jsonl"))
    return sorted(set(paths))


def split_embedded_user_turns(text):
    text = str(text or "")
    if not re.search(r"(?m)^User:\s*", text) or not re.search(r"(?m)^Assistant:\s*", text):
        return [text]
    turns = []
    for match in re.finditer(r"(?ms)^User:\s*(.*?)(?=^Assistant:|^User:|\Z)", text):
        chunk = match.group(1).strip()
        if chunk:
            turns.append(chunk)
    return turns or [text]


def iter_user_messages(path):
    session_id = path.stem
    try:
        handle = path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            item_type = item.get("type")
            payload = item.get("payload") or {}
            if item_type == "session_meta":
                session_id = payload.get("id") or payload.get("session_id") or session_id
                continue
            if item_type != "response_item" or payload.get("type") != "message" or payload.get("role") != "user":
                continue
            text = import_codex_history.normalize_text(import_codex_history.extract_text(payload.get("content")))
            if import_codex_history.is_noise(text):
                continue
            for turn in split_embedded_user_turns(text):
                yield turn, session_id


def prompt_candidates():
    for path in session_paths():
        for text, session_id in iter_user_messages(path):
            if is_testable_prompt(text):
                yield text, f"{path.name}:{session_id}"


def load_golden_data():
    if GOLDEN_TESTS_PATH.exists():
        try:
            data = json.loads(GOLDEN_TESTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("version", 1)
                data.setdefault("createdAt", time.time())
                data.setdefault("tests", [])
                return data
        except Exception:
            pass
    now = time.time()
    return {"version": 1, "createdAt": now, "updatedAt": now, "tests": []}


def harvest(limit=DEFAULT_LIMIT, dry_run=False, replace_history=False):
    seen = set()
    tests = []
    for prompt, source in prompt_candidates():
        key = normalized_key(prompt)
        if not key or key in seen:
            continue
        seen.add(key)
        tests.append(golden_test_from_prompt(prompt, source))

    data = load_golden_data()
    removed = 0
    if replace_history:
        original_count = len(data.get("tests", []))
        data["tests"] = [item for item in data.get("tests", []) if item.get("source") != "history-harvest"]
        removed = original_count - len(data["tests"])
    existing = {item.get("id"): item for item in data.get("tests", []) if item.get("id")}
    tests.sort(key=lambda item: (-int(item.get("qualityScore") or 0), item.get("expectedProjectId", ""), item["name"].lower()))
    new_tests = [item for item in tests if item["id"] not in existing]
    old_tests = [item for item in tests if item["id"] in existing]
    selected = (new_tests + old_tests)[: max(0, int(limit or 0))]
    added = 0
    updated = 0
    for test in selected:
        old = existing.get(test["id"])
        if old:
            created = old.get("createdAt") or test["createdAt"]
            if old.get("source") == "history-harvest" or test.get("source") == "history-harvest":
                for key in DERIVED_HISTORY_TEST_KEYS:
                    if key not in test:
                        old.pop(key, None)
            old.update(test)
            old["createdAt"] = created
            old["updatedAt"] = time.time()
            updated += 1
        else:
            data["tests"].append(test)
            existing[test["id"]] = test
            added += 1

    data["tests"] = sorted(data.get("tests", []), key=lambda item: (item.get("group", ""), item.get("name", "")))
    data["updatedAt"] = time.time()

    summary = {
        "harvestedAt": datetime.now(timezone.utc).isoformat(),
        "sessionFiles": len(session_paths()),
        "candidatePrompts": len(tests),
        "selectedTests": len(selected),
        "added": added,
        "updated": updated,
        "removedHistoryTests": removed,
        "dryRun": dry_run,
        "goldenTestsPath": str(GOLDEN_TESTS_PATH),
        "summaryPath": str(HISTORY_TEST_SUMMARY_PATH),
    }
    if selected:
        summary["sampleTests"] = [{"id": item["id"], "name": item["name"], "project": item.get("expectedProjectId", "")} for item in selected[:10]]

    if not dry_run:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        GOLDEN_TESTS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        HISTORY_TEST_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Harvest private Codex chat prompts into local golden tests.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Maximum tests to add/update this run.")
    parser.add_argument("--dry-run", action="store_true", help="Scan and summarize without writing data/golden_tests.json.")
    parser.add_argument("--replace-history", action="store_true", help="Remove prior history-harvest tests before adding the new selected batch.")
    args = parser.parse_args()
    print(json.dumps(harvest(limit=args.limit, dry_run=args.dry_run, replace_history=args.replace_history), indent=2))


if __name__ == "__main__":
    main()
