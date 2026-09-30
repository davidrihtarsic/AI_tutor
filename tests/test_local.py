"""Small tests that do not require an OpenAI API key."""

from services.tutor_service import discover_tutors, knowledge_files, load_tutor_instructions


def test_example_tutors_are_discovered():
    ids = {item["id"] for item in discover_tutors()}
    assert "robotics" in ids
    assert "electronics" in ids


def test_robotics_has_knowledge_files():
    files = knowledge_files("robotics")
    assert files
    assert all(path.suffix == ".md" for path in files)


def test_tutor_instructions_are_markdown():
    text = load_tutor_instructions("robotics")
    assert text.startswith("# ")
