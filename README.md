# EpubEnhancer

Rewrite badly-written epub books with OpenAI-compatible APIs (LM-Studio, OpenAI, etc.).

It uses LLMs to rewrite the chapters in a correct, or at least readable, grammar.

You can modify the System Prompt from the [system_prompt.txt](system_prompt.txt) file to better suit your needs.

## Getting started

1. Create the virtual environment: `uv venv --python 3.13 --managed-python`
2. Activate the virtual environment: `source .venv/bin/activate`
3. Install the dependencies: `uv pip install -r requirements.txt`

### Configuration

Create a .env file, then insert a line with: `OPENAI_API_KEY=<INSERT_KEY_HERE>`

### Example command

`python epub_reader.py test.epub -o output.epub -s 1 -n 10 -p "Remove all author notes"`

Explanation: fix file `test.epub` (path of the file), output to file `output.epub`, starting from chapter 1 (included), and fix 10 chapters (so until chapter 10).

`-p` adds text to the system prompt, so that you can customize the system prompt more easily.
