import pandas as pd

from annot_aid.model.filtering import apply_filters


def sample_df():
    return pd.DataFrame([
        {"loinc_num": "1", "long_name": "Alpha", "component": "A", "property": "P1", "time": "Pt", "system": "Sys1", "scale": "Qn", "method": "M1", "class": "C", "status": "Active", "deprecated": False},
        {"loinc_num": "2", "long_name": "Beta", "component": "B", "property": "P2", "time": "Pt", "system": "Sys2", "scale": "Qn", "method": "M2", "class": "C", "status": "Active", "deprecated": True},
        {"loinc_num": "3", "long_name": "Gamma", "component": "A", "property": "P2", "time": "24H", "system": "Sys1", "scale": "Ord", "method": "M1", "class": "D", "status": "Active", "deprecated": False},
    ])


def test_text_search():
    df = sample_df()
    out = apply_filters(df, text="alpha")
    assert list(out["loinc_num"]) == ["1"]


def test_axis_filters_and_deprecated():
    df = sample_df()
    out = apply_filters(df, axes={"Component": ["B"], "Property": ["P2"]}, include_deprecated=False)
    assert out.empty  # B,P2 row is deprecated and should be excluded
    out_all = apply_filters(df, axes={"Component": ["B"], "Property": ["P2"]}, include_deprecated=True)
    assert list(out_all["loinc_num"]) == ["2"]
