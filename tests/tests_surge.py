from streaming.surge_engine import calculate_surge

def test_high_demand():
    assert calculate_surge("Mumbai", 150) > 2.5

def test_low_demand():
    assert calculate_surge("Chennai", 10) == 1.0
