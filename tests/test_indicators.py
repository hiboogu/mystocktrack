from mystocktrack import indicators as ind


def test_sma_and_return():
    closes = [1, 2, 3, 4, 5]
    assert ind.sma(closes, 5) == 3
    assert ind.sma(closes, 6) is None
    assert ind.pct_return(closes, 4) == 4.0


def test_max_drawdown():
    assert ind.max_drawdown([100, 120, 60, 90]) == 0.5
    assert ind.max_drawdown([1, 2, 3]) == 0


def test_rsi_extremes():
    assert ind.rsi(list(range(1, 30)), 14) == 100.0
    assert ind.rsi(list(range(30, 1, -1)), 14) == 0.0


def test_volatility_needs_history():
    assert ind.annualized_volatility([1.0] * 5) is None
    assert ind.annualized_volatility([1.0] * 40) == 0.0
