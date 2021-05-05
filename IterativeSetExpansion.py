import re
import sys
import time
import spacy
import socket
import logging
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from spanbert import SpanBERT
import urllib.request
from urllib.error import HTTPError, URLError

spacy2bert = {
    "ORG": "ORGANIZATION",
    "PERSON": "PERSON",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "DATE": "DATE"
}

bert2spacy = {
    "ORGANIZATION": "ORG",
    "PERSON": "PERSON",
    "LOCATION": "LOC",
    "CITY": "GPE",
    "COUNTRY": "GPE",
    "STATE_OR_PROVINCE": "GPE",
    "DATE": "DATE"
}


def get_entities(sentence, entities_of_interest):
    return [(e.text, spacy2bert[e.label_]) for e in sentence.ents if
            e.label_ in spacy2bert and spacy2bert[e.label_] in entities_of_interest]


def create_entity_pairs(sents_doc, entities_of_interest, window_size=40):
    """
    Input: a spaCy Sentence object and a list of entities of interest
    Output: list of extracted entity pairs: (text, entity1, entity2)
    """

    entities_of_interest = {bert2spacy[b] for b in entities_of_interest}
    ents = sents_doc.ents  # get entities for given sentence

    length_doc = len(sents_doc)
    entity_pairs = []
    for i in range(len(ents)):
        e1 = ents[i]
        if e1.label_ not in entities_of_interest:
            continue

        for j in range(1, len(ents) - i):
            e2 = ents[i + j]
            if e2.label_ not in entities_of_interest:
                continue
            if e1.text.lower() == e2.text.lower():  # make sure e1 != e2
                continue

            if 1 <= (e2.start - e1.end) <= window_size:

                punc_token = False
                start = e1.start - 1 - sents_doc.start
                if start > 0:
                    while not punc_token:
                        punc_token = sents_doc[start].is_punct
                        start -= 1
                        if start < 0:
                            break
                    left_r = start + 2 if start > 0 else 0
                else:
                    left_r = 0

                # Find end of sentence
                punc_token = False
                start = e2.end - sents_doc.start
                if start < length_doc:
                    while not punc_token:
                        punc_token = sents_doc[start].is_punct
                        start += 1
                        if start == length_doc:
                            break
                    right_r = start if start < length_doc else length_doc
                else:
                    right_r = length_doc

                if (right_r - left_r) > window_size:  # sentence should not be longer than window_size
                    continue

                x = [token.text for token in sents_doc[left_r:right_r]]
                gap = sents_doc.start + left_r
                e1_info = (e1.text, spacy2bert[e1.label_], (e1.start - gap, e1.end - gap - 1))
                e2_info = (e2.text, spacy2bert[e2.label_], (e2.start - gap, e2.end - gap - 1))
                if e1.start == e1.end:
                    assert x[e1.start - gap] == e1.text, "{}, {}".format(e1_info, x)
                if e2.start == e2.end:
                    assert x[e2.start - gap] == e2.text, "{}, {}".format(e2_info, x)
                entity_pairs.append((x, e1_info, e2_info))
    return entity_pairs


# Format for dictionary:
# Name, internal name, subject, object(s)
relation_dict = {1: ("Schools_Attended", "per:schools_attended", ["PERSON"], ["ORGANIZATION"]),
                 2: ("Work_For", "per:employee_of", ["PERSON"], ["ORGANIZATION"]),
                 3: ("Live_In", "per:cities_of_residence", ["PERSON"],
                     ["LOCATION", "CITY", "STATE_OR_PROVINCE", "COUNTRY"]),
                 4: ("Top_Member_Employees", "org:top_members/employees", ["ORGANIZATION"], ["PERSON"])
                 }


class Tuple:
    def __init__(self, subject, obj, relation, confidence):
        self.subject = subject
        self.obj = obj
        self.relation = relation
        self.confidence = confidence


class IterativeSetExpansion:

    def __init__(self, google_api_key, search_engine_id, r, t, q, k, bert, nlp):
        self.service = build("customsearch", "v1", developerKey=google_api_key)
        self.search_engine_id = search_engine_id
        self.relation = r
        self.threshold = float(t)
        self.query = q
        self.num_tuples_to_output = k
        self.tuple_dict = {}
        self.used_tuples = set()
        self.bert = bert
        self.nlp = nlp

    # sort all the tuples in tuple_dict by their confidence in descending order and return them
    def get_top_k(self):
        candidates = self.tuple_dict.keys()
        candidates = sorted(candidates, key=self.tuple_dict.get, reverse=True)
        return candidates


    def iterative_set_expansion(self):
        ###############################################
        #                  STEP 1                     #
        ###############################################
        # Initialize X, the set of extracted tuples, as the empty set

        iteration = 0
        processed_URLs = set()

        while True:
            print(f'=========== Iteration: {iteration} - Query: {self.query} ===========')
            ###############################################
            #                  STEP 2                     #
            ###############################################
            # Query Google Custom Search Engine to obtain the URLs for the
            # top-10 webpages for query q retrieve up to the top 10 search
            # results for the current query and parse the data

            search_results = self.get_top_10_URLs(self.query)

            if len(search_results) == 0:
                print('No search results found for given query. ')

            if len(search_results) < 10:
                print('Less than 10 search results retrieved for this query.')

            ###############################################
            #                  STEP 3                     #
            ###############################################

            count = 1

            for result in search_results:
                # retrieve web page
                URL = result['link']
                print(f'\n\nURL ({count} / 10): {URL}')
                count += 1

                if URL in processed_URLs:
                    # URL already processed, move to next url
                    print('Already processed this URL. Skipping...')
                    continue

                # URL not processed yet. Begin processing
                print("\tFetching text from url ...")
                # add url to list of processed urls
                processed_URLs.add(URL)

                try:
                    page = urllib.request.urlopen(URL, timeout=10).read().decode('utf-8')
                except HTTPError:
                    logging.error('Unable to fetch URL. Continuing.')
                    continue
                except URLError as error:
                    if isinstance(error.reason, socket.timeout):
                        logging.error('Unable to fetch URL. Continuing', URL)
                        continue
                    else:
                        logging.error('Unable to fetch URL. Continuing.')
                        continue
                except:
                    logging.error('Unable to fetch URL. Continuing')
                    continue

                soup = BeautifulSoup(page, "html.parser")
                text = soup.get_text()
                text = re.sub(r'\[[^]]*\]', '', text)

                # if resulting plain text is longer than 20,000 characters, truncate the text to its first
                # 20,000 characters (for efficiency) and discard the rest
                if len(text) > 20000:
                    # truncate text to its first 20,000 characters
                    text = text[:20000]
                    print("\tWebpage length (num characters): ", len(text))

                print("\tAnnotating the webpage using spacy...")

                # use spaCy library to split the text into sentences
                doc = self.nlp(text)

                assert doc.has_annotation("SENT_START")
                sentences = list(doc.sents)

                print(f'Extracted {len(sentences)} sentences. Processing each sentence one by one to check for presence of '
                      f'right pair of named entity types; if so, will run the second '
                      f'pipeline ...\n\n')

                self.extract_tuples(sentences)

                ###############################################
                #                  STEP 4                     #
                ###############################################
                # Remove exact duplicates from set X:
                # If set X contains tuples that are identical to each other,
                # keep only the copy that has the highest extraction confidence and
                # remove from X the duplicate copies


            ###############################################
            #                  STEP 5                     #
            ###############################################
            # if X contains at least k tuples, return the top-k such tuples sorted in decreasing order by
            # extraction confidence, together with the extraction confidence of each tuple, and stop
            num_tuples_extracted = len(self.tuple_dict)

            print(f'================== ALL RELATIONS for {relation_dict[self.relation][1]} '
                  f'( {num_tuples_extracted} ) =================')
            top_k = self.get_top_k()
            for tup in top_k:
                print(f'Confidence: {self.tuple_dict[tup]} 		| Subject: {tup[0]} 		| Object: {tup[1]}')
            print(f'Total # of iterations = {iteration + 1}')

            if num_tuples_extracted >= self.num_tuples_to_output:
                exit(1)

            ###############################################
            #                  STEP 6                     #
            ###############################################
            # Select from X a tuple y such that
            # 1. y has not been used for querying yet and
            # 2. y has an extraction confidence that is
            #    highest among the tuples in X that have not
            #    yet been used for querying
            else:
                self.select_new_tuple()

            iteration += 1

            print('Next query: ', self.query)
            # END WHILE LOOP

    def remove_exact_duplicates(self, tup):
        # if set X contains tuples that are identical to each other,
        # keep only the copy that has the highest extraction confidence and
        # remove from X the duplicate copies


        # if tuple is not in dictionary, add it - value is the confidence score
        if (tup.subject, tup.obj, tup.relation) not in self.tuple_dict:
            self.tuple_dict[(tup.subject, tup.obj, tup.relation)] = tup.confidence
            print('\t\tAppropriate tuple found. Appending tuple...')
            return 1

        else:
            # get the max confidence score
            if self.tuple_dict[(tup.subject, tup.obj, tup.relation)] < tup.confidence:
                self.tuple_dict[(tup.subject, tup.obj, tup.relation)] = tup.confidence
                print('\t\tDuplicate tuple found with higher confidence. Updating confidence...')
                return 0
            else:
                print('\t\tDuplicate tuple found with lower confidence. Ignoring this...')
                return 0


    # issues a given search query and gets up to 10 html results
    # converts results into a list of dictionaries containing data for each document (url, title, summary)
    def get_top_10_URLs(self, query):

        results = self.service.cse().list(
            q=query,
            cx=self.search_engine_id,
        ).execute()

        if 'items' not in results:
            print('No results retrieved for given query. ')
            return

        results = results['items']
        parsed_data = []

        i = 0
        for res in results:
            # if fileFormat is a field in this result, skip it, since this field appears in non html documents
            if 'fileFormat' in res:
                continue

            if i == 10:
                break
            document_data = {
                'link': res.get('link', ''),
                'title': res.get('title', ''),
                'description': res.get('snippet', '')
            }

            parsed_data.append(document_data)
        return parsed_data



    # sort the tuples in tuple_dict (keys) by their confidence (values) in a list called candidates. Sort in descending order of confidence.
    # for each tuple in candidates, starting with the highest confidence tuple, check if the tuple has been used as a query
    # in used_tuples set. If not used, pick the tuple as the next query. Else, continue to the next best tuple.
    def select_new_tuple(self):

        candidates = self.tuple_dict.keys()
        candidates = sorted(candidates, key=self.tuple_dict.get, reverse=True)

        for tup in candidates:
            if tup in self.used_tuples:
                continue
            self.query = tup[0] + " " + tup[1]
            self.used_tuples.add(tup)
            return

        print('No new tuples found. ')
        exit(1)



    # First, look up the relevant entities of interest for the relation in relations_dict.
    # Then for each sentence of the document, we call the get_entities() helper function to retrieve the relevant entities in each sentence.
    # If no entities are retrieved, we skip to the next sentence.
    # Else, we use the provided helper function create_entity_pairs() to create possible entity pairs for the relation by
    # combining the retrieved entities from get_entities().
    # We then call spanBert for each entity pair if the subject and object are relevant
    # types to the extraction task. If the returned predictions are of the correct relation and above the confidence threshhold,
    # we append the tuple to a list of extracted tuples. After processing each sentence, we return the list of tuples to the main loop.
    def extract_tuples(self, sentences):

        tuples = []

        target = relation_dict[self.relation][1]

        count = 0
        num_extracted_relations = 0
        overall = 0

        for sentence in sentences:

            count += 1
            if count % 5 == 0:
                print(f'\tProcessed {count} / {len(sentences)} sentences')

            # extract named entities
            subject_entities = relation_dict[self.relation][2]
            obj_entities = relation_dict[self.relation][3]

            entities_of_interest = subject_entities + obj_entities

            entities = get_entities(sentence, entities_of_interest)

            # if no entities were extracted for this sentence, move on to the next sentence
            if len(entities) == 0:
                # print('No relevant entities found for this sentence. Continuing to next sentence...\n\n\n\n')
                continue

            candidate_pairs = []

            sentence_entity_pairs = create_entity_pairs(sentence, entities_of_interest)

            for ep in sentence_entity_pairs:

                if ep[1][1] in subject_entities and ep[2][1] in obj_entities:
                    candidate_pairs.append({"tokens": ep[0], "subj": ep[1], "obj": ep[2]})  # e1=Subject, e2=Object
                if ep[2][1] in subject_entities and ep[1][1] in obj_entities:
                    candidate_pairs.append({"tokens": ep[0], "subj": ep[2], "obj": ep[1]})  # e1=Object, e2=Subject

            # if no candidate pairs were extracted for this sentence, move on to the next sentence
            if len(candidate_pairs) == 0:
                # print('No relevant candidate pairs found for this sentence. Continuing to next sentence...\n\n\n\n')
                continue

            # used SpanBERT to predict
            predictions = self.bert.predict(candidate_pairs)

            for ex, pred in list(zip(candidate_pairs, predictions)):
                relation = pred[0]
                confidence = pred[1]
                subject = ex["subj"][0]
                obj = ex["obj"][0]


                if relation.lower() != target.lower():
                    continue
                elif confidence < self.threshold:
                    print('\n\t\t======= Extracted Relation ======')
                    print('\t\tSentence: ', sentence)

                    print(f'\t\tConfidence: {float(confidence)} ;       Subject: {subject} ;       Object: {obj};'
                          f'      Relation: {relation}')
                    print('\t\tConfidence below threshold. Skipping...')
                else:
                    print('\n\t\t======= Extracted Relation ======')
                    print('\t\tSentence: ', sentence)

                    print(f'\t\tConfidence: {float(confidence)} ;       Subject: {subject} ;       Object: {obj};'
                          f'      Relation: {relation}')
                    overall += 1
                    new_tuple = Tuple(subject, obj, relation, confidence)
                    num_extracted_relations += self.remove_exact_duplicates(new_tuple)


                print("\t\t================================\n")

        print(f'\tExtracted annotations for {count} sentences')
        print(f'\tUnique relations extracted from this website: {num_extracted_relations} (Overall: {overall})')




def main():
    if len(sys.argv) != 7:
        print('Invalid number of input arguments.\nFormat: IterativeSetExpansion.py '
              '<google api key> <google engine id> <relation to extract> <confidence threshold> '
              '<seed query> <number of tuples to output>')
        exit(1)

    # API Key: AIzaSyAbUyFNJp6VrdunILLcN-OecO0K7_ZH1OU
    # Search engine ID: b305c2cc7c4272302

    google_api_key = sys.argv[1]  # Google Custom Search Engine JSON API key
    search_engine_id = sys.argv[2]  # Google Engine ID

    r = int(sys.argv[3])  # relation to extract
    # 1 - Schools_attended
    # 2 - Work_For
    # 3 - Live_In
    # 4 - Top_Member_Employees

    t = float(sys.argv[4])  # extraction confidence threshold - 0 <= t <= 1

    q = sys.argv[5]  # seed query - list of words in double quotes
    # corresponding to a plausible tuple for the relation to extract

    k = int(sys.argv[6])  # number of tuples that we request in the output
    '''
    google_api_key = 'AIzaSyAgJ1HuBv8EeTQ6jRvZVryrwwGFYXKbFfE'
    search_engine_id = 'b305c2cc7c4272302'
    r = 4
    t = 0.7
    q = 'bill gates microsoft'
    k = 10
    '''

    bert = SpanBERT("./pretrained_spanbert")
    nlp = spacy.load("en_core_web_lg")
    time.sleep(1)

    print("___________")
    print("Parameters:")
    print("Client Key       = ", google_api_key)
    print("Engine Key       = ", search_engine_id)
    print("Relation         = ", relation_dict[r][1])
    print("Threshold        = ", t)
    print("Query            = ", q)
    print("# of Tuples      = ", k)
    print("Loading necessary libraries; This should take a minute or so ...)")

    client = IterativeSetExpansion(google_api_key, search_engine_id, r, t, q, k, bert, nlp)
    client.iterative_set_expansion()


if __name__ == '__main__':
    main()
