from mystocktrack.data import StaticDataProvider
from mystocktrack.holdings import holdings_markdown


def test_holdings_cost_and_pnl(tmp_path, snapshots):
    path = tmp_path / "portfolio.toml"
    path.write_text(
        '[[positions]]\nticker = "QUAL"\navg_cost = 100.0\nquantity = 2\n',
        encoding="utf-8",
    )
    md = holdings_markdown(path, StaticDataProvider(snapshots))
    assert "QUAL" in md
    assert "200.00" in md
    assert "未實現損益" in md


def test_missing_price_is_not_assumed(tmp_path, snapshots):
    path = tmp_path / "portfolio.toml"
    path.write_text(
        '[[positions]]\nticker = "UNKNOWN"\navg_cost = 5.0\nquantity = 3\n',
        encoding="utf-8",
    )
    md = holdings_markdown(path, StaticDataProvider(snapshots))
    assert "N/A" in md
    assert "部分價格無法取得" in md
