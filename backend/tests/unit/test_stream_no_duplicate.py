"""A streamed answer must not be followed by semantic blocks built from the same answer."""

from app.pipeline.observability import ProgressEmitter


def test_streamed_tokens_mark_the_emitter_so_blocks_are_skipped():
    seen: list[str] = []
    emitter = ProgressEmitter(token_callback=seen.append)
    assert emitter.tokens_streamed is False
    emitter.token_callback("")
    assert emitter.tokens_streamed is False
    emitter.token_callback("Your B12 is low.")
    assert emitter.tokens_streamed is True
    assert seen == ["", "Your B12 is low."]


def test_emitter_without_streaming_still_allows_blocks():
    emitter = ProgressEmitter()
    assert emitter.token_callback is None and emitter.tokens_streamed is False
