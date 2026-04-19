from rich.console import Console

console = Console()

console.print("[cyan]Initializing...")

import time
import ebooklib
from ebooklib import epub
import bs4 as bs
import os
from openai import OpenAI
from dotenv import load_dotenv
import argparse
import nltk
import tiktoken
from tqdm import tqdm

# Suppress warnings from the epub library
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="ebooklib")
warnings.filterwarnings("ignore", category=FutureWarning, module="ebooklib")

load_dotenv()
nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)

DEBUG = False
MAX_FILENAME_LENGTH = 255  # Max length in linux and windows is about the same
MODEL_NAME = "gemini-2.5-flash-lite"
TOKENIZER_MODEL = "gpt-4o-mini"
MAX_CHUNK_TOKENS = 8000
PRICE_PER_MILLION_INPUT = 0.15
PRICE_PER_MILLION_OUTPUT = 0.6
# OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENAI_BASE_URL = "http://127.0.0.1:1234/v1"

encoding = tiktoken.encoding_for_model(TOKENIZER_MODEL)


def is_filename_too_long(filename, max_length):
    return len(os.path.abspath(filename)) > max_length


def printDebug(text, *args):
    if DEBUG:
        print(text, *args)


def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    return len(encoding.encode(string))


def split_text_into_chunks(text, max_tokens=MAX_CHUNK_TOKENS):
    """Splits a text into chunks of max_tokens tokens."""
    sentences = nltk.sent_tokenize(text)
    chunks = []
    current_chunk = []
    current_chunk_tokens = 0

    for sentence in sentences:
        sentence_tokens = num_tokens_from_string(sentence)
        if current_chunk_tokens + sentence_tokens > max_tokens:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_chunk_tokens = sentence_tokens
        else:
            current_chunk.append(sentence)
            current_chunk_tokens += sentence_tokens

    chunks.append(" ".join(current_chunk))  # append the last chunk
    return chunks


def get_text_from_chapter(chapter):
    """Returns the text from a chapter."""
    content = chapter.get_content()
    chapter_html = bs.BeautifulSoup(content, "html.parser")
    current_chapter_text = chapter_html.find_all("p")
    current_chapter_text = "\n".join(
        [str(paragraph) for paragraph in current_chapter_text]
    )
    if current_chapter_text.strip() == "":
        current_chapter_text = chapter_html.find("body").text  # type: ignore
    return current_chapter_text


def estimate_price_from_string(text: str):
    """Estimates the price for a text completion."""
    num_tokens = num_tokens_from_string(text)
    price = (num_tokens / 1_000_000) * PRICE_PER_MILLION_INPUT + (
        num_tokens / 1_000_000
    ) * PRICE_PER_MILLION_OUTPUT
    return price


def estimate_total_price(chapters, options, system_prompt: str) -> float:
    """Estimates the total price for all the chapters."""
    total_price = 0
    system_prompt_cost = estimate_price_from_string(system_prompt)
    for chapter in chapters[options["start"] : options["end_chapter"]]:
        chapter_text = get_text_from_chapter(chapter)
        total_price += estimate_price_from_string(chapter_text) + system_prompt_cost
    return total_price


def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:.2f}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m {seconds % 60:.2f}s"


def parse_arguments():
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Read an epub machine translated book and rewrite it with better grammar using GPT-4o-mini",
        prog="Epub Enhancer",
        usage="%(prog)s <filename.epub>",
    )

    parser.add_argument("filename", help="Epub file to read")
    parser.add_argument("-o", "--output", help="Output file name")
    parser.add_argument(
        "-s", "--start", type=int, default=1, help="Start from this chapter n (from 1)"
    )
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=0,
        help="Number of chapters to process (0: all)",
    )
    parser.add_argument(
        "-p",
        "--prompt",
        type=str,
        default="",
        help="Additional details for the system prompt (default: [])",
    )

    return parser.parse_args()


def build_options(args):
    """Builds the options dict from CLI args."""
    return {
        "filename": args.filename,
        "output": args.output or f"{args.filename.replace('.epub', '')}_enhanced.epub",
        "start": args.start,
        "number": args.number,
        "end_chapter": args.start + args.number,
        "prompt": args.prompt or "",
    }


def validate_options(options):
    """Validates the options, exits with error messages if invalid."""
    if options["start"] < 1:
        console.print("[red]Start chapter must be greater than 0")
        exit(1)

    if options["number"] < 1:
        console.print("[red]Number of chapters must be greater than 0")
        exit(1)

    if is_filename_too_long(options["output"], MAX_FILENAME_LENGTH):
        console.print("[red]Output filename is too long")
        exit(1)


def validate_chapter_range(options, chapters):
    """Validates that the requested chapter range is within the book."""
    if options["end_chapter"] > len(chapters):
        console.print(
            f"[red]Ending chapter's number is higher than the number of chapters: {options['end_chapter']}/{len(chapters)}"
        )
        exit(1)

    if options["end_chapter"] < 1 or options["end_chapter"] < options["start"]:
        console.print("[red]Ending chapter must be greater than the starting chapter")
        exit(1)


def load_system_prompt(additional_prompt: str) -> str:
    """Loads the system prompt from disk and appends any additional text."""
    with open("system_prompt.txt", "r") as f:
        editor_prompt = f.read()
    return f"{editor_prompt}\n{additional_prompt}"


def print_disclaimer():
    """Prints the disclaimer text."""
    with open("disclaimer.txt", "r") as disclaimer:
        print(disclaimer.read())


def load_book(filename: str):
    """Loads an epub file, exits on failure."""
    try:
        return epub.read_epub(filename)
    except:
        console.print(
            "[red]Couldn't open the epub file, make sure the file exists and is a valid epub file (this may be a library issue)"
        )
        exit(1)


def create_openai_client():
    """Creates the OpenAI client configured for Gemini, exits on failure."""
    try:
        return OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=OPENAI_BASE_URL,
        )
    except:
        console.print(
            "[red]Couldn't connect to OpenAI, have you set the OPENAI_API_KEY environment variable?"
        )
        exit(1)


def confirm_price(chapters, options, system_prompt: str) -> bool:
    """Prints the estimated price and asks the user to confirm."""
    estimated_price = estimate_total_price(chapters, options, system_prompt)
    console.print(
        f"Estimated price [from c{options['start']} to c{options['end_chapter'] - 1}]: [red]€{estimated_price:.2f}"
    )
    response = input("Do you want to continue [Y/n]? ")
    return response.lower() == "y"


def stream_completion(client, system_prompt: str, text_chunk: str) -> str:
    """Streams a completion for a single text chunk and returns the full response."""
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text_chunk},
        ],
        model=MODEL_NAME,
        stream=True,
        # reasoning_effort="none",
    )

    parts = []
    for chunk in response:
        if (
            len(chunk.choices) > 0
            and chunk.choices[0].delta
            and chunk.choices[0].delta.content
        ):
            parts.append(chunk.choices[0].delta.content)
    full_response = "".join(parts)
    # Remove <|channel>thought\n<channel|> block
    if "<|channel>" in full_response and "<channel|>" in full_response:
        start = full_response.index("<|channel>")
        end = full_response.index("<channel|>", start) + len("<channel|>")
        full_response = full_response[:start] + full_response[end:]

    return full_response


def enhance_chapter(chapter, client, system_prompt: str) -> str:
    """Processes a single chapter, returning the rewritten text."""
    current_chapter_text = get_text_from_chapter(chapter)
    text_chunks = split_text_into_chunks(current_chapter_text)
    rewritten_chunks = [
        stream_completion(client, system_prompt, text_chunk)
        for text_chunk in text_chunks
    ]
    return "".join(rewritten_chunks)


def process_chapters(book, chapters, client, options, system_prompt: str):
    """Iterates over the selected chapters, rewriting each and saving backups."""
    temp_output = options["output"].replace(".epub", "") + "_temp.epub"

    for chapter_index in tqdm(range(options["start"], options["end_chapter"])):
        chapter = chapters[chapter_index]
        printDebug("Processing chapter", chapter_index)

        chapter_text = enhance_chapter(chapter, client, system_prompt)
        printDebug(chapter_text)
        chapter.set_content(chapter_text)

        epub.write_epub(temp_output, book, {})  # Backup

    epub.write_epub(options["output"], book, {})
    temp_file = os.path.join(os.curdir, temp_output)
    os.remove(temp_file)


def main():
    console.print("[cyan]Parsing arguments...")
    args = parse_arguments()
    options = build_options(args)
    printDebug(options)
    validate_options(options)

    console.print("[green]Arguments parsed, starting the process...")

    book = load_book(options["filename"])
    console.print("[green]Book opened successfully.")

    client = create_openai_client()
    console.print("[green]Connection to OpenAI successful.")

    chapters = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    validate_chapter_range(options, chapters)

    system_prompt = load_system_prompt(options["prompt"])

    # print_disclaimer()

    # if not confirm_price(chapters, options, system_prompt):
    #   console.print("[yellow]Exiting...")
    #   exit(0)

    start_time = time.time()
    console.print(
        f"[green]Starting processing chapters, from chapter {options['start']} to {options['end_chapter'] - 1}."
    )

    process_chapters(book, chapters, client, options, system_prompt)

    console.print(f"[cyan]Time taken: {format_time(time.time() - start_time)}")


if __name__ == "__main__":
    main()
