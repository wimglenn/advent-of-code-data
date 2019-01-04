import aocd


def test_get_answer(tmpdir):
    saved = tmpdir / ".config/aocd/thetesttoken/2017/13b_answer.txt"
    saved.ensure(file=True)
    saved.write("the answer")
    answer = aocd.get_answer(day=13, year=2017, level=2)
    assert answer == "the answer"
