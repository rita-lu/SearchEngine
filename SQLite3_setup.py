import sqlite3
con = sqlite3.connect('dbFile.db')
cur = con.cursor()

cur.execute("CREATE TABLE PageRank_Doc (doc_id integer, doc_url text, pagerank real, title text)")
cur.execute("CREATE TABLE Words (word_id integer, word text, doc_id integer)")

con.commit()
con.close()