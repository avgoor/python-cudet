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
from copy import deepcopy
from fuelclient.commands import base, environment
from fuelclient.cli.actions.fact import DeploymentAction
from fuelclient.cli.actions.settings import SettingsAction
from fuelclient.cli.error import ServerDataException
from fuelclient.client import logger


MU_UPGRADE_DICT_RESTRICTED = {
    'mu_upgrade': {
        'enabled': True,
        'restart_rabbit': True,
        'restart_mysql': True,
    }
}
MU_UPGRADE_DICT_FULL = deepcopy(MU_UPGRADE_DICT_RESTRICTED)
MU_UPGRADE_DICT_FULL['mu_upgrade'].update({
    'metadata': {
        'group': 'general',
        'label': 'MU label',
        'restrictions': [{
            'action': 'hide',
            'condition': 'true'
        }],
        'weight': 10
    },
    'type': 'hidden',
    'value': True
})


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
        parser.add_argument('--restart-rabbit',
                            dest='restart_rabbit',
                            action='store_true',
                            help='Should we restart rabbit')
        parser.add_argument('--restart-mysql',
                            dest='restart_mysql',
                            action='store_true',
                            help='Should we restart mysql')
        return parser

    def _update_settings_file(self, filename, full=True,
                              restart_rabbit=False, restart_mysql=False):
        settings_yaml = None
        upgrade_dict = MU_UPGRADE_DICT_FULL if full \
            else MU_UPGRADE_DICT_RESTRICTED
        with open(filename, 'r') as f:
            settings_yaml = yaml.load(f.read())
        upgrade_dict['mu_upgrade']['restart_rabbit'] = restart_rabbit
        upgrade_dict['mu_upgrade']['restart_mysql'] = restart_mysql
        settings_yaml['editable'].update(upgrade_dict)
        with open(filename, 'w') as f:
            stream = yaml.dump(settings_yaml)
            f.write(stream)

    def take_action(self, parsed_args):
        env_id = parsed_args.env
        # Explicitly set some arguments
        setattr(parsed_args, 'force', None)
        setattr(parsed_args, 'node', None)
        setattr(parsed_args, 'dir', '/root')
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
                            '/root/settings_{0}.yaml'.format(env_id),
                            restart_rabbit=parsed_args.restart_rabbit,
                            restart_mysql=parsed_args.restart_mysql
                        )
                        settings_action.upload(parsed_args)
                else:
                    for filename in glob.glob(
                            "/root/deployment_{0}/*.yaml".format(env_id)):
                        self._update_settings_file(
                            filename,
                            full=False,
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
