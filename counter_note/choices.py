from collections import Counter


FEATURES = ("start", "1", "2", "3", "4", "5", "runes", "spells", "skills3", "skills6", "skills9")
SPECIAL_SKILLS = {"Aphelios", "Elise", "Jayce", "Karma", "Nidalee", "Udyr"}


def positive_id(value):
    return type(value) is int and value > 0


def rune_choice(participant):
    perks = participant.get("perks")
    if not isinstance(perks, dict) or not isinstance(perks.get("styles"), list):
        return None
    styles = perks["styles"]
    if len(styles) != 2 or any(not isinstance(s, dict) for s in styles):
        return None
    primary = [s for s in styles if s.get("description") == "primaryStyle"]
    secondary = [s for s in styles if s.get("description") == "subStyle"]
    if len(primary) != 1 or len(secondary) != 1:
        return None
    if primary[0].get("style") == secondary[0].get("style"):
        return None
    result, seen = [], set()
    for style, length in ((primary[0], 4), (secondary[0], 2)):
        selections = style.get("selections")
        if not positive_id(style.get("style")) or not isinstance(selections, list) or len(selections) != length:
            return None
        ids = [s.get("perk") if isinstance(s, dict) else None for s in selections]
        if any(not positive_id(i) or i in seen for i in ids) or len(set(ids)) != length:
            return None
        seen.update(ids)
        result.extend([str(style["style"]), *map(str, ids if length == 4 else sorted(ids))])
    return result


def skill_choices(participant, champion, events):
    if champion in SPECIAL_SKILLS:
        return {}, "unsupported_champion"
    level = participant.get("champLevel")
    if type(level) is not int or not 1 <= level <= 18:
        return {}, "missing_level"
    seen, sequence, timestamps = set(), [], set()
    for event in events:
        if event.get("type") != "SKILL_LEVEL_UP" or event.get("participantId") != participant["participantId"]:
            continue
        if event.get("levelUpType") != "NORMAL":
            return {}, "special_event"
        slot = event.get("skillSlot")
        if type(slot) is not int or slot not in (1, 2, 3, 4):
            return {}, "invalid_slot"
        identity = (event["timestamp"], slot)
        if identity in seen:
            continue
        seen.add(identity)
        if event["timestamp"] in timestamps:
            return {}, "ambiguous_order"
        timestamps.add(event["timestamp"])
        sequence.append("QWER"[slot - 1])
    ranks = Counter(sequence)
    if len(sequence) != level or any(ranks[s] > limit for s, limit in zip("QWER", (5, 5, 5, 3))):
        return {}, "incomplete_or_duplicate"
    return {f"skills{n}": sequence[:n] for n in (3, 6, 9) if len(sequence) >= n}, "observed"


def extract_choices(participant, champion, events):
    choices, status = {}, {}
    runes = rune_choice(participant)
    if runes:
        choices["runes"] = runes
    status["runes"] = "observed" if runes else "missing_or_invalid"
    spells = [participant.get("summoner1Id"), participant.get("summoner2Id")]
    valid_spells = all(positive_id(s) for s in spells) and len(set(spells)) == 2
    spellbook = bool(runes and "8360" in runes)
    if spellbook or not runes:
        valid_spells = False
    if valid_spells:
        choices["spells"] = list(map(str, sorted(spells)))
    status["spells"] = "observed" if valid_spells else "spellbook" if spellbook else "unknown_runes" if not runes else "missing_or_invalid"
    skills, status["skills"] = skill_choices(participant, champion, events)
    choices.update(skills)
    return choices, status


def values_for(record, feature):
    source = record.get("builds" if feature in FEATURES[:6] else "choices")
    values = source.get(feature) if isinstance(source, dict) else None
    if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
        return None
    return tuple(values)
