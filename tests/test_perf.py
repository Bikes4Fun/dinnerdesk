from app.perf import Laps, record_query, server_timing, start_request


def test_laps_add_up_and_repeat_names_accumulate():
    laps = Laps()
    laps.lap("a")
    laps.lap("b")
    laps.lap("a")
    assert list(laps.ms) == ["a", "b"]
    assert laps.total() == sum(laps.ms.values())
    laps.counts["picked"] = 3
    assert laps.fmt().startswith("picked=3 a=")


def test_request_stats_collect_queries_and_published_phases():
    stats = start_request()
    record_query(2.0)
    record_query(3.0)
    laps = Laps()
    laps.lap("load")
    laps.publish("suggest")
    assert (stats.queries, stats.db_ms) == (2, 5.0)
    header = server_timing(stats, 10.0)
    assert header.startswith('app;dur=10.0, db;dur=5.0;desc="2 queries", suggest.load;dur=')
