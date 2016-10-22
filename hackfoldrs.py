from collections import OrderedDict
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

    def __init__(self, index_url, repo_url, repo_path, gen_foldrs_path):
        self.index_url = index_url
        self.repo_url = repo_url
        self.repo_path = repo_path
        self.repo = None
        self.gen_foldrs_path = gen_foldrs_path

    def _get_csv_ethercalc(self, foldr_id, hackfoldr_version):
        csv, updated_at = None, None

        # although ethercalc says json api should looks like this:
        # `https://ethercalc.org/_/your_id/csv.json`, but
        # `https://ethercalc.org/your_id.csv.json` is more backward compatible.
        csv_url = 'https://ethercalc.org/{}.csv.json'.format(foldr_id)
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
        but some comes from google spreadsheets. """

        if len(foldr_id) < 40:
            source = 'ethercalc'
            csv, updated_at = self._get_csv_ethercalc(foldr_id, hackfoldr_version)
        else:
            source = 'google'
            csv, updated_at = self._get_csv_google(foldr_id)
        return (source, csv, updated_at)

    def pull_repo(self):
        try:
            self.repo = Repo(self.repo_path)
        except NoSuchPathError:
            logging.info('git clone: {}'.format(self.repo_url))
            self.repo = Repo.clone_from(self.repo_url, self.repo_path)
        else:
            logging.info('git pull: {}'.format(self.repo_url))
            self.repo.remote().pull()

    def gen_foldrs(self):
        makedirs(self.gen_foldrs_path, exist_ok=True)
        foldrs = requests.get(self.index_url).json()
        fn = 'foldrs.json'

        # fetch csvs
        for _id, foldr in foldrs.items():
            hackfoldr_version = 2.0 if 'beta' in urlparse(foldr.get('url', '')).netloc else 1.0
            source, csv, updated_at = self._get_csv(_id, hackfoldr_version)
            if source and csv and updated_at:
                foldr.update({'source': source,
                              'updated_at': updated_at.isoformat().replace('+00:00', 'Z')})
                with open(join(self.gen_foldrs_path, '{}.json').format(_id), 'w') as f:
                    json.dump(csv, f, indent=2, ensure_ascii=False)

        # filter foldrs with 'source' key
        foldrs = {k: v for k, v in foldrs.items() if 'source' in v}

        # write foldrs.json
        with open(join(self.gen_foldrs_path, fn), 'w') as f:
            json.dump(foldrs, f, sort_keys=True, indent=2, ensure_ascii=False)

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
