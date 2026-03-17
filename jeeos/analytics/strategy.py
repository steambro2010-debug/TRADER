from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "jee_past_questions.csv"


def strategy_dataframe() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    grouped = df.groupby(["subject", "chapter"], as_index=False).agg({"questions": "sum", "marks": "sum"})
    grouped["roi_score"] = grouped["marks"] / grouped["questions"]
    grouped = grouped.sort_values(["marks", "roi_score"], ascending=False)
    return grouped
