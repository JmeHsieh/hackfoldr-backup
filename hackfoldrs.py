from bs4 import BeautifulSoup, SoupStrainer
from collections import OrderedDict
from git.repo.base import Repo
import json
import logging
from os import listdir, makedirs
from os.path import isfile, join, splitext
import requests
from urllib.parse import urlparse
import shutil


class Hackfoldrs(object):

    def __init__(self, repo_url, repo_path, gen_foldrs_path):
        self.repo_url = repo_url
        self.repo_path = repo_path
        self.repo = None
        self.gen_foldrs_path = gen_foldrs_path

    def _extract_foldrs(self, diff_pads, pads_path):
        """ Construct hackfoldr indexes by
        scanning hackfoldr links from hackpad htmls """

        with open(join(pads_path, 'pads.json'), 'r') as f:
            pads = json.load(f)
            pads = [p for p in pads if p['padid'] in diff_pads]

        foldrs = {}
        for pad in pads:
            pad_id = pad['padid']

            with open(join(pads_path, '{}.html').format(pad_id), 'r') as f:
                html = f.read()

            logging.info('scanning {}.html'.format(pad_id))

            for link in BeautifulSoup(html, "html.parser", parse_only=SoupStrainer('a')):
                if link.has_attr('href'):
                    url = link['href']
                    parsed = urlparse(url)
                    paths = parsed.path.split('/')
                    if 'hackfoldr.org' not in parsed.netloc:
                        continue
                    if len(paths) < 2 or not paths[1]:
                        continue

                    foldr_url = url
                    foldr_id = paths[1]
                    if foldr_id not in foldrs:
                        foldrs[foldr_id] = {'url': foldr_url, 'hackpads': set()}
                    foldrs[foldr_id]['hackpads'].add(pad_id)

        return foldrs

    def _get_csv(self, foldr_id):
        """ In most cases, csv comes from ethercalc,
        but some comes from google spreadsheets."""

        ethercalc = 'https://ethercalc.org/_/{}/csv.json'.format(foldr_id)
        google = 'https://spreadsheets.google.com/feeds/list/{}/od6/public/values?alt=json'.format(foldr_id)
        csv, source = None, None

        r_ethercalc = requests.get(ethercalc)
        if r_ethercalc.status_code is 200:
            csv = r_ethercalc.json()
            source = 'ethercalc'
        else:
            r_google = requests.get(google)
            if r_google.status_code is 200:

                # reformat as ethercalc
                ordered_json = r_google.json(object_pairs_hook=OrderedDict)
                rows = [[(k[len('gsx$'):], v['$t'])
                        for (k, v) in e.items() if k.startswith('gsx$')]
                        for e in ordered_json['feed']['entry']]
                if rows:
                    column_names = ['#' + t[0] for t in rows[0]]
                    row_values = [[t[1] for t in r] for r in rows]
                    csv = [column_names] + row_values
                    source = 'google'

        return (csv, source)

    def _merge_foldr(self, old, new):
        old.update(**{k: v for k, v in new.items()
                      if not isinstance(v, list) and not isinstance(v, dict)})
        for k, v in new.items():
            if isinstance(v, list):
                _o = set(old.get(k, []))
                _n = set(new.get(k, []))
                _u = _o.union(_n)
                old.update({k: sorted(list(_u))})
            elif isinstance(v, dict):
                raise NotImplementedError

    def pull_repo(self):
        try:
            logging.info('git pull: {}'.format(self.repo_url))
            repo = Repo(self.repo_path)
            repo.remote().pull()
        except Exception:
            logging.info('pull failure')
            logging.info('git clone: {}'.format(self.repo_url))
            repo = Repo.clone_from(self.repo_url, self.repo_path)
        self.repo = repo

    def gen_foldrs(self, diff_pads, pads_path):
        makedirs(self.gen_foldrs_path, exist_ok=True)
        fn = 'foldrs.json'

        # write {foldr_id}.json
        foldrs = self._extract_foldrs(diff_pads, pads_path)
        for _id, foldr in foldrs.items():
            (csv, source) = self._get_csv(_id)
            if csv:
                foldr['source'] = source
                with open(join(self.gen_foldrs_path, '{}.json').format(_id), 'w') as f:
                    json.dump(csv, f, indent=2, ensure_ascii=False)

        # Set.toList foldr['hackpads']
        # filter . ((HashMap.hasKey 'source') . (.value)) $ foldrs
        new = {_id: f.update({'hackpads': list(f['hackpads'])}) or f
               for _id, f in foldrs.items()
               if 'source' in f}

        # merge old foldrs with the new
        with open(join(self.repo_path, fn), 'r') as f:
            try:
                old = json.load(f)
            except:
                old = {}
        for _id in old:
            self._merge_foldr(old[_id], new.get(_id, {}))

        # write foldrs.json
        with open(join(self.gen_foldrs_path, fn), 'w') as f:
            json.dump(old, f, sort_keys=True, indent=2, ensure_ascii=False)

        logging.info('gen foldrs complete')

    def copy_to_repo(self):
        logging.info('copy gen foldrs to backup repo')

        files = listdir(self.gen_foldrs_path)
        for f in files:
            if splitext(f)[-1] == '.json':
                full_fn = join(self.gen_foldrs_path, f)
                if isfile(full_fn):
                    shutil.copy(full_fn, self.repo_path)

    def commit_push(self):
        if not self.repo:
            raise 'NoRepoError'
        elif len(self.repo.index.diff(None)) == 0:
            logging.info('nothing to commit')
            return

        logging.info('git add .')
        self.repo.index.add('*')

        logging.info('git commit -m "commit updates."')
        self.repo.index.commit('commit updates.')

        logging.info('git push origin')
        self.repo.remote().push(self.repo.head)

    def clean_gened_foldrs(self):
        logging.info('clean gened foldrs')
        shutil.rmtree(self.gen_foldrs_path)
