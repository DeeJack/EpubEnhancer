# EpubEnhancer

Rewrite badly-written epub books with the GPT APIs.

A python script to fix the grammar for Machine Translated (or simply books with bad writing) epubs, using GPT-4o-mini (or any model from OpenAI).

It uses the GPT API to rewrite the chapters in a correct, or at least readable, grammar.

## Disclaimer

Remember that the GPT API are NOT free. You are paying for each character! The initial estimate given is an **ESTIMATE** using tiktoken, it may be not accurate!
Use with caution, and try to divide the book in batches to be sure.

The results are not perfect, not even nearly. I tried to come up with different system prompts, but I couldn't find a prompt that actually fixes everything without removing details from the story.

I don't take any responsability for what you do with the program. Everything is sent to OpenAI for the processing, so don't send sensitive/copyrighted stuff.

I didn't have any problem with the program, but it's still possible the presence of bugs that cause an infinite loop. Set a limit in the OpenAI key to be sure, and keep track of what the program is doing with the tqdm bar. Stop the program with CTRL+C if you think something is wrong. A backup is created at each chapter processed, so you don't lose any progress.

## Requirements

The only requirement is Python.

## Getting started

Install the dependencies: `pip install -r requirements.txt`

### Configuration

Create a .env file, then insert a line with:
`OPENAI_API_KEY=INSERT_KEY_HERE`

And replace `INSERT_KEY_HERE` with your OpenAI's API key.

### Example command

`python epub_reader.py test.epub -o output.epub -s 1 -n 10 -p "Remove all author notes"`

Explanation: fix file `test.epub` (path of the file), output to file `output.epub`, starting from chapter 1 (included), and fix 10 chapters (so until chapter 10).

`-p` adds text to the system prompt, so that you can customize the system prompt more easily.

## Result

The effect in this one is not as big since the MTL is pretty good, but it will work even in worse scenarios.

Before:

> A pure passerby couldn't stand it, and couldn't help but interject.
>
>[Ruan Qi is kind and honest, why is he not worthy of Lin Jian? Do you think that the higher the academic qualifications, the better? ? ?]
>
> [Upstairs, Ruan Qi came out to film at the age of 19, obviously not paying much attention to cultural literacy. If she is with Lin Jian and Lin Jian talks about academic topics with her parents, wouldn't she be like listening to the fairy tale? ]
>
>[That's it. That kind of intellectual, highly educated girl is worthy of Lin Jian. Ruan Qi should find a big money.]

After:

>A random bystander couldn't help but intervene.
>
>[Ruan Qi is kind and sincere, why isn't she on par with Lin Jian? Do you believe that higher academic qualifications make someone better?]
>
>[Upstairs, Ruan Qi started acting at 19, clearly not focusing much on education. Imagine if she were with Lin Jian and they talked about academic subjects, wouldn't it be like a fairy tale for her?]
>
>[Exactly. Someone intellectual and highly educated like Lin Jian deserves a girl like that. Ruan Qi should find someone wealthy.]