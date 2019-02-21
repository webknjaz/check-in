from functools import lru_cache, partial
import os.path

import github
import requests

from . import __version__ as check_in_version
from .github_checks_requests import NewCheckRequest, UpdateCheckRequest, to_gh_query


cache_once = partial(lru_cache, maxsize=1)

DEFAULT_USER_AGENT = f'check-in/{check_in_version} (+https://pypi.org/p/check-in)'


class GithubClient:
    def __init__(
        self, app_id, installation_id, private_key_file,
        repo_slug=None, user_agent_prefix=None,
        github_url=github.MainClass.DEFAULT_BASE_URL,
    ):
        self._gh_int = get_github_integration(
            app_id, private_key_file,
            github_url,
        )
        self._gh_client = get_installation_client(
            self._gh_int, installation_id,
            github_url,
        )
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
    def __init__(
        self, app_id, installation_id, private_key_file,
        repo_slug, user_agent_prefix=None,
        github_url=github.MainClass.DEFAULT_BASE_URL,
    ):
        self.app_id = app_id
        self.installation_id = installation_id
        self.private_key_file = os.path.expanduser(os.path.expandvars(private_key_file))
        self.repo_slug = repo_slug
        self.user_agent_prefix = user_agent_prefix
        self.github_url = github_url

    def __enter__(self):
        self._gh_client = GithubClient(
            self.app_id,
            self.installation_id,
            self.private_key_file,
            self.repo_slug,
            self.user_agent_prefix,
            self.github_url,
        )
        return self._gh_client

    def __exit__(self, exception_type, exception_value, traceback):
        del self._gh_client
        return any(v is None
                   for v in (exception_type, exception_value, traceback))


class PatchedGithubIntegration(github.GithubIntegration):
    def __init__(
        self, integration_id, private_key,
        github_url=github.MainClass.DEFAULT_BASE_URL,
    ):
        self.__github_url = github_url
        super().__init__(integration_id, private_key)

    def get_access_token(self, installation_id, user_id=None):
        """
        Get an access token for the given installation id.
        POSTs https://api.github.com/installations/<installation_id>/access_tokens
        :param user_id: int
        :param installation_id: int
        :return: :class:`github.InstallationAuthorization.InstallationAuthorization`
        """
        body = {}
        if user_id:
            body = {"user_id": user_id}
        response = requests.post(
            f"{self.__github_url}/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": "Bearer {}".format(self.create_jwt()),
                "Accept": github.Consts.mediaTypeIntegrationPreview,
                "User-Agent": "PyGithub/Python"
            },
            json=body
        )

        if response.status_code == 201:
            return github.InstallationAuthorization.InstallationAuthorization(
                requester=None,  # not required, this is a NonCompletableGithubObject
                headers={},  # not required, this is a NonCompletableGithubObject
                attributes=response.json(),
                completed=True
            )
        elif response.status_code == 403:
            raise github.BadCredentialsException(
                status=response.status_code,
                data=response.text
            )
        elif response.status_code == 404:
            raise github.UnknownObjectException(
                status=response.status_code,
                data=response.text
            )
        raise github.GithubException(
            status=response.status_code,
            data=response.text
        )


@cache_once()
def get_app_key(key_path):
    with open(key_path) as f:
        return f.read()


@cache_once()
def get_github_integration(app_id, key_path, github_url):
    private_key = get_app_key(key_path)
    return PatchedGithubIntegration(app_id, private_key, github_url)


def get_installation_auth_token(gh_integration, install_id):
    return gh_integration.get_access_token(install_id).token


def get_installation_client(
    gh_integration, install_id,
    github_url=github.MainClass.DEFAULT_BASE_URL,
):
    return github.Github(
        get_installation_auth_token(gh_integration, install_id),
        base_url=github_url,
    )
