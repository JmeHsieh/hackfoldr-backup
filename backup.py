import json
import logging
from os.path import abspath, dirname, join
from urllib.parse import urlparse

from hackfoldrs import Hackfoldrs
from hackpads import Hackpads

BASE = dirname(abspath(__file__))
DATA = join(BASE, '_data')
GEN_FOLDRS = join(DATA, 'gen_foldrs')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%I:%M:%S %p')


def repo_info(which):
    with open(join(BASE, 'config.json'), 'r') as f:
        config = json.load(f)

    key = which + '_repo_url'
    if key not in config:
        raise 'Provided key not in config.json'

    url = config[key]
    dir_name = urlparse(url).path.split('/')[-1].split('.')[0]
    return (url, join(DATA, dir_name))


def backup():
    # setup hackpad repo
    pads_url, pads_path = repo_info('hackpad')
    hackpads = Hackpads(pads_url, pads_path)
    hackpads.pull_repo()

    # setup hackfoldr repo
    foldrs_url, foldrs_path = repo_info('hackfoldr')
    hackfoldrs = Hackfoldrs(foldrs_url, foldrs_path, GEN_FOLDRS)
    hackfoldrs.pull_repo()

    try:
        with open(join(DATA, 'last_commit.txt'), 'r') as f:
            last_commit = f.read()
    except OSError:
        last_commit = None

    diff_pads = hackpads.get_diffs(last_commit)
    hackfoldrs.gen_foldrs(diff_pads, pads_path)
    hackfoldrs.copy_to_repo()
    hackfoldrs.commit_push()
    hackfoldrs.clean_gened_foldrs()

    logging.info('update latest commit sha')
    with open(join(DATA, 'last_commit.txt'), 'w') as f:
        f.write(hackpads.latest_commit())


if __name__ == '__main__':
    backup()
