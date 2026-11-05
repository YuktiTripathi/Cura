import json

from app.llm.answer_stream import AnswerFieldStreamer


def _run(raw: str, size: int) -> str:
    out: list[str] = []
    streamer = AnswerFieldStreamer(out.append)
    for i in range(0, len(raw), size):
        streamer.feed(raw[i:i + size])
    return "".join(out)


def test_answer_text_is_streamed_for_any_chunk_size():
    answer = 'Line one.\n- Cholesterol: 277 mg/dL "high" \\ done → ok'
    raw = json.dumps({"answer": answer, "claims": [], "follow_up_questions": ['What is "answer": this?']})
    for size in (1, 2, 3, 5, 7, 50, 500):
        assert _run(raw, size) == answer


def test_nothing_is_streamed_without_an_answer_field():
    assert _run('{"claims": [], "follow_up_questions": []}', 4) == ""


def test_text_after_the_answer_is_not_streamed():
    raw = '{"answer": "Short.", "claims": ["extra"]}'
    assert _run(raw, 3) == "Short."
