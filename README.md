# Blog Generator

This project implements the blog-production workflow shown in
[`Blog Workflow.drawio.png`](<Blog Workflow.drawio.png>). It takes a topic,
clarifies the brief, researches supporting facts, writes and reviews an article,
generates a header image and tags, and creates a local HTML page.

![Blog workflow diagram](<Blog Workflow.drawio.png>)

## Requirements and setup

- Python and the dependencies listed in [`requirements.txt`](requirements.txt).
- An `OPENAI_API_KEY` set in the environment or in a `.env` file in this
  directory. Keep the key private; do not commit `.env`.
- API access to `gpt-6-luna`, `gpt-image-2.5-flare`, and the Responses API
  `web_search` tool.

Install dependencies in the project's virtual environment if needed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the workflow

Pass a topic on the command line:

```powershell
.\.venv\Scripts\python.exe blog_workflow.py "How community gardens improve cities"
```

Or omit the topic to be prompted interactively:

```powershell
.\.venv\Scripts\python.exe blog_workflow.py
```

Choose a different output root with `--output`:

```powershell
.\.venv\Scripts\python.exe blog_workflow.py --output .\published "Your topic"
```

The workflow runs the stages below in order. All text generation and review
stages use `gpt-6-luna`; image generation uses `gpt-image-2.5-flare`.

## Agents and stages

### 1. Clarifier Agent

**Working:** Reads the submitted topic and decides whether a more focused
audience, angle, or scope would help. It can ask up to three targeted
clarification questions. The answers are collected in the terminal. Blank
answers are omitted. If there are no useful questions or no answers, the
workflow continues with the original topic and a note that there was no
additional clarification.

**Input:** The topic supplied on the command line or at the `Blog topic:` prompt.

**Output:** Zero to three questions for the user, followed by a brief containing
the non-empty question-and-answer pairs. The brief is passed to the Researcher
and Writer.

### 2. Researcher Agent

**Working:** Uses the Responses API `web_search` tool to find research relevant
to the topic and brief. The request is capped at two web-search tool calls. It
returns exactly four concise facts, each with a short supporting evidence
excerpt, a source title, and an HTTP(S) source URL. The workflow checks the
response shape and URL format before proceeding.

**Input:** The original topic and clarification brief.

**Output:** Four structured research records (`fact`, `excerpt`, `title`, and
`url`). They are supplied to the Writer and review stages, and the sources are
included in the final HTML and `metadata.json`.

### 3. Writer Agent

**Working:** Produces an original, structured Markdown article based on the
topic, brief, and research. It is instructed to use inline citations `[1]`
through `[4]` and avoid unsupported factual claims. When a reviewer requests
changes, it receives the prior draft and the review feedback and produces a
revised draft.

**Input:** Topic, clarification brief, four cited facts, and—during a revision—
the previous draft and reviewer feedback.

**Output:** A title and Markdown article body. Each accepted draft must contain
an inline marker for every supplied research item.

### 4. Content Verifier

**Working:** Reviews the title and article against the research, focusing on
natural, authentic phrasing, tone, style, clarity, and citations. It returns a
structured JSON verdict. On rejection, its feedback is sent to the Writer.
This review gate allows an initial review plus up to three revisions; the
workflow stops with an error if the final attempt is still rejected or lacks
required inline citations.

**Input:** Draft title, Markdown article, and the four research records.

**Output:** A JSON object with `approved` (`true` or `false`) and `feedback`.
Only an approved draft with all four inline citation markers proceeds to the
Editor.

### 5. Editor Agent

**Working:** Performs a second review, focusing on structure, grammar,
readability, and consistency, as well as the supplied research and citations.
It can request up to three revisions, in addition to the initial review. If the
draft is still not approved, the workflow stops rather than publishing an
unapproved article.

**Input:** The title and draft approved by the Content Verifier, plus the
research records.

**Output:** A JSON object with `approved` (`true` or `false`) and actionable
`feedback`. The approved title and article are passed to the final stages.

### 6. Image Designer

**Working:** First asks `gpt-6-luna` to describe a suitable original landscape
header illustration based on the topic, title, and an article excerpt. It then
passes that prompt to `gpt-image-2.5-flare`.

**Input:** Topic, approved title, and up to the first 1,800 characters of the
article.

**Output:** A generated PNG header image at 1536 × 1024 pixels, saved as
`header.png`, and the image prompt recorded in `metadata.json`.

### 7. Tag Generator

**Working:** Selects concise, distinct, contextually relevant categories for
the approved article.

**Input:** Approved title and full Markdown article.

**Output:** Exactly three non-empty tags. They appear in the HTML page and
`metadata.json`.

### 8. HTML Developer

**Working:** The final page is assembled locally by the Python workflow (it is
not a separate model-powered agent). It escapes generated content before
inserting it into the page, adds the header image, tags, and source links, and
uses a small built-in stylesheet.

**Input:** Approved title and article, generated image filename, three tags,
and the four research sources.

**Output:** `index.html`, a local page that can be opened in a browser. Its
article renderer supports headings, paragraphs, ordered and unordered lists,
and fenced code blocks.

## Generated files

Each successful run creates a timestamped folder beneath `published` (or the
directory specified with `--output`):

- `article.md` — approved article in Markdown, with its title.
- `index.html` — local, styled blog page with image, tags, and source links.
- `header.png` — generated landscape header illustration.
- `metadata.json` — topic, title, tags, image prompt, research facts and sources,
  and model IDs.

The CLI prints the resulting folder path. Open its `index.html` to view the
page. This creates local files; it does not upload or deploy them.

## Assumptions

- The topic is provided in English, and the user can answer clarification
  prompts in the terminal if asked.
- The configured API key is valid, billing is enabled as needed, and the
  account can use both specified model IDs and `web_search`.
- Web search can return enough credible material in at most two tool calls.
- The four research facts and reviewer verdicts are model-generated. The
  workflow checks their structure and citation markers, but it does not
  independently establish that a source or claim is true.
- The output directory is writable, and the user can open local HTML files.

## Out of scope

- Hosting, deployment, CMS integration, scheduling, or social-media publishing.
- A web interface, persistent database, user accounts, or multi-user
  collaboration.
- Fact-checking by a human, independent source crawling, or a guarantee that
  model-generated research and citations are accurate.
- Additional research tools, unlimited search, configurable review thresholds,
  or unlimited review cycles.
- Full Markdown rendering, automatic link processing within the article body,
  and custom themes or site navigation.
- Automatic cleanup or rollback of files if a run fails partway through.

## Author

Created by **Akshat Srivastava** — [akshat.srivastava0312@gmail.com](mailto:akshat.srivastava0312@gmail.com).

## Frequently asked questions

See [`faq.md`](faq.md) for common setup, workflow, output, and troubleshooting
questions.
