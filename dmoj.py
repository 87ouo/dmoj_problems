#coding=utf-8
from __future__ import unicode_literals
import requests
import json
import html2text
from requests_html import HTMLSession  #py3
#import pypandoc
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import progressbar

 
class HTML2TextDmoj(html2text.HTML2Text):
    def __init__(self, out=None, baseurl=''):
        # 0 for no wrapping
        html2text.HTML2Text.__init__(self, out, baseurl, 0)
        self.skip_data = False
        self.tag_callback = HTML2TextDmoj.tag_callback
        self.mathtext = False
        self.inmath = False
        self.svg = False
        
    def handle_data(self, data, entity_char=False): 
        if self.skip_data:
            return
        super(HTML2TextDmoj, self).handle_data(data, entity_char)
    
    def outputtag(self, tag, attrs, start):
        attrs_str = ''
        for key,value in attrs.items():
            attrs_str += ' %s="%s"' % (key, value)
        self.o('%s%s%s>' % ('<' if start else '</', tag, attrs_str))
    
    @staticmethod
    def tag_callback(this, tag, attrs, start):
        #when render
        if tag == 'math':
            if start:
                this.inmath = True
            else:
                this.inmath = False
            return True
        if this.inmath:
            if tag in ['mn','mi','mo', 'semantics', 'mrow', 'mspace', 'msup', 'msub', 
            'msubsup', 'mfrac', 'mtext', 'munder', 'mstyle', 'mtable', 'mtr', 'mtd', 'msqrt',
            'mover', 'munderover', 'mpadded', 'mroot']:
                if start:
                    this.skip_data = True
                else:
                    this.skip_data = False
                return True
            elif tag == 'annotation':
                if start and 'encoding' in attrs and attrs['encoding'] == 'application/x-tex':
                    this.o('~')
                    this.mathtext = True
                elif this.mathtext and not start:
                    this.o('~')
                    this.mathtext = False
                return True
            else:
                raise Exception("!error:%s not handle" % tag)
        #when no render
        if tag == 'img' and 'class' in attrs and attrs['class'] == 'tex-image':
            return True
        #svg    
        if tag == 'svg':
            if start:
                this.svg = True
            else:
                this.svg = False
            this.outputtag(tag, attrs, start)
            return True
        if this.svg:
            this.outputtag(tag, attrs, start)
            return True
        return False        

        
def getproblemlist(base_url):
    url = "%s/api/problem/list" % base_url
    problem_list = {}
    try:
        response = requests.get(url)
        problem_list = json.loads(response.text)   
    except Exception as e:
        print(e)
    return problem_list

session = HTMLSession()
def getproblemdetail(base_url, problem_code):
    url = "%s/api/problem/info/%s" % (base_url, problem_code)
    reponse = requests.get(url)
    problem_info = json.loads(reponse.text)
    url = "%s/problem/%s" % (base_url, problem_code)
    response = session.get(url)
    node = response.html.find('#content-left > div.content-description.screen', first=True)  
    h = HTML2TextDmoj()
    problem_desc = ""
    if node:
        problem_desc = h.handle(node.html)
    else:
        print("!error:problem %s desc emtpy." % problem_code)
    #print(node.html)
    #print(h.handle(node.html))
    #print(pypandoc.convert_text(node.html, 'md', format='html'))
    problem = {"ac_rate": 0.0, "allowed_languages": [1,2,3,4,5,6,7,8,9], "authors": [1], "banned_users": [], 
    "code": "%s" % problem_code, "curators": [], "date": "2017-12-02T05:00:00Z", "description": "%s" % problem_desc, 
    "group": "%s" % problem_info['group'], "is_manually_managed": False, "is_public": False, "license": None, 
    "memory_limit": problem_info['memory_limit'], "name": "%s" % problem_info['name'], "og_image": "", "partial": problem_info['partial'], 
    "points": problem_info['points'], "short_circuit": False, "summary": "","testers": [], "time_limit": problem_info['time_limit'], 
    "types": problem_info['types'], "user_count": 0}   
    return problem_info, problem

    
def saveproblems(problemtypes, problemgroups, problems):
    problemtypes_json = []
    problemtype_keys = {}
    i = 1
    for problemtype in problemtypes:
        problemtypes_json.append({"fields": {"full_name": "%s" % problemtype, "name": "%s" % problemtype}, "model": "judge.problemtype", "pk": i})
        problemtype_keys[problemtype] = i
        i += 1
    problemgroups_json = []
    problemgroup_keys = {}
    i = 1   
    for problemgroup in problemgroups:
        problemgroups_json.append({"fields": {"full_name": "%s" % problemgroup, "name": "%s" % problemgroup}, "model": "judge.problemgroup", "pk": i})
        problemgroup_keys[problemgroup] = i
        i += 1
    problems_json = []
    i = 1
    for problem in problems:
        problem['group'] = problemgroup_keys[problem['group']]
        for j in range(len(problem['types'])):
            problem['types'][j] = problemtype_keys[problem['types'][j]]
        problems_json.append({"fields": problem, "model": "judge.problem", "pk": i})
        i += 1
    with open('problemtypes.json', 'w') as f:
        json.dump(problemtypes_json, f, indent=4)
    with open('problemgroups.json', 'w') as f:
        json.dump(problemgroups_json, f, indent=4)
    with open('problems.json', 'w') as f:
        json.dump(problems_json, f, indent=4)   

def getproblems(base_url, problem_code, task_num):
    problem_codes = []
    if problem_code == "*":
        problem_list = getproblemlist(base_url)
        problem_codes = sorted(problem_list.keys(), key=lambda x:x)
    else:
        problem_codes.append(problem_code)
    total = len(problem_codes)
    if total == 0:
        return
    problemtypes = set()
    problemgroups = set()
    problems = []    
    bar = progressbar.ProgressBar(0, total)   
    n = 1
    with ThreadPoolExecutor(max_workers=task_num) as executor:
        try:
            for problem_info, problem in executor.map(getproblemdetail, 
            [base_url]*len(problem_codes), problem_codes):
                bar.update(n)
                n += 1
                #print("\n%d:%s" % (n, problem_info['name']))
                problems.append(problem)
                for problemtype in problem_info['types']:
                    problemtypes.add(problemtype)
                problemgroups.add(problem_info['group'])
        except KeyboardInterrupt:
            print("\nstopped by user")
            return
        except Exception as e:
            print(e)
            return
        else:
            saveproblems(problemtypes, problemgroups, problems) 
            bar.finish()


base_url = "https://dmoj.ca"
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem_code", "-c", help="Problem code to crawling, * for all", type=str, default="*")
    parser.add_argument("--task_num", "-n", help="Concurrent crawling of tasks", type=int, default=1)
    args = parser.parse_args()
    getproblems(base_url, args.problem_code, args.task_num)
    
    