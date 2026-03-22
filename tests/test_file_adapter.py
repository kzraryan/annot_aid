import pandas as pd

from annot_aid.db.file_adapter import FileAdapter
from annot_aid.db.base import FilterParams


def test_file_adapter_loads_data(tmp_path):
    # Use repo data by default
    fa = FileAdapter(root=".")
    bio = fa.get_biomarker_queue()
    loinc = fa.get_loinc_candidates(FilterParams())
    assert not bio.empty
    assert not loinc.empty
    assert {"id", "description"}.issubset(bio.columns)
    assert {"loinc_num", "long_common_name"}.issubset(loinc.columns)


def test_text_filtering():
    fa = FileAdapter(root=".")
    df = fa.get_loinc_candidates(FilterParams(text="Creatinine"))
    assert (df["long_common_name"].str.contains("Creatinine")).any()


def test_axis_filtering_component():
    fa = FileAdapter(root=".")
    params = FilterParams(axes={"Component": ["Creatinine"]})
    df = fa.get_loinc_candidates(params)
    assert not df.empty
    assert (df["component"] == "Creatinine").all()


def test_deprecated_toggle():
    fa = FileAdapter(root=".")
    df_no_dep = fa.get_loinc_candidates(FilterParams(include_deprecated=False))
    df_all = fa.get_loinc_candidates(FilterParams(include_deprecated=True))
    assert len(df_all) >= len(df_no_dep)
