import json
import logging
from os.path import abspath, dirname, join
from urllib.parse import urlparse

from hackfoldrs import Hackfoldrs

BASE = dirname(abspath(__file__))
DATA = join(BASE, '_data')
GEN_FOLDRS = join(DATA, 'gen_foldrs')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%I:%M:%S %p')


def repo_info():
    with open(join(BASE, 'config.json'), 'r') as f:
        config = json.load(f)

    key = 'foldr_repo'
    if key not in config:
        raise 'Provided key not in config.json'

    url = config[key]
    dir_name = urlparse(url).path.split('/')[-1].split('.')[0]
    return (url, join(DATA, dir_name))


def backup():
    # read config
    with open(join(BASE, 'config.json'), 'r') as f:
        config = json.load(f)
    index_url = config['foldrs_index']
    repo_url = config['foldrs_repo']
    dir_name = urlparse(repo_url).path.split('/')[-1].split('.')[0]
    repo_path = join(DATA, dir_name)

    # setup hackfoldr repo
    hackfoldrs = Hackfoldrs(index_url, repo_url, repo_path, GEN_FOLDRS)
    hackfoldrs.pull_repo()

    hackfoldrs.gen_foldrs()
    hackfoldrs.copy_to_repo()
    hackfoldrs.commit_push()
    hackfoldrs.clean_gened_foldrs()


if __name__ == '__main__':
    backup()
