from rag_pipelines.stats import percentile, render_table

N = dict(art=1, cl=2, pt=3, **{"in": 4, "out": 5, "imp": 6}, drop=7, app=1)


def test_percentile():
    xs = list(range(1, 101))
    assert (percentile(xs, 50), percentile(xs, 95), percentile(xs, 100), percentile([], 50)) == (50, 95, 100, 0)


def test_table_has_total_row():
    lines = render_table([("A", N, [10, 20]), ("B", N, [30])]).splitlines()
    assert len(lines) == 5 and lines[-1].startswith("| **Tổng** | 2 | 4 | 6 | 3 | 2 | 20 | 30 | 30 | 8 | 10 | 12 | 14 |")
