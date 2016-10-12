from bs4 import BeautifulSoup, SoupStrainer
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
from os import listdir, makedirs
from os.path import isfile, join, splitext
from urllib.parse import urlparse
import shutil

from git.repo.base import NoSuchPathError, Repo
import requests


class Hackfoldrs(object):

    def __init__(self, repo_url, repo_path, gen_foldrs_path):
        self.repo_url = repo_url
        self.repo_path = repo_path
        self.repo = None
        self.gen_foldrs_path = gen_foldrs_path

    def _find_new_foldrs(self, diff_pads, pads_path):
        """ Construct new hackfoldr indexes by
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

                    foldr_url = parsed._replace(path=''.join(paths[:2])).geturl()
                    foldr_id = paths[1]
                    if foldr_id not in foldrs:
                        foldrs[foldr_id] = {'url': foldr_url, 'hackpads': set()}
                    foldrs[foldr_id]['hackpads'].add(pad_id)

        return foldrs

    def _merged_foldr(self, old, new):
        _old = deepcopy(old)
        _new = deepcopy(new)
        for k, v in _new.items():
            if isinstance(v, list):
                _o = set(_old.get(k, []))
                _n = set(v)
                _u = _o | _n
                _old.update({k: sorted(list(_u))})
            elif isinstance(v, set):
                _u = _old.get(k, set()) | v
                _old.update({k: _u})
            elif isinstance(v, dict):
                raise NotImplementedError
            else:
                _old.update({k: v})
        return _old

    def _get_csv_ethercalc(self, foldr_id, hackfoldr_version):
        csv, updated_at = None, None

        csv_url = 'https://ethercalc.org/_/{}/csv.json'.format(foldr_id)
        csv_response = requests.get(csv_url)
        if csv_response.status_code == 200:
            csv = csv_response.json()

            # redirect case: ethercalc -> google
            A1 = csv[0][0]
            if hackfoldr_version >= 2.0 and not A1.startswith('#') and len(A1) >= 40:
                gsheets_id = A1
                return self._get_csv_google(gsheets_id)

            # normal case:
            log_url = 'https://ethercalc.org/log/{}'.format(foldr_id)
            log_response = requests.get(log_url)
            if log_response.status_code == 200:
                csv = csv_response.json()
                history = log_response.json()
                updated_at = max(map(lambda h: datetime.strptime(h['mtime'], '%a, %d %b %Y %H:%M:%S GMT'), history)).replace(tzinfo=timezone.utc)

        return csv, updated_at

    def _get_csv_google(self, foldr_id):
        csv, updated_at = None, None

        csv_url = 'https://spreadsheets.google.com/feeds/list/{}/od6/public/values?alt=json'.format(foldr_id)
        csv_response = requests.get(csv_url)
        if csv_response.status_code == 200:
            ordered_json = csv_response.json(object_pairs_hook=OrderedDict)

            # reformat as ethercalc
            rows = [[(k[len('gsx$'):], v['$t'])
                    for (k, v) in e.items() if k.startswith('gsx$')]
                    for e in ordered_json['feed']['entry']]
            if rows:
                column_names = ['#' + t[0] for t in rows[0]]
                row_values = [[t[1] for t in r] for r in rows]
                csv = [column_names] + row_values
                updated_at = datetime.strptime(ordered_json['feed']['updated']['$t'][:-5], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)

        return csv, updated_at

    def _get_csv(self, foldr_id, hackfoldr_version):
        """ In most cases, csv comes from ethercalc,
        but some comes from google spreadsheets.

        We will try google first, because ethercalc
        is too easy to create a new.

        e.g. We can easily copy gsheets_id and
        ```
        $ curl -XGET https://ethercalc.org/gsheets_id
        ```
        to create a same_gsheets_id sheet on ethercalc.

        If we try ethercalc first, we won't be able to
        reach the actual csv source if it's on google.
        """

        csv, updated_at = self._get_csv_google(foldr_id)
        if csv and updated_at:
            return ('google', csv, updated_at)

        csv, updated_at = self._get_csv_ethercalc(foldr_id, hackfoldr_version)
        if csv and updated_at:
            return ('ethercalc', csv, updated_at)

        return (None, None, None)

    def pull_repo(self):
        try:
            self.repo = Repo(self.repo_path)
        except NoSuchPathError:
            logging.info('git clone: {}'.format(self.repo_url))
            self.repo = Repo.clone_from(self.repo_url, self.repo_path)
        else:
            logging.info('git pull: {}'.format(self.repo_url))
            self.repo.remote().pull()

    def gen_foldrs(self, diff_pads, pads_path):
        makedirs(self.gen_foldrs_path, exist_ok=True)
        fn = 'foldrs.json'

        # merge old w/ new
        try:
            with open(join(self.repo_path, fn), 'r') as f:
                old = json.load(f)
                for v in old.values():
                    v.update({'hackpads': set(v.get('hackpads', []))})
        except OSError:
            old = {}
        new = self._find_new_foldrs(diff_pads, pads_path)
        mix = {_id: self._merged_foldr(old.get(_id, {}), new.get(_id, {}))
               for _id in old.keys() | new.keys()}

        # fetch csvs
        for _id, foldr in mix.items():
            hackfoldr_version = 2.0 if 'beta' in urlparse(foldr.get('url', '')).netloc else 1.0
            source, csv, updated_at = self._get_csv(_id, hackfoldr_version)
            if source and csv and updated_at:
                foldr.update({'source': source,
                              'updated_at': updated_at.isoformat().replace('+00:00', 'Z')})
                with open(join(self.gen_foldrs_path, '{}.json').format(_id), 'w') as f:
                    json.dump(csv, f, indent=2, ensure_ascii=False)

        # convert 'hackpads' from set to list
        # remove foldrs without 'source' key
        clean = {_id: f.update({'hackpads': sorted(list(f['hackpads']))}) or f
                 for _id, f in mix.items() if 'source' in f}

        # write foldrs.json
        with open(join(self.gen_foldrs_path, fn), 'w') as f:
            json.dump(clean, f, sort_keys=True, indent=2, ensure_ascii=False)

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
