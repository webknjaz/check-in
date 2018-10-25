from functools import lru_cache, partial
import os.path

import github

from . import __version__ as check_in_version
from .github_checks_requests import NewCheckRequest, UpdateCheckRequest, to_gh_query


cache_once = partial(lru_cache, maxsize=1)

DEFAULT_USER_AGENT = f'check-in/{check_in_version} (+https://pypi.org/p/check-in)'


class GithubClient:
    def __init__(self, app_id, installation_id, private_key_file, repo_slug=None, user_agent_prefix=None):
        self._gh_int = get_github_integration(app_id, private_key_file)
        self._gh_client = get_installation_client(self._gh_int, installation_id)
        self._check_runs_base_uri = f'/repos/{repo_slug}/check-runs'
        self._repo_slug = repo_slug
        self.user_agent = user_agent_prefix

    def __getattr__(self, key):
        return getattr(self._gh_client, key)

    @property
    def user_agent(self):
        return self._user_agent

    @user_agent.setter
    def user_agent(self, user_agent_prefix):
        self._user_agent = DEFAULT_USER_AGENT
        if user_agent_prefix:
            self._user_agent = f'{user_agent_prefix} built with {self._user_agent}'

    def _get_check_caller(self):
        rp = self._gh_client.get_repo(self._repo_slug)
        check_headers={
            'Accept': 'application/vnd.github.antiope-preview+json',
            'User-Agent': self.user_agent,
        }
        return partial(
            rp._requester.requestJsonAndCheck,
            headers=check_headers,
        )

    def _get_check_creator(self):
        checker = self._get_check_caller()
        return partial(
            checker,
            url=self._check_runs_base_uri,
            verb='POST',
        )

    def _get_check_updater(self, check_run_id):
        checker = self._get_check_caller()
        return partial(
            checker,
            url=f'{self._check_runs_base_uri}/{check_run_id}',
            verb='PATCH',
        )

    def post_check(self, head_branch, head_sha, req):
        check_creator = self._get_check_creator()
        post_parameters = to_gh_query(NewCheckRequest(head_branch, head_sha, **req))
        headers, data = check_creator(input=post_parameters)
        return data

    def update_check(self, check_run_id, req):
        check_updater = self._get_check_updater(check_run_id)
        patch_parameters = to_gh_query(UpdateCheckRequest(**req))
        headers, data = check_updater(input=patch_parameters)
        return data


class GithubAPI:
    def __init__(self, app_id, installation_id, private_key_file, repo_slug, user_agent_prefix=None):
        self.app_id = app_id
        self.installation_id = installation_id
        self.private_key_file = os.path.expanduser(os.path.expandvars(private_key_file))
        self.repo_slug = repo_slug
        self.user_agent_prefix = user_agent_prefix

    def __enter__(self):
        self._gh_client = GithubClient(
            self.app_id,
            self.installation_id,
            self.private_key_file,
            self.repo_slug,
            self.user_agent_prefix,
        )
        return self._gh_client

    def __exit__(self, exception_type, exception_value, traceback):
        del self._gh_client
        return any(v is None
                   for v in (exception_type, exception_value, traceback))


@cache_once()
def get_app_key(key_path):
    with open(key_path) as f:
        return f.read()


@cache_once()
def get_github_integration(app_id, key_path):
    private_key = get_app_key(key_path)
    return github.GithubIntegration(app_id, private_key)


def get_installation_auth_token(gh_integration, install_id):
    return gh_integration.get_access_token(install_id).token


def get_installation_client(gh_integration, install_id):
    return github.Github(get_installation_auth_token(gh_integration, install_id))
