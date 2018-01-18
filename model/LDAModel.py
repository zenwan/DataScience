import codecs
import os
import re
import pickle
import random
from pprint import pprint
import gensim
import jieba
import jieba.analyse
import jieba.analyse
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from gensim import corpora, models
from gensim import matutils
from gensim.corpora import Dictionary
from gensim.models import LdaModel
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from tqdm import tqdm
from functools import lru_cache

class WordSeg1():
    def __init__(self,stopwords_path = ''):
        self.stop_words = [line.strip() for line in open(stopwords_path, 'r', encoding='utf-8').readlines()]

    def seg_stopword_sentence(self,sentence):
        sentence = sentence
        sentence_seged = jieba.cut(sentence)
        outstr = ''
        for word in sentence_seged:
            if word not in self.stopwords:
                if word != '\t':
                    outstr += word
                    outstr += " "
        return outstr

    def cut(self,df,col='content'):
        return df[col].apply(self.seg_stopword_sentence)


class WordSeg():
    def __init__(self,stopwords_path = '',user_dict=None):
        jieba.initialize()
        jieba.enable_parallel()
        jieba.analyse.set_stop_words(stopwords_path)
        if user_dict is not None:
            jieba.load_userdict(user_dict)

    def remove_illegal(self,input):
        line = input.strip().replace("<br>", "")
        line, _ = re.subn('【', '', line)
        line, _ = re.subn('】', '', line)
        line, _ = re.subn(r'/:[a-z]+', '', line)
        line, _ = re.subn(r'%[0-9A-Z]+', '', line)
        line, _ = re.subn(r' +', ' ', line)
        line, _ = re.subn(r'nan', '', line)
        line, _ = re.subn("[\s+\.\!\/_,$%^*(+\"\']+|[+——！，。？、~@#￥%……&*（）：]+",' ',line)
        return line

    def seg_stopword_sentence(self,sentence):
        line = self.remove_illegal(sentence)
        return list(jieba.cut(line))

    def cut_df(self,df,col='content'):
        return df[col].apply(self.seg_stopword_sentence)

    def cut(self,texts):
        return [self.seg_stopword_sentence(doc) for doc in tqdm(texts,desc='Seg documents') ]


class LDA_by_sklearn():
    def __init__(self, stopwords_path = '',texts=None):
        self.stopwords = codecs.open(stopwords_path, 'r', encoding='utf-8')
        self.stopwords = [w.strip() for w in self.stopwords]

        self.lda = None
        self.tf_vectorizer = None

    def run_lda(self, n_topics=5):
        self.tf_vectorizer = CountVectorizer(strip_accents='unicode', stop_words=self.stopwords)
        tf = self.tf_vectorizer.fit_transform(open("/home/tanglek/dataset/corpus_seg_100k.txt", 'r', encoding='utf-8'))
        self.lda = LatentDirichletAllocation(n_topics=n_topics, max_iter=100,learning_method='online', learning_offset=50, random_state=999)
        self.lda.fit(tf)

    def print_top_words(self, n_top_words=10):
        tf_feature_names = self.tf_vectorizer.get_feature_names()
        for topic_idx, topic in enumerate(self.lda.components_):
            print('Topic #{0}:'.format(str(topic_idx)))
            print(' '.join([tf_feature_names[i] for i in topic.argsort()[:-n_top_words - 1:-1]]))
            print()

class LDA_by_gensim():
    def __init__(self, stopwords_path = '',texts=None):
        self.stopwords = codecs.open(stopwords_path, 'r', encoding='utf-8')
        self.stopwords = [w.strip() for w in self.stopwords]

        self.train_set = texts

    def run_lda(self, n_topics=10):
        self.n_topics = n_topics
        dictionary = Dictionary(self.train_set)
        corpus = [dictionary.doc2bow(text) for text in self.train_set]

        self.lda = LdaModel(corpus=corpus, id2word=dictionary, num_topics=n_topics)

    def print_top_words(self, n_top_words=10):
        pprint(self.lda.show_topics(num_topics=self.n_topics, num_words=n_top_words, formatted=False))
        # for topic in self.lda.print_topics(20):
        #     print(topic)

class ChnTfidfLDAModel():
    def __init__(self,train_texts,test_texts):
        self.train_texts = train_texts
        self.test_texts = test_texts
        # self.num_topics = [5]
        self.num_topics = [5, 10, 15, 20]
        # topicnums = [1, 5, 10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        self.no_below_this_number = 50
        self.no_above_fraction_of_doc = 0.2
        self.ldamodels_tfidf = {}
        self.ldamodels_eval = {}

    # http://radimrehurek.com/topic_modeling_tutorial/2%20-%20Topic%20Modeling.html
    def intra_inter_tfidf(self,lda_model, dictionary, test_docs, num_pairs=10000):
        # Split each test document into two halves and compute topics for each half
        part1 = [lda_model[self.tfidf[dictionary.doc2bow(tokens[:int(list(tokens) / 2)])]] for tokens in test_docs]
        part2 = [lda_model[self.tfidf[dictionary.doc2bow(tokens[int(list(tokens) / 2):])]] for tokens in test_docs]
        # Compute topic distribution similarities using cosine similarity
        # print("Average cosine similarity between corresponding parts (higher is better):")
        corresp_parts = np.mean([gensim.matutils.cossim(p1, p2) for p1, p2 in zip(part1, part2)])
        # print("Average cosine similarity between 10,000 random parts (lower is better):")
        random.seed(42)
        random_pairs = np.random.randint(0, len(test_docs), size=(num_pairs, 2))
        random_parts = np.mean([gensim.matutils.cossim(part1[i[0]], part2[i[1]]) for i in random_pairs])
        return corresp_parts, random_parts

    def fit(self,df,col="content"):
        pass

    def print_features(clf, vocab, n=10):
        """ Print sorted list of non-zero features/weights. """
        coef = clf.coef_[0]
        print('positive features: %s' % (
        ' '.join(['%s/%.2f' % (vocab[j], coef[j]) for j in np.argsort(coef)[::-1][:n] if coef[j] > 0])))
        print('negative features: %s' % (
        ' '.join(['%s/%.2f' % (vocab[j], coef[j]) for j in np.argsort(coef)[:n] if coef[j] < 0])))

    def fit_classifier(X, y, C=0.1):
        """ Fit L1 Logistic Regression classifier. """
        # Smaller C means fewer features selected.
        clf = LogisticRegression(penalty='l1', C=C)
        clf.fit(X, y)
        return clf

    def fit_lda(X, vocab, num_topics=5, passes=20):
        """ Fit LDA from a scipy CSR matrix (X). """
        print('fitting lda...')
        return models.ldamodel.LdaModel(matutils.Sparse2Corpus(X), num_topics=num_topics,
                        passes=passes,
                        id2word=dict([(i, s) for i, s in enumerate(vocab)]))

    def jaccard_similarity(query, document):
        intersection = set(query).intersection(set(document))
        union = set(query).union(set(document))
        return float(len(intersection)) / float(len(union))

    def eval(self):
        dictionary = corpora.Dictionary(self.train_texts)
        dictionary.filter_extremes(no_below=self.no_below_this_number, no_above=self.no_above_fraction_of_doc)
        corpus = [dictionary.doc2bow(text) for text in self.train_texts]
        self.tfidf = models.TfidfModel(corpus)
        corpus_tfidf = self.tfidf[corpus]
        for i in tqdm(self.num_topics, desc='num of topics'):
            random.seed(42)
            self.ldamodels_tfidf[i] = models.ldamodel.LdaModel(corpus_tfidf, num_topics=i, id2word=dictionary)
            self.ldamodels_tfidf[i].save('./data/ldamodels_tfidf_' + str(i) + '.lda')
            for j in range(i):
                print('Topic {} : {}'.format (str(j) , self.ldamodels_tfidf[i].print_topic(j)))


        # for i in tqdm(self.topicnums, desc='num of topics'):
        #     lda_model = models.ldamodel.LdaModel.load('./data/ldamodels_tfidf_' + str(i) + '.lda')
        #     self.ldamodels_eval[i] = self.intra_inter_tfidf(lda_model, dictionary, self.test_texts)
        #
        # pickle.dump(self.ldamodels_eval, open('./data/pub_ldamodels_tfidf_eval.pkl', 'wb'))

    def visualize_eval(self):
        # ldamodels_eval = pickle.load(open('./data/pub_ldamodels_tfidf_eval.pkl', 'rb'))
        corresp_parts = [self.ldamodels_eval[i][0] for i in self.num_topics]
        random_parts = [self.ldamodels_eval[i][1] for i in self.num_topics]
        sns.set_context("poster")
        with sns.axes_style("darkgrid"):
            x = self.num_topics
            y1 = corresp_parts
            y2 = random_parts
            plt.plot(x, y1, label='Parts from same article')
            plt.plot(x, y2, label='Parts from random articles')
            plt.ylim([0.0, 1.0])
            plt.xlabel('Number of topics')
            plt.ylabel('Average cosine similarity')
            plt.legend()
            plt.show()

    def visualize_stability(self):
        lda_stability = pickle.load(open('./data/pub_lda_tfidf_stability.pkl', 'rb'))
        mean_stability = [np.array(lda_stability[i]).mean() for i in self.num_topics[:-1]]

        with sns.axes_style("darkgrid"):
            x = self.num_topics[:-1]
            y = mean_stability
            plt.plot(x, y, label='Mean overlap')
            plt.xlim([1, 100])
            plt.ylim([0, 1])
            plt.xlabel('Number of topics')
            plt.ylabel('Average Jaccard similarity')
            # plt.legend()
            plt.show()

    def print_top_words(self, feature_names, n_top_words):
        for topic_idx, topic in enumerate(self.model.components_):
            print("Topic #{}:".format(topic_idx))
            print(" ".join([feature_names[i]  for i in topic.argsort()[:-n_top_words - 1:-1]]))

    def print_topics(self,n=10):
        """ Print the top words for each topic. """
        for k,lda in self.ldamodels_tfidf.items():
            topics = lda.show_topics(num_topics=k,num_words=n, log=True,formatted=False)
            for ti, topic in enumerate(topics):
                print('{}:{}'.format(ti,topic))
                print('-'*60)
            #     print('topic %d: %s' % (ti, ' '.join('%s/%.2f' % (t[1], t[0]) for t in topic)))
            print("{}{} topics{}".format("="*25,k,"="*25))

def ccfnews():
    data = pd.read_csv("~/dataset/ccf_news_rec/train.txt", sep='\t', header=None)
    data.columns = ['user_id', 'news_id', 'browse_time', 'title', 'content', 'published_at']
    data['title'] = data['title'].astype(str)
    data['content'] = data['content'].astype(str)
    wordseg = WordSeg("/home/tanglek/opensource/stopwords/all_stopwords.txt")
    df = data.drop_duplicates(['news_id'])
    texts=df['content'].tolist()
    texts = wordseg.cut(texts)
    # print(texts[0])
    print("texts size:{}".format(len(texts)))
    random.seed(42)
    train_set = random.sample(list(range(0, len(texts))), len(texts) - 1000)
    test_set = [x for x in list(range(0, len(texts))) if x not in train_set]

    train_texts = [texts[i] for i in train_set]
    test_texts = [texts[i] for i in test_set]
    model = ChnTfidfLDAModel(texts,texts)
    # model = ChnTfidfLDAModel(train_texts,test_texts)
    model.eval()
    model.print_topics()


def large_corpus_test():
    stop_words = [line.strip() for line in open("/home/tanglek/workspace/funlp/data/stop_words.txt", 'r', encoding='utf-8').readlines()]
    texts = []
    with codecs.open("/home/tanglek/dataset/corpus_seg_100k.txt",'r',encoding='utf-8') as f:
        for line in f.readlines():
            outstr = []
            for word in line.strip("\n").split(" "):
                if word not in stop_words:
                    if word != '\t':
                        outstr.append(word)
            texts.append(outstr)

    print("texts size:{}".format(len(texts)))
    # texts = wordseg.cut(texts)
    model = LDA_by_sklearn("/home/tanglek/workspace/funlp/data/stop_words.txt",texts)
    model.run_lda()
    model.print_top_words()


if __name__ == '__main__':
    ccfnews()