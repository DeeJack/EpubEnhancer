import re
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
warnings.filterwarnings("ignore", category=UserWarning, module='ebooklib')
warnings.filterwarnings("ignore", category=FutureWarning, module='ebooklib')

load_dotenv()
nltk.download("punkt", quiet=True)

epub_name = "test.epub"
DEBUG = False
MAX_FILENAME_LENGTH = 255  # Max length in linux and windows is about the same


def is_filename_too_long(filename, max_length):
    return len(os.path.abspath(filename)) > max_length


def printDebug(text, *args):
    if DEBUG:
        print(text, *args)


def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    num_tokens = len(encoding.encode(string))
    return num_tokens


def split_text_into_chunks(text, max_tokens=4000):
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
    if current_chapter_text.strip() == '':
        current_chapter_text = chapter_html.find('body').text
    return current_chapter_text


def estimate_price_from_string(text: str):
    """Estimates the price for a text completion."""
    num_tokens = num_tokens_from_string(text)
    price = ((num_tokens / 1000) * 0.0005) + (
        (num_tokens / 1000) * 0.0015
    )  # 0.0005€ per 1000 tokens in input, 0.0015€ per 1000 tokens in output
    return price


def estimate_total_price():
    """Estimates the total price for all the chapters."""
    total_price = 0
    for chapter in chapters[options["start"] : options["end_chapter"]]:
        chapter_text = get_text_from_chapter(chapter)
        total_price += estimate_price_from_string(chapter_text)
    return total_price


def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:.2f}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m {seconds % 60:.2f}s"


if __name__ == "__main__":
    """System prompt for GPT"""
    editor_prompt = ""

    with open("system_prompt.txt", "r") as f:
        editor_prompt = f.read()

    """
        Make sure that the arguments are passed correctly.
        The program requires:
        - The name of the epub file to read
        - The name of the output file
        - The starting chapter number (the first chapter is 1)
        - The number of chapters to process (NUMBER OF CHAPTERS, NOT THE LAST CHAPTER NUMBER)
        Example:
        python epub_reader.py test.epub -o output.epub -s 1 -n 10
    """

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

    args = parser.parse_args()

    """
        Compute the last chapter, set the starting chapter on a 0-based index
    """
    options = {
        "filename": args.filename,
        "output": args.output or f"{args.filename.replace('.epub', '')}_enhanced.epub",
        "start": args.start,
        "number": args.number,
        "end_chapter": args.start + args.number,
    }
    printDebug(options)

    if options["start"] < 1:
        print("Start chapter must be greater than 0")
        exit(1)

    if options["number"] < 1:
        print("Number of chapters must be greater than 0")
        exit(1)

    # Check if the output filename is too long (max 255 characters in linux and windows)
    if is_filename_too_long(options["output"], MAX_FILENAME_LENGTH):
        print("Output filename is too long")
        exit(1)

    """
        Load the epub file.
    """
    try:
        book = epub.read_epub(options.get("filename"))
    except:
        print(
            "Couldn't open the epub file, make sure the file exists and is a valid epub file (this may be a library issue)"
        )
        exit(1)

    """
        Connect to OpenAI
    """
    try:
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
    except:
        print(
            "Couldn't connect to OpenAI, have you set the OPENAI_API_KEY environment variable?"
        )
        exit(1)

    # Get all the chapters
    chapters = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    encoding = tiktoken.encoding_for_model("gpt-4o-mini")
    
    if options["end_chapter"] > len(chapters):
        print(f"Ending chapter\'s number is higher than the number of chapters: {options["end_chapter"]}/{len(chapters)}")
        exit(1)
    
    # Print the disclaimer
    with open('disclaimer.txt', "r") as disclaimer:
        print(disclaimer.read())

    """
        Estimate the price and ask the user if they want to continue
    """
    estimated_price = estimate_total_price()
    print(f"Estimated price [from c{options["start"]} to c{options["end_chapter"] - 1}]: €{estimated_price:.2f}")
    response = input("Do you want to continue? [Y/n]")

    if response.lower() != "y":
        print("Exiting...")
        exit(0)

    index = 0
    count = 1
    start_time = time.time()
    printDebug(
        "Starting processing chapters, from chapter",
        options["start"],
        "to",
        options["end_chapter"] - 1,
    )
    for chapter_index in tqdm(
            range(options["start"], 
                    options["end_chapter"])):
        chapter = chapters[chapter_index]
        printDebug("Processing chapter", chapter_index)

        current_chapter_text = get_text_from_chapter(chapter)

        printDebug("Parsed content, sending request")

        text_chunks = split_text_into_chunks(
            current_chapter_text
        )  # Split the text into chunks of max 4000 tokens
        chapter_text_chunks = []

        for text_chunk in text_chunks:
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": editor_prompt,
                    },
                    {
                        "role": "user",
                        "content": text_chunk,
                    },
                ],
                model="gpt-4o-mini",
                stream=True,
                # max_tokens=4000,  # 0.001$ per 1000 tokens input, 0.002$ per 1000 tokens output
            )

            for chunk in response:
                if (
                    len(chunk.choices) > 0
                    and chunk.choices[0].delta
                    and chunk.choices[0].delta.content
                ):
                    chapter_text_chunks.append(chunk.choices[0].delta.content)

        chapter_text = "".join(chapter_text_chunks)  # Join the chunks back together
        printDebug(chapter_text)
        chapter.set_content(
            chapter_text
        )  # Set the new content for the chapter in the epub
        count += 1
        epub.write_epub(
            options["output"].replace(".epub", "") + "_temp.epub", book, {}
        )  # Backup

    epub.write_epub(options["output"], book, {})  # Write the epub to the output file
    current_dir = os.curdir
    temp_file = os.path.join(current_dir, options["output"].replace(".epub", "") + "_temp.epub")
    os.remove(temp_file)
    print(f"Time taken: {format_time(time.time() - start_time)}")
