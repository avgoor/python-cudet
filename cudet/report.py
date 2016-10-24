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

from fuelclient.commands import base
from fuelclient.commands.task import TaskMixIn
from fuelclient.common import data_utils


class SummaryReport(TaskMixIn, base.BaseListCommand):
    """Show filtered task summary for the given noop-run task id"""

    entity_name = 'deployment_history'
    columns = ('task_name', 'node', 'summary')

    def get_parser(self, prog_name):

        parser = super(SummaryReport, self).get_parser(prog_name)
        parser.add_argument('id', type=int, help='Task id')
        return parser

    def take_action(self, parsed_args):

        def _is_noop_event(task):
            """Checks if the task report is a noop-task report"""
            try:
                return 'noop' in task['summary']['events']
            except (KeyError, AttributeError, TypeError):
                return False

        data = self.client.get_all(
            transaction_id=parsed_args.id,
            include_summary=True,
            statuses=('ready',)
        )

        data = [{
            'task_name': item['task_name'],
            'node': item['node_id'],
            'summary': "\n".join(["{}:{}".format(x['source'], x['message'])
                                  for x in item['summary']['raw_report']
                                  if 'should be' in x['message']])
            } for item in data if _is_noop_event(item)]

        data = data_utils.get_display_data_multi(self.columns, data)

        return self.columns, data
