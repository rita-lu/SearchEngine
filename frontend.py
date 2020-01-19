from bottle import route, template, run, static_file, request, redirect
from collections import Counter
# Google Auth
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.client import flow_from_clientsecrets 
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
import httplib2
#Beaker
import bottle
from beaker.middleware import SessionMiddleware
#SQL
import sqlite3

session_opts = {
    'session.type': 'file',
    'session.cookie_expires': 300,
    'session.data_dir': './data',
    'session.auto': True
}
app = SessionMiddleware(bottle.app(), session_opts)

@route('/static/<filename>')
def server_static(filename):
    return static_file(filename, root='./')

class History(object):
	#initializer function
	def __init__(self):
		self.word_to_count ={} #keeps track of the words searched and the number of times word has been searched
 		self.top_20_words = [] #a list of the top 20 words

 	#add the word/count to the dictionary
 	def add_count(self, word, count):
 		if word in self.word_to_count:
 			self.word_to_count[word] += count
 		else:
 			self.word_to_count[word] = count
 		self.add_if_top_20(word, self.word_to_count[word]) #see if the word can now be in the top 20 list

 	#check if word can be in top 20 list
 	def add_if_top_20(self, word, count):
 		if word in self.top_20_words:
 			index = self.top_20_words.index(word)
 		else:
 			#if top 20 list does not have 20 words, add the word to the list
	 		if len(self.top_20_words)<20:
	 			self.top_20_words.append(word)
	 			index = len(self.top_20_words)-1
	 		#if top 20 list already has 20 words check if the word count for the word at the end of list is less than 
	 		#the count of the word being checked. If it is, add the new word to the end of the list.
	 		else:
	 			index = len(self.top_20_words)-1
	 			if self.word_to_count[self.top_20_words[index]] < count:
	 				self.top_20_words[index] = word
	 			else:
	 				return

	 	#compare the new word's count to the counts of the words before it. If previous index's word has lower count, 
	 	#swap the 2 words. Keep doing this until the word is in the proper place and the list is from highest to lowest word count.
		while index > 0:
			prevCount = self.word_to_count[self.top_20_words[index-1]]
			if prevCount < count:
				self.top_20_words[index-1], self.top_20_words[index] = self.top_20_words[index], self.top_20_words[index-1]
				index= index - 1
			else: 
				return
		return

	#returns 20 tuples for the top 20 list with each tuple being the word and its count
	def get_top_20_words(self):
		top_20_list = [ ]
		for word in self.top_20_words:
			count = self.word_to_count[word]
			top_20_list.append((word, count))
		return top_20_list

new_History = History()
wordCount = ''
emailToHistory = {}
emailToRecentSearches = {}
pageCounter = 1

@route('/')
def frontend():
	global new_History
	global wordCount
	global pageCounter

	s = request.environ.get('beaker.session')
	if 'email' in s:
		signed_in = 1
		email = s['email']
		picture = s['picture']

		if 'email' not in emailToHistory:
			emailToHistory['email'] = History()
		new_History = emailToHistory['email']

		if 'email' not in emailToRecentSearches:
			emailToRecentSearches['email'] = []
		recent = emailToRecentSearches['email']
	else:
		signed_in = 0

	#check if form data is being processed
	keywords = request.query.keywords.lower()

	#page number
	if request.query.page:
		pageCounter = int(request.query.page)

	first_word = keywords.partition(' ')[0]

	# Populating search results from SQL Database
	con = sqlite3.connect('dbFile.db')
	cur = con.cursor()
	cur.execute("SELECT * FROM Words WHERE word = '%s'" % first_word)
	search_result_fetch = cur.fetchall()
	search_result = [x[2] for x in search_result_fetch] #get doc-id
	doc_url_pagerank = {}

	for x in search_result:
		cur.execute("SELECT * FROM PageRank_Doc WHERE doc_id = '%d'" % x)
		doc_info = cur.fetchone()
		doc_url_pagerank[doc_info[1]] = (doc_info[2], doc_info[3]) #doc_info[1]/key - docurl, doc_info[2]/v[0] - pagerank, doc_info[3]/v[1] - title
	
	doc_url_pagerank = sorted(doc_url_pagerank.iteritems(), key=lambda (k,v):(v[0],v[1],k), reverse = True ) #sort by pagerank 

	con.commit()
	con.close()

	# Calculating the number of pages necessary
	if len(doc_url_pagerank) == 0:
		pageMax = 0
	elif (len(doc_url_pagerank) % 5) == 0:
		pageMax = (len(doc_url_pagerank) / 5)
	else:
		pageMax = (len(doc_url_pagerank) / 5) + 1

	if pageCounter == pageMax:
		url_rank_list = doc_url_pagerank [5 * (pageCounter - 1): len(doc_url_pagerank)]		
	else:
		url_rank_list = doc_url_pagerank [5 * (pageCounter - 1): 5 + (5 * (pageCounter - 1))]

	#Show word count and top 20 words
	if signed_in == True:
		if keywords == None or len(keywords) == 0:
			newH = new_History.get_top_20_words()
			return template('index', wordCount=wordCount, history=newH, signed_in=signed_in, email=email, picture=picture, recent=recent, pageMax=pageMax, firstKeyword=first_word, pageCounter = pageCounter, url_rank=url_rank_list)
		else:
			keywords = keywords.lower().split()
			wordCount = Counter(keywords)

			for item, count in wordCount.items():
				new_History.add_count(item,count)
			newH = new_History.get_top_20_words()

			for item, count in wordCount.items():
				if item in recent:
					recent.remove(item)
				elif (len(recent)==10):
					recent.pop()
				recent.insert(0,item)

			return template('index', history=newH, wordCount=wordCount, signed_in=signed_in, email=email, picture=picture, recent=recent, pageMax=pageMax, firstKeyword=first_word, pageCounter = pageCounter, url_rank=url_rank_list)
	#Show word count only
	else:
		if keywords == None or len(keywords) == 0:
			return template('index', wordCount=wordCount, signed_in=signed_in, pageMax=pageMax, firstKeyword=first_word, pageCounter = pageCounter, url_rank=url_rank_list)
		else:
			keywords = keywords.lower().split()
			wordCount = Counter(keywords)
			return template('index', wordCount=wordCount, signed_in=signed_in, pageMax=pageMax, firstKeyword=first_word, pageCounter = pageCounter, url_rank=url_rank_list)

@route('/signin')
def signin():
	#Google API client signin
	flow = flow_from_clientsecrets("client_secret_570417207409-r3onfui39g5qb9b4mi52a2cbs14c284v.apps.googleusercontent.com.json",
		scope='https://www.googleapis.com/auth/plus.me https://www.googleapis.com/auth/userinfo.email', 
		redirect_uri="http://localhost:8080/redirect")
	uri = flow.step1_get_authorize_url()
	redirect(str(uri))

@route('/signout')
def signout():
	s = request.environ.get('beaker.session')
	s.delete()
	redirect('/')

@route('/redirect')
def redirect_page():
	code = request.query.get('code', '')
	flow = OAuth2WebServerFlow(client_id='570417207409-r3onfui39g5qb9b4mi52a2cbs14c284v.apps.googleusercontent.com', 
							client_secret='J1Mh3GjskMGaYwSqfjFgHwPP',
							scope='https://www.googleapis.com/auth/plus.me https://www.googleapis.com/auth/userinfo.email',
							redirect_uri="http://localhost:8080/redirect")
	credentials = flow.step2_exchange(code)
	token = credentials.id_token['sub']

	http = httplib2.Http()
	http = credentials.authorize(http)
	# Get user email
	users_service = build('oauth2', 'v2', http=http)
	user_document = users_service.userinfo().get().execute()      
	user_email = user_document['email']
	
	s = bottle.request.environ.get('beaker.session')
	s['email'] = user_document['email']
	s['picture'] = user_document['picture']
	s.save()
	redirect('/')


run(app=app, host='localhost', port=8080, debug=True)