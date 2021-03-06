"""
This is the (unofficial) Python API for malwr.com Website.
Using this code, you can retrieve recent analyses, domains, tags but also latest comments.
You can also submit files

"""
import hashlib

import re
import requests
import os
from bs4 import BeautifulSoup


class MalwrAPI(object):
    """
        MalwrAPI Main Handler
    """
    session = None
    logged = False
    verbose = False
    url = "https://malwr.com"
    headers = {
        'User-Agent': "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:41.0) " +
                      "Gecko/20100101 Firefox/41.0"
    }

    def __init__(self, verbose=False, username=None, password=None, apikey=None):
        self.verbose = verbose
        self.session = requests.session()
        self.username = username
        self.password = password
        self.apikey = apikey

    def login(self):
        """Login on malwr.com website"""
        if self.username and self.password:
            soup = self.request_to_soup(self.url + '/account/login')
            csrf_input = soup.find(attrs=dict(name='csrfmiddlewaretoken'))
            csrf_token = csrf_input['value']
            payload = {
                'csrfmiddlewaretoken': csrf_token,
                'username': u'{0}'.format(self.username),
                'password': u'{0}'.format(self.password)
            }
            login_request = self.session.post(self.url + "/account/login/",
                                              data=payload, headers=self.headers)

            if login_request.status_code == 200:
                self.logged = True
                return True
            else:
                self.logged = False
                return False

    def request_to_soup(self, url=None):
        """Request url and return the Beautifoul Soup object of html returned"""
        if not url:
            url = self.url

        req = self.session.get(url, headers=self.headers)
        soup = BeautifulSoup(req.content, "html.parser")
        return soup

    def display_message(self, s):
        """Display the message"""
        if self.verbose:
            print('[verbose] %s' % s)

    def get_latest_comments(self):
        """Request the last comments on malwr.com"""
        res = []
        soup = self.request_to_soup()
        comments = soup.findAll('div', {'class': 'span6'})[3]

        for comment in comments.findAll('tr'):
            infos = comment.findAll('td')

            infos_to_add = {
                'comment': infos[0].string,
                'comment_url': infos[1].find('a')['href']
            }
            res.append(infos_to_add)

        return res

    def get_recent_domains(self):
        """Get recent domains on index page
        Returns a list of objects with keys domain_name and url_analysis"""
        res = []
        soup = self.request_to_soup()

        domains = soup.findAll('div', {'class': 'span6'})[1]
        for domain in domains.findAll('tr'):
            infos = domain.findAll('td')
            infos_to_add = {
                'domain_name': infos[0].find('span').string,
                'url_analysis': infos[1].find('a')['href']
            }
            res.append(infos_to_add)

        return res

    def get_public_tags(self):
        """Get public tags on index page
        Return a tag list"""
        res = []
        soup = self.request_to_soup()

        tags = soup.findAll('div', {'class': 'span6'})[2]
        for tag in tags.findAll('a', {'class': 'tag-label'}):
            res.append(tag.string)

        return res

    def get_recent_analyses(self):

        res = []
        soup = self.request_to_soup()

        submissions = soup.findAll('div', {'class': 'span6'})[0]
        for submission in submissions.findAll('tr'):
            infos = submission.findAll('td')

            infos_to_add = {
                'submission_time': infos[0].string,
                'hash': infos[1].find('a').string,
                'submission_url': infos[1].find('a')['href']
            }
            res.append(infos_to_add)

        return res

    def submit_folder(self, path, analyze=True, share=True, private=True):
        filelist = [f for f in os.listdir(path)]
        res = []
        for item in filelist:
            res.append(self.submit_sample(path + item, analyze, share, private))
        return res

    def submit_sample(self, filepath, analyze=True, share=True, private=True):
        if self.logged is False:
            self.login()

        s = self.session
        req = s.get(self.url + '/submission/', headers=self.headers)

        soup = BeautifulSoup(req.content, "html.parser")

        # TODO: math_captcha_question might be unused. Remove.
        # math_captcha_question = soup.find('input', {'name': 'math_captcha_question'})['value']

        pattern = '(\d [-+*] \d) ='
        data = {
            'math_captcha_field': eval(re.findall(pattern, req.content)[0]),
            'math_captcha_question': soup.find('input', {'name': 'math_captcha_question'})['value'],
            'csrfmiddlewaretoken': soup.find('input', {'name': 'csrfmiddlewaretoken'})['value'],
            'share': 'on' if share else 'off',  # share by default
            'analyze': 'on' if analyze else 'off',  # analyze by default
            'private': 'on' if private else 'off'  # private by default
        }

        req = s.post(self.url + '/submission/', data=data, headers=self.headers,
                     files={'sample': open(filepath, 'rb')})

        # TODO: soup might be unused. Remove.
        # soup = BeautifulSoup(req.content, "html.parser")

        # regex to check if the file was already submitted before
        pattern = '(\/analysis\/[a-zA-Z0-9]{12,}\/)'
        submission_links = re.findall(pattern, req.content)

        res = {
            'md5': hashlib.md5(open(filepath, 'rb').read()).hexdigest(),
            'file': filepath
        }

        if len(submission_links) > 0:
            self.display_message('File %s was already submitted, taking last analysis' % filepath)
            res['analysis_link'] = submission_links[0]
        else:
            pattern = '(\/submission\/status\/[a-zA-Z0-9]{12,}\/)'
            submission_status = re.findall(pattern, req.content)

            if len(submission_status) > 0:
                res['analysis_link'] = submission_status[0]
            elif 'file like this waiting for processing, submission aborted.' in req.content:
                self.display_message('File already submitted, check on the site')

                return None
            else:
                self.display_message('Error with the file %s' % filepath)

                return None

        return res

    def search(self, search_word):
        # Do nothing if not logged in
        if not self.logged:
            res = self.login()
            if res is False:
                return False

        search_url = self.url + '/analysis/search/'
        c = self.request_to_soup(search_url)

        csrf_input = c.find(attrs=dict(name='csrfmiddlewaretoken'))
        csrf_token = csrf_input['value']
        payload = {
            'csrfmiddlewaretoken': csrf_token,
            'search': u'{}'.format(search_word)
        }
        sc = self.session.post(search_url, data=payload, headers=self.headers)
        ssc = BeautifulSoup(sc.content, "html.parser")

        res = []
        error = ssc.findAll('div', {'class': 'alert-error'})
        if len(error) > 0:
            self.display_message('Invalid search term')
            return []
        submissions = ssc.findAll('div', {'class': 'box-content'})[0]
        sub = submissions.findAll('tbody')[0]
        for submission in sub.findAll('tr'):
            infos = submission.findAll('td')
            infos_to_add = {
                'submission_time': infos[0].string,
                'hash': infos[1].find('a').string,
                'submission_url': infos[1].find('a')['href'],
                'file_name': infos[2].string
            }
            res.append(infos_to_add)

        return res

    def getReport(self, search_url):
        # Do nothing if not logged in
        if not self.logged:
            res = self.login()
            if res is False:
                return False

        search_url = self.url + search_url
        c = self.request_to_soup(search_url)

        csrf_input = c.find(attrs=dict(name='csrfmiddlewaretoken'))
        csrf_token = csrf_input['value']
        payload = {
            'csrfmiddlewaretoken': csrf_token,
        }
        sc = self.session.post(search_url, data=payload, headers=self.headers)
        ssc = BeautifulSoup(sc.content, "html.parser")
        
        output = {"IP": [], "Domain": []}
       
        domains = ssc.find(id="domains").find_all("td")
        # Will go domain, IP, domain, IP
        for i in range(len(domains)):
            if i%2 == 0:
                # Domain
                output["Domain"].append(domains[i].text)
            else:
                # IP 
                output["IP"].append(domains[i].text)
    
        ips = ssc.find(id="hosts").find_all("td")
        output["IP"] += [x.text for x in ips]
        
        return output
