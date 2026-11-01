"""Interactive AI-assisted blog publishing workflow."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

TEXT_MODEL = "gpt-6-luna"
IMAGE_MODEL = "gpt-image-2.5-flare"
MAX_REVISION_ATTEMPTS = 3


@dataclass(frozen=True)
class ResearchFact:
    fact: str
    excerpt: str
    title: str
    url: str


@dataclass(frozen=True)
class Research:
    facts: list[ResearchFact]


def ask_json(
    client: OpenAI,
    *,
    name: str,
    schema: dict[str, Any],
    prompt: str,
    tools: list[dict[str, Any]] | None = None,
    max_tool_calls: int | None = None,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "model": TEXT_MODEL,
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": name,
                "strict": True,
                "schema": schema,
            }
        },
    }
    if tools is not None:
        request["tools"] = tools
    if max_tool_calls is not None:
        request["max_tool_calls"] = max_tool_calls

    response = client.responses.create(**request)
    if not response.output_text:
        raise RuntimeError(f"{name} returned an empty response.")
    result = json.loads(response.output_text)
    if not isinstance(result, dict):
        raise RuntimeError(f"{name} returned an invalid response shape.")
    return result


def clarify_topic(client: OpenAI, topic: str) -> str:
    result = ask_json(
        client,
        name="blog_clarifications",
        schema={
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 3,
                }
            },
            "required": ["questions"],
            "additionalProperties": False,
        },
        prompt=(
            "You are the Clarifier Agent. Formulate up to 3 targeted questions "
            "that would materially improve a blog post based on this topic. "
            "If the topic is already clear enough, return no questions.\n"
            f"Topic: {topic}"
        ),
    )
    questions = result["questions"]
    if not isinstance(questions, list) or len(questions) > 3:
        raise RuntimeError("Clarifier Agent returned more than 3 questions.")

    answers: list[str] = []
    for index, question in enumerate(questions, start=1):
        if not isinstance(question, str) or not question.strip():
            raise RuntimeError("Clarifier Agent returned an empty question.")
        answer = input(f"\nClarification {index}/{len(questions)}: {question}\n> ")
        if answer.strip():
            answers.append(f"Q: {question}\nA: {answer.strip()}")
    return "\n".join(answers) if answers else "No additional clarification."


def research_topic(client: OpenAI, topic: str, brief: str) -> Research:
    result = ask_json(
        client,
        name="blog_research",
        schema={
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "fact": {"type": "string"},
                            "excerpt": {"type": "string"},
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                        },
                        "required": ["fact", "excerpt", "title", "url"],
                        "additionalProperties": False,
                    },
                    "minItems": 4,
                    "maxItems": 4,
                }
            },
            "required": ["facts"],
            "additionalProperties": False,
        },
        prompt=(
            "You are the Researcher Agent. Research the topic using web search. "
            "Return exactly 4 concise, useful facts, each verified against a "
            "credible source. For each fact include that source's exact title "
            "and URL, plus a short paraphrase of the relevant supporting passage "
            "as an evidence excerpt. Do not invent citations or copy long "
            "passages verbatim. Prefer primary or authoritative sources and "
            "avoid repeating the same source.\n"
            f"Topic: {topic}\nBrief: {brief}"
        ),
        tools=[{"type": "web_search"}],
        max_tool_calls=2,
    )
    raw_facts = result["facts"]
    if not isinstance(raw_facts, list) or len(raw_facts) != 4:
        raise RuntimeError("Researcher Agent must return exactly 4 cited facts.")

    facts: list[ResearchFact] = []
    for item in raw_facts:
        if not isinstance(item, dict):
            raise RuntimeError("Researcher Agent returned an invalid fact.")
        fact = item.get("fact")
        excerpt = item.get("excerpt")
        title = item.get("title")
        url = item.get("url")
        parsed_url = urlparse(url) if isinstance(url, str) else None
        if (
            not isinstance(fact, str)
            or not fact.strip()
            or not isinstance(excerpt, str)
            or not excerpt.strip()
            or not isinstance(title, str)
            or not title.strip()
            or parsed_url is None
            or parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
        ):
            raise RuntimeError("Researcher Agent returned an invalid fact citation.")
        facts.append(
            ResearchFact(
                fact=fact.strip(),
                excerpt=excerpt.strip(),
                title=title.strip(),
                url=url.strip(),
            )
        )
    return Research(facts=facts)


def render_facts(research: Research) -> str:
    return "\n".join(
        f"[{index}] {fact.fact} (Evidence excerpt: {fact.excerpt}) "
        f"(Source: {fact.title} - {fact.url})"
        for index, fact in enumerate(research.facts, start=1)
    )


def write_draft(
    client: OpenAI,
    topic: str,
    brief: str,
    research: Research,
    *,
    previous_draft: str | None = None,
    feedback: str | None = None,
) -> tuple[str, str]:
    result = ask_json(
        client,
        name="blog_draft",
        schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "markdown": {"type": "string"},
            },
            "required": ["title", "markdown"],
            "additionalProperties": False,
        },
        prompt=(
            "You are the Writer Agent. Write an original, useful, well-structured "
            "Markdown blog post based on the topic, brief, and cited research. "
            "Use the supplied citations inline as [1] through [4], and do not "
            "introduce unsupported factual claims. Return a concise title and "
            "the complete post body (do not include a duplicate title heading).\n"
            f"Topic: {topic}\nBrief and clarifications: {brief}\n"
            f"Verified research:\n{render_facts(research)}\n"
            f"Previous draft:\n{previous_draft or 'None'}\n"
            f"Revision feedback:\n{feedback or 'None'}"
        ),
    )
    title = result.get("title")
    markdown = result.get("markdown")
    if (
        not isinstance(title, str)
        or not title.strip()
        or not isinstance(markdown, str)
        or not markdown.strip()
    ):
        raise RuntimeError("Writer Agent returned an empty title or article.")
    return title.strip(), markdown.strip()


def review_draft(
    client: OpenAI,
    *,
    stage: str,
    title: str,
    markdown: str,
    research: Research,
) -> tuple[bool, str]:
    result = ask_json(
        client,
        name=f"blog_{stage}_review",
        schema={
            "type": "object",
            "properties": {
                "approved": {"type": "boolean"},
                "feedback": {"type": "string"},
            },
            "required": ["approved", "feedback"],
            "additionalProperties": False,
        },
        prompt=(
            f"You are the {stage.replace('_', ' ').title()} Agent. Review this "
            "draft and return a programmatic approval verdict with actionable "
            "feedback. Reject unsupported claims, inaccurate or missing "
            "citations, and unclear writing. For the Content Verifier, focus "
            "especially on natural, authentic phrasing and tone/style. For the "
            "Editor, focus on structure, grammar, readability, and consistency. "
            "Approve only when the relevant checks pass.\n"
            f"Title: {title}\nArticle:\n{markdown}\n"
            f"Research sources:\n{render_facts(research)}"
        ),
    )
    approved = result.get("approved")
    feedback = result.get("feedback")
    if not isinstance(approved, bool) or not isinstance(feedback, str):
        raise RuntimeError(f"{stage} Agent returned an invalid review verdict.")
    return approved, feedback


def pass_review_gate(
    client: OpenAI,
    *,
    stage: str,
    topic: str,
    brief: str,
    research: Research,
    title: str,
    markdown: str,
) -> tuple[str, str]:
    for revision_attempt in range(MAX_REVISION_ATTEMPTS + 1):
        approved, feedback = review_draft(
            client,
            stage=stage,
            title=title,
            markdown=markdown,
            research=research,
        )
        missing_citations = [
            str(index)
            for index in range(1, len(research.facts) + 1)
            if not re.search(rf"(?<!\d)\[{index}\](?!\d)", markdown)
        ]
        if approved and not missing_citations:
            return title, markdown
        if approved:
            feedback = (
                "Add inline citations for each researched fact using these "
                f"citation numbers: {', '.join(missing_citations)}."
            )
        if revision_attempt == MAX_REVISION_ATTEMPTS:
            break
        print(
            f"{stage.replace('_', ' ').title()} requested revision "
            f"{revision_attempt + 1}/{MAX_REVISION_ATTEMPTS}."
        )
        title, markdown = write_draft(
            client,
            topic,
            brief,
            research,
            previous_draft=markdown,
            feedback=feedback,
        )
    raise RuntimeError(
        f"The {stage.replace('_', ' ')} review did not approve the draft after "
        f"{MAX_REVISION_ATTEMPTS} revision attempts. Last feedback: {feedback}"
    )


def generate_header_image(
    client: OpenAI, topic: str, title: str, markdown: str, output_path: Path
) -> str:
    result = ask_json(
        client,
        name="blog_image_prompt",
        schema={
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
            "additionalProperties": False,
        },
        prompt=(
            "You are the Image Designer. Create a detailed image-generation "
            "prompt for a tasteful, original landscape blog header image. "
            "Describe visual composition, subject, lighting, and palette. "
            "Do not request text or lettering in the image.\n"
            f"Topic: {topic}\nTitle: {title}\nArticle excerpt:\n{markdown[:1800]}"
        ),
    )
    image_prompt = result.get("prompt")
    if not isinstance(image_prompt, str) or not image_prompt.strip():
        raise RuntimeError("Image Designer returned an empty image prompt.")

    image_response = client.images.generate(
        model=IMAGE_MODEL,
        prompt=image_prompt.strip(),
        size="1536x1024",
        output_format="png",
    )
    if not image_response.data or not image_response.data[0].b64_json:
        raise RuntimeError("Image generation returned no image data.")
    import base64

    output_path.write_bytes(base64.b64decode(image_response.data[0].b64_json))
    return image_prompt.strip()


def generate_tags(client: OpenAI, title: str, markdown: str) -> list[str]:
    result = ask_json(
        client,
        name="blog_tags",
        schema={
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 3,
                }
            },
            "required": ["tags"],
            "additionalProperties": False,
        },
        prompt=(
            "You are the Tag Generator. Generate exactly 3 concise, distinct, "
            "high-relevance tags for article categorization. Return tags without "
            "a leading #.\n"
            f"Title: {title}\nArticle:\n{markdown}"
        ),
    )
    tags = result.get("tags")
    if (
        not isinstance(tags, list)
        or len(tags) != 3
        or any(not isinstance(tag, str) or not tag.strip() for tag in tags)
    ):
        raise RuntimeError("Tag Generator must return exactly 3 non-empty tags.")
    return [tag.strip().lstrip("#") for tag in tags]


def markdown_to_html(markdown: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_tag: str | None = None
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph:
            text = "<br>\n".join(paragraph)
            blocks.append(f"<p>{text}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if list_items and list_tag:
            blocks.append(f"<{list_tag}>{''.join(list_items)}</{list_tag}>")
        list_items.clear()
        list_tag = None

    for raw_line in markdown.splitlines():
        line = html.escape(raw_line.strip())
        if raw_line.strip().startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                code = "\n".join(code_lines)
                blocks.append(f"<pre><code>{code}</code></pre>")
                code_lines.clear()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(html.escape(raw_line))
            continue
        if not line:
            flush_paragraph()
            flush_list()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{heading.group(2)}</h{level}>")
            continue
        item = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if item:
            flush_paragraph()
            if list_tag != "ul":
                flush_list()
                list_tag = "ul"
            list_items.append(f"<li>{item.group(1)}</li>")
            continue
        item = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if item:
            flush_paragraph()
            if list_tag != "ol":
                flush_list()
                list_tag = "ol"
            list_items.append(f"<li>{item.group(1)}</li>")
            continue
        flush_list()
        paragraph.append(line)
    flush_paragraph()
    flush_list()
    if in_code:
        code = "\n".join(code_lines)
        blocks.append(f"<pre><code>{code}</code></pre>")
    return "\n".join(blocks)


def make_html(
    title: str,
    markdown: str,
    tags: list[str],
    research: Research,
    image_name: str,
) -> str:
    source_list = "\n".join(
        f'<li><a href="{html.escape(fact.url, quote=True)}" '
        f'rel="noopener noreferrer">{html.escape(fact.title)}</a></li>'
        for fact in research.facts
    )
    tag_list = " ".join(
        f'<span class="tag">{html.escape(tag)}</span>' for tag in tags
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{html.escape(title, quote=True)}">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #172033; background: #f4f6fa; }}
    body {{ margin: 0; }}
    main {{ max-width: 780px; margin: 3rem auto; padding: 2rem; background: white; border-radius: 16px; box-shadow: 0 8px 32px #17203312; }}
    h1 {{ line-height: 1.15; }}
    .hero {{ width: 100%; aspect-ratio: 3 / 2; object-fit: cover; border-radius: 12px; }}
    article {{ line-height: 1.75; }}
    article h2, article h3 {{ margin-top: 2rem; }}
    .tag {{ display: inline-block; margin: .25rem .4rem .25rem 0; padding: .3rem .7rem; border-radius: 999px; background: #edf2ff; }}
    .sources {{ border-top: 1px solid #e5e9f2; margin-top: 2rem; padding-top: 1rem; }}
    a {{ color: #3159b8; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{html.escape(title)}</h1>
      <img class="hero" src="{html.escape(image_name, quote=True)}" alt="">
      <p>{tag_list}</p>
    </header>
    <article>
      {markdown_to_html(markdown)}
    </article>
    <section class="sources" aria-labelledby="sources-heading">
      <h2 id="sources-heading">Sources</h2>
      <ol>{source_list}</ol>
    </section>
  </main>
</body>
</html>
"""


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:60].strip("-") or "blog-post"


def run_workflow(topic: str, output_root: Path) -> Path:
    load_dotenv()
    client = OpenAI()

    print("Clarifier Agent: preparing targeted questions...")
    brief = clarify_topic(client, topic)
    print("Researcher Agent: searching for verified facts and sources...")
    research = research_topic(client, topic, brief)
    print("Writer Agent: drafting the article...")
    title, markdown = write_draft(client, topic, brief, research)

    print("Content Verifier: checking tone, style, authenticity, and citations...")
    title, markdown = pass_review_gate(
        client,
        stage="content_verifier",
        topic=topic,
        brief=brief,
        research=research,
        title=title,
        markdown=markdown,
    )
    print("Editor Agent: checking editorial quality...")
    title, markdown = pass_review_gate(
        client,
        stage="editor",
        topic=topic,
        brief=brief,
        research=research,
        title=title,
        markdown=markdown,
    )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    publish_dir = output_root / f"{timestamp}-{slugify(title)}"
    publish_dir.mkdir(parents=True, exist_ok=False)

    print("Image Designer: creating the landscape header image...")
    image_prompt = generate_header_image(
        client, topic, title, markdown, publish_dir / "header.png"
    )
    print("Tag Generator: generating article tags...")
    tags = generate_tags(client, title, markdown)

    (publish_dir / "article.md").write_text(
        f"# {title}\n\n{markdown}\n", encoding="utf-8"
    )
    (publish_dir / "index.html").write_text(
        make_html(title, markdown, tags, research, "header.png"), encoding="utf-8"
    )
    (publish_dir / "metadata.json").write_text(
        json.dumps(
            {
                "title": title,
                "topic": topic,
                "tags": tags,
                "image_prompt": image_prompt,
                "sources": [
                    {
                        "fact": fact.fact,
                        "excerpt": fact.excerpt,
                        "title": fact.title,
                        "url": fact.url,
                    }
                    for fact in research.facts
                ],
                "text_model": TEXT_MODEL,
                "image_model": IMAGE_MODEL,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return publish_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Research, write, review, illustrate, and publish a blog post."
    )
    parser.add_argument("topic", nargs="?", help="Topic for the blog post")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("published"),
        help="Directory for generated blog posts (default: published)",
    )
    args = parser.parse_args()
    topic = (args.topic or input("Blog topic: ")).strip()
    if not topic:
        parser.error("A non-empty blog topic is required.")

    try:
        publish_dir = run_workflow(topic, args.output)
    except OpenAIError as error:
        print(f"OpenAI API error: {error}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"Workflow failed: {error}", file=sys.stderr)
        return 1

    print(f"\nPublished blog files: {publish_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
