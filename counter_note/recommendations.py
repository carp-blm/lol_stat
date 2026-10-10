import math
from collections import defaultdict
from .choices import FEATURES, values_for
from .statistics import fisher_greater, fdr_adjust, wilson


def count_choices(records):
    counts = {feature: defaultdict(lambda: [0, 0]) for feature in FEATURES}
    for record in records:
        for feature in FEATURES:
            values = values_for(record, feature)
            if values:
                cell = counts[feature][values]
                cell[0] += 1
                cell[1] += int(record["win"])
    return counts


def interaction_test(target, target_other, control, control_other, minimum=20, minimum_cell=5):
    groups = (target, target_other, control, control_other)
    if any(type(n) is not int or type(w) is not int or not 0 <= w <= n for n, w in groups):
        raise ValueError("비교 도수는 0 ≤ 승수 ≤ 경기 수인 정수여야 합니다.")
    if any(n < minimum for n, _ in groups):
        return {"status": "insufficient_sample", "p": None, "interactionP": None, "withinP": None, "ratio": None, "ratioCi": None}
    cells = [x for n, w in groups for x in (w, n - w)]
    if any(x < minimum_cell for x in cells):
        return {"status": "sparse_outcomes", "p": None, "interactionP": None, "withinP": None, "ratio": None, "ratioCi": None}
    a, b, c, d, e, f, g, h = cells
    log_ratio = math.log(a) - math.log(b) - math.log(c) + math.log(d) - math.log(e) + math.log(f) + math.log(g) - math.log(h)
    standard_error = math.sqrt(math.fsum(1 / cell for cell in cells))
    p_interaction = 0.5 * math.erfc(log_ratio / standard_error / math.sqrt(2))
    p_within = fisher_greater(a, b, c, d)
    return {"status": "tested", "p": max(p_interaction, p_within), "interactionP": p_interaction, "withinP": p_within, "ratio": math.exp(log_ratio), "ratioCi": [math.exp(log_ratio - 1.959963984540054 * standard_error), math.exp(log_ratio + 1.959963984540054 * standard_error)]}


def recommendation_pair(records, overall, config):
    local = count_choices(records)
    features, tested = {}, []
    minimum = config.get("min_comparison_games", 20)
    minimum_cell = config.get("min_comparison_outcomes", 5)
    for feature in FEATURES:
        local_n = sum(v[0] for v in local[feature].values())
        local_w = sum(v[1] for v in local[feature].values())
        all_n = sum(v[0] for v in overall[feature].values())
        all_w = sum(v[1] for v in overall[feature].values())
        rows = []
        for values, (n, w) in local[feature].items():
            total_n, total_w = overall[feature].get(values, (0, 0))
            control_n, control_w = total_n - n, total_w - w
            other = (local_n - n, local_w - w)
            control_other = (all_n - local_n - control_n, all_w - local_w - control_w)
            if min(control_n, control_w, control_n - control_w, *control_other, control_other[0] - control_other[1]) < 0:
                raise ValueError("전체 표본에 해당 매치업 표본이 포함되어야 합니다.")
            test = interaction_test((n, w), other, (control_n, control_w), control_other, minimum, minimum_cell)
            row = {"values": list(values), "games": n, "wins": w, "winRate": w / n, "ci": wilson(w, n), "pickRate": n / local_n, "alternativeGames": other[0], "alternativeWinRate": other[1] / other[0] if other[0] else None, "overallGames": total_n, "overallWinRate": total_w / total_n, "baselineGames": control_n, "baselineWinRate": control_w / control_n if control_n else None, "baselineAlternativeGames": control_other[0], "baselineAlternativeWinRate": control_other[1] / control_other[0] if control_other[0] else None, **test, "q": None, "significant": False}
            rows.append(row)
            if row["p"] is not None:
                tested.append(row)
        features[feature] = {"observedGames": local_n, "excludedGames": len(records) - local_n, "baselineGames": all_n - local_n, "candidateCount": len(rows), "status": "available" if local_n else "unavailable", "rows": rows}
    for row, q in zip(tested, fdr_adjust([r["p"] for r in tested], config["fdr_method"])):
        row["q"] = q
        row["significant"] = q < config["fdr_alpha"] and row["ratio"] > 1 and row["winRate"] > row["alternativeWinRate"]
    for feature in features.values():
        feature["rows"] = sorted(feature["rows"], key=lambda row: (-row["games"], -row["winRate"], row["values"]))[:10]
    return {"schemaVersion": 1, "features": features, "minimumGames": minimum, "minimumOutcomes": minimum_cell, "fdr": {"tests": len(tested), "method": config["fdr_method"], "alpha": config["fdr_alpha"], "family": "동일 라인·상대·내 챔피언의 모든 선택지·단계, 상위 10개 제한 전"}, "baseline": "같은 챔피언·라인·서버·큐·패치·기간의 다른 상대 경기", "method": "단측 로그 오즈비 상호작용 Wald 검정과 매치업 내 Fisher 검정의 교집합(max p)"}
