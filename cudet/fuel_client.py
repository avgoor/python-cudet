# -*- coding: utf-8 -*-

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

"""
Working with fuel client as a library
"""

import logging
from pkg_resources import parse_version

NEWER_901 = False
try:
    import fuelclient
    from fuelclient import fuelclient_settings
    if parse_version('9.0.1') >= parse_version(fuelclient.__version__):
        from fuelclient.client import Client as FuelClient
    else:
        from fuelclient.client import APIClient as FuelClient
        NEWER_901 = True
except ImportError:
    FuelClient = None

# LP bug 1592445
try:
    from fuelclient.client import logger
    logger.handlers = []
except:
    pass

from cudet import utils


logger = logging.getLogger(__name__)


def get_client(config):
    """Returns initialized Fuel client

    :param config: The ``cudet.CudetConfig`` instance
    :returns: Fuel client instance
    """

    client = None

    if FuelClient is not None:

        try:
            if NEWER_901:
                client = FuelClient(host=config.fuel_ip,
                                    port=config.fuel_port,
                                    http_proxy=config.fuel_http_proxy,
                                    os_username=config.fuel_user,
                                    os_password=config.fuel_pass,
                                    os_tenant_name=config.fuel_tenant)
            else:
                fuel_settings = fuelclient_settings.get_settings()
                fuel_config = fuel_settings.config
                fuel_config['OS_USERNAME'] = config.fuel_user
                fuel_config['OS_PASSWORD'] = config.fuel_pass
                fuel_config['OS_TENANT_NAME'] = config.fuel_tenant
                fuel_config['HTTP_PROXY'] = config.fuel_http_proxy

                with utils.environ_settings(
                        http_proxy=config.fuel_http_proxy,
                        HTTP_PROXY=config.fuel_http_proxy):

                    client = FuelClient()

        except Exception as e:
            logger.info('Failed to initialize fuelclient instance:%s' % e,
                        exc_info=True)
    else:
        logger.info('Fuelclient can not be imported')

    return client
