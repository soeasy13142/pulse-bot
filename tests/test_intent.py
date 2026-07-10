from pulse_bot.intent import infer_intent


def test_infer_idea_chinese():
    """含"想"的句子应判为 idea."""
    assert infer_intent("想做个 skills 管理器") == "idea"
    assert infer_intent("想做开源项目") == "idea"


def test_infer_task_chinese():
    """含"要"/"需要"的句子应判为 task."""
    assert infer_intent("要修一下 vault 的 frontmatter") == "task"
    assert infer_intent("需要写 plan 文件") == "task"


def test_infer_question_chinese():
    """含问号的句子应判为 question."""
    assert infer_intent("为什么 Dataview 查询这么慢？") == "question"


def test_infer_reference_default():
    """无关键字的句子应默认为 reference."""
    assert infer_intent("看了本书") == "reference"
    assert infer_intent("claude code obsidian") == "reference"


def test_infer_priority_order():
    """问号优先于其他关键字."""
    assert infer_intent("想做 X？") == "question"
