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

import contextlib
import json
import logging
import multiprocessing
import os
import pipes
import subprocess
import sys
import tempfile
import threading
import yaml

from cudet import exceptions
from cudet import flock


logger = logging.getLogger(__name__)


def interrupt_wrapper(f):
    def wrapper(*args, **kwargs):
        try:
            f(*args, **kwargs)
        except KeyboardInterrupt:
            logger.warning('Interrupted, exiting.')
        except exceptions.AllNodesFiltered as e:
            logger.warning(e.message)
        except Exception as e:
            logger.error('Error: %s' % e, exc_info=True)
            for k in dir(e):
                '''debug: print all exception attrs except internal
                and except 'message', which is deprecated since Python 2.6'''
                if not k.startswith('__') and k != 'message':
                    v = getattr(e, k)
                    logger.debug('Error details: %s = %s' % (k, v))
    return wrapper


def run_with_lock(f):
    def wrapper(*args, **kwargs):
        lock = flock.FLock(os.path.join(tempfile.gettempdir(),
                                        'cudet_%s.lock' % f.__name__))
        if not lock.lock():
            logger.warning('Unable to obtain lock, skipping "%s"' %
                           f.__name__)
            return ''
        f(*args, **kwargs)
        lock.unlock()
    return wrapper


class RunItem():
    def __init__(self, target, args=None, key=None, logger=None):
        self.target = target
        self.args = args
        self.key = key
        self.process = None
        self.queue = None
        self.logger = logger or logging.getLogger(__name__)


class SemaphoreProcess(multiprocessing.Process):
    def __init__(self, semaphore, target, args=None, queue=None, logger=None):
        super(SemaphoreProcess, self).__init__()
        self.logger = logger or logging.getLogger(__name__)
        self.semaphore = semaphore
        self.target = target
        if not args:
            args = {}
        self.args = args
        self.queue = queue

    def run(self):
        try:
            result = self.target(**self.args)
            if self.queue:
                self.queue.put_nowait(result)
        except Exception as error:
            self.logger.exception(error)
            if self.queue:
                self.queue.put_nowait(error)
        finally:
            self.logger.debug('finished call: %s' % self.target)
            self.semaphore.release()
            self.logger.debug('semaphore released')


def run_batch(item_list, maxthreads, dict_result=False):
    def cleanup():
        logger.debug('cleanup processes')
        for run_item in item_list:
            if run_item.process:
                run_item.process.terminate()
    semaphore = multiprocessing.BoundedSemaphore(maxthreads)
    try:
        for run_item in item_list:
            semaphore.acquire(True)
            run_item.queue = multiprocessing.Queue()
            p = SemaphoreProcess(target=run_item.target,
                                 semaphore=semaphore,
                                 args=run_item.args,
                                 queue=run_item.queue)
            run_item.process = p
            p.start()
        for run_item in item_list:
            run_item.result = run_item.queue.get()
            if isinstance(run_item.result, Exception):
                logger.critical('%s, exiting' % run_item.result)
                cleanup()
                sys.exit(42)
            run_item.process.join()
            run_item.process = None
        if dict_result:
            result = {}
            for run_item in item_list:
                result[run_item.key] = run_item.result
            return result
        else:
            return [run_item.result for run_item in item_list]
    except KeyboardInterrupt:
        cleanup()
        raise KeyboardInterrupt()


def load_json_file(filename):
    """
    Loads json data from file
    """
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except IOError as e:
        logger.critical("I/O error(%s): file: %s; msg: %s" %
                        (e.errno, e.filename, e.strerror))
        sys.exit(1)
    except ValueError:
        logger.critical("Could not convert data")
        sys.exit(1)


def load_yaml_file(filename):
    """
    Loads yaml data from file
    """
    try:
        with open(filename, 'r') as f:
            return yaml.load(f)
    except IOError as e:
        logger.critical("I/O error(%s): file: %s; msg: %s" %
                        (e.errno, e.filename, e.strerror))
        sys.exit(1)
    except ValueError:
        logger.critical("Could not convert data")
        sys.exit(1)
    except yaml.parser.ParserError as e:
        logger.critical("Could not parse %s:\n%s" %
                        (filename, str(e)))
        sys.exit(1)


def mdir(directory):
    """
    Creates a directory if it doesn't exist
    """
    if not os.path.exists(directory):
        logger.debug('creating directory %s' % directory)
        try:
            os.makedirs(directory)
        except:
            logger.critical("Can't create a directory: %s" % directory)
            sys.exit(3)


def launch_cmd(cmd, timeout, input=None, ok_codes=None):
    def _timeout_terminate(pid):
        try:
            os.kill(pid, 15)
            logger.error("launch_cmd: pid %d killed by timeout" % pid)
        except:
            pass

    logger.info('launching cmd %s' % cmd)
    p = subprocess.Popen(cmd,
                         shell=True,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    timeout_killer = None
    try:
        timeout_killer = threading.Timer(timeout, _timeout_terminate, [p.pid])
        timeout_killer.start()
        outs, errs = p.communicate(input=input)
        outs = outs.decode('utf-8')
        errs = errs.decode('utf-8')
        errs = errs.rstrip('\n')
    except:
        try:
            p.kill()
        except:
            pass
        p.stdin = None
        outs, errs = p.communicate()
        outs = outs.decode('utf-8')
        errs = errs.decode('utf-8')
        errs = errs.rstrip('\n')
    finally:
        if timeout_killer:
            timeout_killer.cancel()
        input = input.decode('utf-8') if input else None
        logger.debug(('___command: %s\n'
                      '_exit_code: %s\n'
                      '_____stdin: %s\n'
                      '____stdout: %s\n'
                      '____stderr: %s') % (cmd, p.returncode, input, outs,
                                           errs))
    return outs, errs, p.returncode


def ssh_node(ip, command='', ssh_opts=None, env_vars=None, timeout=15,
             filename=None, inputfile=None, outputfile=None,
             ok_codes=None, input=None, prefix=None):
    if ssh_opts is None:
        ssh_opts = ''
    if env_vars is None:
        env_vars = ''
    if prefix is None:
        prefix = ''
    if type(ssh_opts) is list:
        ssh_opts = ' '.join(ssh_opts)
    if type(env_vars) is list:
        env_vars = ' '.join(env_vars)
    if (ip in ['localhost', '127.0.0.1']) or ip.startswith('127.'):
        logger.info("skip ssh")
        bstr = "%s timeout '%s' bash -c " % (
               env_vars, timeout)
    else:
        logger.info("exec ssh")
        bstr = "timeout '%s' ssh -t -T %s '%s' '%s' " % (
               timeout, ssh_opts, ip, env_vars)
    if filename is None:
        cmd = '%s %s' % (bstr, pipes.quote(prefix + ' ' + command))
        if inputfile is not None:
            '''inputfile and stdin will not work together,
            give priority to inputfile'''
            input = None
            cmd = "%s < '%s'" % (cmd, inputfile)
    else:
        cmd = "%s'%s bash -s' < '%s'" % (bstr, prefix, filename)
        logger.info("inputfile selected, cmd: %s" % cmd)
    if outputfile is not None:
        cmd = "%s > '%s'" % (cmd, outputfile)
    cmd = ("input=\"$(cat | xxd -p)\"; trap 'kill $pid' 15; " +
           "trap 'kill $pid' 2; echo -n \"$input\" | xxd -r -p | " + cmd +
           ' &:; pid=$!; wait $!')
    return launch_cmd(cmd, timeout, input=input, ok_codes=ok_codes)


# wrap non-list into list
def w_list(value):
    return value if type(value) == list else [value]


@contextlib.contextmanager
def environ_settings(**kwargs):
    environ_dump = os.environ
    for opt, value in kwargs.iteritems():
        os.environ[opt] = value
    try:
        yield
    finally:
        os.environ = environ_dump
