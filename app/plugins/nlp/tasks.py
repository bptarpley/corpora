import re
import string
from django.utils.text import slugify
from huey.contrib.djhuey import db_task
from corpus import *


REGISTRY = {
    "Analyze Document for Word Frequency": {
        "version": "0",
        "jobsite_type": "HUEY",
        "configuration": {
            "parameters": {
                "collection": {
                    "value": "",
                    "type": "page_file_collection",
                    "label": "Page Text Collection",
                    "note": "Be sure to select a collection consisting of plain text files."
                }
            },
        },
        "module": 'plugins.nlp.tasks',
        "functions": ['analyze_document_for_word_frequency']
     }
}


@db_task(priority=2)
def analyze_document_for_word_frequency(job_id):
    job = Job(job_id)
    job.set_status('running')

    page_file_collections = job.document.page_file_collections
    page_file_collection_key = job.configuration['parameters']['collection']['value']
    text_files = page_file_collections[page_file_collection_key]['files']
    word_freq_chart_file = "{0}/files/{1}_word_frequency.png".format(
        job.document.path,
        slugify(page_file_collection_key)
    )
    full_text = ''

    for text_file in text_files:
        if os.path.exists(text_file['path']):
            with open(text_file['path'], 'r', encoding='utf-8') as fin:
                full_text += fin.read() + '\n'

    print("full text length: {0}".format(len(full_text)))
    tokens = get_tokens(full_text)
    print("tokens length: {0}".format(len(tokens)))
    make_frequency_distribution_chart(tokens, word_freq_chart_file)
    job.document.save_file(process_corpus_file(
        word_freq_chart_file,
        desc="Word Frequency Analysis PNG Image",
        prov_type="Word Frequency Analysis Job",
        prov_id=job_id
    ))
    job.complete('complete')


def get_word_count(text):
    if text:
        return len(text.replace('\n', ' ').split(' '))
    return None


def get_tokens(text, additional_stopwords=None, remove_stopwords=True, remove_non_nouns=True):
    if text:
        import nltk
        # tokens need to be all lower case
        cleaned_text = text.lower()

        # we need to remove punctuation from the text
        for punctuation in string.punctuation:
            cleaned_text = cleaned_text.replace(punctuation, " ")

        if remove_stopwords:
            # we need a list of common english stopwords so we can remove them from the text
            stop_words = list(nltk.corpus.stopwords.words('english'))

            # we need to add all the additional stopwords being passed in to the stop_words list
            if additional_stopwords:
                for stop_word in additional_stopwords:
                    stop_words.append(stop_word.lower())

        # let's make our initial list of tokens for the topic model
        tokens = cleaned_text.split()

        stopped_tokens = []
        if remove_stopwords:
            # let's make a list to keep track of the tokens that aren't in the
            # stopwords list
            for token in tokens:
                if token not in stop_words:
                    stopped_tokens.append(token)
        else:
            stopped_tokens = tokens

        # now we need to lemmatize the tokens to increase the frequency of words like plurals
        lemmatized_tokens = []
        lemma = nltk.stem.wordnet.WordNetLemmatizer()
        for token in stopped_tokens:
            lemmatized_tokens.append(lemma.lemmatize(token))

        nouns_only = []
        if remove_non_nouns:
            # now we're going to POS tag these tokens and get rid of everything but nouns
            pos_tagged_tokens = nltk.pos_tag(lemmatized_tokens)
            for token in pos_tagged_tokens:
                if token[1] == 'NN':
                    nouns_only.append(token[0])
        else:
            nouns_only = lemmatized_tokens

        return nouns_only


def get_levenshtein_distance(text_1, text_2):
    if text_1 and text_2:
        import jellyfish
        return jellyfish.levenshtein_distance(text_1, text_2)
    return None


def split_by_regex(text, regular_expression):
    if text and regular_expression:
        parts = re.split(regular_expression, text)
        return parts
    return None


def find_regex_matches(text, regular_expression):
    if text and regular_expression:
        return re.compile(regular_expression).findall(text)
    return None


def make_frequency_distribution_chart(tokens, image_file, width=20, height=10, num_terms=50):
    if tokens and image_file:
        print("doing a thing")
        from nltk.probability import FreqDist
        import matplotlib.pyplot as plt

        # generate the frequency distribution
        freq_dist = FreqDist(tokens)
        freq_dist.pprint()

        # the object returned by nltk.FreqDist has a .plot() method which creates the chart. that method calls
        # pylab.show(), which normally requires a GUI to display the chart. we'll override pylab.show by having
        # it save the image to a file instead!
        plt.show = lambda: plt.savefig(image_file)

        # create a figure for our chart, 20" wide, 10" high, with tight margins
        plt.figure(figsize=(width, height), tight_layout=True)

        # actually create the diagram of 50 most frequent words
        freq_dist.plot(num_terms, cumulative=False)
