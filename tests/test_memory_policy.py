from core.memory.write_policy import MemoryWritePolicy


def test_memory_policy_filters_short_text() -> None:
    policy = MemoryWritePolicy()

    assert policy.should_save("short").save is False
    assert policy.should_save("This should be kept").save is True
