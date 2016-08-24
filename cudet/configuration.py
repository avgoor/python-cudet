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

import pkg_resources

from cudet import utils

_CONFIG = None
DEFAULT_CONFIG_FILE = 'default_config.yaml'


class CudetConfig(object):
    """Represents configuration of Cudet

    Initializes default configuration and updates it by options
    provided via command-line arguments.
    """

    def __init__(self, args=None):
        self.config = {}
        self._init_default_config()

        if args is not None:
            self._update_config_by_args(args)

    def _init_default_config(self):
        default_config_file = pkg_resources.resource_filename(
            'cudet',
            DEFAULT_CONFIG_FILE)
        self.config = utils.load_yaml_file(default_config_file)

    def _update_config_by_args(self, args):
        user_config = getattr(args, 'config', None)

        if user_config is not None:
            self._update_by_config_file(args.config)

        env_ids = getattr(args, 'env', None)

        if env_ids is not None:
            self.config['filters']['cluster'] = env_ids

        node_ids = getattr(args, 'node', None)

        if node_ids is not None:
            self.config['filters']['id'] = node_ids

    def _update_by_config_file(self, config_file):
        additional_config = utils.load_yaml_file(config_file)
        self.config.update(additional_config)

    def __getattr__(self, option):
        if option in self.config:
            return self.config[option]

        raise AttributeError('Option with name {0} is not configured'
                             'in config or is not supported'.format(option))

    def __getitem__(self, item):
        return self.config[item]

    def __setitem__(self, item, value):
        self.config[item] = value

    def __contains__(self, item):
        return item in self.config

    def __iter__(self):
        return iter(self.config)

    def __repr__(self):
        return '<cudet config object>'


def _init_config(args=None):
    global _CONFIG
    _CONFIG = CudetConfig(args)


def get_config(args=None):
    if _CONFIG is None:
        _init_config(args)
    return _CONFIG
