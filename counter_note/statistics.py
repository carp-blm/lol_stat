import math
from collections import Counter, defaultdict
from functools import lru_cache
from .config import CATEGORIES


def log_choose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


@lru_cache(maxsize=50000)
def fisher_greater(a, b, c, d):
    if min(a, b, c, d) < 0:
        raise ValueError("음수 도수입니다.")
    n, successes, draws = a + b + c + d, a + c, a + b
    if n == 0 or draws == 0 or c + d == 0:
        return 1.0
    terms = [log_choose(successes, k) + log_choose(n - successes, draws - k) - log_choose(n, draws) for k in range(a, min(draws, successes) + 1)]
    peak = max(terms)
    return min(1.0, math.exp(peak) * math.fsum(math.exp(term - peak) for term in terms))


def fdr_adjust(values, method="by"):
    if not values:
        return []
    if method not in ("bh", "by") or any(not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise ValueError("잘못된 FDR 입력입니다.")
    count = len(values)
    factor = math.fsum(1 / i for i in range(1, count + 1)) if method == "by" else 1
    ordered = sorted(range(count), key=lambda i: values[i])
    result, running = [1.0] * count, 1.0
    for rank in range(count, 0, -1):
        index = ordered[rank - 1]
        running = min(running, values[index] * count * factor / rank)
        result[index] = running
    return result


def wilson(wins, total):
    if not total:
        return None
    z = 1.959963984540054
    p = wins / total
    denominator = 1 + z * z / total
    midpoint = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0, midpoint - spread), min(1, midpoint + spread)]


def aggregate_pair(records, config):
    games = len(records)
    wins = sum(r["win"] for r in records)
    levels = {}
    for level in ("2", "3", "6"):
        outcomes = Counter(r["levels"][level]["outcome"] for r in records)
        sources = Counter(r["levels"][level]["source"] for r in records)
        observed = games - outcomes[None]
        levels[level] = {"first": outcomes[1], "opponentFirst": outcomes[-1], "ties": outcomes[0], "unknown": outcomes[None], "observed": observed, "rate": outcomes[1] / observed if observed else None, "opponentRate": outcomes[-1] / observed if observed else None, "eventPairs": sources["event"], "framePairs": sources["frame"], "ci": wilson(outcomes[1], observed)}
    solo, against = sum(r["solo"] for r in records), sum(r["soloAgainst"] for r in records)
    sufficient = games >= config["min_matchup_games"]
    pressure = sufficient and levels["6"]["observed"] >= config["min_level_observations"] and levels["6"]["first"] > levels["6"]["opponentFirst"]
    kill = sufficient and solo > against
    early = sufficient and any(levels[level]["observed"] >= config["min_level_observations"] and levels[level]["first"] < levels[level]["opponentFirst"] for level in ("2", "3"))
    category = "both" if pressure and kill else "pressure" if pressure else "solo" if kill else None
    builds, tested = {}, []
    for stage in ("start", "1", "2", "3", "4", "5"):
        eligible = [r for r in records if r["builds"].get(stage)]
        total, total_wins = len(eligible), sum(r["win"] for r in eligible)
        combos = defaultdict(lambda: [0, 0])
        for record in eligible:
            entry = combos[tuple(record["builds"][stage])]
            entry[0] += 1
            entry[1] += record["win"]
        rows = []
        for item_ids, (n, w) in combos.items():
            other_n, other_w = total - n, total_wins - w
            testable = n >= config["min_build_games"] and other_n >= config["min_build_games"]
            p = fisher_greater(w, n - w, other_w, other_n - other_w) if testable else None
            row = {"items": list(item_ids), "games": n, "wins": w, "pickRate": n / total, "winRate": w / n, "ci": wilson(w, n), "otherGames": other_n, "otherWinRate": other_w / other_n if other_n else None, "p": p, "q": None, "significant": False}
            rows.append(row)
            if testable:
                tested.append(row)
        builds[stage] = {"eligibleGames": total, "candidateCount": len(rows), "rows": rows}
    q_values = fdr_adjust([row["p"] for row in tested], config["fdr_method"])
    for row, q in zip(tested, q_values):
        row["q"] = q
        row["significant"] = q < config["fdr_alpha"] and row["winRate"] > row["otherWinRate"]
    for stage in builds.values():
        stage["rows"] = sorted(stage["rows"], key=lambda row: (-row["games"], -row["winRate"], row["items"]))[:10]
    return {"games": games, "wins": wins, "winRate": wins / games if games else None, "ci": wilson(wins, games), "levels": levels, "solo": {"kills": solo, "opponentKills": against, "perGame": solo / games if games else None, "opponentPerGame": against / games if games else None}, "category": category, "early": early, "sufficient": sufficient, "builds": builds, "fdr": {"method": config["fdr_method"], "alpha": config["fdr_alpha"], "tests": len(tested), "family": "이 라인·상대·챔피언의 시작~5코어 전체 적격 빌드"}}


def aggregate(records, config):
    from .recommendations import count_choices, recommendation_pair
    grouped = defaultdict(list)
    champion_records = defaultdict(list)
    for record in records:
        grouped[(record["lane"], record["enemy"], record["own"])].append(record)
        champion_records[(record["lane"], record["own"])].append(record)
    overall = {key: count_choices(rows) for key, rows in champion_records.items()}
    board = {"schemaVersion": 2, "id": "counter-note-published-v3", "matchups": {}, "earlyDisadvantage": {}, "tiers": {}, "rosterSort": "tier"}
    details, index = {}, {}
    for (lane, enemy, own), rows in sorted(grouped.items()):
        result = aggregate_pair(rows, config)
        result["recommendations"] = recommendation_pair(rows, overall[(lane, own)], config)
        details.setdefault(lane, {}).setdefault(enemy, {})[own] = result
        index.setdefault(lane, {}).setdefault(enemy, {})[own] = {k: result[k] for k in ("games", "winRate", "category", "early", "sufficient")}
        if result["category"]:
            groups = board["matchups"].setdefault(lane, {}).setdefault(enemy, {key: [] for key in CATEGORIES})
            groups[result["category"]].append(own)
            if result["early"]:
                board["earlyDisadvantage"].setdefault(lane, {}).setdefault(enemy, []).append(own)
    for lane, enemies in board["matchups"].items():
        for enemy, groups in enemies.items():
            for ids in groups.values():
                ids.sort(key=lambda own: (-index[lane][enemy][own]["games"], own))
    return board, index, details
