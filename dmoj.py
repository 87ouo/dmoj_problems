#coding=utf-8
from __future__ import unicode_literals
import requests
import json
import html2text
from requests_html import HTMLSession  #py3
#import pypandoc
from concurrent.futures import ThreadPoolExecutor
import argparse
import progressbar
import logging
import re
import os
import codecs
import yaml
 
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
        logging.critical(e)
    return problem_list
    
session = HTMLSession()    
def getproblemdesc(base_url, problem_code):
    url = "%s/problem/%s" % (base_url, problem_code)
    r = session.get(url)
    return r.html.find('#content-left > div.content-description.screen', first=True)

def getproblemdetail(base_url, problem_code):
    url = "%s/api/problem/info/%s" % (base_url, problem_code)
    reponse = requests.get(url)
    problem_info = json.loads(reponse.text)
    node = getproblemdesc(base_url, problem_code) 
    h = HTML2TextDmoj()
    problem_desc = ""
    if node:
        problem_desc = h.handle(node.html)
    else:
        logging.error("problem %s desc emtpy." % problem_code)
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

def getrepeat(data):
    result = []
    i = len(data) - 2
    while i >= 0:
        if data[i][0] == data[i + 1][0]:
            result.append((data[i], data[i + 1]))
            del data[i + 1]             
            del data[i]
            i -= 2
        else:
            i -= 1
    return result        
    
    
def fix(problem_desc, inputs, outputs):
    if len(inputs) == 0 and len(outputs) == 1 and len(re.findall(r'There is none.|There is no input.', problem_desc)) > 0:
        inputs.append(('', ''))
        return True
    inputrepeat = getrepeat(inputs)
    outputrepeat = getrepeat(outputs)
    for repeat in inputrepeat + outputrepeat:
        inputs.append(repeat[0])
        outputs.append(repeat[1])
    return len(inputs) == len(outputs)

def gen_test_data_problem(problem):  
    problem_desc = problem['fields']['description']
    problem_code = problem['fields']['code']
    inputs = re.findall(r"# ((?:Sample Input|Sample input|Input for Sample Input)(?: \d+)?)[^\n]*?\n( .*?|.{0})\n\n", problem_desc, flags=re.DOTALL)
    outputs = re.findall(r"(?:# |\n)((?:Sample Output|Sample output|Output for Sample Input|Possible Output for Sample Input)(?: \d+)?)[^\n]*?\n( .*?|.{0})\n\n", problem_desc, flags=re.DOTALL)
    if len(inputs) != len(outputs) and not fix(problem_desc, inputs, outputs):
        logging.error("inputs num not equal to outputs:%s" % problem_code)      
        return
    if len(inputs) == 0:
        logging.warning("test data empty:%s" % problem_code)
        return
    datadir = os.path.join("test_data", problem_code)
    if not os.path.exists(datadir):
        os.makedirs(datadir)
    init = {}
    init['test_cases'] = []
    for i in range(0, len(inputs)):
        input = inputs[i][1].strip()
        input = re.sub(r'\n\s+', '\n', input)
        output = outputs[i][1].strip()
        output = re.sub(r'\n\s+', '\n', output)                
        try:
            infile = '%s.%d.in' % (problem_code, i + 1)
            with codecs.open(os.path.join(datadir, infile), 'w', 'utf-8') as f:
                f.write(input)
            outfile = '%s.%d.out' % (problem_code, i + 1)
            with codecs.open(os.path.join(datadir, outfile), 'w', 'utf-8') as f:
                f.write(output)
            init['test_cases'].append({'in': infile, 'out': outfile, 'points': 10})
        except Exception as e:
            logging.error("%s:%s" % (problem_code, e))
    with open(os.path.join(datadir, "init.yml"), 'w', newline='') as f:
        yaml.dump(init, f, line_break='\n')         
    
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
        problem_json = {"fields": problem, "model": "judge.problem", "pk": i}
        problems_json.append(problem_json)
        i += 1
        gen_test_data_problem(problem_json)
        
    with open('problemtypes.json', 'w', newline='') as f:
        json.dump(problemtypes_json, f, indent=4)
    with open('problemgroups.json', 'w', newline='') as f:
        json.dump(problemgroups_json, f, indent=4)
    with open('problems.json', 'w', newline='') as f:
        json.dump(problems_json, f, indent=4)   

def crawlproblems(base_url, problem_code, task_num):
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
            logging.info("\nstopped by user")
            return
        except Exception as e:
            logging.critical(e)
            return
        else:
            saveproblems(problemtypes, problemgroups, problems) 
            bar.finish()
       

def gen_test_data(problemspath):
    with open(problemspath, 'r') as f:
        try:
            problems = json.load(f)
            for problem in problems:
                gen_test_data_problem(problem)
        except Exception as e:
            print(e)
                
                        
def getloglevel(loglevel):
    return {'debug':logging.DEBUG,'info':logging.INFO,
    'warning':logging.WARNING,'error':logging.ERROR,'critical':logging.CRITICAL}[loglevel]

base_url = "https://dmoj.ca"
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem_code", "-c", help="Problem code to crawling, * for all", type=str, default="*")
    parser.add_argument("--task_num", "-n", help="Concurrent crawling of tasks", type=int, default=1)
    parser.add_argument("--log_level", "-l", help="log level", type=str, choices=['debug','info','warning','error','critical'], default='warning')
    parser.add_argument("--test_data_only", "-t", help="test_data_only", action="store_true", default=False)
    args = parser.parse_args()
    logging.basicConfig(level=getloglevel(args.log_level))
    if args.test_data_only:
        gen_test_data("problems.json")
    else:
        crawlproblems(base_url, args.problem_code, args.task_num)
    
    