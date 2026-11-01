# Blog Generator FAQ

## What does this project do?

It takes a blog topic through clarification, web research, drafting, two review
gates, header-image generation, tag generation, and local HTML generation.

## How do I run it?

From the project directory, run:

```powershell
.\.venv\Scripts\python.exe blog_workflow.py "Your blog topic"
```

You can leave out the topic to enter it when prompted. Use `--output` to select
a different output directory.

## Which models and API features are required?

Text generation and review use `gpt-6-luna`; header-image generation uses
`gpt-image-2.5-flare`. Research requires the Responses API `web_search` tool.
Your API account must have access to all of them.

## Where do I put my API key?

Set `OPENAI_API_KEY` in your environment or in a `.env` file in the project
directory. Do not share the key or commit `.env` to source control.

## Will the workflow always ask clarification questions?

No. The Clarifier can ask up to three questions if it believes the topic would
benefit from more detail. If it asks, answer in the terminal. Blank answers are
ignored.

## How many sources and searches are used?

The Researcher is asked for exactly four cited facts and the API request limits
web-search tool calls to two. The workflow validates each result's fields and
URL format, but it does not independently verify the source contents.

## What happens if a reviewer rejects the article?

The Writer receives feedback and revises the draft. The Content Verifier and
Editor each allow up to three revisions after their initial review. If a gate
still rejects the article, the workflow stops with an error instead of
continuing to publication.

## What does “published” mean here?

It means the workflow generated local files. It does not host, upload, or
deploy the page. Open the generated `index.html` in a browser to view it.

## Where are the generated files?

By default, each run creates a timestamped subfolder beneath `published`. It
contains `article.md`, `index.html`, `header.png`, and `metadata.json`. The CLI
prints the full output path at the end of a successful run.

## Can I change the output location?

Yes. For example:

```powershell
.\.venv\Scripts\python.exe blog_workflow.py --output .\my-posts "Your topic"
```

## What Markdown is supported in the generated page?

The built-in renderer handles headings, paragraphs, ordered and unordered
lists, and fenced code blocks. It is not a full Markdown implementation.

## What if a model is unavailable or the API request fails?

Check that the API key is configured correctly, that the account has access to
the requested model and web-search feature, and that network access is
available. The CLI reports API and workflow errors and exits unsuccessfully.
Because files are created during the final stages, a failure may leave a
partially populated timestamped output folder.

## Does a generated citation guarantee that a claim is correct?

No. The workflow asks the model to research and cite credible sources, and the
review stages assess the draft, but these are not a guarantee of accuracy.
Verify important claims and links before using or publishing the content.

## Will using the workflow incur API charges?

API calls may incur charges according to the provider account's pricing and
usage terms. Research, revisions, text generation, and image generation all
make API requests.
