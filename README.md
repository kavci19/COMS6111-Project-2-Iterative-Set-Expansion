# COMS6111-Project-2-Iterative-Set-Expansion

Name: Kaan Avci
UNI: koa2107

Name: Brian Yang
UNI: by2289



List of all the files submitted:
1. IterativeSetExpansion.py 	(contains the code)
2. README.txt               	(description of steps, program structure, etc.)
3. transcript.txt           	(contains transcript of the test case)



How to Run Program:
Steps:

1. install all relevant libraries using "pip3 install" command
    pip3 install google-api-python-client
    pip3 install beautifulsoup4


2. Follow instructions given in project description to install spaCy and SpanBERT
	
	sudo apt-get update
    	pip3 install -U pip setuptools wheel
    	pip3 install -U spacy
    	python3 -m spacy download en_core_web_lg

	git clone https://github.com/gkaramanolakis/SpanBERT
    	cd SpanBERT
    	pip3 install -r requirements.txt
    	bash download_finetuned.sh

3. Make sure to move the IterativeSetExpansion.py into the SpanBERT directory 
   and run the program in the SpanBERT directory.
   This can be done using the 'mv' command on Google VM:
   For example, if your current directory contains the SpanBERT directory and 
   the python files:
    			/current directory
				/SpanBERT/
				/IterativeSetExpansion.py


   we would move the files into the SpanBERT directory as follows:

		mv IterativeSetExpansion.py ./SpanBERT


4. Once all files are in the SpanBERT directory, cd into the SpanBERT directory 
   and run using the following command line format (use python3):

   	python3 IterativeSetExpansion.py <google api key> <google engine id> <relation to extract> <confidence threshold> <seed query> <number of tuples to output>


Example:
    
    	python3 IterativeSetExpansion.py AIzaSyAbUyFNJp6VrdunILLcN-OecO0K7_ZH1OU b305c2cc7c4272302 2 0.7 "bill gates microsoft" 10


Description of Internal Design - General Structure:

The program is composed of several helper functions in the IterativeSetExpansion class and 
a main loop in the iterative_set_expansion() function. We maintain a dictionary (called tuples_dict) 
that maps tuples of (subject, object, relation) to confidence, and a set (called used_tuples) that contains 
all the tuples used for queries.


Explanation of functions

iterative_set_expansion() 
	- The main loop that executes the program and calls the necessary helper functions (described below).

get_top_10_urls() 
	- Issues a query to the google search api to retrieve the 10 best results for tuple extraction. 
	  Returns the top 10 search results.

extract_tuples() 
	- Accepts a generator object of the spacy sentences for a document and returns a list of relevant 
	  tuples extracted from the document with a certain confidence threshold.

remove_exact_duplicates() 
	- Updates the tuples_dict. For each newly extracted tuple from a document, if the tuple already
	  exists in the dictionary, we take the max of the new and old tuples' confidences; otherwise we 
	  add the new tuple to the dictionary with its confidence.

select_new_tuple() 
	- Sorts the tuples in tuple_dict by their keys and picks the highest confidence tuple 
	  that hasn't been used as a query (not in used_tuples set). 

get_top_k() 
	- Returns the the tuples in the tuples_dict sorted in descending order by their confidences.


The general structure is as follows:

In the main loop in iterative_set_expansion():

1. Call get_top_10_urls() to retrieve the search results for the current query.

2. Iterate through each search result, calling extract_tuples() for each document to 
   retrieve the extracted tuples. For each extracted tuple, we call remove_exact_duplicates() to update 
   the main tuples_dict with the newly retrieved tuples.

3. If we have retrieved enough tuples in total, call get_top_k() and print the tuples 
   and terminate. Otherwise, call select_new_tuple() to get the top confidence unused
   tuple as the next query and repeat steps 1-3. If no such tuple exists, terminate.



A detailed description of how you carried out Step 3 in the "Description" section above

The program is composed of several helper functions in the IterativeSetExpansion class
and a main loop in the iterative_set_expansion() function. We maintain a dictionary 
(called tuples_dict) that maps tuples of (subject, object, relation) to confidence, 
and a set (called used_tuples) that contains all the tuples used for queries, and a 
dictionary relations_dict that maps a relation number to its name and entities of interest.

1. In the main loop iterative_set_expansion(), we first initialize a set called processed_urls that tracks the URLs that we have read. 

2. We then issue the current query (which is initially the user's seed query) and retrieve the top 10 results. 

3. For each search result:
	1. We open the URL. If there is an error in opening the document, we skip it.
	 Otherwise, we parse the html of the document and perform some text preprocessing/cleaning 
	 by remove HTML markup using html.parser and use regular expressions to remove open/close 
	 brackets and text in between such brackets (useful for reading wikipedia pages where citations 
	 are included in brackets and such). We then truncate the cleaned text to up to 20000 characters 
	 and use spaCy library to split the text into sentences.

	2. Call self.extract_tuples(), which takes in the spacy sentences for a document and 
	   returns the relevent extracted tuples for the relation. 

	   extract_tuples() works as follows:
	   First, look up the relevant entities of interest for the relation in relations_dict. 
	   Then for each sentence of the document, we call the get_entities() helper function 
	   to retrieve the relevant entities in each sentence. If no entities are retrieved, 
	   we skip to the next sentence. Else, we use the provided helper function create_entity_pairs() 
	   to create possible entity pairs for the relation by combining the retrieved entities from 
	   get_entities(). We then call spanBert for each entity pair if the subject and object are relevant
	   types to the extraction task. If the returned predictions are of the correct relation and above the 
	   confidence threshhold, we call remove_exact_duplicates() to check if the tuple is already in our main 
	   tuple_dict or not. If it is, we check for confidence score and take the max confidence score. If it
	   is not, we append the tuple to our dictionary.

4. If we have extracted enough tuples in total, we print them and terminate. Otherwise, 
   we sort the tuples in the dictionary by their values (confidence) and pick the highest 
   confidence unused tuple with the help of the used_tuples set and issue another query with 
   this tuple, repeating steps 2 through 5 until we have retrieved enough total tuples or 
   we do not have any unused tuples to use as queries.


External Libraries:

1. spaCy 				- Used to process and annotate text through linguistic analysis
2. SpanBERT				- Used to extract the four relations specified in the project description from text documents
3. BeautifulSoup4			- Used to extract plain text from a given web page
4. googleapiclient.discovery's build   	- Used to connect to Google API




Your Google Custom Search Engine JSON API Key and Engine ID (so we can test your project)

Google Custom Search Engine JSON API Key: AIzaSyAbUyFNJp6VrdunILLcN-OecO0K7_ZH1OU

Engine ID: b305c2cc7c4272302


Sources:

https://www.crummy.com/software/BeautifulSoup/bs4/doc/
https://realpython.com/beautiful-soup-web-scraper-python/
https://www.techiedelight.com/sort-list-of-objects-python/
https://www.secopshub.com/t/handling-api-errors-using-python-requests/589
https://spacy.io/usage/linguistic-features#sbd
https://www.kite.com/python/answers/how-to-detect-when-a-urllib-connection's-timeout-expires-in-python
https://www.pluralsight.com/guides/implementing-web-scraping-with-beautifulsoup
https://stackoverflow.com/questions/8763451/how-to-handle-urllibs-timeout-in-python-3
https://levelup.gitconnected.com/two-simple-ways-to-scrape-text-from-wikipedia-in-python-9ce07426579b
https://www.geeksforgeeks.org/python-sort-python-dictionaries-by-key-or-value/
https://docs.python.org/3/library/re.html
https://lzone.de/examples/Python%20re.sub
https://stackoverflow.com/questions/5843518/remove-all-special-characters-punctuation-and-spaces-from-string
https://docs.python.org/3/library/logging.html
https://docs.python.org/3/library/urllib.error.html
https://www.w3schools.com/python/ref_string_join.asp
