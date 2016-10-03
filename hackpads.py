import logging

from git.repo.base import NoSuchPathError, Repo


class Hackpads(object):

    def __init__(self, repo_url, repo_path):
        self.repo_url = repo_url
        self.repo_path = repo_path
        self.repo = None

    def pull_repo(self):
        try:
            self.repo = Repo(self.repo_path)
        except NoSuchPathError:
            logging.info('git clone: {}'.format(self.repo_url))
            self.repo = Repo.clone_from(self.repo_url, self.repo_path)
        else:
            logging.info('git pull: {}'.format(self.repo_url))
            self.repo.remote().pull()

    def get_diffs(self, last_commit):
        if not self.repo:
            raise 'NoRepoError'

        if not last_commit:
            # 'repo.index.entries.keys()' look something like this:
            # [('file1.html', 0), ('file2.html', 0), ('f3.xxx', 0), ...]
            diff_pads = [k[0][:-len('.html')]
                         for k in self.repo.index.entries.keys()
                         if k[0].endswith('.html')]
        else:
            diffs = self.repo.index.diff(last_commit)
            diff_pads = [d.b_path[:-len('.html')]
                         for d in diffs
                         if d.b_path.endswith('.html')]

        logging.info('last commit:{}'.format(last_commit))
        logging.info('cur head:{}'.format(self.repo.head.commit))
        logging.info('diff pads: {}'.format('\n' + '\n'.join(diff_pads)))
        return diff_pads

    def latest_commit(self):
        if not self.repo:
            raise 'NoRepoError'
        return str(self.repo.head.commit)
