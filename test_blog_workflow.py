import unittest
from unittest.mock import patch

from blog_workflow import (
    MAX_REVISION_ATTEMPTS,
    Research,
    ResearchFact,
    markdown_to_html,
    make_html,
    pass_review_gate,
    slugify,
)


class BlogWorkflowTests(unittest.TestCase):
    def test_slugify_produces_safe_non_empty_path_component(self):
        self.assertEqual(slugify("  What’s New in Python? "), "what-s-new-in-python")
        self.assertEqual(slugify("..."), "blog-post")

    def test_markdown_to_html_escapes_untrusted_html(self):
        rendered = markdown_to_html(
            "# Title\n\n<script>alert(1)</script>\n\n- first\n- second"
        )
        self.assertIn("<h1>Title</h1>", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertIn("<ul><li>first</li><li>second</li></ul>", rendered)

    def test_make_html_includes_sources_and_tags(self):
        research = Research(
            facts=[
                ResearchFact(
                    "A cited fact",
                    "A supporting excerpt.",
                    "Example Source",
                    "https://example.com/fact",
                )
            ]
        )
        page = make_html("Example", "An article.", ["gardening"], research, "header.png")
        self.assertIn('<img class="hero" src="header.png"', page)
        self.assertIn("Example Source", page)
        self.assertIn("gardening", page)

    def test_review_gate_stops_after_three_revisions(self):
        research = Research(
            facts=[
                ResearchFact(
                    f"Fact {index}",
                    f"Evidence {index}",
                    f"Source {index}",
                    f"https://example.com/{index}",
                )
                for index in range(1, 5)
            ]
        )
        with (
            patch("blog_workflow.review_draft", return_value=(False, "Revise")) as review,
            patch(
                "blog_workflow.write_draft",
                side_effect=[
                    (f"Title {index}", f"Draft {index} [1] [2] [3] [4]")
                    for index in range(1, MAX_REVISION_ATTEMPTS + 1)
                ],
            ) as writer,
            self.assertRaisesRegex(RuntimeError, "3 revision attempts"),
        ):
            pass_review_gate(
                object(),
                stage="editor",
                topic="Topic",
                brief="Brief",
                research=research,
                title="Title",
                markdown="Draft [1] [2] [3] [4]",
            )
        self.assertEqual(review.call_count, MAX_REVISION_ATTEMPTS + 1)
        self.assertEqual(writer.call_count, MAX_REVISION_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
