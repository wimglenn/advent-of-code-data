from aocd.models import Puzzle


def test_get_answer(tmpdir):
    saved = tmpdir / ".config/aocd/thetesttoken/2017/13b_answer.txt"
    saved.ensure(file=True)
    saved.write("the answer")
    puzzle = Puzzle(day=13, year=2017)
    assert puzzle.answer_b == "the answer"
