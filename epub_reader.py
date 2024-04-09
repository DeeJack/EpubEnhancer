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

load_dotenv()
nltk.download('punkt')

epub_name = "test.epub"
DEBUG = True
MAX_FILENAME_LENGTH = 255 # Max length in linux and windows is about the same

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
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_chunk_tokens = sentence_tokens
        else:
            current_chunk.append(sentence)
            current_chunk_tokens += sentence_tokens

    chunks.append(' '.join(current_chunk))  # append the last chunk
    return chunks

def estimate_price(text: str):
    """Estimates the price for a text completion."""
    num_tokens = num_tokens_from_string(text) * options['number']
    price = (num_tokens / 1000) * 0.0005 # 0.0005 per 1000 tokens
    return price

"""System prompt for GPT"""
editor_prompt = "From now on you'll act as an editor. \\\
                You will be given some text extracted from a book which was machine translated. \\\
                    Your job is to correct the text and make it sound as natural as possible. \\\
                    You cannot change the story itself.\\\
                    Keep the length of the chapter about the same."

if __name__ == '__main__':
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
        description="Read an epub machine translated book and rewrite it with better grammar using GPT-3.5",
        prog="Epub Enhancer",
        usage="%(prog)s <filename.epub>",
    )

    parser.add_argument('filename', help='Epub file to read')
    parser.add_argument('-o', '--output', help='Output file name')
    parser.add_argument('-s', '--start', type=int, default=1, help='Start from this chapter n (from 1)')
    parser.add_argument('-n', '--number', type=int, default=0, help='Number of chapters to process (0: all)')

    args = parser.parse_args()
    
    """
        Compute the last chapter, set the starting chapter on a 0-based index
    """
    options = {
        'filename': args.filename,
        'output': args.output or f"{args.filename}_enhanced.epub",
        'start': args.start - 1,
        'number': args.number,
        'end_chapter': args.start + args.number - 1,
    }
    printDebug(options)

    if options['start'] < 1:
        print("Start chapter must be greater than 0")
        exit(1)

    if options['number'] < 1:
        print("Number of chapters must be greater than 0")
        exit(1)
        
    # Check if the output filename is too long (max 255 characters in linux and windows)
    if is_filename_too_long(options['output'], MAX_FILENAME_LENGTH): 
        print("Output filename is too long")
        exit(1)

    """
        Load the epub file.
    """
    try:
        book = epub.read_epub(options.get('filename'))
    except:
        print("Couldn't open the epub file")
        exit(1)

    """
        Connect to OpenAI
    """
    try:
        client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
    except:
        print("Couldn't connect to OpenAI")
        exit(1)
        
    # Get all the chapters
    chapters = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    encoding = tiktoken.encoding_for_model('gpt-3.5-turbo')
    
    """
        Estimate the price and ask the user if they want to continue
    """
    first_chapter = chapters[0]
    first_chapter_text = bs.BeautifulSoup(
        first_chapter.get_content(), "html.parser"
    ).get_text()
    estimated_price = estimate_price(first_chapter_text)
    print(f"Estimated price for the first chapter: €{estimated_price}")
    response = input('Do you want to continue? [Y/n]')
    
    if response.lower() != 'y':
        print("Exiting...")
        exit(0)    
    
    index = 0
    count = 1
    start_time = time.time()
    printDebug('Starting processing chapters, from chapter', options['start'] + 1, 'to', options['end_chapter'])
    for chapter_index in range(options['start'], options['end_chapter']):
        chapter = chapters[chapter_index]
        content = chapter.get_content()  # Get the HTML content for the chapter
        print('Got content for chapter', chapter_index + 1)
        text = bs.BeautifulSoup(
            content, "html.parser"
        ).get_text()  # Parse the html and get only the text
        printDebug('Parsed content, sending request')

        text_chunks = split_text_into_chunks(text) # Split the text into chunks of max 4000 tokens
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
                    }
                ],
                model="gpt-3.5-turbo-0125",
                stream=True,
                max_tokens=4000, # 0.001$ per 1000 tokens input, 0.002$ per 1000 tokens output
            )

            for chunk in response:
                if len(chunk.choices) > 0 and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    chapter_text_chunks.append(chunk.choices[0].delta.content)

        chapter_text = ''.join(chapter_text_chunks) # Join the chunks back together
        chapter_text = chapter_text.replace('\n', '</p><p>')
        chapter_text = chapter_text.replace('\\n', '</p><p>')
        chapter.set_content(chapter_text) # Set the new content for the chapter in the epub
        count += 1
        if count % 10: # Every 10 chapter, backup
            epub.write_epub(options['output'] + 'temp.epub', book, {})

    epub.write_epub(options['output'], book, {}) # Write the epub to the output file
    print(f"Time taken: {time.time() - start_time}s")