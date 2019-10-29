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
                    "label": "Page Image Collection",
                    "note": "Be sure to select a collection consisting of images."
                }
            },
        },
        "module": 'plugins.nlp.tasks',
        "functions": ['analyze_document_for_word_frequency']
     }
}


@db_task(priority=2, context=True)
def analyze_document_for_word_frequency(corpus_id, job_id, task=None):
    corpus = get_corpus(corpus_id)
    if corpus:
        job = corpus.get_job(job_id)
        if job and task:
            job.processes.append(task.id)
            job.status = 'running'
            corpus.save_job(job)

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
                    with open(text_file['path'], 'r') as fin:
                        full_text += fin.read() + '\n'

            tokens = get_tokens(full_text)
            make_frequency_distribution_chart(tokens, word_freq_chart_file)
            job.document.save_file(process_corpus_file(
                word_freq_chart_file,
                desc="Word Frequency Analysis PNG Image",
                prov_type="Word Frequency Analysis Job",
                prov_id=str(job_id)
            ))
            corpus.complete_job_process(job_id, task.id)


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
        import nltk
        import matplotlib.pylab

        # generate the frequency distribution
        freq_dist = nltk.FreqDist(tokens)

        # the object returned by nltk.FreqDist has a .plot() method which creates the chart. that method calls
        # pylab.show(), which normally requires a GUI to display the chart. we'll override pylab.show by having
        # it save the image to a file instead!
        matplotlib.pylab.show = lambda: matplotlib.pylab.savefig(image_file)

        # create a figure for our chart, 20" wide, 10" high, with tight margins
        matplotlib.pylab.figure(figsize=(width, height), tight_layout=True)

        # actually create the diagram of 50 most frequent words
        freq_dist.plot(num_terms, cumulative=False)
