from app.contracts.risk_status import category_risk_highlight


def test_one_increased_or_very_high_label():
    assert category_risk_highlight(["Increased Risk"]) == "increased"
    assert category_risk_highlight(["Very High Risk"]) == "very_high"


def test_highest_label_wins_and_lower_bands_stay_plain():
    assert category_risk_highlight(["Healthy", "Increased Risk", "Very High Risk"]) == "very_high"
    assert category_risk_highlight(["Healthy", "High Risk", "low"]) is None
    assert category_risk_highlight([None, "", "unknown"]) is None
    assert category_risk_highlight([]) is None
