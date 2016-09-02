#!/usr/bin/env python2.7
import json
import os
from collections import namedtuple
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.plugins.callback import CallbackBase
from bottle import request, route, redirect, run
from pexpect import pxssh

'''
example input JSON:
{
    "ID":"5525",
    "IP_ADDRESS":"10.14.27.58",
    "SSH_PORT":"22",
    "USER":"user",
    "PASSWORD":"123",
    "COMMAND": "install" {install | delete | status}
}
'''

class Init():
    def __init__(self, config):
        self.config = config

    def LoadCfg(self):
        global PLAYBOOK_INSTALL_PATH, PLAYBOOK_REMOVE_PATH, ANSIBLE_KEY, BASE_DIR, PORT_API, LISTEN_IP
        with open(self.config) as conf_file:
            conf_data = json.load(conf_file)

        PLAYBOOK_INSTALL_PATH = conf_data['PLAYBOOK_INSTALL_PATH']
        PLAYBOOK_REMOVE_PATH = conf_data['PLAYBOOK_REMOVE_PATH']
        ANSIBLE_KEY = conf_data['ANSIBLE_KEY']
        BASE_DIR = conf_data['BASE_DIR']
        PORT_API = conf_data['PORT_API']
        LISTEN_IP = conf_data['LISTEN_IP']

    def RunApi(self):
        run(host=LISTEN_IP, port=PORT_API, quiet=True)


class Halls(object):
    def __init__(self, id, ip, port, user, pswrd):
        self.id = id
        self.ip = ip
        self.port = port
        self.user = user
        self.pswrd = pswrd

    @property
    def PlayWithBook(self):

        playbook_path = PLAYBOOK_PATH
        ansible_key = ANSIBLE_KEY
        basedir=BASE_DIR

        Options = namedtuple('Options', {
            'verbosity',
            'forks',
            'become',
            'listhosts',
            'listtasks',
            'listtags',
            'syntax',
            'module_path',
            'connection',
            'become_method',
            'become_user',
            'check',
            'private_key_file',
            'retry_files_enabled',
            'retry_files_save_path'
        })
        options = Options(verbosity=5,
                          forks=100,
                          become=True,
                          listhosts=False,
                          listtasks=False,
                          listtags=False,
                          syntax=False,
                          module_path=None,
                          connection='ssh',
                          become_method='sudo',
                          become_user=self.user,
                          check=False,
                          private_key_file=ansible_key,
                          retry_files_enabled=False,
                          retry_files_save_path = '/tmp/'
                          )

        results_callback = ResultCallback()
        loader = DataLoader()
        variable_manager = VariableManager()

        inventory = Inventory(loader=loader,
                              variable_manager=variable_manager,
                              host_list=[self.ip,]
                              )

        variable_manager.extra_vars = dict(host=self.ip,
                                           ansible_ssh_host=self.ip,
                                           ansible_ssh_port=self.port,
                                           id=self.id,
                                           secret_root=basedir,
                                           ansible_ssh_user=self.user,
                                           remote_user=self.user,
                                           ansible_ssh_pass=self.pswrd
                                           )
        variable_manager.set_inventory(inventory)

        passwords = {'become_pass' : self.pswrd}

        if not os.path.exists(playbook_path) or not os.path.exists(basedir) or not os.path.exists(ansible_key):
            print '[ERROR] The files or path not exist.'
            return 'Internal Server Error'

        pbex = PlaybookExecutor(playbooks=[playbook_path],
                                inventory=inventory,
                                variable_manager=variable_manager,
                                loader=loader,
                                options=options,
                                passwords=passwords)

        pbex._tqm._stdout_callback = results_callback
        result = pbex.run()

        results_raw = {'success': {self.ip : {"TASK" : {}}}, 'failed': {self.ip : {"TASK" : {}}}, 'unreachable': {self.ip : {"TASK" : {}}}}

        for task, result in results_callback.host_ok_result.items():
            results_raw['success'][self.ip]["TASK"][task] = result._result['changed']

        for task, result in results_callback.host_unreachable_result.items():
            results_raw['unreachable'][self.ip]["TASK"][task] = result._result['msg']

        for task, result in results_callback.host_failed_result.items():
            results_raw['failed'][self.ip]["TASK"][task] = result._result['msg']

        return json.dumps(results_raw, indent=4)

    def statusHalls(self):
        try:
            session = pxssh.pxssh()
            session.force_password = True
            session.login(self.ip, self.user, self.pswrd, port=self.port)
            session.sendline('systemctl show ssh-redirector --no-pager')
            session.prompt()
            result = session.before
            session.logout()
#
            for line in result.splitlines():
                if 'LoadError' not in line:
                    if "ActiveState=" in line:
                        state = (line.split("="))[1]
                    elif "Description=" in line:
                        hall = line[(len(line) - 4):]
                    elif "ExecStart=" in line:
                        exec_raw = line.split(";")
                        command = exec_raw[1][8:((len(exec_raw[1])) - 1)]
                        code = exec_raw[6].split('=')[1][0:(len(exec_raw[6].split('=')[1]) - 1)]
                        status = exec_raw[7].split('=')[1].split(' ')[0]
                else:
                    hall = self.id
                    state = command = code = status = 'Unknown'

        except pxssh.ExceptionPxssh as e:
            hall = self.id
            state = command = code = status = 'Could not establish connection to host'
        finally:
            status_raw = {self.ip: {hall: {'ServiceState': state, 'ExecCommand': command, 'ExecCode': code,
                                           'ExecStatus': status}}}
            return json.dumps(status_raw, indent=4)


class ResultCallback(CallbackBase):
    def __init__(self, *args, **kwargs):
        super(ResultCallback, self).__init__(*args, **kwargs)
        self.host_ok_result = {}
        self.host_failed_result = {}
        self.host_unreachable_result = {}

    def playbook_on_task_start (self, name, is_conditional):
        if not name:
            name = 'gathering facts'
        self.task = name

    def v2_runner_on_unreachable(self, result):
        self.host_unreachable_result[self.task] = result

    def v2_runner_on_ok(self, result, *args, **kwargs):
        self.host_ok_result[self.task] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        self.host_failed_result[self.task] = result


@route('/', method='POST')
def reqest_halls():
    halls=Halls(request.json['ID'], request.json['IP_ADDRESS'], request.json['SSH_PORT'], request.json['USER'], request.json['PASSWORD'])
    global PLAYBOOK_PATH

    if request.json['COMMAND'] == 'install':
        PLAYBOOK_PATH=PLAYBOOK_INSTALL_PATH
        return halls.PlayWithBook

    elif request.json['COMMAND'] == 'status':
        return halls.statusHalls()

    elif request.json['COMMAND'] == 'delete':
        PLAYBOOK_PATH = PLAYBOOK_REMOVE_PATH
        return halls.PlayWithBook
    else:
        return redirect('/', code=400)

if __name__ == "__main__":
    api = Init('conf.json')
    api.LoadCfg()
    api.RunApi()