#    Copyright 2016 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import yaml
import glob

from fuelclient.commands import base, environment
from fuelclient.cli.actions.fact import DeploymentAction
from fuelclient.cli.actions.settings import SettingsAction
from fuelclient.cli.error import ServerDataException
from fuelclient.client import logger
from fuelclient.objects import Environment
from six import string_types

DEFAULT_REPOS_LIST = 'mos, mos-updates, mos-security, mos-holdback'
MU_UPGRADE_FOR_SETTINGS = {
    'mu_upgrade': {
        'metadata': {
            'label': 'Maintenance update',
            'weight': 65,
            'group': 'general',
        },
        'repos': {
            'value': DEFAULT_REPOS_LIST,
            'type': 'text',
            'label': 'Repos for upgrade',
            'description': 'The list of repositories to be used for cluster maintenance upgrade'
        },
        'restart_rabbit': {
            'value': True,
            'type': 'hidden'
        },
        'restart_mysql': {
            'value': True,
            'type': 'hidden'
        },
        'enabled': {
            'value': True,
            'type': 'hidden'
        }
    }
}
MU_UPGRADE_FOR_DEPLOYMENT_INFO = {
    'mu_upgrade': {
        'enabled': True,
        'metadata': {
            'label': 'Maintenance update',
            'weight': 65,
            'group': 'general',
        },
        'repos': DEFAULT_REPOS_LIST,
        'restart_rabbit': True,
        'restart_mysql': True
    }
}


class Updates(environment.EnvMixIn, base.BaseCommand):
    """Sets the needed options for environment and starts the update"""

    def get_parser(self, prog_name):
        parser = super(Updates, self).get_parser(prog_name)
        parser.add_argument('install',
                            type=bool,
                            help='Install update')
        parser.add_argument('--env',
                            type=int,
                            help='Environment ID')
        parser.add_argument('--repos',
                            nargs='+',
                            default=[
                                'mos',
                                'mos-updates',
                                'mos-security',
                                'mos-holdback'
                            ],
                            help='List of repositories')
        parser.add_argument('--restart-rabbit',
                            '--restart-rabbitmq',
                            dest='restart_rabbit',
                            action='store_true',
                            help='Should we restart rabbit')
        parser.add_argument('--restart-mysql',
                            dest='restart_mysql',
                            action='store_true',
                            help='Should we restart mysql')
        return parser

    def _update_settings_file(self, filename, repos, deployment_info=False,
                              restart_rabbit=False, restart_mysql=False):
        settings_yaml = None
        with open(filename, 'r') as f:
            settings_yaml = yaml.load(f.read())
        if deployment_info:
            upgrade_dict = MU_UPGRADE_FOR_DEPLOYMENT_INFO
            upgrade_dict['mu_upgrade']['restart_rabbit'] = restart_rabbit
            upgrade_dict['mu_upgrade']['restart_mysql'] = restart_mysql
            upgrade_dict['mu_upgrade']['repos'] = repos
        else:
            upgrade_dict = MU_UPGRADE_FOR_SETTINGS
            upgrade_dict['mu_upgrade']['restart_rabbit']['value'] = restart_rabbit
            upgrade_dict['mu_upgrade']['restart_mysql']['value'] = restart_mysql
            upgrade_dict['mu_upgrade']['repos']['value'] = repos
        settings_yaml['editable'].update(upgrade_dict)
        with open(filename, 'w') as f:
            stream = yaml.dump(settings_yaml)
            f.write(stream)

    @staticmethod
    def _validate_repo_list(env_id, repo_input):

        env = Environment(env_id)
        repo_names = {
            x['name'] for x in env.get_settings_data()['editable'][
                'repo_setup']['repos']['value']
        }
        repo_set = set([repo_input]) if isinstance(repo_input, string_types) \
            else set(repo_input)

        if not repo_set.issubset(repo_names):
            raise Exception(
                "Invalid repository list: {}, valid repositories are: {}"
                "".format(", ".join(repo_set), ", ".join(repo_names))
            )

    def take_action(self, parsed_args):
        env_id = parsed_args.env
        # Explicitly set some arguments
        setattr(parsed_args, 'force', None)
        setattr(parsed_args, 'node', None)
        setattr(parsed_args, 'split', True)
        setattr(parsed_args, 'dir', '/root')
        repos = DEFAULT_REPOS_LIST
        if parsed_args.repos:
            # Validate the list of repos, if it is not ok or anything happened
            # during the check - just throw an exception and fail
            self._validate_repo_list(env_id, parsed_args.repos)
            repos = ', '.join(parsed_args.repos)
        if parsed_args.install:
            try:
                deployment_action = DeploymentAction()
                settings_action = SettingsAction()
                try:
                    deployment_action.download(parsed_args)
                except ServerDataException as e:
                    if 'no deployment info for this environment' in e.message:
                        settings_action.download(parsed_args)
                        self._update_settings_file(
                            '/root/settings_{0}.yaml'.format(env_id), repos,
                            restart_rabbit=parsed_args.restart_rabbit,
                            restart_mysql=parsed_args.restart_mysql
                        )
                        settings_action.upload(parsed_args)
                else:
                    for filename in glob.glob(
                            "/root/deployment_{0}/*.yaml".format(env_id)):
                        self._update_settings_file(
                            filename, repos,
                            deployment_info=True,
                            restart_rabbit=parsed_args.restart_rabbit,
                            restart_mysql=parsed_args.restart_mysql
                        )
                    deployment_action.upload(parsed_args)

                task_id = self.client.redeploy_changes(env_id)
                logger.info('Successfully prepared and started updates on'
                            ' cluster {0} as task {1}. Check the status of'
                            ' the updates deployment procedure by running'
                            ' `fuel2 task show {1}` or using Web UI.'
                            ''.format(env_id, task_id))

            except Exception as e:
                logger.exception('Fail to install updates for environment '
                                 '{0}'.format(env_id), exc_info=True)
